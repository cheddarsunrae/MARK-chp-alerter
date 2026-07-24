#!/usr/bin/env python3
"""Simple cross-platform polygon editor for CHP Alerter GeoJSON files."""

from __future__ import annotations

import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from service_area_runtime import ServiceAreaError, load_service_area

ROOT = Path(__file__).resolve().parent
DEFAULT_MAP = ROOT / "service_area.geojson"
STATION = (32.711277, -116.865630)
DULZURA = (32.6442247, -116.7814093)
OTAY_EDGE = (32.647464, -116.931540)


class MapEditor(tk.Tk):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.title("CHP Alerter — Service Area Editor")
        self.geometry("1050x760")
        self.minsize(820, 600)
        self.path = path
        self.payload: dict[str, Any] = {}
        self.vertices: list[tuple[float, float]] = []
        self.selected: int | None = None
        self.dragging = False
        self.margin = 45
        self.bounds = (32.60, 32.85, -116.98, -116.68)
        self.status = tk.StringVar(value="")
        self._build()
        self.load_file(path)

    def _build(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Button(top, text="Open GeoJSON…", command=self.open_file).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Reload", command=lambda: self.load_file(self.path)).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Save", command=self.save).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Save As…", command=self.save_as).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Add Vertex", command=self.add_vertex).pack(side="left", padx=(14, 6))
        ttk.Button(top, text="Delete Selected", command=self.delete_selected).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Reset View", command=self.fit_bounds).pack(side="left")

        help_text = (
            "Drag red vertices to edit. Double-click adds a vertex on the nearest polygon edge. "
            "Right-click a vertex to delete it. GeoJSON uses longitude, latitude; this editor validates before saving."
        )
        ttk.Label(self, text=help_text, padding=(12, 0, 12, 8), wraplength=980).pack(fill="x")

        self.canvas = tk.Canvas(self, background="#eef2f3", highlightthickness=1, highlightbackground="#87939a")
        self.canvas.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.canvas.bind("<Configure>", lambda _event: self.draw())
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_right_click)

        footer = ttk.Frame(self, padding=(10, 0, 10, 10))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status).pack(side="left")
        ttk.Label(footer, text="Operational geometry only — verify critical boundaries independently.").pack(side="right")

    def open_file(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self,
            title="Open service-area GeoJSON",
            initialdir=self.path.parent,
            filetypes=[("GeoJSON", "*.geojson *.json"), ("All files", "*.*")],
        )
        if selected:
            self.load_file(Path(selected))

    def load_file(self, path: Path) -> None:
        try:
            area = load_service_area(path)
        except ServiceAreaError as exc:
            messagebox.showerror("Invalid map", str(exc), parent=self)
            return
        self.path = path.resolve()
        self.payload = area["geojson"]
        self.vertices = list(area["polygon"])
        self.selected = None
        self.fit_bounds()
        self.status.set(f"Loaded {self.path} — {len(self.vertices)} vertices")

    def fit_bounds(self) -> None:
        points = self.vertices + [STATION, DULZURA, OTAY_EDGE]
        if not points:
            return
        lats = [p[0] for p in points]
        lons = [p[1] for p in points]
        lat_pad = max((max(lats) - min(lats)) * 0.12, 0.01)
        lon_pad = max((max(lons) - min(lons)) * 0.12, 0.01)
        self.bounds = (min(lats) - lat_pad, max(lats) + lat_pad, min(lons) - lon_pad, max(lons) + lon_pad)
        self.draw()

    def to_canvas(self, point: tuple[float, float]) -> tuple[float, float]:
        lat_min, lat_max, lon_min, lon_max = self.bounds
        width = max(self.canvas.winfo_width() - 2 * self.margin, 1)
        height = max(self.canvas.winfo_height() - 2 * self.margin, 1)
        lat, lon = point
        x = self.margin + (lon - lon_min) / max(lon_max - lon_min, 1e-9) * width
        y = self.margin + (lat_max - lat) / max(lat_max - lat_min, 1e-9) * height
        return x, y

    def from_canvas(self, x: float, y: float) -> tuple[float, float]:
        lat_min, lat_max, lon_min, lon_max = self.bounds
        width = max(self.canvas.winfo_width() - 2 * self.margin, 1)
        height = max(self.canvas.winfo_height() - 2 * self.margin, 1)
        lon = lon_min + (x - self.margin) / width * (lon_max - lon_min)
        lat = lat_max - (y - self.margin) / height * (lat_max - lat_min)
        return round(lat, 7), round(lon, 7)

    def draw(self) -> None:
        self.canvas.delete("all")
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        for i in range(1, 6):
            x = self.margin + i * (width - 2 * self.margin) / 6
            y = self.margin + i * (height - 2 * self.margin) / 6
            self.canvas.create_line(x, self.margin, x, height - self.margin, fill="#d7dee2")
            self.canvas.create_line(self.margin, y, width - self.margin, y, fill="#d7dee2")

        if len(self.vertices) >= 3:
            coords = [value for point in self.vertices for value in self.to_canvas(point)]
            self.canvas.create_polygon(*coords, fill="#ef9a9a", stipple="gray50", outline="#c62828", width=3)

        for index, point in enumerate(self.vertices):
            x, y = self.to_canvas(point)
            radius = 7 if index == self.selected else 5
            fill = "#ffeb3b" if index == self.selected else "#d32f2f"
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=fill, outline="#7f0000", width=2)
            self.canvas.create_text(x + 9, y - 9, text=str(index + 1), anchor="sw", fill="#5d0000", font=("Segoe UI", 9, "bold"))

        for label, point, colour in (
            ("Station 36", STATION, "#8e0000"),
            ("Dulzura", DULZURA, "#1b5e20"),
            ("Otay edge", OTAY_EDGE, "#0d47a1"),
        ):
            x, y = self.to_canvas(point)
            self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill=colour, outline="white")
            self.canvas.create_text(x + 8, y, text=label, anchor="w", fill=colour, font=("Segoe UI", 10, "bold"))

        lat_min, lat_max, lon_min, lon_max = self.bounds
        self.canvas.create_text(self.margin, 18, anchor="w", text=f"N {lat_max:.5f}°", font=("Consolas", 9))
        self.canvas.create_text(self.margin, height - 18, anchor="w", text=f"S {lat_min:.5f}°", font=("Consolas", 9))
        self.canvas.create_text(width - self.margin, height - 18, anchor="e", text=f"E {lon_max:.5f}°", font=("Consolas", 9))
        self.canvas.create_text(self.margin, height - 18, anchor="w", text=f"W {lon_min:.5f}°", font=("Consolas", 9))

    def nearest_vertex(self, x: float, y: float, radius: float = 14) -> int | None:
        best: tuple[float, int] | None = None
        for index, point in enumerate(self.vertices):
            px, py = self.to_canvas(point)
            distance = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
            if distance <= radius and (best is None or distance < best[0]):
                best = (distance, index)
        return best[1] if best else None

    def nearest_edge(self, x: float, y: float) -> int:
        best = (float("inf"), 0)
        for index in range(len(self.vertices)):
            ax, ay = self.to_canvas(self.vertices[index])
            bx, by = self.to_canvas(self.vertices[(index + 1) % len(self.vertices)])
            dx, dy = bx - ax, by - ay
            if dx == 0 and dy == 0:
                distance = ((x - ax) ** 2 + (y - ay) ** 2) ** 0.5
            else:
                t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
                px, py = ax + t * dx, ay + t * dy
                distance = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
            if distance < best[0]:
                best = (distance, index)
        return best[1]

    def on_press(self, event: tk.Event) -> None:
        self.selected = self.nearest_vertex(event.x, event.y)
        self.dragging = self.selected is not None
        self.draw()

    def on_drag(self, event: tk.Event) -> None:
        if self.dragging and self.selected is not None:
            self.vertices[self.selected] = self.from_canvas(event.x, event.y)
            self.status.set(f"Vertex {self.selected + 1}: lat {self.vertices[self.selected][0]:.7f}, lon {self.vertices[self.selected][1]:.7f}")
            self.draw()

    def on_release(self, _event: tk.Event) -> None:
        self.dragging = False

    def on_double_click(self, event: tk.Event) -> None:
        if len(self.vertices) < 2:
            self.vertices.append(self.from_canvas(event.x, event.y))
        else:
            edge = self.nearest_edge(event.x, event.y)
            self.vertices.insert(edge + 1, self.from_canvas(event.x, event.y))
        self.selected = edge + 1 if len(self.vertices) >= 2 else len(self.vertices) - 1
        self.draw()

    def on_right_click(self, event: tk.Event) -> None:
        index = self.nearest_vertex(event.x, event.y)
        if index is not None:
            self.selected = index
            self.delete_selected()

    def add_vertex(self) -> None:
        lat_min, lat_max, lon_min, lon_max = self.bounds
        self.vertices.append(((lat_min + lat_max) / 2, (lon_min + lon_max) / 2))
        self.selected = len(self.vertices) - 1
        self.draw()

    def delete_selected(self) -> None:
        if self.selected is None:
            return
        if len(self.vertices) <= 3:
            messagebox.showwarning("Cannot delete", "A polygon must retain at least three vertices.", parent=self)
            return
        self.vertices.pop(self.selected)
        self.selected = None
        self.draw()

    def updated_payload(self) -> dict[str, Any]:
        payload = json.loads(json.dumps(self.payload))
        ring = [[lon, lat] for lat, lon in self.vertices]
        ring.append(ring[0])
        features = payload.get("features", []) if payload.get("type") == "FeatureCollection" else [payload]
        for feature in features:
            geometry = feature.get("geometry") if isinstance(feature, dict) else None
            if isinstance(geometry, dict) and geometry.get("type") == "Polygon":
                geometry["coordinates"] = [ring]
                return payload
        raise ServiceAreaError("No Polygon feature was found while saving")

    def save_to(self, path: Path) -> None:
        if len(self.vertices) < 3:
            raise ServiceAreaError("Polygon needs at least three vertices")
        payload = self.updated_payload()
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        load_service_area(temporary)
        temporary.replace(path)
        self.path = path.resolve()
        self.payload = payload
        self.status.set(f"Saved {self.path} — restart or reload the monitor to apply it")

    def save(self) -> None:
        try:
            self.save_to(self.path)
        except (OSError, ServiceAreaError) as exc:
            messagebox.showerror("Could not save map", str(exc), parent=self)

    def save_as(self) -> None:
        selected = filedialog.asksaveasfilename(
            parent=self,
            title="Save service-area GeoJSON",
            initialdir=self.path.parent,
            initialfile=self.path.name,
            defaultextension=".geojson",
            filetypes=[("GeoJSON", "*.geojson"), ("JSON", "*.json")],
        )
        if selected:
            try:
                self.save_to(Path(selected))
            except (OSError, ServiceAreaError) as exc:
                messagebox.showerror("Could not save map", str(exc), parent=self)


def main() -> int:
    path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else DEFAULT_MAP
    app = MapEditor(path)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
