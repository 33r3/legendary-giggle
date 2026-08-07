"""Loads all region boundaries from content/regions/*.geojson into the
database. Safe to rerun — existing regions are upserted by slug.
"""

from app.config import get_settings
from app.db import SessionLocal
from app.geo.regions import load_regions_from_dir


def main() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        regions = load_regions_from_dir(db, settings.regions_content_dir)
        print(f"loaded {len(regions)} region(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
