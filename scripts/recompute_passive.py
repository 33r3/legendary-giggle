"""Recomputes passive-tier Fragment awards for a range of days from raw
step data. Safe to rerun any time — every day's award is fully
overwritten from raw, never accumulated.

Usage:
  python scripts/recompute_passive.py                    # yesterday and today (UTC)
  python scripts/recompute_passive.py 2026-08-01 2026-08-07
"""

import sys
from datetime import date

from app.db import SessionLocal
from app.rewards.passive import default_recompute_range, recompute_range


def main() -> None:
    if len(sys.argv) == 3:
        start, end = date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2])
    elif len(sys.argv) == 1:
        start, end = default_recompute_range()
    else:
        print("usage: python scripts/recompute_passive.py [start end]")
        sys.exit(1)

    db = SessionLocal()
    try:
        recompute_range(db, start, end)
    finally:
        db.close()


if __name__ == "__main__":
    main()
