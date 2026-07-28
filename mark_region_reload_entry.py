#!/usr/bin/env python3
"""MARK Region GUI with explicit service-area map loading controls.

This layer sits above the region-aware GUI and fixes three usability problems:
configuration controls can outgrow the middle pane, previously used maps need an
obvious load path, and loaded maps must visibly replace the displayed map. It
keeps the last saved map behavior while adding a scrollbar, a recent-map picker,
a displayed-map status line, and one primary file-picker action: Load Map.
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
    """Add scrollable config, one map-load path, and last-map reopening."""

    def __init__(self) -> None:
        self.saved_map_choices: dict[str, Path] = {}
        self.saved_map_combo: ttk.Combobox | None = None
        self.displayed_map_status_text: tk.StringVar | None = None
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

    def _build_map(self, frame: ttk.Frame) -> None:
        """Build the inherited map editor and add a visible displayed-map status."""
        super()._build_map(frame)

        status_bar = ttk.Frame(frame, style="Panel.TFrame")
        self.displayed_map_status_text = tk.StringVar(value="Displayed map: not loaded yet")
        ttk.Label(
            status_bar,
            textvariable=self.displayed_map_status_text,
            style="PanelHead.TLabel",
            wraplength=650,
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(status_bar, text="Refit Map View", command=self.refit_displayed_map).pack(side="right", padx=(8, 0))

        children = frame.pack_slaves()
        before = children[1] if len(children) >= 2 else None
        if before is not None:
            status_bar.pack(fill="x", pady=(6, 0), before=before)
        else:
            status_bar.pack(fill="x", pady=(6, 0))

    def load_configuration(self) -> None:
        super().load_configuration()
        self._refresh_saved_map_options()
        self.after(0, self.reload_last_saved_service_area_map)

    def _insert_region_map_panel(self, frame: ttk.Frame) -> None:
        super()._insert_region_map_panel(frame)
        panel = self._find_region_panel(frame)
        if panel is None:
            return
        self._retitle_inherited_map_buttons(panel)

        saved_box = ttk.LabelFrame(panel, text="Recent Service-Area Maps", padding=8)
        children = panel.pack_slaves()
        # Keep this control near the top, directly after the center selector.
        before = children[2] if len(children) >= 3 else None
        if before is not None:
            saved_box.pack(fill="x", pady=(9, 0), before=before)
        else:
            saved_box.pack(fill="x", pady=(9, 0))

        ttk.Label(
            saved_box,
            text=(
                "Use Load Map to choose a GeoJSON service-area file. "
                "MARK remembers recent maps here and reloads the last saved map on startup."
            ),
            wraplength=390,
        ).pack(anchor="w", fill="x")

        row_pick = ttk.Frame(saved_box)
        row_pick.pack(fill="x", pady=(7, 0))
        ttk.Label(row_pick, text="Recent map").pack(side="left")
        self.saved_map_combo = ttk.Combobox(
            row_pick,
            textvariable=self.vars["MARK_SAVED_MAP_DISPLAY"],
            values=(),
            state="readonly",
        )
        self.saved_map_combo.pack(side="left", fill="x", expand=True, padx=(8, 0))

        row_buttons = ttk.Frame(saved_box)
        row_buttons.pack(fill="x", pady=(7, 0))
        ttk.Button(row_buttons, text="Load Map", command=self.load_service_area_map_from_file).pack(side="left")
        ttk.Button(row_buttons, text="Refresh Recent List", command=self._refresh_saved_map_options).pack(side="left", padx=(6, 0))

        self._refresh_saved_map_options()

    def _retitle_inherited_map_buttons(self, parent: tk.Widget) -> None:
        """Make inherited file-picker buttons use the same Load Map action."""
        for child in parent.winfo_children():
            try:
                if isinstance(child, ttk.Button) and str(child.cget("text")) == "Browse":
                    child.configure(text="Load Map", command=self.load_service_area_map_from_file)
            except tk.TclError:
                pass
            self._retitle_inherited_map_buttons(child)

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

    def _set_displayed_map_status(self, path: Path, vertices: int, action: str) -> None:
        label = self._map_display_label(path)
        text = f"Displayed map: {label} • {vertices} vertices • {action}"
        if self.displayed_map_status_text is not None:
            self.displayed_map_status_text.set(text)

    def _reset_map_editing_state_for_new_map(self) -> None:
        if hasattr(self, "direct_line_start_index"):
            self.direct_line_start_index = None
        if hasattr(self, "_refresh_direct_line_status"):
            self._refresh_direct_line_status()
        if hasattr(self, "selected_vertex_index"):
            self.selected_vertex_index = None
        if hasattr(self, "cancel_extension"):
            self.cancel_extension()
        if hasattr(self, "anchor_status"):
            self.anchor_status.configure(text="Anchor: none")

    def _display_service_area_map_path(
        self,
        path: Path,
        action: str,
        *,
        show_result: bool = False,
        remember: bool = True,
    ) -> bool:
        """Load a GeoJSON file directly into the map widget and refit the display."""
        normalized = self._normalize_path(path)
        if not normalized.exists():
            message = f"The selected service-area map does not exist:\n{normalized}"
            if show_result:
                messagebox.showwarning("Map not found", message, parent=self)
            else:
                self.append_log(f"Map not found: {normalized}")
            return False

        try:
            payload, points = mark_app.load_polygon(normalized)
            self.vars["CHP_ALERT_SERVICE_AREA_FILE"].set(str(normalized))
            self.map_path = normalized
            self.map_payload = payload
            self.map_points = points
            self._reset_map_editing_state_for_new_map()
            self._draw_polygon(True)
            self.update_idletasks()

            if remember:
                self._remember_service_area_map(normalized)
            self._refresh_saved_map_options()
            self._refresh_region_summary()
            self._set_displayed_map_status(normalized, len(points), action)
            self.append_log(f"{action}: {normalized} ({len(points)} vertices displayed)")
        except Exception as exc:  # pragma: no cover - Tk/map failures are surfaced to user
            messagebox.showerror("Could not display map", str(exc), parent=self)
            return False

        if show_result:
            messagebox.showinfo(
                "Map displayed",
                f"{action}:\n{normalized}\n\nDisplayed {len(points)} vertices and refit the map view.",
                parent=self,
            )
        return True

    def reload_map(self, prompt: bool = True) -> None:
        """Reload the active service-area file and visibly redraw the map pane."""
        path = self._last_saved_map_path()
        if path is None:
            path = self._normalize_path(Path(str(getattr(self, "map_path", mark_app.DEFAULT_MAP))))
        loaded = self._display_service_area_map_path(path, "Reloaded active service-area map", remember=True)
        if loaded and prompt and self.process and self.process.poll() is None:
            messagebox.showinfo("Restart required", "Restart the monitor to apply the map.", parent=self)

    def refit_displayed_map(self) -> None:
        if not getattr(self, "map_points", None):
            messagebox.showinfo("No map displayed", "Load a service-area map first.", parent=self)
            return
        try:
            self._draw_polygon(True)
            self.update_idletasks()
            self._set_displayed_map_status(self.map_path, len(self.map_points), "refit map view")
            self.append_log(f"Refit displayed map view: {self.map_path}")
        except Exception as exc:
            messagebox.showerror("Could not refit map", str(exc), parent=self)

    def _load_service_area_map_path(self, path: Path, action: str) -> bool:
        if not self._display_service_area_map_path(path, action, show_result=True, remember=True):
            return False
        self.save_region_map()
        return True

    def load_selected_saved_map(self) -> None:
        """Compatibility fallback; user-facing loading now uses Load Map."""
        messagebox.showinfo(
            "Use Load Map",
            "Use Load Map to choose the service-area GeoJSON file directly.",
            parent=self,
        )

    def reload_last_saved_service_area_map(self, show_result: bool = False) -> bool:
        path = self._last_saved_map_path()
        if path is None:
            if show_result:
                messagebox.showinfo(
                    "No saved map",
                    "No service-area map is saved yet. Use Load Map, Load Center Test Map, or Build Address Box Map.",
                    parent=self,
                )
            return False
        return self._display_service_area_map_path(
            path,
            "Reloaded last saved service-area map",
            show_result=show_result,
            remember=True,
        )

    def load_service_area_map_from_file(self) -> None:
        current = self._last_saved_map_path()
        initial_dir = current.parent if current and current.parent.exists() else ROOT
        selected = filedialog.askopenfilename(
            parent=self,
            title="Load MARK service-area GeoJSON map",
            initialdir=str(initial_dir),
            filetypes=(("GeoJSON maps", "*.geojson *.json"), ("All files", "*.*")),
        )
        if not selected:
            return
        self._load_service_area_map_path(Path(selected).expanduser(), "Loaded service-area map")

    def import_existing_service_area_map(self) -> None:
        """Compatibility alias for older callbacks; use Load Map wording in the GUI."""
        self.load_service_area_map_from_file()

    def browse_service_area_map(self) -> None:
        """Use the same working file-picker path for every map file control."""
        self.load_service_area_map_from_file()

    def save_map(self, save_as: bool = False) -> None:
        super().save_map(save_as=save_as)
        self._remember_service_area_map(self.map_path)
        self._refresh_saved_map_options()
        if getattr(self, "map_path", None) and getattr(self, "map_points", None):
            self._set_displayed_map_status(self.map_path, len(self.map_points), "saved map")

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
            self._display_service_area_map_path(after, "Displayed generated center smoke-test map", remember=True)

    def build_address_box_map(self) -> None:
        before = str(self._last_saved_map_path() or "")
        super().build_address_box_map()
        after = self._last_saved_map_path()
        if after is not None and str(after) != before:
            self._display_service_area_map_path(after, "Displayed generated address-box map", remember=True)


def main() -> int:
    try:
        ReloadingRegionMarkApp().mainloop()
        return 0
    except Exception:
        mark_gui_entry.report_startup_failure()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
