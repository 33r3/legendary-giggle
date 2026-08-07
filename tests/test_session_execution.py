import json
import random
from datetime import datetime, timedelta, timezone

from app.geo.attribution import load_region_polygons
from app.geo.regions import load_regions
from app.loot.tables import load_drop_table
from app.models import IngestEvent, Region, SessionTierConfig, Workout, WorkoutRollResult, WorkoutRoutePoint
from app.rewards.fragments import current_fragment_balance
from app.rewards.session_execution import process_session
from app.rewards.unlocks import unlock_region

SQUARE_A = {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]}

PLACEHOLDER_TABLE = {
    "region_slug": "area-a",
    "bands": [{"tier": "common", "roll_min": 1, "roll_max": 100, "items": ["Widget A"]}],
}

PLACEHOLDER_TABLE_RARE_ONLY = {
    "region_slug": "area-a",
    "bands": [{"tier": "rare", "roll_min": 1, "roll_max": 100, "items": ["Widget B"]}],
}

SESSION_CONFIG_KWARGS = dict(
    roll_interval_minutes=15,
    max_rolls_per_session=5,
    effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
)


def geojson_collection(features):
    return json.dumps({"type": "FeatureCollection", "features": features})


def feature(slug, geometry, always_unlocked=False):
    return {
        "type": "Feature",
        "properties": {"slug": slug, "name": slug, "always_unlocked": always_unlocked},
        "geometry": geometry,
    }


def make_workout_with_route(db_session, minutes_in_region=30, distance_meters=None) -> Workout:
    event = IngestEvent(raw_payload="{}")
    db_session.add(event)
    db_session.flush()

    workout = Workout(
        ingest_event_id=event.id,
        external_id="w1",
        workout_type="Walk",
        source="Test",
        start_time=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 1, 9, tzinfo=timezone.utc) + timedelta(minutes=minutes_in_region),
        duration_seconds=minutes_in_region * 60,
        distance_meters=distance_meters,
    )
    db_session.add(workout)
    db_session.flush()

    base = datetime(2026, 8, 1, 9, tzinfo=timezone.utc)
    db_session.add(
        WorkoutRoutePoint(
            workout_id=workout.id, sequence_index=0, latitude=0.5, longitude=0.5, recorded_at=base
        )
    )
    db_session.add(
        WorkoutRoutePoint(
            workout_id=workout.id,
            sequence_index=1,
            latitude=0.5,
            longitude=0.5,
            recorded_at=base + timedelta(minutes=minutes_in_region),
        )
    )
    db_session.commit()
    db_session.refresh(workout)
    return workout


def test_locked_region_produces_no_results(db_session):
    load_regions(db_session, geojson_collection([feature("area-a", SQUARE_A)]))
    load_drop_table(db_session, json.dumps(PLACEHOLDER_TABLE))
    loaded_regions = load_region_polygons(db_session.query(Region).all())
    session_config = SessionTierConfig(**SESSION_CONFIG_KWARGS)

    workout = make_workout_with_route(db_session)
    results = process_session(db_session, workout, loaded_regions, session_config, rng=random.Random(1))

    assert results == []


def test_unlocked_region_produces_results(db_session):
    load_regions(db_session, geojson_collection([feature("area-a", SQUARE_A)]))
    load_drop_table(db_session, json.dumps(PLACEHOLDER_TABLE))
    region = db_session.query(Region).one()
    region.unlock_cost_fragments = 0
    db_session.commit()
    unlock_region(db_session, region)

    loaded_regions = load_region_polygons(db_session.query(Region).all())
    session_config = SessionTierConfig(**SESSION_CONFIG_KWARGS)

    workout = make_workout_with_route(db_session, minutes_in_region=30)
    results = process_session(db_session, workout, loaded_regions, session_config, rng=random.Random(1))

    assert len(results) == 2  # 30 minutes / 15-minute interval
    assert all(r.item_name == "Widget A" for r in results)
    assert all(r.region_id == region.id for r in results)


def test_common_rolls_auto_convert_to_fragments(db_session):
    load_regions(db_session, geojson_collection([feature("area-a", SQUARE_A)]))
    load_drop_table(db_session, json.dumps(PLACEHOLDER_TABLE))
    region = db_session.query(Region).one()
    region.unlock_cost_fragments = 0
    db_session.commit()
    unlock_region(db_session, region)

    loaded_regions = load_region_polygons(db_session.query(Region).all())
    session_config = SessionTierConfig(**SESSION_CONFIG_KWARGS)

    workout = make_workout_with_route(db_session, minutes_in_region=30)
    results = process_session(db_session, workout, loaded_regions, session_config, rng=random.Random(1))

    assert all(r.tier == "common" for r in results)
    assert current_fragment_balance(db_session) == len(results)


def test_non_common_rolls_do_not_convert_to_fragments(db_session):
    load_regions(db_session, geojson_collection([feature("area-a", SQUARE_A)]))
    load_drop_table(db_session, json.dumps(PLACEHOLDER_TABLE_RARE_ONLY))
    region = db_session.query(Region).one()
    region.unlock_cost_fragments = 0
    db_session.commit()
    unlock_region(db_session, region)

    loaded_regions = load_region_polygons(db_session.query(Region).all())
    session_config = SessionTierConfig(**SESSION_CONFIG_KWARGS)

    workout = make_workout_with_route(db_session, minutes_in_region=30)
    results = process_session(db_session, workout, loaded_regions, session_config, rng=random.Random(1))

    assert all(r.tier == "rare" for r in results)
    assert current_fragment_balance(db_session) == 0


def test_idle_workout_in_unlocked_region_produces_no_results(db_session):
    """Long enough, region unlocked, but distance implies no real
    movement — the region/duration mechanics alone shouldn't be
    sufficient to earn a roll."""
    load_regions(db_session, geojson_collection([feature("area-a", SQUARE_A, always_unlocked=True)]))
    load_drop_table(db_session, json.dumps(PLACEHOLDER_TABLE))

    loaded_regions = load_region_polygons(db_session.query(Region).all())
    session_config = SessionTierConfig(**SESSION_CONFIG_KWARGS)

    workout = make_workout_with_route(db_session, minutes_in_region=45, distance_meters=30)
    results = process_session(db_session, workout, loaded_regions, session_config, rng=random.Random(1))

    assert results == []


def test_processing_is_idempotent(db_session):
    load_regions(db_session, geojson_collection([feature("area-a", SQUARE_A, always_unlocked=True)]))
    load_drop_table(db_session, json.dumps(PLACEHOLDER_TABLE))
    loaded_regions = load_region_polygons(db_session.query(Region).all())
    session_config = SessionTierConfig(**SESSION_CONFIG_KWARGS)

    workout = make_workout_with_route(db_session, minutes_in_region=30)
    first = process_session(db_session, workout, loaded_regions, session_config, rng=random.Random(1))
    second = process_session(db_session, workout, loaded_regions, session_config, rng=random.Random(2))

    assert [r.id for r in first] == [r.id for r in second]
    assert db_session.query(WorkoutRollResult).count() == len(first)
