#!/usr/bin/env python3
"""MARK desktop launcher and advanced service-area editor."""
from __future__ import annotations

import math
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import mark_app
from mark_app import COLORS, DEFAULT_MAP, MarkApp, load_polygon

ROOT = Path(__file__).resolve().parent
mark_app.BACKEND = ROOT / "mark_backend.py"
MIN_POLL_INTERVAL = 30.0


class BrandedMarkApp(MarkApp):
    """MARK dashboard with branded header and anchored polygon editing."""

    def _defaults(self) -> dict[str, str]:
        values = super()._defaults()
        values["CHP_ALERT_INTERVAL"] = "30"
        return values

    def collect_configuration(self) -> dict[str, str]:
        values = {key: var.get().strip() for key, var in self.vars.items()}
        if not values["PUSHOVER_APP_TOKEN"] or not values["PUSHOVER_USER_KEY"]:
            raise ValueError("Enter both Pushover credentials")
        if float(values["CHP_ALERT_INTERVAL"]) < MIN_POLL_INTERVAL:
            raise ValueError("Poll interval must be at least 30 seconds")
        if int(values["PUSHOVER_PRIORITY"]) == 2 and int(values["PUSHOVER_RETRY_SECONDS"]) < 30:
            raise ValueError("Priority 2 retry must be at least 30 seconds")
        for key in ("CHP_ALERT_STATE_FILE", "CHP_ALERT_DETAIL_LOG_FILE"):
            Path(values[key]).expanduser().parent.mkdir(parents=True, exist_ok=True)
        return values

    def _build_header(self, root: ttk.Frame) -> None:
        header = ttk.Frame(root)
        header.pack(fill="x")
        brand = ttk.Frame(header)
        brand.pack(side="left", fill="x", expand=True)
        self._load_logo(brand)
        words = ttk.Frame(brand)
        words.pack(side="left", anchor="center")
        ttk.Label(words, text="MARK", style="Title.TLabel").pack(anchor="w")
        ttk.Label(words, text="Map-Aware Roadway Knowledge", style="Subtitle.TLabel").pack(anchor="w")
        ttk.Label(words, text="Real-time CHP incident monitoring and map-aware notifications.", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        cards = ttk.Frame(header)
        cards.pack(side="right")
        self.status_card_value = self._card(cards, "STATUS", self.status)
        self._card(cards, "LAST POLL", self.last_poll)
        self._card(cards, "LATEST SUMMARY", self.latest_summary, width=28)

    def _build_map(self, frame: ttk.Frame) -> None:
        self.map_edit_enabled = tk.BooleanVar(value=False)
        self.map_insert_mode = tk.StringVar(value="After selected anchor")
        self.selected_vertex_index: int | None = None
        self._map_press_xy: tuple[int, int] | None = None
        self._dragging_vertex = False

        head = ttk.Frame(frame, style="Panel.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="▣  Map Editor", style="PanelHead.TLabel").pack(side="left")
        ttk.Button(head, text="Reset", command=self.reload_map).pack(side="right", padx=3)
        ttk.Button(head, text="Save As", command=lambda: self.save_map(save_as=True)).pack(side="right", padx=3)
        ttk.Button(head, text="Save Map", command=self.save_map).pack(side="right", padx=3)

        if mark_app.tkintermapview:
            self.map_widget = mark_app.tkintermapview.TkinterMapView(frame, corner_radius=0)
            self.map_widget.pack(fill="both", expand=True, pady=(8, 6))
            self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png", max_zoom=19)
            canvas = self.map_widget.canvas
            canvas.bind("<ButtonPress-1>", self._editor_press, add="+")
            canvas.bind("<B1-Motion>", self._editor_drag, add="+")
            canvas.bind("<ButtonRelease-1>", self._editor_release, add="+")
            notice = "Editing is off by default. Enable it, select an anchor vertex, then click or drag."
        else:
            self.map_widget = tk.Canvas(frame, bg="#d9d3c7", highlightthickness=0)
            self.map_widget.pack(fill="both", expand=True, pady=(8, 6))
            self.map_widget.create_text(20, 20, anchor="nw", text="Install tkintermapview for the road basemap", fill="#111827", font=("Segoe UI", 13, "bold"))
            notice = "Basemap unavailable; install tkintermapview to edit visually."

        ttk.Label(frame, text=notice, style="PanelHead.TLabel").pack(anchor="w")
        controls = ttk.Frame(frame, style="Panel.TFrame")
        controls.pack(fill="x", pady=(5, 0))
        ttk.Checkbutton(controls, text="Enable service-area editing", variable=self.map_edit_enabled, command=self._edit_mode_changed).pack(side="left")
        ttk.Combobox(controls, textvariable=self.map_insert_mode, values=("After selected anchor", "On nearest edge", "Move selected vertex"), state="readonly", width=22).pack(side="left", padx=8)
        ttk.Button(controls, text="Delete Selected", command=self.delete_selected_vertex).pack(side="left", padx=3)
        ttk.Button(controls, text="Clear Selection", command=self.clear_vertex_selection).pack(side="left", padx=3)
        self.map_anchor_status = ttk.Label(controls, text="Anchor: none", style="PanelHead.TLabel")
        self.map_anchor_status.pack(side="right", padx=(8, 0))
        self.map_stats = ttk.Label(controls, text="0 vertices", style="PanelHead.TLabel")
        self.map_stats.pack(side="right")

    @staticmethod
    def _is_map_control_click(x: int, y: int) -> bool:
        return x <= 58 and y <= 112

    def _edit_mode_changed(self) -> None:
        state = "enabled" if self.map_edit_enabled.get() else "disabled"
        self.append_log(f"Map editing {state}")
        if not self.map_edit_enabled.get():
            self._dragging_vertex = False

    def _nearest_vertex(self, x: int, y: int, radius: float = 28.0) -> int | None:
        if not mark_app.tkintermapview:
            return None
        best_index = None
        best_distance = radius
        for index, marker in enumerate(self.map_markers):
            try:
                marker_x, marker_y = marker.get_canvas_pos(marker.position)
            except Exception:
                continue
            distance = math.hypot(marker_x - x, marker_y - y)
            if distance <= best_distance:
                best_index = index
                best_distance = distance
        return best_index

    def _select_vertex(self, index: int) -> None:
        if not 0 <= index < len(self.map_points):
            return
        self.selected_vertex_index = index
        lat, lon = self.map_points[index]
        self.map_anchor_status.configure(text=f"Anchor: {index + 1} ({lat:.5f}, {lon:.5f})")
        self._draw_polygon(refit=False)

    def clear_vertex_selection(self) -> None:
        self.selected_vertex_index = None
        self.map_anchor_status.configure(text="Anchor: none")
        self._draw_polygon(refit=False)

    def delete_selected_vertex(self) -> None:
        index = self.selected_vertex_index
        if index is None:
            messagebox.showinfo("No vertex selected", "Click a numbered vertex first.", parent=self)
            return
        if len(self.map_points) <= 3:
            messagebox.showerror("Cannot delete", "A service area must retain at least three vertices.", parent=self)
            return
        self.map_points.pop(index)
        self.selected_vertex_index = min(index, len(self.map_points) - 1)
        self._select_vertex(self.selected_vertex_index)

    def _editor_press(self, event: tk.Event) -> None:
        self._map_press_xy = (event.x, event.y)
        self._dragging_vertex = False
        if not self.map_edit_enabled.get() or self._is_map_control_click(event.x, event.y):
            return
        nearest = self._nearest_vertex(event.x, event.y)
        if nearest is not None:
            self._select_vertex(nearest)
            self._dragging_vertex = True

    def _editor_drag(self, event: tk.Event) -> None:
        if not self.map_edit_enabled.get() or not self._dragging_vertex:
            return
        if self.selected_vertex_index is None or self._is_map_control_click(event.x, event.y):
            return
        try:
            lat, lon = self.map_widget.convert_canvas_coords_to_decimal_coords(event.x, event.y)
        except Exception:
            return
        self.map_points[self.selected_vertex_index] = (float(lat), float(lon))
        self._draw_polygon(refit=False)

    def _editor_release(self, event: tk.Event) -> None:
        press = self._map_press_xy
        was_dragging = self._dragging_vertex
        self._map_press_xy = None
        self._dragging_vertex = False
        if not self.map_edit_enabled.get() or self._is_map_control_click(event.x, event.y) or press is None:
            return
        moved = math.hypot(event.x - press[0], event.y - press[1])
        if was_dragging or moved > 5 or self._nearest_vertex(event.x, event.y) is not None:
            return
        try:
            lat, lon = self.map_widget.convert_canvas_coords_to_decimal_coords(event.x, event.y)
        except Exception:
            return
        point = (float(lat), float(lon))
        mode = self.map_insert_mode.get()
        if mode == "Move selected vertex":
            if self.selected_vertex_index is None:
                messagebox.showinfo("Select a vertex", "Choose an anchor vertex before moving it.", parent=self)
                return
            self.map_points[self.selected_vertex_index] = point
            self._draw_polygon(refit=False)
            return
        insert_at = self.selected_vertex_index + 1 if mode == "After selected anchor" and self.selected_vertex_index is not None else self._nearest_edge_insert_index(point)
        self.map_points.insert(insert_at, point)
        self.selected_vertex_index = insert_at
        self._select_vertex(insert_at)

    def _nearest_edge_insert_index(self, point: tuple[float, float]) -> int:
        if len(self.map_points) < 2:
            return len(self.map_points)
        latitude_scale = math.cos(math.radians(point[0]))

        def distance_to_segment(a: tuple[float, float], b: tuple[float, float]) -> float:
            px, py = point[1] * latitude_scale, point[0]
            ax, ay = a[1] * latitude_scale, a[0]
            bx, by = b[1] * latitude_scale, b[0]
            dx, dy = bx - ax, by - ay
            if dx == 0 and dy == 0:
                return math.hypot(px - ax, py - ay)
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
            return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

        edge = min(range(len(self.map_points)), key=lambda index: distance_to_segment(self.map_points[index], self.map_points[(index + 1) % len(self.map_points)]))
        return edge + 1

    def reload_map(self, prompt: bool = True) -> None:
        try:
            variable = self.vars.get("CHP_ALERT_SERVICE_AREA_FILE")
            path = Path(variable.get() if variable else str(self.map_path or DEFAULT_MAP)).expanduser()
            self.map_payload, self.map_points = load_polygon(path)
            self.map_path = path
            self.selected_vertex_index = None
            if hasattr(self, "map_anchor_status"):
                self.map_anchor_status.configure(text="Anchor: none")
            self._draw_polygon(refit=True)
            self.append_log(f"Loaded map {path} ({len(self.map_points)} vertices)")
            if prompt and self.process and self.process.poll() is None:
                messagebox.showinfo("Restart required", "Map reloaded. Restart the monitor to apply it.", parent=self)
        except Exception as exc:
            messagebox.showerror("Map error", str(exc), parent=self)

    def _draw_polygon(self, refit: bool = False) -> None:
        if hasattr(self, "map_stats"):
            self.map_stats.configure(text=f"{len(self.map_points)} vertices")
        if not mark_app.tkintermapview or not hasattr(self, "map_widget"):
            return
        try:
            if self.map_polygon:
                self.map_polygon.delete()
            for marker in self.map_markers:
                marker.delete()
        except Exception:
            pass
        self.map_polygon = None
        self.map_markers = []
        if len(self.map_points) >= 3:
            self.map_polygon = self.map_widget.set_polygon(self.map_points, fill_color="#d99b20", outline_color="#ffc43d", border_width=3)
        for index, point in enumerate(self.map_points):
            selected = index == self.selected_vertex_index
            marker = self.map_widget.set_marker(*point, text=str(index + 1), marker_color_circle="#e4483f" if selected else "#ffc43d", marker_color_outside="#ffffff" if selected else "#13243a", command=lambda _marker, selected_index=index: self._select_vertex(selected_index))
            self.map_markers.append(marker)
        if refit and self.map_points:
            north = max(point[0] for point in self.map_points)
            south = min(point[0] for point in self.map_points)
            west = min(point[1] for point in self.map_points)
            east = max(point[1] for point in self.map_points)
            if north > south and east > west:
                self.map_widget.fit_bounding_box((north, west), (south, east))


def main() -> int:
    BrandedMarkApp().mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
