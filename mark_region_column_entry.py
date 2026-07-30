#!/usr/bin/env python3
"""Column-safe MARK Region GUI entry point.

This wrapper keeps the current region/reload behavior but normalizes the middle
Configuration pane so labels, explanations, checkboxes, and buttons stay inside
the available column instead of disappearing off the right edge. It also keeps
the human-readable service-area label synchronized with the map loaded through
Load Map so notifications cannot reuse a stale label from an older map.
"""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

import mark_app
import mark_gui_entry
from mark_region_reload_entry import ReloadingRegionMarkApp

WRAP_LENGTH = 320
LONG_LABEL_THRESHOLD = 38
LABEL_MAX_CHARS = 120


class ColumnSafeRegionMarkApp(ReloadingRegionMarkApp):
    """Reflow inherited configuration controls for a narrow middle column."""

    def _insert_region_map_panel(self, frame: ttk.Frame) -> None:
        super()._insert_region_map_panel(frame)
        panel = self._find_region_panel(frame)
        if panel is not None:
            self._make_column_safe(panel)
            self.after(120, lambda: self._make_column_safe(panel))

    def _load_service_area_map_path(self, path: Path, action: str) -> bool:
        """Load a map and keep the alert-facing service-area label in sync."""
        normalized = self._normalize_path(path)
        label = self._label_for_loaded_map(normalized)
        if label:
            self.vars["CHP_ALERT_SERVICE_AREA_LABEL"].set(label)
        return super()._load_service_area_map_path(normalized, action)

    def _label_for_loaded_map(self, path: Path) -> str:
        """Return the best human-readable label for a newly loaded map file."""
        try:
            payload, _points = mark_app.load_polygon(path)
        except Exception:
            return self._fallback_map_label(path)

        properties = self._first_feature_properties(payload)
        for key in ("name", "title", "label", "service_area", "description"):
            value = str(properties.get(key, "")).strip()
            if value:
                return value[:LABEL_MAX_CHARS]
        return self._fallback_map_label(path)

    def _first_feature_properties(self, payload: object) -> dict[str, object]:
        if not isinstance(payload, dict):
            return {}
        if isinstance(payload.get("properties"), dict):
            return payload["properties"]
        features = payload.get("features")
        if isinstance(features, list) and features:
            first = features[0]
            if isinstance(first, dict) and isinstance(first.get("properties"), dict):
                return first["properties"]
        return {}

    def _fallback_map_label(self, path: Path) -> str:
        stem = path.stem.replace("_", "-").strip() or "loaded service-area map"
        return stem[:LABEL_MAX_CHARS]

    def _make_column_safe(self, widget: tk.Widget) -> None:
        """Apply conservative no-overflow rules to a widget subtree."""
        self._configure_column_widget(widget)
        self._collapse_multi_column_grid(widget)
        for child in widget.winfo_children():
            self._make_column_safe(child)

    def _configure_column_widget(self, widget: tk.Widget) -> None:
        try:
            if isinstance(widget, ttk.Label):
                text = str(widget.cget("text") or "")
                textvariable = str(widget.cget("textvariable") or "")
                if text or textvariable:
                    widget.configure(wraplength=WRAP_LENGTH, justify="left")
                if len(text) >= LONG_LABEL_THRESHOLD:
                    self._move_packed_label_to_own_line(widget)
            elif isinstance(widget, ttk.Entry):
                widget.configure(width=10)
            elif isinstance(widget, ttk.Combobox):
                widget.configure(width=14)
        except tk.TclError:
            return

    def _move_packed_label_to_own_line(self, label: tk.Widget) -> None:
        """Move long side-packed labels below their row controls."""
        try:
            if label.winfo_manager() != "pack":
                return
            info = label.pack_info()
            if str(info.get("side", "top")) != "left":
                return
            siblings = [
                child
                for child in label.master.winfo_children()
                if child is not label and child.winfo_manager() == "pack"
            ]
            if not any(str(child.pack_info().get("side", "top")) == "left" for child in siblings):
                return
            label.pack_forget()
            label.pack(anchor="w", fill="x", pady=(3, 0))
        except tk.TclError:
            return

    def _collapse_multi_column_grid(self, widget: tk.Widget) -> None:
        """Change inherited two-column grids into single-column rows."""
        try:
            gridded = [child for child in widget.winfo_children() if child.winfo_manager() == "grid"]
            if len(gridded) < 3:
                return
            if not any(isinstance(child, (ttk.Checkbutton, ttk.Button)) for child in gridded):
                return
            ordered = sorted(
                gridded,
                key=lambda child: (
                    int(child.grid_info().get("row", 0)),
                    int(child.grid_info().get("column", 0)),
                ),
            )
            for row, child in enumerate(ordered):
                child.grid_configure(row=row, column=0, columnspan=2, sticky="ew", padx=0, pady=2)
            widget.columnconfigure(0, weight=1)
            for column in range(1, 5):
                widget.columnconfigure(column, weight=0)
        except tk.TclError:
            return



def main() -> int:
    try:
        ColumnSafeRegionMarkApp().mainloop()
        return 0
    except Exception:
        mark_gui_entry.report_startup_failure()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
