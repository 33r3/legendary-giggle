"""Time-weighted region attribution for a workout route.

A route isn't a point and can cross boundaries. Start-point attribution
is gameable; majority-of-points is biased by sampling density. Instead,
bucket the minutes between consecutive route points by whichever region
the segment's midpoint falls in, and allocate proportionally.
"""

import json
from dataclasses import dataclass

from shapely.geometry import Point, shape

from app.models import Region, WorkoutRoutePoint


@dataclass
class LoadedRegion:
    id: int
    polygon: object  # shapely geometry


def load_region_polygons(regions: list[Region]) -> list[LoadedRegion]:
    return [LoadedRegion(id=region.id, polygon=shape(json.loads(region.polygon_geojson))) for region in regions]


def _region_for_point(lat: float, lon: float, regions: list[LoadedRegion]) -> int | None:
    point = Point(lon, lat)
    for region in regions:
        if region.polygon.contains(point) or region.polygon.touches(point):
            return region.id
    return None


def attribute_route_minutes(
    route_points: list[WorkoutRoutePoint], regions: list[LoadedRegion]
) -> dict[int | None, float]:
    """Returns minutes spent per region id. `None` collects any time spent
    outside every loaded region (expected until the region set fully
    tiles the space)."""
    minutes_by_region: dict[int | None, float] = {}

    ordered = sorted(route_points, key=lambda p: p.sequence_index)
    for previous, current in zip(ordered, ordered[1:]):
        segment_seconds = (current.recorded_at - previous.recorded_at).total_seconds()
        if segment_seconds <= 0:
            continue

        mid_lat = (previous.latitude + current.latitude) / 2
        mid_lon = (previous.longitude + current.longitude) / 2
        region_id = _region_for_point(mid_lat, mid_lon, regions)

        minutes_by_region[region_id] = minutes_by_region.get(region_id, 0.0) + segment_seconds / 60.0

    return minutes_by_region
