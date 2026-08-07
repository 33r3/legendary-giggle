"""Recomputes passive-tier Fragment awards for a range of days from raw
step data. Safe to rerun any time — every day's award is fully
overwritten from raw, never accumulated.

Usage: python scripts/recompute_passive.py 2026-08-01 2026-08-07
"""

import sys
from datetime import date, timedelta

from app.db import SessionLocal
from app.rewards.passive import recompute_passive_award


def recompute_range(start: date, end: date) -> None:
    db = SessionLocal()
    try:
        day = start
        while day <= end:
            recompute_passive_award(db, day)
            day += timedelta(days=1)
    finally:
        db.close()


if __name__ == "__main__":
    start_arg, end_arg = sys.argv[1], sys.argv[2]
    recompute_range(date.fromisoformat(start_arg), date.fromisoformat(end_arg))
