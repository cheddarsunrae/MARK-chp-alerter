#!/usr/bin/env python3
"""Cross-platform CHP Alerter entry point with runtime GeoJSON loading."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import chp_detail_alert as detail
import chp_jamul_alert as core
from service_area_runtime import ServiceAreaError, apply_to_core

ROOT = Path(__file__).resolve().parent
DEFAULT_MAP = ROOT / "service_area.geojson"
LOG = logging.getLogger("chp-alerter.map")


def configured_map_path() -> Path:
    raw = os.getenv("CHP_ALERT_SERVICE_AREA_FILE", str(DEFAULT_MAP))
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def configure_runtime() -> Path:
    map_path = configured_map_path()
    area = apply_to_core(core, map_path)

    detail_path = os.getenv("CHP_ALERT_DETAIL_LOG_FILE")
    if detail_path:
        detail.DETAIL_LOG_FILE = Path(detail_path).expanduser()

    LOG.info(
        "Loaded service-area map %s with %d polygon vertices",
        map_path,
        len(area["polygon"]),
    )
    return map_path


def main() -> int:
    try:
        configure_runtime()
    except ServiceAreaError as exc:
        print(f"Service-area configuration error: {exc}", file=sys.stderr)
        return 2
    return detail.main()


if __name__ == "__main__":
    raise SystemExit(main())
