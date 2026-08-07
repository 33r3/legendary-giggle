from app.geo.mapview import build_region_map
from app.models import Region

# Synthetic squares, not real geography — for shape testing only.
SQUARE_A = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]],
}
SQUARE_B = {
    "type": "Polygon",
    "coordinates": [[[2, 0], [2, 1], [3, 1], [3, 0], [2, 0]]],
}


def make_region(slug: str, geometry: dict, region_id: int = 1) -> Region:
    import json

    region = Region(slug=slug, name=slug, polygon_geojson=json.dumps(geometry), always_unlocked=False)
    region.id = region_id
    return region


def test_empty_input_returns_no_shapes():
    region_map = build_region_map([])
    assert region_map.shapes == []
    assert region_map.view_box == "0 0 640 480"


def test_each_region_produces_one_shape_with_status():
    region_a = make_region("area-a", SQUARE_A, region_id=1)
    region_b = make_region("area-b", SQUARE_B, region_id=2)

    region_map = build_region_map([(region_a, True), (region_b, False)])

    assert [s.slug for s in region_map.shapes] == ["area-a", "area-b"]
    assert [s.unlocked for s in region_map.shapes] == [True, False]
    for shape in region_map.shapes:
        assert len(shape.rings) == 1
        assert shape.rings[0].count(",") >= 4  # at least 5 coordinate pairs (closed ring)


def test_projected_points_stay_within_canvas():
    region_a = make_region("area-a", SQUARE_A, region_id=1)
    region_b = make_region("area-b", SQUARE_B, region_id=2)

    region_map = build_region_map([(region_a, True), (region_b, False)], width=640, height=480)

    for shape in region_map.shapes:
        for ring in shape.rings:
            for pair in ring.split(" "):
                x, y = (float(v) for v in pair.split(","))
                assert 0 <= x <= 640
                assert 0 <= y <= 480


def test_relative_east_west_ordering_is_preserved():
    """area-b is east of area-a in real coordinates (higher longitude) —
    the projection should keep that ordering on the canvas (higher x)."""
    region_a = make_region("area-a", SQUARE_A, region_id=1)
    region_b = make_region("area-b", SQUARE_B, region_id=2)

    region_map = build_region_map([(region_a, True), (region_b, False)])

    label_a = next(s.label_x for s in region_map.shapes if s.slug == "area-a")
    label_b = next(s.label_x for s in region_map.shapes if s.slug == "area-b")
    assert label_b > label_a
