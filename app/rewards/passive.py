"""Passive-tier Fragment accrual: recomputed from raw step data on demand,
never written during ingestion. Retuning the curve only requires a fresh
recompute, since nothing about it is baked into the raw rows.
"""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PassiveFragmentAward, PassiveTierConfig, StepSample


def dedup_daily_steps(db: Session, day: date) -> int:
    """Approximates a HealthKit statistics-query total from raw,
    per-source samples.

    Two dedup passes, for two different reasons:
    1. Collapse repeated deliveries of the same (source, period) sample to
       its max rather than summing — export automations typically resend
       a rolling window on every run, so the same period can legitimately
       arrive many times.
    2. Take the max across sources rather than summing them, since
       summing double-counts a step seen by more than one device.

    This is an interim heuristic — validate against the Health app before
    trusting it at scale.
    """
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    rows = db.execute(
        select(StepSample.source, StepSample.period_start, StepSample.quantity).where(
            StepSample.period_start >= start, StepSample.period_start < end
        )
    ).all()

    max_per_source_period: dict[tuple[str, datetime], float] = {}
    for source, period_start, quantity in rows:
        key = (source, period_start)
        max_per_source_period[key] = max(max_per_source_period.get(key, 0.0), quantity)

    totals_by_source: dict[str, float] = {}
    for (source, _period_start), quantity in max_per_source_period.items():
        totals_by_source[source] = totals_by_source.get(source, 0.0) + quantity

    if not totals_by_source:
        return 0
    return int(max(totals_by_source.values()))


def compute_fragments(steps: int, config: PassiveTierConfig) -> int:
    excess = max(0, steps - config.floor_steps)
    fragments = excess // config.steps_per_fragment
    return min(fragments, config.daily_cap_fragments)


def current_config(db: Session) -> PassiveTierConfig | None:
    return db.execute(
        select(PassiveTierConfig).order_by(PassiveTierConfig.effective_from.desc()).limit(1)
    ).scalar_one_or_none()


def recompute_passive_award(db: Session, day: date) -> PassiveFragmentAward:
    config = current_config(db)
    if config is None:
        raise RuntimeError("no passive tier config materialized")

    steps = dedup_daily_steps(db, day)
    fragments = compute_fragments(steps, config)

    award = db.execute(
        select(PassiveFragmentAward).where(PassiveFragmentAward.award_date == day)
    ).scalar_one_or_none()

    if award is None:
        award = PassiveFragmentAward(award_date=day)
        db.add(award)

    award.steps_counted = steps
    award.fragments_awarded = fragments
    award.config_id = config.id

    db.commit()
    db.refresh(award)
    return award


def recompute_range(db: Session, start: date, end: date) -> list[PassiveFragmentAward]:
    awards = []
    day = start
    while day <= end:
        awards.append(recompute_passive_award(db, day))
        day += timedelta(days=1)
    return awards


def default_recompute_range() -> tuple[date, date]:
    """Yesterday and today (UTC) — covers a step count still trickling in
    from an export automation, plus the day-boundary rollover."""
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=1), today
