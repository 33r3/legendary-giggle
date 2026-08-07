"""Unlocks a region by slug, spending Fragments if it isn't already
always_unlocked. Safe to rerun — unlocking an already-unlocked region
is a no-op, never a double charge.

Usage: python scripts/unlock_region.py <slug>
"""

import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Region
from app.rewards.fragments import current_fragment_balance
from app.rewards.unlocks import InsufficientFragments, is_region_unlocked, unlock_region


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python scripts/unlock_region.py <slug>")
        sys.exit(1)
    slug = sys.argv[1]

    db = SessionLocal()
    try:
        region = db.execute(select(Region).where(Region.slug == slug)).scalar_one_or_none()
        if region is None:
            print(f"no region with slug {slug!r}")
            sys.exit(1)

        if is_region_unlocked(db, region):
            print(f"{slug!r} is already unlocked")
            return

        try:
            unlock_region(db, region)
        except InsufficientFragments as exc:
            print(f"can't unlock {slug!r}: {exc}")
            sys.exit(1)

        print(f"unlocked {slug!r}. Fragment balance: {current_fragment_balance(db)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
