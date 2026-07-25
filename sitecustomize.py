"""Apply MARK runtime policy and the configured service-area polygon at startup.

Python imports ``sitecustomize`` automatically when this repository/application
folder is on ``sys.path``. This keeps the runtime geofence synchronized with the
GeoJSON edited through the desktop interface and applies MARK's 30-second
minimum polling policy without duplicating the monitor implementation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

MINIMUM_POLL_INTERVAL_SECONDS = 30.0


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
    import chp_jamul_alert as core

    # Make 30 seconds the backend default and minimum while preserving every
    # other argument validation performed by the original monitor.
    core.DEFAULT_INTERVAL = MINIMUM_POLL_INTERVAL_SECONDS
    original_validate_args = core.validate_args

    def validate_args_with_mark_policy(args: Any) -> None:
        if args.interval < MINIMUM_POLL_INTERVAL_SECONDS:
            raise SystemExit(
                f"--interval must be at least {int(MINIMUM_POLL_INTERVAL_SECONDS)} seconds"
            )
        original_interval = args.interval
        if original_interval < 60:
            args.interval = 60
        try:
            original_validate_args(args)
        finally:
            args.interval = original_interval

    core.validate_args = validate_args_with_mark_policy

    path = _service_area_path()
    if path.exists():
        core.SERVICE_AREA_POLYGON = _read_polygon(path)


try:
    _apply()
except Exception as exc:  # Startup must remain diagnosable rather than bricked.
    print(
        f"MARK warning: could not apply startup configuration: {exc}",
        file=__import__("sys").stderr,
    )
