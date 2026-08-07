"""Prints current status: Fragment balance and recent activity, region
unlock state and costs, recent session finds, and wager status.
"""

from app.db import SessionLocal
from app.models import Region
from app.status import (
    fragment_balance,
    latest_wager_declaration,
    latest_wager_payoff,
    recent_finds,
    recent_fragment_activity,
    region_statuses,
)


def print_fragments(db) -> None:
    print("=== Fragments ===")
    print(f"Balance: {fragment_balance(db)}")

    recent = recent_fragment_activity(db)
    if recent:
        print("Recent activity:")
        for entry in recent:
            sign = "+" if entry.amount >= 0 else ""
            note = f" ({entry.note})" if entry.note else ""
            print(f"  {entry.occurred_at:%Y-%m-%d %H:%M}  {sign}{entry.amount}  {entry.kind}{note}")


def print_regions(db) -> None:
    print()
    print("=== Regions ===")
    for status in region_statuses(db):
        if status.unlocked:
            print(f"  {status.region.name}: unlocked")
        else:
            print(f"  {status.region.name}: locked (cost {status.region.unlock_cost_fragments})")


def print_recent_finds(db) -> None:
    print()
    print("=== Recent finds (last 10) ===")
    results = recent_finds(db)
    if not results:
        print("  (none yet)")
        return
    for result in results:
        region = db.get(Region, result.region_id)
        region_name = region.name if region else "unknown region"
        print(f"  {result.rolled_at:%Y-%m-%d %H:%M}  {result.item_name} ({result.tier})  —  {region_name}")


def print_wager(db) -> None:
    print()
    print("=== Wager ===")
    upcoming = latest_wager_declaration(db)
    if upcoming:
        print(f"  Declared: {upcoming.tier} for the period starting {upcoming.period_start}")
    else:
        print("  No wager declared")

    latest_payoff = latest_wager_payoff(db)
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
