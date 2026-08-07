import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app.generation.economy import generate_wager_config_params
from app.geo.regions import load_regions
from app.loot.tables import load_drop_table
from app.models import IngestEvent, Region, WagerConfig, WagerDeclaration, Workout, WorkoutRoutePoint
from app.rewards.fragments import current_fragment_balance
from app.rewards.unlocks import unlock_region
from app.rewards.wager import (
    declare_wager,
    period_start_for,
    qualifying_session_count,
    resolve_all_completed_payoffs,
    resolve_wager_payoff,
)

SQUARE_A = {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]}

PLACEHOLDER_TABLE = {
    "region_slug": "area-a",
    "bands": [{"tier": "common", "roll_min": 1, "roll_max": 115, "items": ["Widget A"]}],
}

# Invented test-only curve — not a real generated value.
TEST_CONFIG_KWARGS = dict(
    modest_session_threshold=1,
    standard_session_threshold=2,
    standard_bonus=5,
    ambitious_session_threshold=3,
    ambitious_bonus=20,
    effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
)


def make_config(db_session) -> WagerConfig:
    config = WagerConfig(**TEST_CONFIG_KWARGS)
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


def geojson_collection(features):
    return json.dumps({"type": "FeatureCollection", "features": features})


def feature(slug, geometry, always_unlocked=False):
    return {
        "type": "Feature",
        "properties": {"slug": slug, "name": slug, "always_unlocked": always_unlocked},
        "geometry": geometry,
    }


def make_workout(db_session, start_time, duration_minutes, with_route=True, distance_meters=None) -> Workout:
    event = IngestEvent(raw_payload="{}")
    db_session.add(event)
    db_session.flush()

    end_time = start_time + timedelta(minutes=duration_minutes)
    workout = Workout(
        ingest_event_id=event.id,
        workout_type="Walk",
        source="Test",
        start_time=start_time,
        end_time=end_time,
        duration_seconds=duration_minutes * 60,
        distance_meters=distance_meters,
    )
    db_session.add(workout)
    db_session.flush()

    if with_route:
        db_session.add(
            WorkoutRoutePoint(
                workout_id=workout.id, sequence_index=0, latitude=0.5, longitude=0.5, recorded_at=start_time
            )
        )
        db_session.add(
            WorkoutRoutePoint(
                workout_id=workout.id, sequence_index=1, latitude=0.5, longitude=0.5, recorded_at=end_time
            )
        )
    db_session.commit()
    db_session.refresh(workout)
    return workout


def test_generator_is_deterministic_per_seed():
    assert generate_wager_config_params("seed-a") == generate_wager_config_params("seed-a")


def test_period_start_for_returns_monday():
    # 2026-08-07 is a Friday.
    assert period_start_for(date(2026, 8, 7)) == date(2026, 8, 3)
    assert period_start_for(date(2026, 8, 3)) == date(2026, 8, 3)  # Monday itself


def test_declare_wager_always_targets_next_period(db_session):
    make_config(db_session)
    now = datetime(2026, 8, 7, 12, tzinfo=timezone.utc)  # a Friday
    declaration = declare_wager(db_session, "standard", now=now)
    assert declaration.period_start == date(2026, 8, 10)  # next Monday


def test_declare_wager_upserts_before_period_starts(db_session):
    make_config(db_session)
    now = datetime(2026, 8, 7, 12, tzinfo=timezone.utc)
    declare_wager(db_session, "modest", now=now)
    second = declare_wager(db_session, "ambitious", now=now)

    assert second.tier == "ambitious"
    all_declarations = db_session.query(second.__class__).all()
    assert len(all_declarations) == 1


def test_declare_wager_rejects_unknown_tier(db_session):
    make_config(db_session)
    with pytest.raises(ValueError):
        declare_wager(db_session, "extreme")


def test_qualifying_session_count_filters_by_duration_and_period(db_session):
    period_start = date(2026, 8, 3)
    make_workout(db_session, datetime(2026, 8, 4, 9, tzinfo=timezone.utc), duration_minutes=20)  # in, long enough
    make_workout(db_session, datetime(2026, 8, 5, 9, tzinfo=timezone.utc), duration_minutes=10)  # in, too short
    make_workout(db_session, datetime(2026, 8, 11, 9, tzinfo=timezone.utc), duration_minutes=20)  # next period

    assert qualifying_session_count(db_session, period_start) == 1


