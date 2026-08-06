"""Loads region boundaries from an operator-supplied GeoJSON file into the
database. The file (path via REGIONS_GEOJSON_PATH) is never committed —
see README for the expected FeatureCollection shape.
"""

from app.config import get_settings
from app.db import SessionLocal
from app.geo.regions import load_regions


def main() -> None:
    settings = get_settings()
    with open(settings.regions_geojson_path, encoding="utf-8") as f:
        geojson_text = f.read()

    db = SessionLocal()
    try:
        regions = load_regions(db, geojson_text)
        print(f"loaded {len(regions)} region(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
