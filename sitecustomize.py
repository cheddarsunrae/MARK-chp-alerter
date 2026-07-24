"""Load the configured service-area polygon before CHP Alerter starts.

Python imports ``sitecustomize`` automatically when this repository/application
folder is on ``sys.path``.  This keeps the runtime geofence synchronized with the
GeoJSON edited or reloaded through the desktop interface without duplicating
polygon coordinates in multiple programs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _service_area_path() -> Path:
    configured = os.getenv("CHP_ALERT_SERVICE_AREA_FILE", "service_area.geojson")
    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    return path


def _read_polygon(path: Path) -> tuple[tuple[float, float], ...]:
    payload: Any = json.loads(path.read_text(encoding="utf-8-sig"))
    features = payload.get("features", []) if isinstance(payload, dict) else []
    polygon = next(
        (
            feature
            for feature in features
            if isinstance(feature, dict)
            and isinstance(feature.get("geometry"), dict)
            and feature["geometry"].get("type") == "Polygon"
        ),
        None,
    )
    if polygon is None:
        raise ValueError("GeoJSON does not contain a Polygon feature")

    rings = polygon["geometry"].get("coordinates")
    if not isinstance(rings, list) or not rings or not isinstance(rings[0], list):
        raise ValueError("GeoJSON Polygon has no exterior ring")

    ring = rings[0]
    if len(ring) >= 2 and ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) < 3:
        raise ValueError("GeoJSON Polygon must contain at least three vertices")

    converted: list[tuple[float, float]] = []
    for coordinate in ring:
        if not isinstance(coordinate, list) or len(coordinate) < 2:
            raise ValueError("Invalid GeoJSON polygon coordinate")
        longitude = float(coordinate[0])
        latitude = float(coordinate[1])
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError("GeoJSON coordinate is outside valid longitude/latitude ranges")
        converted.append((latitude, longitude))
    return tuple(converted)


def _apply() -> None:
    path = _service_area_path()
    if not path.exists():
        return
    polygon = _read_polygon(path)

    # Importing the core here is intentional: later imports receive this same
    # module object with the authoritative polygon already installed.
    import chp_jamul_alert as core

    core.SERVICE_AREA_POLYGON = polygon


try:
    _apply()
except Exception as exc:  # Startup must remain diagnosable rather than bricked.
    print(f"CHP Alerter warning: could not load service-area map: {exc}", file=__import__("sys").stderr)
