#!/usr/bin/env python3
"""MARK runtime entry point with a 30-second minimum poll interval."""
from __future__ import annotations

import sys
from typing import Any, Iterable

import chp_detail_alert
import chp_jamul_alert as core

MINIMUM_POLL_INTERVAL_SECONDS = 30.0


def validate_args(args: Any) -> None:
    if args.interval < MINIMUM_POLL_INTERVAL_SECONDS:
        raise SystemExit("--interval must be at least 30 seconds")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if bool(args.pushover_token) != bool(args.pushover_user):
        raise SystemExit("Pushover requires both PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY")
    if args.test_pushover and not args.pushover_token:
        raise SystemExit("--test-pushover requires Pushover credentials")
    if args.pushover_priority not in {-2, -1, 0, 1, 2}:
        raise SystemExit("PUSHOVER_PRIORITY must be -2, -1, 0, 1, or 2")
    if args.pushover_priority == 2:
        if args.pushover_retry < 30:
            raise SystemExit("PUSHOVER_RETRY_SECONDS must be at least 30")
        if not 1 <= args.pushover_expire <= 10800:
            raise SystemExit("PUSHOVER_EXPIRE_SECONDS must be between 1 and 10800")
    if args.geocoder == "nominatim" and not args.geocode_contact:
        raise SystemExit("Nominatim requires CHP_ALERT_CONTACT")


def main(argv: Iterable[str] | None = None) -> int:
    core.DEFAULT_INTERVAL = MINIMUM_POLL_INTERVAL_SECONDS
    core.validate_args = validate_args
    return chp_detail_alert.main(argv)


if __name__ == "__main__":
    sys.exit(main())
