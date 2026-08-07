"""Session-tier roll allocation: how many table rolls a walk earns per
region, from time-weighted minutes. Rolling against the actual drop
tables is a later step — this only decides roll counts."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SessionTierConfig


def current_session_tier_config(db: Session) -> SessionTierConfig | None:
    return db.execute(
        select(SessionTierConfig).order_by(SessionTierConfig.effective_from.desc()).limit(1)
    ).scalar_one_or_none()


def session_roll_counts(
    minutes_by_region: dict[int, float], config: SessionTierConfig
) -> dict[int, int]:
    """One roll per full roll_interval_minutes in a region, capped at
    max_rolls_per_session total across the whole workout. Over the cap,
    rolls are scaled down proportionally (largest-remainder method) so
    time split across regions stays split roughly the same way."""
    raw_rolls = {
        region_id: minutes // config.roll_interval_minutes
        for region_id, minutes in minutes_by_region.items()
        if region_id is not None
    }
    total = sum(raw_rolls.values())
    if total <= config.max_rolls_per_session:
        return {region_id: int(count) for region_id, count in raw_rolls.items() if count > 0}

    scale = config.max_rolls_per_session / total
    scaled = {region_id: count * scale for region_id, count in raw_rolls.items()}
    allocated = {region_id: int(value) for region_id, value in scaled.items()}

    remainder = config.max_rolls_per_session - sum(allocated.values())
    by_fractional_part = sorted(
        scaled.items(), key=lambda item: item[1] - allocated[item[0]], reverse=True
    )
    for region_id, _ in by_fractional_part:
        if remainder <= 0:
            break
        allocated[region_id] += 1
        remainder -= 1

    return {region_id: count for region_id, count in allocated.items() if count > 0}
