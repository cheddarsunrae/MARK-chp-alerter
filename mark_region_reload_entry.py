#!/usr/bin/env python3
"""MARK Region GUI with explicit service-area map import/reload controls.

This layer sits above the region-aware GUI and fixes two usability problems:
configuration controls can outgrow the middle pane, and previously used maps need
an obvious load path. It keeps the last saved map behavior while adding a
scrollbar and a saved/recent map picker.
"""
from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import mark_app
import mark_gui_entry
from mark_region_entry import ROOT, RegionMarkApp

RECENT_MAPS_FILE = ROOT / "runtime" / "recent_service_area_maps.json"
MAP_SEARCH_DIRS = (
    ROOT,
    ROOT / "test_maps",
    ROOT / "profiles" / "maps",
    ROOT / "runtime" / "test_maps",
    ROOT / "runtime" / "address_maps",
)


class ReloadingRegionMarkApp(RegionMarkApp):
    """Add scrollable config, map import/reload UX, and last-map reopening."""

    def __init__(self) -> None:
        self.saved_map_choices: dict[str, Path] = {}
        self.saved_map_combo: ttk.Combobox | None = None
        super().__init__()

    def _ensure_region_vars(self) -> None:
        super()._ensure_region_vars()
        self.vars.setdefault("MARK_SAVED_MAP_DISPLAY", tk.StringVar(value=""))

    def _build_config(self, frame: ttk.Frame) -> None:
        """Build the full inherited config panel inside a scrollable viewport."""
        outer = ttk.Frame(frame, style="Panel.TFrame")
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(
            outer,
            bg=mark_app.COLORS["panel"],
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas, style="Panel.TFrame")
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def refresh_scroll_region(_event: tk.Event | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_content_width(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        def on_mousewheel(event: tk.Event) -> None:
            if getattr(event, "delta", 0):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def on_linux_scroll_up(_event: tk.Event) -> None:
            canvas.yview_scroll(-1, "units")

        def on_linux_scroll_down(_event: tk.Event) -> None:
            canvas.yview_scroll(1, "units")

        def bind_mousewheel(_event: tk.Event) -> None:
            canvas.bind_all("<MouseWheel>", on_mousewheel)
            canvas.bind_all("<Button-4>", on_linux_scroll_up)
            canvas.bind_all("<Button-5>", on_linux_scroll_down)

        def unbind_mousewheel(_event: tk.Event) -> None:
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        content.bind("<Configure>", refresh_scroll_region)
        canvas.bind("<Configure>", fit_content_width)
        canvas.bind("<Enter>", bind_mousewheel)
        canvas.bind("<Leave>", unbind_mousewheel)

        super()._build_config(content)
        refresh_scroll_region()

    def load_configuration(self) -> None:
        super().load_configuration()
        self._refresh_saved_map_options()
        self.after(0, self.reload_last_saved_service_area_map)

    def _insert_region_map_panel(self, frame: ttk.Frame) -> None:
        super()._insert_region_map_panel(frame)
        panel = self._find_region_panel(frame)
        if panel is None:
            return

        saved_box = ttk.LabelFrame(panel, text="Saved / Recent Service-Area Maps", padding=8)
        children = panel.pack_slaves()
        # Keep this control near the top, directly after the center selector.
        before = children[2] if len(children) >= 3 else None
        if before is not None:
            saved_box.pack(fill="x", pady=(9, 0), before=before)
        else:
            saved_box.pack(fill="x", pady=(9, 0))

        ttk.Label(
            saved_box,
            text="The last saved map is loaded automatically on startup. Use this list to reopen imported, generated, profile, and smoke-test maps.",
            wraplength=390,
        ).pack(anchor="w", fill="x")

        row_pick = ttk.Frame(saved_box)
        row_pick.pack(fill="x", pady=(7, 0))
        ttk.Label(row_pick, text="Saved map").pack(side="left")
        self.saved_map_combo = ttk.Combobox(
            row_pick,
            textvariable=self.vars["MARK_SAVED_MAP_DISPLAY"],
            values=(),
            state="readonly",
        )
        self.saved_map_combo.pack(side="left", fill="x", expand=True, padx=(8, 0))

        row_buttons = ttk.Frame(saved_box)
        row_buttons.pack(fill="x", pady=(7, 0))
        ttk.Button(row_buttons, text="Load Selected Map", command=self.load_selected_saved_map).pack(side="left")
        ttk.Button(row_buttons, text="Import Existing Map", command=self.import_existing_service_area_map).pack(side="left", padx=(6, 0))
        ttk.Button(row_buttons, text="Reload Last Used", command=lambda: self.reload_last_saved_service_area_map(show_result=True)).pack(side="left", padx=(6, 0))
        ttk.Button(row_buttons, text="Refresh List", command=self._refresh_saved_map_options).pack(side="left", padx=(6, 0))

        self._refresh_saved_map_options()

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

    def _normalize_path(self, path: Path) -> Path:
        expanded = path.expanduser()
        if not expanded.is_absolute():
            expanded = ROOT / expanded
        try:
            return expanded.resolve(strict=False)
        except OSError:
            return expanded

    def _last_saved_map_path(self) -> Path | None:
        raw = ""
        var = self.vars.get("CHP_ALERT_SERVICE_AREA_FILE")
        if var is not None:
            raw = var.get().strip()
        if not raw and mark_app.ENV_FILE.exists():
            raw = mark_app.parse_env(mark_app.ENV_FILE).get("CHP_ALERT_SERVICE_AREA_FILE", "").strip()
        if not raw:
            return None
        return self._normalize_path(Path(raw))

    def _read_recent_maps(self) -> list[Path]:
        try:
            payload = json.loads(RECENT_MAPS_FILE.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return []
        raw_values = payload.get("maps", payload) if isinstance(payload, dict) else payload
        if not isinstance(raw_values, list):
            return []
        paths: list[Path] = []
        for value in raw_values:
            if isinstance(value, str) and value.strip():
                paths.append(self._normalize_path(Path(value.strip())))
        return paths

    def _write_recent_maps(self, paths: list[Path]) -> None:
        RECENT_MAPS_FILE.parent.mkdir(parents=True, exist_ok=True)
        RECENT_MAPS_FILE.write_text(
            json.dumps({"maps": [str(path) for path in paths[:25]]}, indent=2) + "\n",
            encoding="utf-8",
        )

    def _remember_service_area_map(self, path: Path | None = None) -> None:
        selected = path or self._last_saved_map_path()
        if selected is None:
            return
        selected = self._normalize_path(selected)
        if not selected.exists() or not selected.is_file():
            return
        existing = [self._normalize_path(item) for item in self._read_recent_maps()]
        selected_text = str(selected).casefold()
        revised = [selected]
        revised.extend(item for item in existing if str(item).casefold() != selected_text)
        try:
            self._write_recent_maps(revised)
        except OSError as exc:
            self.append_log(f"Could not update recent map list: {exc}")

    def _discover_service_area_maps(self) -> list[Path]:
        candidates: list[Path] = []
        current = self._last_saved_map_path()
        if current is not None:
            candidates.append(current)
        candidates.extend(self._read_recent_maps())
        for folder in MAP_SEARCH_DIRS:
            if folder.exists():
                candidates.extend(sorted(folder.glob("*.geojson")))
        seen: set[str] = set()
        maps: list[Path] = []
        for candidate in candidates:
            path = self._normalize_path(candidate)
            key = str(path).casefold()
            if key in seen or not path.exists() or not path.is_file():
                continue
            seen.add(key)
            maps.append(path)
        return maps

    def _map_display_label(self, path: Path) -> str:
        normalized = self._normalize_path(path)
        try:
            relative = normalized.relative_to(ROOT)
            return str(relative).replace("\\", "/")
        except ValueError:
            return f"{normalized.name} — {normalized.parent}"

    def _refresh_saved_map_options(self) -> None:
        paths = self._discover_service_area_maps()
        choices: dict[str, Path] = {}
        labels: list[str] = []
        for path in paths:
            label = self._map_display_label(path)
            if label in choices:
                label = f"{label} — {path.parent}"
            choices[label] = path
            labels.append(label)
        self.saved_map_choices = choices
        if self.saved_map_combo is not None:
            self.saved_map_combo.configure(values=labels)
        current = self._last_saved_map_path()
        if current is not None:
            current_key = str(self._normalize_path(current)).casefold()
            for label, path in choices.items():
                if str(self._normalize_path(path)).casefold() == current_key:
                    self.vars["MARK_SAVED_MAP_DISPLAY"].set(label)
                    break
        elif labels:
            self.vars["MARK_SAVED_MAP_DISPLAY"].set(labels[0])

    def _load_service_area_map_path(self, path: Path, action: str) -> bool:
        normalized = self._normalize_path(path)
        if not normalized.exists():
            messagebox.showwarning(
                "Map not found",
                f"The selected service-area map does not exist:\n{normalized}",
                parent=self,
            )
            return False
        try:
            self.vars["CHP_ALERT_SERVICE_AREA_FILE"].set(str(normalized))
            self.map_path = normalized
            self.reload_map(prompt=False)
            self._remember_service_area_map(normalized)
            self._refresh_saved_map_options()
            self._refresh_region_summary()
            self.append_log(f"{action}: {normalized}")
        except Exception as exc:  # pragma: no cover - Tk/map failures are surfaced to user
            messagebox.showerror("Could not load map", str(exc), parent=self)
            return False
        self.save_region_map()
        return True

    def load_selected_saved_map(self) -> None:
        self._refresh_saved_map_options()
        label = self.vars["MARK_SAVED_MAP_DISPLAY"].get().strip()
        path = self.saved_map_choices.get(label)
        if path is None:
            messagebox.showinfo(
                "No saved map selected",
                "Choose a saved/recent service-area map first, or click Import Existing Map.",
                parent=self,
            )
            return
        self._load_service_area_map_path(path, "Loaded saved service-area map")

    def reload_last_saved_service_area_map(self, show_result: bool = False) -> bool:
        path = self._last_saved_map_path()
        if path is None:
            if show_result:
                messagebox.showinfo(
                    "No saved map",
                    "No service-area map is saved yet. Use Import Existing Map, Load Center Test Map, or Build Address Box Map.",
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
            self._remember_service_area_map(path)
            self._refresh_saved_map_options()
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
        self._load_service_area_map_path(Path(selected).expanduser(), "Imported service-area map")

    def browse_service_area_map(self) -> None:
        before = str(self._last_saved_map_path() or "")
        super().browse_service_area_map()
        after = self._last_saved_map_path()
        if after is None or str(after) == before:
            return
        self._remember_service_area_map(after)
        self._refresh_saved_map_options()
        self.save_region_map()

    def save_map(self, save_as: bool = False) -> None:
        super().save_map(save_as=save_as)
        self._remember_service_area_map(self.map_path)
        self._refresh_saved_map_options()

    def save_configuration(self, quiet: bool = False) -> bool:
        ok = super().save_configuration(quiet=quiet)
        if ok:
            self._remember_service_area_map(self._last_saved_map_path())
            self._refresh_saved_map_options()
        return ok

    def load_center_smoke_test_map(self) -> None:
        before = str(self._last_saved_map_path() or "")
        super().load_center_smoke_test_map()
        after = self._last_saved_map_path()
        if after is not None and str(after) != before:
            self._remember_service_area_map(after)
            self._refresh_saved_map_options()

    def build_address_box_map(self) -> None:
        before = str(self._last_saved_map_path() or "")
        super().build_address_box_map()
        after = self._last_saved_map_path()
        if after is not None and str(after) != before:
            self._remember_service_area_map(after)
            self._refresh_saved_map_options()



def main() -> int:
    try:
        ReloadingRegionMarkApp().mainloop()
        return 0
    except Exception:
        mark_gui_entry.report_startup_failure()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
