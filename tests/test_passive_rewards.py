from datetime import date, datetime, timezone

from app.generation.economy import generate_passive_tier_params
from app.models import IngestEvent, PassiveTierConfig, StepSample
from app.rewards.passive import compute_fragments, dedup_daily_steps, recompute_passive_award

# Invented test-only curve — not a real generated value.
TEST_CONFIG_KWARGS = {
    "floor_steps": 1000,
    "steps_per_fragment": 100,
    "daily_cap_fragments": 5,
    "effective_from": datetime(2020, 1, 1, tzinfo=timezone.utc),
}


def make_config(db_session) -> PassiveTierConfig:
    config = PassiveTierConfig(**TEST_CONFIG_KWARGS)
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


def add_step_sample(db_session, day: date, source: str, qty: float) -> None:
    event = IngestEvent(raw_payload="{}")
    db_session.add(event)
    db_session.flush()
    db_session.add(
        StepSample(
            ingest_event_id=event.id,
            source=source,
            period_start=datetime(day.year, day.month, day.day, 8, tzinfo=timezone.utc),
            period_end=datetime(day.year, day.month, day.day, 8, tzinfo=timezone.utc),
            quantity=qty,
            units="count",
        )
    )
    db_session.commit()


def test_generator_is_deterministic_per_seed():
    assert generate_passive_tier_params("seed-a") == generate_passive_tier_params("seed-a")


def test_generator_varies_by_seed():
    assert generate_passive_tier_params("seed-a") != generate_passive_tier_params("seed-b")


def test_compute_fragments_below_floor_is_zero():
    config = PassiveTierConfig(**TEST_CONFIG_KWARGS)
    assert compute_fragments(500, config) == 0


def test_compute_fragments_applies_rate_and_cap():
    config = PassiveTierConfig(**TEST_CONFIG_KWARGS)
    assert compute_fragments(1250, config) == 2  # 250 excess / 100 per fragment
    assert compute_fragments(10_000, config) == config.daily_cap_fragments


def test_dedup_takes_max_across_sources_not_sum(db_session):
    day = date(2026, 8, 1)
    add_step_sample(db_session, day, "Test iPhone", 3000)
    add_step_sample(db_session, day, "Test Watch", 3500)
    assert dedup_daily_steps(db_session, day) == 3500


def test_recompute_is_idempotent_and_overwrites(db_session):
    config = make_config(db_session)
    day = date(2026, 8, 1)
    add_step_sample(db_session, day, "Test iPhone", 2000)

    first = recompute_passive_award(db_session, day)
    assert first.steps_counted == 2000
    assert first.fragments_awarded == compute_fragments(2000, config)

    add_step_sample(db_session, day, "Test iPhone", 4000)
    second = recompute_passive_award(db_session, day)

    assert second.id == first.id
    assert second.steps_counted == 6000
