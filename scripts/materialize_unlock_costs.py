"""Generates and stores unlock costs for every loaded region that isn't
always_unlocked. Deterministic per (seed, region slug), so rerunning is
a no-op unless GAME_SEED changes.
"""

from app.config import get_settings
from app.db import SessionLocal
from app.generation.economy import generate_region_unlock_cost
from app.models import Region


def materialize_unlock_costs() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        regions = db.query(Region).filter_by(always_unlocked=False).all()
        for region in regions:
            region.unlock_cost_fragments = generate_region_unlock_cost(settings.game_seed, region.slug)
        db.commit()
        print(f"materialized unlock costs for {len(regions)} region(s)")
    finally:
        db.close()


if __name__ == "__main__":
    materialize_unlock_costs()
