#!/usr/bin/env python3
"""Reliable MARK GUI entry point.

This initializes Tk before any Tk variables are created and records otherwise-hidden
pythonw startup failures in runtime/mark-gui-error.log.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

from chp_gui import BrandedMarkApp
from mark_app import MarkApp

ROOT = Path(__file__).resolve().parent
ERROR_LOG = ROOT / "runtime" / "mark-gui-error.log"


class SafeMarkApp(BrandedMarkApp):
    """Initialize non-Tk state first, then let MarkApp create the Tk root."""

    def __init__(self) -> None:
        self.profiles = self._read_profiles()
        self.selected_vertex_index: int | None = None
        self.zone_active = False
        self.zone_start_index: int | None = None
        self.zone_points: list[tuple[float, float]] = []
        self.zone_markers: list = []
        self.zone_path = None
        self._press_xy: tuple[int, int] | None = None
        self._dragging = False
        MarkApp.__init__(self)


def report_startup_failure() -> None:
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    details = traceback.format_exc()
    ERROR_LOG.write_text(details, encoding="utf-8")
    message = (
        "MARK could not start.\n\n"
        f"The full error was written to:\n{ERROR_LOG}\n\n"
        "Run start-chp-alerter.ps1 again after correcting the reported problem."
    )
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "MARK startup error", 0x10)
            return
        except Exception:
            pass
    print(message, file=sys.stderr)
    print(details, file=sys.stderr)


def main() -> int:
    try:
        SafeMarkApp().mainloop()
        return 0
    except Exception:
        report_startup_failure()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
