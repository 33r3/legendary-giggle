"""Status-gathering logic shared between scripts/status.py and the web
dashboard — one source of truth for what "current status" means.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FragmentLedgerEntry, Region, WagerDeclaration, WagerPayoff, WorkoutRollResult
from app.rewards.fragments import current_fragment_balance
from app.rewards.unlocks import is_region_unlocked


@dataclass
class RegionStatus:
    region: Region
    unlocked: bool


def fragment_balance(db: Session) -> int:
    return current_fragment_balance(db)


def recent_fragment_activity(db: Session, limit: int = 5) -> list[FragmentLedgerEntry]:
    return db.execute(
        select(FragmentLedgerEntry).order_by(FragmentLedgerEntry.occurred_at.desc()).limit(limit)
    ).scalars().all()


def region_statuses(db: Session) -> list[RegionStatus]:
    return [
        RegionStatus(region=region, unlocked=is_region_unlocked(db, region))
        for region in db.query(Region).order_by(Region.name).all()
    ]


def recent_finds(db: Session, limit: int = 10) -> list[WorkoutRollResult]:
    return db.execute(
        select(WorkoutRollResult).order_by(WorkoutRollResult.rolled_at.desc()).limit(limit)
    ).scalars().all()


def latest_wager_declaration(db: Session) -> WagerDeclaration | None:
    return db.execute(
        select(WagerDeclaration).order_by(WagerDeclaration.period_start.desc()).limit(1)
    ).scalar_one_or_none()


def latest_wager_payoff(db: Session) -> WagerPayoff | None:
    return db.execute(
        select(WagerPayoff).order_by(WagerPayoff.period_start.desc()).limit(1)
    ).scalar_one_or_none()
