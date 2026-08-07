"""Region unlocks — the Fragment sink. Spending opens a region's drop
table for good; there's no re-locking.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FragmentLedgerEntry, Region, RegionUnlock
from app.rewards.fragments import current_fragment_balance


class InsufficientFragments(Exception):
    pass


def is_region_unlocked(db: Session, region: Region) -> bool:
    if region.always_unlocked:
        return True
    existing = db.execute(
        select(RegionUnlock).where(RegionUnlock.region_id == region.id)
    ).scalar_one_or_none()
    return existing is not None


def unlock_region(db: Session, region: Region) -> RegionUnlock:
    if is_region_unlocked(db, region):
        return db.execute(
            select(RegionUnlock).where(RegionUnlock.region_id == region.id)
        ).scalar_one()

    cost = region.unlock_cost_fragments
    if cost is None:
        raise ValueError(f"region {region.slug!r} has no materialized unlock cost")

    balance = current_fragment_balance(db)
    if balance < cost:
        raise InsufficientFragments(f"need {cost}, have {balance}")

    db.add(FragmentLedgerEntry(kind="region_unlock", amount=-cost, region_id=region.id))
    unlock = RegionUnlock(region_id=region.id)
    db.add(unlock)
    db.commit()
    db.refresh(unlock)
    return unlock
