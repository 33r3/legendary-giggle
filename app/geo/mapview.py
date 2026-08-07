"""Projects loaded region boundaries into a shared SVG coordinate space
for the dashboard map. Deliberately not a basemap-tile viewer — no
external tile service is called (self-hosted only), and a stylized
shape-only rendering fits the RPG's presentation better than a literal
street map anyway.
"""

import json
import math
from dataclasses import dataclass

from shapely.geometry import shape

from app.models import Region


@dataclass
class RegionMapShape:
    slug: str
    name: str
    unlocked: bool
    rings: list[str]  # SVG polygon "points" attribute values, one per ring
    label_x: float
    label_y: float


@dataclass
class RegionMap:
    view_box: str
    shapes: list[RegionMapShape]


def _rings(geometry) -> list[list[tuple[float, float]]]:
    if geometry.geom_type == "Polygon":
        return [list(geometry.exterior.coords)]
    if geometry.geom_type == "MultiPolygon":
        return [list(polygon.exterior.coords) for polygon in geometry.geoms]
    raise ValueError(f"unsupported region geometry type: {geometry.geom_type}")


def build_region_map(
    regions_with_status: list[tuple[Region, bool]],
    width: int = 640,
    height: int = 480,
    padding: float = 0.1,
) -> RegionMap:
    """Projects every region's real boundary into one shared canvas,
    preserving relative position, scale, and shape across regions."""
    if not regions_with_status:
        return RegionMap(view_box=f"0 0 {width} {height}", shapes=[])

    geometries = [shape(json.loads(region.polygon_geojson)) for region, _ in regions_with_status]

    min_lon = min(g.bounds[0] for g in geometries)
    min_lat = min(g.bounds[1] for g in geometries)
    max_lon = max(g.bounds[2] for g in geometries)
    max_lat = max(g.bounds[3] for g in geometries)

    # Equirectangular projection: scale longitude by cos(latitude) so
    # shapes aren't stretched horizontally at this latitude.
    lon_scale = math.cos(math.radians((min_lat + max_lat) / 2)) or 1.0
    lon_span = max((max_lon - min_lon) * lon_scale, 1e-9)
    lat_span = max(max_lat - min_lat, 1e-9)

    pad_w, pad_h = width * padding, height * padding
    draw_w, draw_h = width - 2 * pad_w, height - 2 * pad_h
    scale = min(draw_w / lon_span, draw_h / lat_span)

    offset_x = pad_w + (draw_w - lon_span * scale) / 2
    offset_y = pad_h + (draw_h - lat_span * scale) / 2

    def project(lon: float, lat: float) -> tuple[float, float]:
        x = offset_x + (lon - min_lon) * lon_scale * scale
        y = offset_y + (max_lat - lat) * scale  # flip: north is up
        return x, y

    shapes = []
    for (region, unlocked), geometry in zip(regions_with_status, geometries):
        rings = [
            " ".join(f"{x:.2f},{y:.2f}" for x, y in (project(lon, lat) for lon, lat in ring))
            for ring in _rings(geometry)
        ]
        label_x, label_y = project(*geometry.representative_point().coords[0])
        shapes.append(
            RegionMapShape(
                slug=region.slug,
                name=region.name,
                unlocked=unlocked,
                rings=rings,
                label_x=label_x,
                label_y=label_y,
            )
        )

    return RegionMap(view_box=f"0 0 {width} {height}", shapes=shapes)
