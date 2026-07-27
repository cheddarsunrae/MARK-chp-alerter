#!/usr/bin/env python3
"""MARK Region GUI with explicit service-area map import/reload controls."""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import mark_app
import mark_gui_entry
from mark_region_entry import ROOT, RegionMarkApp


class ReloadingRegionMarkApp(RegionMarkApp):
    """Add explicit map import/reload UX and always reopen the last saved map."""

    def load_configuration(self) -> None:
        super().load_configuration()
        self.after(0, self.reload_last_saved_service_area_map)

    def _insert_region_map_panel(self, frame: ttk.Frame) -> None:
        super()._insert_region_map_panel(frame)
        panel = self._find_region_panel(frame)
        if panel is None:
            return
        row = ttk.Frame(panel)
        row.pack(fill="x", pady=(7, 0))
        ttk.Button(row, text="Import Existing Map", command=self.import_existing_service_area_map).pack(side="left")
        ttk.Button(row, text="Reload Last Saved Map", command=lambda: self.reload_last_saved_service_area_map(show_result=True)).pack(side="left", padx=(6, 0))
        ttk.Label(
            row,
            text="Import a GeoJSON service-area map, or reload the map saved in .env.",
            wraplength=330,
        ).pack(side="left", padx=(8, 0))

    def _find_region_panel(self, parent: tk.Widget) -> ttk.LabelFrame | None:
        for child in parent.winfo_children():
            try:
                if isinstance(child, ttk.LabelFrame) and str(child.cget("text")) == "CHP Region / Service-Area Map":
                    return child
            except tk.TclError:
                pass
            nested = self._find_region_panel(child)
            if nested is not None:
                return nested
        return None

    def _last_saved_map_path(self) -> Path | None:
        raw = ""
        var = self.vars.get("CHP_ALERT_SERVICE_AREA_FILE")
        if var is not None:
            raw = var.get().strip()
        if not raw and mark_app.ENV_FILE.exists():
            raw = mark_app.parse_env(mark_app.ENV_FILE).get("CHP_ALERT_SERVICE_AREA_FILE", "").strip()
        if not raw:
            return None
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        return path

    def reload_last_saved_service_area_map(self, show_result: bool = False) -> bool:
        path = self._last_saved_map_path()
        if path is None:
            if show_result:
                messagebox.showinfo(
                    "No saved map",
                    "No service-area map is saved yet. Use Import Existing Map or Build Address Box Map.",
                    parent=self,
                )
            return False
        if not path.exists():
            if show_result:
                messagebox.showwarning(
                    "Saved map not found",
                    f"The last saved service-area map does not exist:\n{path}\n\nUse Import Existing Map to select it again.",
                    parent=self,
                )
            return False
        try:
            self.vars["CHP_ALERT_SERVICE_AREA_FILE"].set(str(path))
            self.map_path = path
            self.reload_map(prompt=False)
            self._refresh_region_summary()
            self.append_log(f"Reloaded last saved service-area map: {path}")
            if show_result:
                messagebox.showinfo("Map reloaded", f"Reloaded service-area map:\n{path}", parent=self)
            return True
        except Exception as exc:  # pragma: no cover - Tk/map failures are surfaced to user
            if show_result:
                messagebox.showerror("Could not reload map", str(exc), parent=self)
            return False

    def import_existing_service_area_map(self) -> None:
        current = self._last_saved_map_path()
        initial_dir = current.parent if current and current.parent.exists() else ROOT
        selected = filedialog.askopenfilename(
            parent=self,
            title="Import existing MARK service-area GeoJSON map",
            initialdir=str(initial_dir),
            filetypes=(("GeoJSON maps", "*.geojson *.json"), ("All files", "*.*")),
        )
        if not selected:
            return
        path = Path(selected).expanduser()
        try:
            self.vars["CHP_ALERT_SERVICE_AREA_FILE"].set(str(path))
            self.map_path = path
            self.reload_map(prompt=False)
            self._refresh_region_summary()
            self.append_log(f"Imported service-area map: {path}")
        except Exception as exc:  # pragma: no cover - Tk/map failures are surfaced to user
            messagebox.showerror("Could not import map", str(exc), parent=self)
            return
        self.save_region_map()


def main() -> int:
    try:
        ReloadingRegionMarkApp().mainloop()
        return 0
    except Exception:
        mark_gui_entry.report_startup_failure()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
