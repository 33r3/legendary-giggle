"""Resolves the wager payoff for every completed period that doesn't
already have one. Safe to run on any schedule (e.g. daily) — periods
still in progress are left alone, and already-resolved ones are never
re-rolled.
"""

from app.db import SessionLocal
from app.rewards.wager import resolve_all_completed_payoffs


def main() -> None:
    db = SessionLocal()
    try:
        resolved = resolve_all_completed_payoffs(db)
        hits = sum(1 for payoff in resolved if payoff.hit_target)
        print(f"resolved {len(resolved)} period(s), {hits} hit target")
    finally:
        db.close()


if __name__ == "__main__":
    main()
