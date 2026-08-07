import json
from datetime import datetime, timedelta, timezone

import pytest

from app.geo.attribution import attribute_route_minutes, load_region_polygons
from app.geo.regions import InvalidRegionGeometry, load_regions, parse_region_features
from app.models import Region, WorkoutRoutePoint

# Synthetic squares, not real geography — for shape testing only.
SQUARE_A = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]],
}
SQUARE_B = {
    "type": "Polygon",
    "coordinates": [[[2, 0], [2, 1], [3, 1], [3, 0], [2, 0]]],
}
BOWTIE = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]],
}


def geojson_collection(features: list[dict]) -> str:
    return json.dumps({"type": "FeatureCollection", "features": features})


def feature(slug: str, geometry: dict) -> dict:
    return {"type": "Feature", "properties": {"slug": slug, "name": slug}, "geometry": geometry}


def test_parse_rejects_invalid_geometry():
    collection = geojson_collection([feature("bad", BOWTIE)])
    with pytest.raises(InvalidRegionGeometry):
        parse_region_features(collection)


def test_load_regions_upserts_by_slug(db_session):
    collection = geojson_collection([feature("area-a", SQUARE_A)])
    first = load_regions(db_session, collection)
    assert len(first) == 1

    second = load_regions(db_session, collection)
    assert len(second) == 1
    assert second[0].id == first[0].id
    assert db_session.query(Region).count() == 1


def _route_point(workout_id, index, lat, lon, seconds_offset):
    base = datetime(2026, 8, 1, 9, tzinfo=timezone.utc)
    return WorkoutRoutePoint(
        workout_id=workout_id,
        sequence_index=index,
        latitude=lat,
        longitude=lon,
        recorded_at=base + timedelta(seconds=seconds_offset),
    )


def test_attribute_route_minutes_splits_by_region(db_session):
    load_regions(db_session, geojson_collection([feature("area-a", SQUARE_A), feature("area-b", SQUARE_B)]))
    regions = load_region_polygons(db_session.query(Region).all())

    points = [
        _route_point(None, 0, 0.5, 0.5, 0),      # inside area-a
        _route_point(None, 1, 0.5, 0.5, 600),    # 10 min still in area-a
        _route_point(None, 2, 0.5, 2.5, 900),    # 5 min crossing the gap between areas
        _route_point(None, 3, 0.5, 2.5, 1200),   # 5 min settled in area-b
    ]

    minutes = attribute_route_minutes(points, regions)

    area_a_id = next(r.id for r in regions if json.loads(db_session.get(Region, r.id).polygon_geojson) == SQUARE_A)
    area_b_id = next(r.id for r in regions if r.id != area_a_id)

    assert minutes[area_a_id] == pytest.approx(10.0)
    assert minutes[area_b_id] == pytest.approx(5.0)
    assert minutes[None] == pytest.approx(5.0)


def test_attribute_route_minutes_buckets_outside_points_as_none(db_session):
    load_regions(db_session, geojson_collection([feature("area-a", SQUARE_A)]))
    regions = load_region_polygons(db_session.query(Region).all())

    points = [
        _route_point(None, 0, 50, 50, 0),
        _route_point(None, 1, 50, 50, 300),
    ]

    minutes = attribute_route_minutes(points, regions)
    assert minutes == {None: pytest.approx(5.0)}
