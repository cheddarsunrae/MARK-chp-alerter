#!/usr/bin/env python3
"""MARK runtime entry point with profile-driven filters and 30-second polling."""
from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import chp_detail_alert as detail
import chp_jamul_alert as core
import mark_detail_runtime
from service_area_runtime import ServiceAreaError, apply_to_core

MINIMUM_POLL_INTERVAL_SECONDS = 30.0
ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger("mark.backend")
DEFAULT_AREA_PREFIXES = ("BC", "El")
DEFAULT_TYPE_FRAGMENTS = (
    "Unk",
    "1140",
    "1141",
    "Min",
    "Maj",
    "1179",
    "1180",
    "1178",
    "un w",
    "Repo",
)


def split_csv(value: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[,;\n]+", value or "")
        if item.strip()
    ]


def validate_args(args: Any) -> None:
    if args.interval < MINIMUM_POLL_INTERVAL_SECONDS:
        raise SystemExit("--interval must be at least 30 seconds")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if bool(args.pushover_token) != bool(args.pushover_user):
        raise SystemExit(
            "Pushover requires both PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY"
        )
    if args.test_pushover and not args.pushover_token:
        raise SystemExit("--test-pushover requires Pushover credentials")
    if args.pushover_priority not in {-2, -1, 0, 1, 2}:
        raise SystemExit("PUSHOVER_PRIORITY must be -2, -1, 0, 1, or 2")
    if args.pushover_priority == 2:
        if args.pushover_retry < 30:
            raise SystemExit("PUSHOVER_RETRY_SECONDS must be at least 30")
        if not 1 <= args.pushover_expire <= 10800:
            raise SystemExit(
                "PUSHOVER_EXPIRE_SECONDS must be between 1 and 10800"
            )


def configure_profile() -> None:
    raw_map = os.getenv(
        "CHP_ALERT_SERVICE_AREA_FILE",
        "service_area.geojson",
    )
    map_path = Path(raw_map).expanduser()
    if not map_path.is_absolute():
        map_path = ROOT / map_path
    try:
        area = apply_to_core(core, map_path)
    except ServiceAreaError as exc:
        raise SystemExit(
            f"Service-area configuration error: {exc}"
        ) from exc

    area_prefixes = split_csv(
        os.getenv(
            "CHP_ALERT_AREA_PREFIXES",
            ",".join(DEFAULT_AREA_PREFIXES),
        )
    )
    if not area_prefixes:
        raise SystemExit(
            "CHP_ALERT_AREA_PREFIXES must contain at least one prefix"
        )

    type_fragments = split_csv(
        os.getenv(
            "CHP_ALERT_TYPE_FRAGMENTS",
            ",".join(DEFAULT_TYPE_FRAGMENTS),
        )
    )
    if not type_fragments:
        raise SystemExit(
            "CHP_ALERT_TYPE_FRAGMENTS must contain at least one fragment"
        )

    detail_path = os.getenv("CHP_ALERT_DETAIL_LOG_FILE")
    if detail_path:
        detail.DETAIL_LOG_FILE = Path(detail_path).expanduser()

    profile = os.getenv("CHP_ALERT_PROFILE", "").strip() or "custom"
    LOG.info(
        "Loaded MARK profile %s: map=%s vertices=%d "
        "area_prefixes=%s type_fragments=%s location_source=CHP-detail-Lat/Lon",
        profile,
        map_path,
        len(area["polygon"]),
        ", ".join(area_prefixes),
        ", ".join(type_fragments),
    )


def main(argv: Iterable[str] | None = None) -> int:
    core.DEFAULT_INTERVAL = MINIMUM_POLL_INTERVAL_SECONDS
    core.validate_args = validate_args
    mark_detail_runtime.install()
    configure_profile()
    return detail.main(argv)


if __name__ == "__main__":
    sys.exit(main())
