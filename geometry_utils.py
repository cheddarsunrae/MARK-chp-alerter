"""Geometry helpers for MARK service-area polygons."""
from __future__ import annotations

import math
from typing import Iterable

Point = tuple[float, float]
EARTH_RADIUS_M = 6_371_008.8


def _to_local_xy(point: Point, origin: Point) -> tuple[float, float]:
    """Convert latitude/longitude to local equirectangular metres."""
    lat, lon = point
    origin_lat, origin_lon = origin
    x = math.radians(lon - origin_lon) * EARTH_RADIUS_M * math.cos(math.radians(origin_lat))
    y = math.radians(lat - origin_lat) * EARTH_RADIUS_M
    return x, y


def distance_to_segment_metres(point: Point, start: Point, end: Point) -> float:
    """Return perpendicular distance from point to the start/end segment."""
    px, py = _to_local_xy(point, start)
    ex, ey = _to_local_xy(end, start)
    length_squared = ex * ex + ey * ey
    if length_squared == 0:
        return math.hypot(px, py)
    t = max(0.0, min(1.0, (px * ex + py * ey) / length_squared))
    return math.hypot(px - t * ex, py - t * ey)


def simplify_closed_polygon(points: Iterable[Point], tolerance_metres: float = 25.0) -> list[Point]:
    """Remove near-collinear vertices from a closed polygon.

    The polygon is represented without a duplicated closing vertex. A vertex is
    removed only when it lies within ``tolerance_metres`` of the direct segment
    between its neighbours. The pass repeats until stable and never reduces the
    polygon below three vertices.

    This is intentionally conservative. It simplifies redundant hand-drawn
    points; it does not attempt to redraw or smooth genuine bends.
    """
    result = [(float(lat), float(lon)) for lat, lon in points]
    if tolerance_metres < 0:
        raise ValueError("tolerance_metres must be non-negative")
    if len(result) <= 3:
        return result

    changed = True
    while changed and len(result) > 3:
        changed = False
        for index in range(len(result)):
            previous = result[index - 1]
            current = result[index]
            following = result[(index + 1) % len(result)]
            if distance_to_segment_metres(current, previous, following) <= tolerance_metres:
                result.pop(index)
                changed = True
                break
    return result


def remove_shorter_path_between(
    points: Iterable[Point],
    start_index: int,
    end_index: int,
) -> tuple[list[Point], int, int]:
    """Replace the shorter boundary path between two vertices with one segment.

    The polygon is represented without a duplicated closing vertex. The two
    endpoint vertices are preserved. All intermediate vertices along the shorter
    of the two possible boundary paths are removed. The returned selected index
    points to the second endpoint in the new cyclic order.
    """
    result = [(float(lat), float(lon)) for lat, lon in points]
    count = len(result)
    if count < 3:
        raise ValueError("A polygon needs at least three vertices")
    if not 0 <= start_index < count or not 0 <= end_index < count:
        raise IndexError("waypoint index out of range")
    if start_index == end_index:
        raise ValueError("Choose two different waypoints")

    forward_between = (end_index - start_index - 1) % count
    backward_between = (start_index - end_index - 1) % count
    remove_forward = forward_between <= backward_between
    removed = forward_between if remove_forward else backward_between
    if removed <= 0:
        raise ValueError("The selected waypoints are already adjacent")
    if count - removed < 3:
        raise ValueError("Removing those waypoints would leave fewer than three vertices")

    if remove_forward:
        new_points = [result[start_index], result[end_index]]
        index = (end_index + 1) % count
        while index != start_index:
            new_points.append(result[index])
            index = (index + 1) % count
        selected_index = 1
    else:
        new_points = [result[end_index], result[start_index]]
        index = (start_index + 1) % count
        while index != end_index:
            new_points.append(result[index])
            index = (index + 1) % count
        selected_index = 1

    return new_points, removed, selected_index
