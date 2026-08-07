"""The wager: a declared weekly set point that earns a bonus Payoff roll
if met. Mirrors the paper-playtest structure (declare in advance, locked
for the period, miss forfeits the bonus with no other penalty) but with
generated-not-committed thresholds and bonuses.

Periods are Monday-Sunday (UTC). A declaration always targets the period
after whichever one is current — see declare_wager — which is what makes
"declared in advance, changes take effect on a lag" true by construction:
there's no way to declare for a period that has already started.
"""

import random
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.geo.attribution import load_region_polygons, attribute_route_minutes
from app.loot.tables import load_table_for_region, resolve_roll
from app.models import Region, WagerConfig, WagerDeclaration, WagerPayoff, Workout
from app.rewards.fragments import record_common_conversion
from app.rewards.movement import passes_movement_gate
from app.rewards.unlocks import is_region_unlocked

QUALIFYING_SESSION_SECONDS = 15 * 60
MODEST_BONUS = 0

_TIERS = ("modest", "standard", "ambitious")


def period_start_for(d: date) -> date:
    """Monday of the ISO week containing d."""
    return d - timedelta(days=d.weekday())


def current_wager_config(db: Session) -> WagerConfig | None:
    return db.execute(
        select(WagerConfig).order_by(WagerConfig.effective_from.desc()).limit(1)
    ).scalar_one_or_none()


def tier_threshold_and_bonus(config: WagerConfig, tier: str) -> tuple[int, int]:
    if tier == "modest":
        return config.modest_session_threshold, MODEST_BONUS
    if tier == "standard":
        return config.standard_session_threshold, config.standard_bonus
    if tier == "ambitious":
        return config.ambitious_session_threshold, config.ambitious_bonus
    raise ValueError(f"unknown wager tier {tier!r}, expected one of {_TIERS}")


def declare_wager(db: Session, tier: str, now: datetime | None = None) -> WagerDeclaration:
    if tier not in _TIERS:
        raise ValueError(f"unknown wager tier {tier!r}, expected one of {_TIERS}")

    config = current_wager_config(db)
    if config is None:
        raise RuntimeError("no wager config materialized")

    now = now or datetime.now(timezone.utc)
    target_period = period_start_for(now.date()) + timedelta(days=7)

    declaration = db.execute(
        select(WagerDeclaration).where(WagerDeclaration.period_start == target_period)
    ).scalar_one_or_none()

    if declaration is None:
        declaration = WagerDeclaration(period_start=target_period)
        db.add(declaration)

    declaration.tier = tier
    declaration.config_id = config.id
    db.commit()
    db.refresh(declaration)
    return declaration


def _qualifying_workouts(db: Session, period_start: date) -> list[Workout]:
    """Workouts long enough and active enough to count toward the wager —
    duration alone isn't sufficient, see app/rewards/movement.py."""
    period_start_dt = datetime.combine(period_start, time.min, tzinfo=timezone.utc)
    period_end_dt = period_start_dt + timedelta(days=7)
    candidates = db.execute(
        select(Workout).where(
            Workout.start_time >= period_start_dt,
            Workout.start_time < period_end_dt,
            Workout.duration_seconds >= QUALIFYING_SESSION_SECONDS,
        )
    ).scalars().all()
    return [w for w in candidates if passes_movement_gate(w)]


def qualifying_session_count(db: Session, period_start: date) -> int:
    return len(_qualifying_workouts(db, period_start))


def _payoff_region(db: Session, period_start: date) -> int | None:
    """The unlocked region with the most attributed minutes across the
    period's qualifying sessions — that's what the bonus roll counts
    against."""
    qualifying_workouts = _qualifying_workouts(db, period_start)
    loaded_regions = load_region_polygons(db.query(Region).all())

    minutes_by_region: dict[int, float] = {}
    for workout in qualifying_workouts:
        for region_id, minutes in attribute_route_minutes(workout.route_points, loaded_regions).items():
            if region_id is None:
                continue
            minutes_by_region[region_id] = minutes_by_region.get(region_id, 0.0) + minutes

    unlocked_candidates = {
        region_id: minutes
        for region_id, minutes in minutes_by_region.items()
        if is_region_unlocked(db, db.get(Region, region_id))
    }
    if not unlocked_candidates:
        return None
    return max(unlocked_candidates, key=unlocked_candidates.get)


def resolve_wager_payoff(db: Session, period_start: date, rng: random.Random | None = None) -> WagerPayoff:
    existing = db.execute(
        select(WagerPayoff).where(WagerPayoff.period_start == period_start)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    declaration = db.execute(
        select(WagerDeclaration).where(WagerDeclaration.period_start == period_start)
    ).scalar_one_or_none()

    session_count = qualifying_session_count(db, period_start)

    if declaration is None:
        payoff = WagerPayoff(
            period_start=period_start,
            tier=None,
            qualifying_sessions=session_count,
            hit_target=False,
        )
        db.add(payoff)
        db.commit()
        db.refresh(payoff)
        return payoff

    config = db.get(WagerConfig, declaration.config_id)
    threshold, bonus = tier_threshold_and_bonus(config, declaration.tier)
    hit_target = session_count >= threshold

    payoff = WagerPayoff(
        period_start=period_start,
        tier=declaration.tier,
        qualifying_sessions=session_count,
        hit_target=hit_target,
    )

    if hit_target:
        region_id = _payoff_region(db, period_start)
        if region_id is not None:
            table = load_table_for_region(db, region_id)
            if table is not None:
                rng = rng or random.Random()
                roll_value = rng.randint(1, 100) + bonus
                outcome = resolve_roll(table, roll_value, rng=rng)
                if outcome is not None:
                    payoff.region_id = region_id
                    payoff.roll_value = roll_value
                    payoff.tier_result = outcome.tier
                    payoff.item_name = outcome.item_name
                    if outcome.tier == "common":
                        record_common_conversion(db, outcome.item_name, region_id)

    db.add(payoff)
    db.commit()
    db.refresh(payoff)
    return payoff


def resolve_all_completed_payoffs(db: Session, now: datetime | None = None) -> list[WagerPayoff]:
    """Resolves every declared period that has ended and doesn't already
    have a payoff. Safe to run on any schedule — already-resolved periods
    are skipped without hitting the database twice."""
    now = now or datetime.now(timezone.utc)

    already_resolved = set(db.execute(select(WagerPayoff.period_start)).scalars().all())
    all_periods = set(db.execute(select(WagerDeclaration.period_start)).scalars().all())

    pending = sorted(
        period_start
        for period_start in all_periods - already_resolved
        if period_start + timedelta(days=7) <= now.date()
    )

    return [resolve_wager_payoff(db, period_start) for period_start in pending]
