#!/usr/bin/env python3
"""Column-safe MARK Region GUI entry point.

This wrapper keeps the current region/reload behavior but normalizes the middle
Configuration pane so labels, explanations, checkboxes, and buttons stay inside
the available column instead of disappearing off the right edge.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import mark_gui_entry
from mark_region_reload_entry import ReloadingRegionMarkApp

WRAP_LENGTH = 320
LONG_LABEL_THRESHOLD = 38


class ColumnSafeRegionMarkApp(ReloadingRegionMarkApp):
    """Reflow inherited configuration controls for a narrow middle column."""

    def _insert_region_map_panel(self, frame: ttk.Frame) -> None:
        super()._insert_region_map_panel(frame)
        panel = self._find_region_panel(frame)
        if panel is not None:
            self._make_column_safe(panel)
            self.after(120, lambda: self._make_column_safe(panel))

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
