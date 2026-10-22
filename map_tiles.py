#!/usr/bin/env python3
"""Policy-aware background tile sources for MARK's service-area editor.

Tiles are for the GUI basemap only. The incident matcher always uses the
user's GeoJSON boundary, not the visual basemap. Do not fall back to the
volunteer-operated tile.openstreetmap.org infrastructure.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

DEFAULT_PROVIDER = "USGS Topo"
PROVIDERS = ("USGS Topo", "USGS Imagery Topo", "MapTiler Streets")

USGS_TOPO = (
    "https://basemap.nationalmap.gov/arcgis/rest/services/"
    "USGSTopo/MapServer/tile/{z}/{y}/{x}"
)
USGS_IMAGERY_TOPO = (
    "https://basemap.nationalmap.gov/arcgis/rest/services/"
    "USGSImageryTopo/MapServer/tile/{z}/{y}/{x}"
)
USGS_CREDIT = "Map services and data available from U.S. Geological Survey, National Geospatial Program."
MAPTILER_CREDIT = "© MapTiler © OpenStreetMap contributors"


@dataclass(frozen=True)
class TileSource:
    provider: str
    url: str
    max_zoom: int
    attribution: str


def resolve_tile_source(provider: str, maptiler_key: str = "") -> TileSource:
    """Validate a supported provider and return its XYZ tile template.

    USGS requires no API key. MapTiler requires a user-provided API key
    and acceptance of its service terms; no shared keys are shipped.
    """
    requested = (provider or DEFAULT_PROVIDER).strip()
    if requested == "USGS Topo":
        return TileSource(requested, USGS_TOPO, 16, USGS_CREDIT)
    if requested == "USGS Imagery Topo":
        return TileSource(requested, USGS_IMAGERY_TOPO, 15, USGS_CREDIT)
    if requested == "MapTiler Streets":
        key = (maptiler_key or "").strip()
        if not key:
            raise ValueError("MapTiler Streets requires your own MapTiler API key.")
        return TileSource(
            requested,
            "https://api.maptiler.com/maps/streets-v4/256/"
            "{z}/{x}/{y}.png?key=" + quote(key, safe=""),
            19,
            MAPTILER_CREDIT,
        )
    raise ValueError("Unknown basemap provider. Choose USGS Topo, USGS Imagery Topo, or MapTiler Streets.")


def tile_source_from_settings(settings: dict[str, str]) -> TileSource:
    """Resolve settings loaded from the local, untracked .env file."""
    return resolve_tile_source(
        settings.get("MARK_BASEMAP_PROVIDER", DEFAULT_PROVIDER),
        settings.get("MARK_MAPTILER_API_KEY", ""),
    )
