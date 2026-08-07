from datetime import datetime, timedelta, timezone

from app.models import IngestEvent, Region, WagerPayoff, Workout, WorkoutRollResult
from app.status import collection_items


def make_region(db_session, slug="area-a") -> Region:
    region = Region(slug=slug, name="Test Region", polygon_geojson="{}")
    db_session.add(region)
    db_session.commit()
    db_session.refresh(region)
    return region


def make_workout(db_session) -> Workout:
    event = IngestEvent(raw_payload="{}")
    db_session.add(event)
    db_session.flush()
    workout = Workout(
        ingest_event_id=event.id,
        workout_type="Walk",
        source="Test",
        start_time=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 1, 9, 20, tzinfo=timezone.utc),
        duration_seconds=1200,
    )
    db_session.add(workout)
    db_session.commit()
    db_session.refresh(workout)
    return workout


def add_roll_result(db_session, workout, region, tier, item_name, rolled_at):
    result = WorkoutRollResult(
        workout_id=workout.id, region_id=region.id, tier=tier, item_name=item_name, rolled_at=rolled_at
    )
    db_session.add(result)
    db_session.commit()


def add_wager_payoff(db_session, period_start, region, tier_result, item_name, resolved_at):
    payoff = WagerPayoff(
        period_start=period_start,
        tier="modest",
        qualifying_sessions=1,
        hit_target=True,
        region_id=region.id,
        roll_value=50,
        tier_result=tier_result,
        item_name=item_name,
        resolved_at=resolved_at,
    )
    db_session.add(payoff)
    db_session.commit()


def test_collection_excludes_commons(db_session):
    region = make_region(db_session)
    workout = make_workout(db_session)
    add_roll_result(db_session, workout, region, "common", "Widget Common", datetime(2026, 8, 1, tzinfo=timezone.utc))
    add_roll_result(db_session, workout, region, "rare", "Widget Rare", datetime(2026, 8, 1, tzinfo=timezone.utc))

    items = collection_items(db_session)

    assert [i.item_name for i in items] == ["Widget Rare"]


def test_collection_includes_session_and_wager_sources(db_session):
    region = make_region(db_session)
    workout = make_workout(db_session)
    add_roll_result(db_session, workout, region, "rare", "Session Rare", datetime(2026, 8, 1, tzinfo=timezone.utc))
    add_wager_payoff(db_session, datetime(2026, 8, 1).date(), region, "signature", "Wager Signature", datetime(2026, 8, 2, tzinfo=timezone.utc))

    items = collection_items(db_session)

    sources = {(i.item_name, i.source) for i in items}
    assert ("Session Rare", "session") in sources
    assert ("Wager Signature", "wager") in sources


def test_collection_sorts_rarest_tier_first(db_session):
    region = make_region(db_session)
    workout = make_workout(db_session)
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    add_roll_result(db_session, workout, region, "uncommon", "The Uncommon", now)
    add_roll_result(db_session, workout, region, "beyond", "The Beyond", now)
    add_roll_result(db_session, workout, region, "rare", "The Rare", now)

    items = collection_items(db_session)

    assert [i.item_name for i in items] == ["The Beyond", "The Rare", "The Uncommon"]


def test_collection_sorts_most_recent_first_within_a_tier(db_session):
    region = make_region(db_session)
    workout = make_workout(db_session)
    earlier = datetime(2026, 8, 1, tzinfo=timezone.utc)
    later = earlier + timedelta(days=1)
    add_roll_result(db_session, workout, region, "rare", "Older Rare", earlier)
    add_roll_result(db_session, workout, region, "rare", "Newer Rare", later)

    items = collection_items(db_session)

    assert [i.item_name for i in items] == ["Newer Rare", "Older Rare"]
