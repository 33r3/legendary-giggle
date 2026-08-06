"""Loads all drop tables from content/tables/*.json into the database.
Regions must already be loaded (run load_regions.py first). Safe to
rerun — replaces a region's bands/items each time.
"""

from app.db import SessionLocal
from app.loot.tables import load_drop_tables_from_dir

CONTENT_DIR = "content/tables"


def main() -> None:
    db = SessionLocal()
    try:
        tables = load_drop_tables_from_dir(db, CONTENT_DIR)
        print(f"loaded {len(tables)} drop table(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
