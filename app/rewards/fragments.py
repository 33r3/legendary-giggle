"""Fragment balance: passive awards plus the append-only ledger of spends
and common-item conversions. Never a mutable counter — always summed.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FragmentLedgerEntry, PassiveFragmentAward


def current_fragment_balance(db: Session) -> int:
    passive_total = db.execute(
        select(func.coalesce(func.sum(PassiveFragmentAward.fragments_awarded), 0))
    ).scalar_one()
    ledger_total = db.execute(
        select(func.coalesce(func.sum(FragmentLedgerEntry.amount), 0))
    ).scalar_one()
    return int(passive_total) + int(ledger_total)


def record_common_conversion(db: Session, item_name: str, region_id: int) -> FragmentLedgerEntry:
    """Converting a common item back to Fragments — the loop that feeds
    unlocks from ordinary session results."""
    entry = FragmentLedgerEntry(
        kind="common_conversion",
        amount=1,
        region_id=region_id,
        note=item_name,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
