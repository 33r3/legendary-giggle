"""Prints current status: Fragment balance and recent activity, region
unlock state and costs, recent session finds, and wager status.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import FragmentLedgerEntry, Region, WagerDeclaration, WagerPayoff, WorkoutRollResult
from app.rewards.fragments import current_fragment_balance
from app.rewards.unlocks import is_region_unlocked


def print_fragments(db) -> None:
    print("=== Fragments ===")
    print(f"Balance: {current_fragment_balance(db)}")

    recent = db.execute(
        select(FragmentLedgerEntry).order_by(FragmentLedgerEntry.occurred_at.desc()).limit(5)
    ).scalars().all()
    if recent:
        print("Recent activity:")
        for entry in recent:
            sign = "+" if entry.amount >= 0 else ""
            note = f" ({entry.note})" if entry.note else ""
            print(f"  {entry.occurred_at:%Y-%m-%d %H:%M}  {sign}{entry.amount}  {entry.kind}{note}")


def print_regions(db) -> None:
    print()
    print("=== Regions ===")
    for region in db.query(Region).order_by(Region.name).all():
        if is_region_unlocked(db, region):
            print(f"  {region.name}: unlocked")
        else:
            print(f"  {region.name}: locked (cost {region.unlock_cost_fragments})")


def print_recent_finds(db) -> None:
    print()
    print("=== Recent finds (last 10) ===")
    recent = db.execute(
        select(WorkoutRollResult).order_by(WorkoutRollResult.rolled_at.desc()).limit(10)
    ).scalars().all()
    if not recent:
        print("  (none yet)")
        return
    for result in recent:
        region = db.get(Region, result.region_id)
        region_name = region.name if region else "unknown region"
        print(f"  {result.rolled_at:%Y-%m-%d %H:%M}  {result.item_name} ({result.tier})  —  {region_name}")


def print_wager(db) -> None:
    print()
    print("=== Wager ===")
    upcoming = db.execute(
        select(WagerDeclaration).order_by(WagerDeclaration.period_start.desc()).limit(1)
    ).scalar_one_or_none()
    if upcoming:
        print(f"  Declared: {upcoming.tier} for the period starting {upcoming.period_start}")
    else:
        print("  No wager declared")

    latest_payoff = db.execute(
        select(WagerPayoff).order_by(WagerPayoff.period_start.desc()).limit(1)
    ).scalar_one_or_none()
    if latest_payoff is None:
        return
    if latest_payoff.hit_target and latest_payoff.item_name:
        print(
            f"  Last resolved period ({latest_payoff.period_start}): hit target "
            f"({latest_payoff.qualifying_sessions} sessions) — payoff: "
            f"{latest_payoff.item_name} ({latest_payoff.tier_result})"
        )
    elif latest_payoff.hit_target:
        print(
            f"  Last resolved period ({latest_payoff.period_start}): hit target "
            f"but no region was available to roll against"
        )
    else:
        print(
            f"  Last resolved period ({latest_payoff.period_start}): missed target "
            f"({latest_payoff.qualifying_sessions} sessions)"
        )


def main() -> None:
    db = SessionLocal()
    try:
        print_fragments(db)
        print_regions(db)
        print_recent_finds(db)
        print_wager(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
