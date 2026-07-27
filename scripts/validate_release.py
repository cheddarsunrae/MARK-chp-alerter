#!/usr/bin/env python3
"""Validate the MARK source tree before building a beta release package."""
from __future__ import annotations

import json
import py_compile
import subprocess
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
    "address_box_runtime.py",
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

FORBIDDEN_TRACKED_PATHS = (
    ".env",
    "runtime/",
    ".venv/",
    "venv/",
    "dist/",
    "releases/",
)


def _fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def _git_ls_files() -> set[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return set()
    return {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}


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


def validate_forbidden_paths_not_tracked() -> None:
    tracked = _git_ls_files()
    for forbidden in FORBIDDEN_TRACKED_PATHS:
        if forbidden.endswith("/"):
            if any(path.startswith(forbidden) for path in tracked):
                _fail(f"Forbidden tracked release/runtime directory: {forbidden}")
        elif forbidden in tracked:
            _fail(f"Forbidden tracked secret/runtime file: {forbidden}")


def main() -> int:
    validate_required_files()
    validate_json_files()
    validate_python_compile()
    validate_forbidden_paths_not_tracked()
    print("MARK release validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
