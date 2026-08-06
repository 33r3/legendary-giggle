"""Loads region boundaries from an operator-supplied GeoJSON file.

Geometry (and the real-world places it corresponds to) is something only
the player can supply — this module just validates and persists it. The
file itself is never committed; point it at a local path via
REGIONS_GEOJSON_PATH.
"""

import json

from shapely.geometry import shape
from shapely.validation import explain_validity
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Region


class InvalidRegionGeometry(Exception):
    pass


def parse_region_features(geojson_text: str) -> list[dict]:
    collection = json.loads(geojson_text)
    features = []
    for feature in collection["features"]:
        props = feature["properties"]
        polygon = shape(feature["geometry"])
        if not polygon.is_valid:
            raise InvalidRegionGeometry(
                f"region '{props.get('slug', '?')}' has invalid geometry: {explain_validity(polygon)}"
            )
        features.append(
            {
                "slug": props["slug"],
                "name": props["name"],
                "polygon_geojson": json.dumps(feature["geometry"]),
            }
        )
    return features


def load_regions(db: Session, geojson_text: str) -> list[Region]:
    features = parse_region_features(geojson_text)

    loaded = []
    for feature in features:
        region = db.execute(select(Region).where(Region.slug == feature["slug"])).scalar_one_or_none()
        if region is None:
            region = Region(slug=feature["slug"])
            db.add(region)
        region.name = feature["name"]
        region.polygon_geojson = feature["polygon_geojson"]
        loaded.append(region)

    db.commit()
    for region in loaded:
        db.refresh(region)
    return loaded
