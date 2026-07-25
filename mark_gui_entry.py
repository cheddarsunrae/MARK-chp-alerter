#!/usr/bin/env python3
"""Reliable MARK GUI entry point.

This initializes Tk before any Tk variables are created, records otherwise-hidden
pythonw startup failures in runtime/mark-gui-error.log, and adds conservative
service-area boundary simplification to the map editor.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from chp_gui import BrandedMarkApp
from geometry_utils import simplify_closed_polygon
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

    def _build_map(self, frame: ttk.Frame) -> None:
        super()._build_map(frame)
        simplify_bar = ttk.Frame(frame, style="Panel.TFrame")
        simplify_bar.pack(fill="x", pady=(5, 0))
        ttk.Button(
            simplify_bar,
            text="Simplify Boundary",
            command=self.simplify_boundary,
        ).pack(side="left")
        ttk.Label(
            simplify_bar,
            text="Removes near-collinear waypoints; review the preview before saving.",
            style="PanelHead.TLabel",
        ).pack(side="left", padx=8)

    def simplify_boundary(self) -> None:
        if self.zone_active:
            messagebox.showinfo(
                "Finish extension first",
                "Finish or cancel the active zone extension before simplifying.",
                parent=self,
            )
            return
        if len(self.map_points) <= 3:
            messagebox.showinfo(
                "Nothing to simplify",
                "The boundary already has the minimum number of waypoints.",
                parent=self,
            )
            return

        tolerance = simpledialog.askfloat(
            "Simplify boundary",
            "Maximum deviation from a straight segment, in metres:",
            initialvalue=25.0,
            minvalue=0.1,
            maxvalue=500.0,
            parent=self,
        )
        if tolerance is None:
            return

        simplified = simplify_closed_polygon(self.map_points, tolerance)
        removed = len(self.map_points) - len(simplified)
        if removed <= 0:
            messagebox.showinfo(
                "No redundant points",
                f"No waypoint was within {tolerance:g} m of a straight segment.",
                parent=self,
            )
            return

        if not messagebox.askyesno(
            "Apply simplification?",
            f"Remove {removed} of {len(self.map_points)} waypoints using a "
            f"{tolerance:g} m tolerance?\n\nReview the resulting boundary before "
            "pressing Save Map.",
            parent=self,
        ):
            return

        self.map_points = simplified
        self.selected_vertex_index = None
        if hasattr(self, "anchor_status"):
            self.anchor_status.configure(text="Anchor: none")
        self._draw_polygon(False)
        self.append_log(
            f"Simplified boundary: removed {removed} waypoint(s) at {tolerance:g} m tolerance"
        )


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
