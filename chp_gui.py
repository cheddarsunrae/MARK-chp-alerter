#!/usr/bin/env python3
"""Temporary recovery launcher for MARK.

The full dashboard rebuild is being split into smaller modules so GitHub's contents
API can accept it reliably. This file keeps the repository runnable during that
transition by delegating to the last known-good controller when available.
"""
from __future__ import annotations

import sys

try:
    from mark_app import main
except ImportError as exc:
    raise SystemExit(
        "MARK dashboard modules are incomplete. Run git pull again after the current update completes. "
        f"Missing dependency: {exc}"
    )

if __name__ == "__main__":
    sys.exit(main())
