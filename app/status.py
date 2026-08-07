"""Status-gathering logic shared between scripts/status.py and the web
dashboard — one source of truth for what "current status" means.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FragmentLedgerEntry, Region, WagerDeclaration, WagerPayoff, WorkoutRollResult
from app.rewards.fragments import current_fragment_balance
from app.rewards.unlocks import is_region_unlocked

# Commons auto-convert to Fragments and don't stick around as items, so
# they're excluded from the collection — everything else is a permanent
# find, worth showing. Order here doubles as display order (rarest first).
COLLECTIBLE_TIER_ORDER = ["beyond", "signature", "very_rare", "rare", "uncommon"]


@dataclass
class RegionStatus:
    region: Region
    unlocked: bool


@dataclass
class CollectionItem:
    item_name: str
    tier: str
    region_name: str | None
    found_at: datetime
    source: str  # "session" or "wager"


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


def collection_items(db: Session) -> list[CollectionItem]:
    """Every uncommon-or-better find, from session rolls and wager
    payoffs alike, rarest first (most recent within a tier first)."""
    items: list[CollectionItem] = []

    session_results = db.execute(
        select(WorkoutRollResult).where(WorkoutRollResult.tier != "common")
    ).scalars().all()
    for result in session_results:
        region = db.get(Region, result.region_id)
        items.append(
            CollectionItem(
                item_name=result.item_name,
                tier=result.tier,
                region_name=region.name if region else None,
                found_at=result.rolled_at,
                source="session",
            )
        )

    payoffs = db.execute(
        select(WagerPayoff).where(
            WagerPayoff.item_name.is_not(None), WagerPayoff.tier_result != "common"
        )
    ).scalars().all()
    for payoff in payoffs:
        region = db.get(Region, payoff.region_id) if payoff.region_id else None
        items.append(
            CollectionItem(
                item_name=payoff.item_name,
                tier=payoff.tier_result,
                region_name=region.name if region else None,
                found_at=payoff.resolved_at,
                source="wager",
            )
        )

    def sort_key(item: CollectionItem) -> tuple[int, float]:
        tier_rank = (
            COLLECTIBLE_TIER_ORDER.index(item.tier) if item.tier in COLLECTIBLE_TIER_ORDER else len(COLLECTIBLE_TIER_ORDER)
        )
        return (tier_rank, -item.found_at.timestamp())

    items.sort(key=sort_key)
    return items
