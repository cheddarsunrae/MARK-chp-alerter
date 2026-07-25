"""Shared configuration and GeoJSON helpers for MARK."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_TITLE = "MARK — CHP Alerting & Monitoring Tool"
ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
BACKEND = ROOT / "mark_backend.py"
DEFAULT_MAP = ROOT / "service_area.geojson"

BG = "#071425"
PANEL = "#0c1d31"
PANEL_2 = "#10263e"
BORDER = "#28435f"
TEXT = "#eef4fb"
MUTED = "#a9b8c8"
GOLD = "#f5bd2e"
GREEN = "#63c744"
RED = "#d63832"
BLUE = "#155487"
LOG_BG = "#06111e"

LONG_SOUNDS = {
    "alien": "Alien Alarm (long)", "climb": "Climb (long)",
    "echo": "Pushover Echo (long)", "updown": "Up Down (long)",
    "persistent": "Persistent (long)",
}
ALL_SOUNDS = {
    **LONG_SOUNDS, "siren": "Siren", "spacealarm": "Space Alarm",
    "tugboat": "Tug Boat", "bugle": "Bugle", "incoming": "Incoming",
    "mechanical": "Mechanical", "pushover": "Pushover default",
}


def default_data_dir() -> Path:
    local = os.getenv("LOCALAPPDATA")
    if local:
        return Path(local) / "MARK"
    xdg = os.getenv("XDG_STATE_HOME")
    return Path(xdg) / "mark" if xdg else Path.home() / ".local" / "state" / "mark"


def default_tile_dir() -> Path:
    local = os.getenv("LOCALAPPDATA")
    if local:
        return Path(local) / "MARK" / "tiles"
    xdg = os.getenv("XDG_CACHE_HOME")
    return Path(xdg) / "mark" / "tiles" if xdg else Path.home() / ".cache" / "mark" / "tiles"


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_env(path: Path, values: dict[str, str]) -> None:
    order = [
        ("# Polling and state", None),
        ("CHP_ALERT_INTERVAL", values["CHP_ALERT_INTERVAL"]),
        ("CHP_ALERT_TIMEOUT", values["CHP_ALERT_TIMEOUT"]),
        ("CHP_ALERT_STATE_FILE", values["CHP_ALERT_STATE_FILE"]),
        ("CHP_ALERT_DETAIL_LOG_FILE", values["CHP_ALERT_DETAIL_LOG_FILE"]),
        ("CHP_ALERT_SERVICE_AREA_FILE", values["CHP_ALERT_SERVICE_AREA_FILE"]),
        ("CHP_ALERT_RETENTION_HOURS", values["CHP_ALERT_RETENTION_HOURS"]),
        ("CHP_ALERT_LOG_LEVEL", values["CHP_ALERT_LOG_LEVEL"]),
        ("", None), ("# Geocoding", None),
        ("CHP_ALERT_GEOCODER", values["CHP_ALERT_GEOCODER"]),
        ("CHP_ALERT_CONTACT", values["CHP_ALERT_CONTACT"]),
        ("", None), ("# Startup and update behaviour", None),
        ("CHP_ALERT_EXISTING", values["CHP_ALERT_EXISTING"]),
        ("CHP_ALERT_UPDATES", values["CHP_ALERT_UPDATES"]),
        ("", None), ("# Pushover", None),
        ("PUSHOVER_APP_TOKEN", values["PUSHOVER_APP_TOKEN"]),
        ("PUSHOVER_USER_KEY", values["PUSHOVER_USER_KEY"]),
        ("PUSHOVER_PRIORITY", values["PUSHOVER_PRIORITY"]),
        ("PUSHOVER_RETRY_SECONDS", values["PUSHOVER_RETRY_SECONDS"]),
        ("PUSHOVER_EXPIRE_SECONDS", values["PUSHOVER_EXPIRE_SECONDS"]),
        ("PUSHOVER_SOUND", values["PUSHOVER_SOUND"]),
    ]
    path.write_text("\n".join(k if v is None else f"{k}={v}" for k, v in order).rstrip() + "\n", encoding="utf-8")


def resolve_path(value: str) -> Path:
    path = Path(os.path.expandvars(value)).expanduser()
    return path if path.is_absolute() else ROOT / path


def load_geojson_polygon(path: Path) -> tuple[dict[str, Any], list[tuple[float, float]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", []) if payload.get("type") == "FeatureCollection" else [payload]
    for feature in features:
        geometry = feature.get("geometry", {})
        if geometry.get("type") == "Polygon":
            ring = geometry.get("coordinates", [[]])[0]
            points = [(float(lat), float(lon)) for lon, lat in ring]
            if len(points) > 1 and points[0] == points[-1]:
                points.pop()
            if len(points) < 3:
                raise ValueError("Service-area polygon must have at least three vertices.")
            return payload, points
    raise ValueError("GeoJSON does not contain a Polygon feature.")


def save_geojson_polygon(path: Path, payload: dict[str, Any], points: list[tuple[float, float]]) -> None:
    if len(points) < 3:
        raise ValueError("Service-area polygon must have at least three vertices.")
    ring = [[lon, lat] for lat, lon in points]
    ring.append(ring[0])
    features = payload.get("features", []) if payload.get("type") == "FeatureCollection" else [payload]
    for feature in features:
        geometry = feature.get("geometry", {})
        if geometry.get("type") == "Polygon":
            geometry["coordinates"] = [ring]
            break
    else:
        raise ValueError("GeoJSON does not contain a Polygon feature.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
