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
    per-source samples: take the max across sources rather than summing
    them, since summing double-counts when a step is seen by more than
    one source. This is an interim heuristic — validate against the
    Health app before trusting it at scale.
    """
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    rows = db.execute(
        select(StepSample.source, StepSample.quantity).where(
            StepSample.period_start >= start, StepSample.period_start < end
        )
    ).all()

    totals_by_source: dict[str, float] = {}
    for source, quantity in rows:
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
