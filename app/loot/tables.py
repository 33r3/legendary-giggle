"""Loads drop tables from committed JSON files under content/tables/ and
resolves a roll against a loaded table.
"""

import json
import random
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import DropTable, DropTableBand, DropTableItem, Region


class UnknownRegionSlug(Exception):
    pass


def parse_drop_table_file(json_text: str) -> dict:
    data = json.loads(json_text)
    bands = data["bands"]
    for band in bands:
        if band["roll_min"] > band["roll_max"]:
            raise ValueError(f"band {band['tier']!r} has roll_min > roll_max")
        if not band["items"]:
            raise ValueError(f"band {band['tier']!r} has no items")
    return data


def load_drop_table(db: Session, json_text: str) -> DropTable:
    data = parse_drop_table_file(json_text)

    region = db.execute(select(Region).where(Region.slug == data["region_slug"])).scalar_one_or_none()
    if region is None:
        raise UnknownRegionSlug(f"no region loaded with slug {data['region_slug']!r}")

    table = db.execute(select(DropTable).where(DropTable.region_id == region.id)).scalar_one_or_none()
    if table is None:
        table = DropTable(region_id=region.id)
        db.add(table)
        db.flush()
    else:
        table.bands.clear()
        db.flush()

    for band_data in data["bands"]:
        band = DropTableBand(
            drop_table_id=table.id,
            tier=band_data["tier"],
            roll_min=band_data["roll_min"],
            roll_max=band_data["roll_max"],
        )
        db.add(band)
        db.flush()
        for item_name in band_data["items"]:
            db.add(DropTableItem(band_id=band.id, name=item_name))

    db.commit()
    db.refresh(table)
    return table


def load_drop_tables_from_dir(db: Session, content_dir: str) -> list[DropTable]:
    loaded = []
    for path in sorted(Path(content_dir).glob("*.json")):
        loaded.append(load_drop_table(db, path.read_text(encoding="utf-8")))
    return loaded


def load_table_for_region(db: Session, region_id: int) -> DropTable | None:
    return db.execute(
        select(DropTable)
        .options(selectinload(DropTable.bands).selectinload(DropTableBand.items))
        .where(DropTable.region_id == region_id)
    ).scalar_one_or_none()


@dataclass
class RollResult:
    tier: str
    item_name: str


def resolve_roll(table: DropTable, roll_value: int, rng: random.Random | None = None) -> RollResult | None:
    """Picks a band containing roll_value and a uniformly random item from
    it. Returns None if no band covers that roll (e.g. a non-Payoff roll
    landing above 100, which only Beyond bands should cover)."""
    rng = rng or random
    for band in table.bands:
        if band.roll_min <= roll_value <= band.roll_max:
            item = rng.choice(band.items)
            return RollResult(tier=band.tier, item_name=item.name)
    return None
