import pytest

from app.models import PassiveTierConfig, Region
from app.rewards.fragments import current_fragment_balance, record_common_conversion
from app.rewards.passive import recompute_passive_award
from app.rewards.unlocks import InsufficientFragments, is_region_unlocked, unlock_region
from datetime import date, datetime, timezone

from app.models import IngestEvent, StepSample


def make_region(db_session, slug="test-region", always_unlocked=False, cost=None) -> Region:
    region = Region(
        slug=slug,
        name="Test Region",
        polygon_geojson="{}",
        always_unlocked=always_unlocked,
        unlock_cost_fragments=cost,
    )
    db_session.add(region)
    db_session.commit()
    db_session.refresh(region)
    return region


def test_always_unlocked_region_needs_no_unlock_row(db_session):
    region = make_region(db_session, always_unlocked=True)
    assert is_region_unlocked(db_session, region) is True


def test_locked_region_is_locked_until_unlocked(db_session):
    region = make_region(db_session, cost=5)
    assert is_region_unlocked(db_session, region) is False


def test_unlock_fails_without_enough_fragments(db_session):
    region = make_region(db_session, cost=5)
    with pytest.raises(InsufficientFragments):
        unlock_region(db_session, region)


def test_unlock_spends_balance_and_marks_unlocked(db_session):
    region = make_region(db_session, cost=3)
    record_common_conversion(db_session, "Test Item", region.id)
    record_common_conversion(db_session, "Test Item", region.id)
    record_common_conversion(db_session, "Test Item", region.id)

    assert current_fragment_balance(db_session) == 3
    unlock_region(db_session, region)

    assert is_region_unlocked(db_session, region) is True
    assert current_fragment_balance(db_session) == 0


def test_unlocking_twice_does_not_double_charge(db_session):
    region = make_region(db_session, cost=3)
    record_common_conversion(db_session, "Test Item", region.id)
    record_common_conversion(db_session, "Test Item", region.id)
    record_common_conversion(db_session, "Test Item", region.id)

    unlock_region(db_session, region)
    unlock_region(db_session, region)

    assert current_fragment_balance(db_session) == 0


def test_balance_includes_passive_awards(db_session):
    config = PassiveTierConfig(
        floor_steps=1000,
        steps_per_fragment=100,
        daily_cap_fragments=5,
        effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(config)
    db_session.commit()

    day = date(2026, 8, 1)
    event = IngestEvent(raw_payload="{}")
    db_session.add(event)
    db_session.flush()
    db_session.add(
        StepSample(
            ingest_event_id=event.id,
            source="Test",
            period_start=datetime(2026, 8, 1, 8, tzinfo=timezone.utc),
            period_end=datetime(2026, 8, 1, 8, tzinfo=timezone.utc),
            quantity=2000,
            units="count",
        )
    )
    db_session.commit()
    recompute_passive_award(db_session, day)

    assert current_fragment_balance(db_session) == 5  # 1000 excess / 100 per fragment, capped at 5
