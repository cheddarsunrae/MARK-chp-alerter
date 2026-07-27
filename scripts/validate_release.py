#!/usr/bin/env python3
"""Validate the MARK source tree before building a beta release package."""
from __future__ import annotations

import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "VERSION",
    "RELEASE_README.md",
    "README.md",
    "MARK_QUICK_START_GUIDE.md",
    "MARK_TECHNICAL_USER_GUIDE.md",
    ".env.example",
    "requirements.txt",
    "Install MARK - Windows.bat",
    "Install MARK - macOS.command",
    "install-mark-linux.sh",
    "start-chp-alerter.ps1",
    "start-chp-alerter.sh",
    "mark_region_entry.py",
    "mark_update_entry.py",
    "mark_gui_entry.py",
    "mark_app.py",
    "mark_backend.py",
    "chp_center_runtime.py",
    "mark_filter_runtime.py",
    "mark_detail_runtime.py",
    "mark_postback_runtime.py",
    "notification_runtime.py",
    "service_area_runtime.py",
    "geometry_utils.py",
    "data/chp_communications_centers.json",
    "data/chp_center_smoke_boundaries.json",
    "test_maps/san_diego_region_smoke_test.geojson",
)

PYTHON_FILES = tuple(path for path in REQUIRED_FILES if path.endswith(".py")) + (
    "chp_detail_alert.py",
    "chp_jamul_alert.py",
    "chp_gui.py",
    "update_runtime.py",
)

FORBIDDEN_RELEASE_PATHS = (
    ".env",
    "runtime",
    ".venv",
    "venv",
    "dist",
    "releases",
)


def _fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_required_files() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    if missing:
        _fail("Missing required release file(s): " + ", ".join(missing))


def validate_json_files() -> None:
    for path in (
        ROOT / "data" / "chp_communications_centers.json",
        ROOT / "data" / "chp_center_smoke_boundaries.json",
    ):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - report any JSON/read failure clearly
            _fail(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}")


def validate_python_compile() -> None:
    for relative in PYTHON_FILES:
        path = ROOT / relative
        if path.exists():
            py_compile.compile(str(path), doraise=True)


def validate_secrets_absent_from_repo() -> None:
    # These are allowed to be ignored/untracked locally, but must not be committed.
    for relative in FORBIDDEN_RELEASE_PATHS:
        path = ROOT / relative
        if path.is_file() and relative == ".env":
            _fail("A committed .env file would expose local configuration/secrets")


def main() -> int:
    validate_required_files()
    validate_json_files()
    validate_python_compile()
    validate_secrets_absent_from_repo()
    print("MARK release validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
