#!/usr/bin/env python3
"""Load and validate CHP Alerter service-area GeoJSON at runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ServiceAreaError(ValueError):
    """Raised when a service-area file is missing or invalid."""


def _features(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("type") == "FeatureCollection":
        values = payload.get("features")
        if not isinstance(values, list):
            raise ServiceAreaError("FeatureCollection.features must be a list")
        return [item for item in values if isinstance(item, dict)]
    if payload.get("type") == "Feature":
        return [payload]
    raise ServiceAreaError("GeoJSON must be a FeatureCollection or Feature")


def load_service_area(path: Path) -> dict[str, Any]:
    """Return validated polygon and named point references.

    Polygon coordinates are returned in the monitor's internal ``(lat, lon)`` order.
    GeoJSON itself remains standard ``[lon, lat]``.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ServiceAreaError(f"service-area file not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ServiceAreaError(f"cannot read service-area file {path}: {exc}") from exc

    polygon: list[tuple[float, float]] | None = None
    points: dict[str, tuple[float, float]] = {}

    for feature in _features(payload):
        geometry = feature.get("geometry")
        properties = feature.get("properties") or {}
        if not isinstance(geometry, dict):
            continue
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")
        if geometry_type == "Polygon" and polygon is None:
            if not isinstance(coordinates, list) or not coordinates or not isinstance(coordinates[0], list):
                raise ServiceAreaError("Polygon must contain an exterior coordinate ring")
            ring: list[tuple[float, float]] = []
            for pair in coordinates[0]:
                if not isinstance(pair, list) or len(pair) < 2:
                    raise ServiceAreaError("Polygon coordinates must be [longitude, latitude]")
                lon, lat = float(pair[0]), float(pair[1])
                if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                    raise ServiceAreaError("Polygon coordinate is outside valid longitude/latitude limits")
                ring.append((lat, lon))
            if len(ring) >= 2 and ring[0] == ring[-1]:
                ring.pop()
            if len(ring) < 3:
                raise ServiceAreaError("Polygon needs at least three distinct vertices")
            polygon = ring
        elif geometry_type == "Point" and isinstance(coordinates, list) and len(coordinates) >= 2:
            name = str(properties.get("name", "")).strip()
            if name:
                lon, lat = float(coordinates[0]), float(coordinates[1])
                points[name.casefold()] = (lat, lon)

    if polygon is None:
        raise ServiceAreaError("No Polygon feature was found")

    return {
        "path": path,
        "polygon": tuple(polygon),
        "points": points,
        "geojson": payload,
    }


def apply_to_core(core: Any, path: Path) -> dict[str, Any]:
    """Load a file and apply its polygon/reference points to the monitor module."""
    area = load_service_area(path)
    core.SERVICE_AREA_POLYGON = area["polygon"]

    for name, coordinates in area["points"].items():
        if "station 36" in name:
            core.STATION_COORDINATES = coordinates
        elif "dulzura" in name:
            core.DULZURA_COORDINATES = coordinates
        elif "otay lakes" in name or "chula vista" in name:
            core.OTAY_LAKES_CHULA_VISTA_EDGE = coordinates
    return area
