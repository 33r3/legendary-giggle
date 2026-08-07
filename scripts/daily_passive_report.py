"""Prints steps counted and Fragments awarded per day, from the passive
tier's already-computed history — useful for auditing why a given
week's total looks the way it does.

Usage:
  python scripts/daily_passive_report.py                    # everything on record
  python scripts/daily_passive_report.py 2026-08-01 2026-08-07
"""

import sys
from datetime import date

from app.db import SessionLocal
from app.status import daily_passive_awards


def main() -> None:
    if len(sys.argv) == 3:
        start, end = date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2])
    elif len(sys.argv) == 1:
        start, end = None, None
    else:
        print("usage: python scripts/daily_passive_report.py [start end]")
        sys.exit(1)

    db = SessionLocal()
    try:
        awards = daily_passive_awards(db, start, end)
        if not awards:
            print("no passive awards on record for that range")
            return

        print(f"{'DATE':<12}{'STEPS':>10}{'FRAGMENTS':>12}")
        total = 0
        for award in awards:
            print(f"{award.award_date!s:<12}{award.steps_counted:>10}{award.fragments_awarded:>12}")
            total += award.fragments_awarded
        print("-" * 34)
        print(f"{'TOTAL':<12}{'':>10}{total:>12}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
