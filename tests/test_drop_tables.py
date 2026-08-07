import json
import random

import pytest

from app.loot.tables import (
    UnknownRegionSlug,
    load_drop_table,
    load_table_for_region,
    resolve_roll,
)
from app.models import Region

# Placeholder table shape, not real content.
PLACEHOLDER_TABLE = {
    "region_slug": "test-region",
    "bands": [
        {"tier": "common", "roll_min": 1, "roll_max": 80, "items": ["Widget A", "Widget B"]},
        {"tier": "rare", "roll_min": 81, "roll_max": 99, "items": ["Widget C"]},
        {"tier": "signature", "roll_min": 100, "roll_max": 100, "items": ["Widget D"]},
    ],
}


def add_region(db_session, slug="test-region") -> Region:
    region = Region(slug=slug, name="Test Region", polygon_geojson="{}")
    db_session.add(region)
    db_session.commit()
    db_session.refresh(region)
    return region


def test_load_drop_table_requires_existing_region(db_session):
    with pytest.raises(UnknownRegionSlug):
        load_drop_table(db_session, json.dumps(PLACEHOLDER_TABLE))


def test_load_drop_table_creates_bands_and_items(db_session):
    region = add_region(db_session)
    table = load_drop_table(db_session, json.dumps(PLACEHOLDER_TABLE))
    assert table.region_id == region.id
    assert len(table.bands) == 3
    assert {item.name for item in table.bands[0].items} == {"Widget A", "Widget B"}


def test_load_drop_table_replaces_bands_on_reload(db_session):
    add_region(db_session)
    load_drop_table(db_session, json.dumps(PLACEHOLDER_TABLE))

    updated = dict(PLACEHOLDER_TABLE)
    updated["bands"] = [{"tier": "common", "roll_min": 1, "roll_max": 100, "items": ["Widget Z"]}]
    table = load_drop_table(db_session, json.dumps(updated))

    assert len(table.bands) == 1
    assert table.bands[0].items[0].name == "Widget Z"


def test_resolve_roll_picks_correct_band(db_session):
    add_region(db_session)
    load_drop_table(db_session, json.dumps(PLACEHOLDER_TABLE))
    table = load_table_for_region(db_session, db_session.query(Region).one().id)

    result = resolve_roll(table, 100)
    assert result.tier == "signature"
    assert result.item_name == "Widget D"


def test_resolve_roll_picks_uniformly_within_band(db_session):
    add_region(db_session)
    load_drop_table(db_session, json.dumps(PLACEHOLDER_TABLE))
    table = load_table_for_region(db_session, db_session.query(Region).one().id)

    rng = random.Random(1234)
    results = {resolve_roll(table, 50, rng=rng).item_name for _ in range(20)}
    assert results == {"Widget A", "Widget B"}


def test_resolve_roll_returns_none_outside_all_bands(db_session):
    add_region(db_session)
    load_drop_table(db_session, json.dumps(PLACEHOLDER_TABLE))
    table = load_table_for_region(db_session, db_session.query(Region).one().id)

    assert resolve_roll(table, 150) is None