def test_qualifying_session_count_excludes_idle_workouts(db_session):
    """Long enough duration, but distance implies the person never
    actually moved — shouldn't count toward the wager."""
    period_start = date(2026, 8, 3)
    make_workout(
        db_session,
        datetime(2026, 8, 4, 9, tzinfo=timezone.utc),
        duration_minutes=45,
        distance_meters=30,  # ~30m of GPS jitter over 45 minutes, not a walk
    )

    assert qualifying_session_count(db_session, period_start) == 0


def test_resolve_payoff_with_no_declaration_does_not_hit(db_session):
    payoff = resolve_wager_payoff(db_session, date(2026, 8, 3))
    assert payoff.hit_target is False
    assert payoff.tier is None
    assert payoff.item_name is None


def test_resolve_payoff_miss_has_no_roll(db_session):
    make_config(db_session)
    period_start = date(2026, 8, 3)
    declare_wager(db_session, "ambitious", now=datetime(2026, 7, 31, tzinfo=timezone.utc))
    # Only one qualifying session; ambitious needs three.
    make_workout(db_session, datetime(2026, 8, 4, 9, tzinfo=timezone.utc), duration_minutes=20)

    payoff = resolve_wager_payoff(db_session, period_start)

    assert payoff.hit_target is False
    assert payoff.tier == "ambitious"
    assert payoff.item_name is None
    assert payoff.roll_value is None


def test_resolve_payoff_hit_rolls_against_most_active_unlocked_region(db_session):
    make_config(db_session)
    load_regions(db_session, geojson_collection([feature("area-a", SQUARE_A, always_unlocked=True)]))
    load_drop_table(db_session, json.dumps(PLACEHOLDER_TABLE))
    region = db_session.query(Region).one()

    period_start = date(2026, 8, 3)
    declare_wager(db_session, "modest", now=datetime(2026, 7, 31, tzinfo=timezone.utc))
    make_workout(db_session, datetime(2026, 8, 4, 9, tzinfo=timezone.utc), duration_minutes=20)

    payoff = resolve_wager_payoff(db_session, period_start)

    assert payoff.hit_target is True
    assert payoff.region_id == region.id
    assert payoff.item_name == "Widget A"
    assert payoff.roll_value is not None
    assert 1 <= payoff.roll_value <= 100  # modest tier's bonus is always 0
    assert payoff.tier_result == "common"
    assert current_fragment_balance(db_session) == 1  # common payoff auto-converted


def test_resolve_payoff_is_idempotent(db_session):
    make_config(db_session)
    load_regions(db_session, geojson_collection([feature("area-a", SQUARE_A, always_unlocked=True)]))
    load_drop_table(db_session, json.dumps(PLACEHOLDER_TABLE))

    period_start = date(2026, 8, 3)
    declare_wager(db_session, "modest", now=datetime(2026, 7, 31, tzinfo=timezone.utc))
    make_workout(db_session, datetime(2026, 8, 4, 9, tzinfo=timezone.utc), duration_minutes=20)

    first = resolve_wager_payoff(db_session, period_start)
    second = resolve_wager_payoff(db_session, period_start)

    assert first.id == second.id
    assert first.roll_value == second.roll_value


def test_resolve_all_completed_payoffs_skips_in_progress_period(db_session):
    make_config(db_session)
    # Declares a period that started this week and hasn't ended yet.
    now = datetime(2026, 8, 7, tzinfo=timezone.utc)  # Friday
    current_period = period_start_for(now.date())
    declare_wager(db_session, "modest", now=now - timedelta(days=7))
    # Force the declaration onto the still-in-progress period for this test.
    declaration = db_session.query(WagerDeclaration).one()
    declaration.period_start = current_period
    db_session.commit()

    resolved = resolve_all_completed_payoffs(db_session, now=now)
    assert resolved == []
