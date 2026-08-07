"""Declares a wager tier. Always applies to the period after the current
one — see app/rewards/wager.py for why — so this always sets next week's
set point, never this week's.

Usage: python scripts/declare_wager.py <modest|standard|ambitious>
"""

import sys

from app.db import SessionLocal
from app.rewards.wager import declare_wager


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python scripts/declare_wager.py <modest|standard|ambitious>")
        sys.exit(1)
    tier = sys.argv[1]

    db = SessionLocal()
    try:
        try:
            declaration = declare_wager(db, tier)
        except ValueError as exc:
            print(str(exc))
            sys.exit(1)
        print(f"declared {declaration.tier!r} for the period starting {declaration.period_start}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
