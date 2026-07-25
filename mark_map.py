"""OpenStreetMap-backed polygon editor for MARK."""
from __future__ import annotations

import io
import math
import queue
import threading
import tkinter as tk
from pathlib import Path
from typing import Any, Callable

import requests
from PIL import Image, ImageTk

from mark_common import BORDER, GOLD, MUTED, PANEL, default_tile_dir, load_geojson_polygon, save_geojson_polygon

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE_SIZE = 256
USER_AGENT = "MARK-CHP-Alerter/1.0 (service-area editor)"


def lon_to_world_x(lon: float, zoom: int) -> float:
    return (lon + 180.0) / 360.0 * TILE_SIZE * (2**zoom)


def lat_to_world_y(lat: float, zoom: int) -> float:
    lat = max(-85.05112878, min(85.05112878, lat))
    rad = math.radians(lat)
    return (1.0 - math.asinh(math.tan(rad)) / math.pi) / 2.0 * TILE_SIZE * (2**zoom)


def world_x_to_lon(x: float, zoom: int) -> float:
    return x / (TILE_SIZE * (2**zoom)) * 360.0 - 180.0


def world_y_to_lat(y: float, zoom: int) -> float:
    n = math.pi - 2.0 * math.pi * y / (TILE_SIZE * (2**zoom))
    return math.degrees(math.atan(math.sinh(n)))


def polygon_area_sq_miles(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    ref_lat = math.radians(sum(p[0] for p in points) / len(points))
    xy = [(lon * 69.172 * math.cos(ref_lat), lat * 69.0) for lat, lon in points]
    cross = sum(
        xy[i][0] * xy[(i + 1) % len(xy)][1] - xy[(i + 1) % len(xy)][0] * xy[i][1]
        for i in range(len(xy))
    )
    return abs(cross) / 2


def haversine_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    radius = 3958.7613
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


class RoadMapEditor(tk.Frame):
    """Road basemap plus draggable GeoJSON polygon vertices."""

    def __init__(self, master: tk.Misc, *, on_changed: Callable[[Path], None] | None = None) -> None:
        super().__init__(master, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        self.on_changed = on_changed
        self.canvas = tk.Canvas(self, bg="#d8dde0", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.status = tk.StringVar(value="No map loaded")
        tk.Label(self, textvariable=self.status, bg=PANEL, fg=MUTED, anchor="w", padx=10, pady=5).pack(fill="x")
        self.points: list[tuple[float, float]] = []
        self.payload: dict[str, Any] = {}
        self.path = Path("service_area.geojson")
        self.zoom = 11
        self.center = (32.69, -116.83)
        self._drag_index: int | None = None
        self._pan_start: tuple[int, int] | None = None
        self._tile_images: list[ImageTk.PhotoImage] = []
        self._tile_queue: queue.Queue[tuple[int, int, int, Image.Image | None]] = queue.Queue()
        self._requested: set[tuple[int, int, int]] = set()
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})
        self._tile_dir = default_tile_dir()
        self._tile_dir.mkdir(parents=True, exist_ok=True)
        self.canvas.bind("<Configure>", lambda _e: self.redraw())
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Double-Button-1>", self._add_vertex)
        self.canvas.bind("<Button-3>", self._remove_vertex)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda _e: self.zoom_by(1))
        self.canvas.bind("<Button-5>", lambda _e: self.zoom_by(-1))
        self.after(100, self._drain_tiles)

    def load(self, path: Path) -> None:
        payload, points = load_geojson_polygon(path)
        self.path, self.payload, self.points = path, payload, points
        self.fit_polygon()
        self.redraw()

    def save(self, path: Path | None = None) -> None:
        target = path or self.path
        save_geojson_polygon(target, self.payload, self.points)
        self.path = target
        self.status.set(f"Saved {len(self.points)} vertices • {target}")
        if self.on_changed:
            self.on_changed(target)

    def fit_polygon(self) -> None:
        if not self.points:
            return
        self.center = (
            (min(p[0] for p in self.points) + max(p[0] for p in self.points)) / 2,
            (min(p[1] for p in self.points) + max(p[1] for p in self.points)) / 2,
        )
        width = max(self.canvas.winfo_width(), 700)
        height = max(self.canvas.winfo_height(), 420)
        for zoom in range(16, 5, -1):
            xs = [lon_to_world_x(p[1], zoom) for p in self.points]
            ys = [lat_to_world_y(p[0], zoom) for p in self.points]
            if max(xs) - min(xs) < width * 0.75 and max(ys) - min(ys) < height * 0.75:
                self.zoom = zoom
                break

    def zoom_by(self, delta: int) -> None:
        self.zoom = max(6, min(17, self.zoom + delta))
        self.redraw()

    def _center_world(self) -> tuple[float, float]:
        return lon_to_world_x(self.center[1], self.zoom), lat_to_world_y(self.center[0], self.zoom)

    def geo_to_canvas(self, point: tuple[float, float]) -> tuple[float, float]:
        cx, cy = self._center_world()
        return (
            lon_to_world_x(point[1], self.zoom) - cx + self.canvas.winfo_width() / 2,
            lat_to_world_y(point[0], self.zoom) - cy + self.canvas.winfo_height() / 2,
        )

    def canvas_to_geo(self, x: float, y: float) -> tuple[float, float]:
        cx, cy = self._center_world()
        wx = cx + x - self.canvas.winfo_width() / 2
        wy = cy + y - self.canvas.winfo_height() / 2
        return world_y_to_lat(wy, self.zoom), world_x_to_lon(wx, self.zoom)

    def redraw(self) -> None:
        if self.canvas.winfo_width() < 50 or self.canvas.winfo_height() < 50:
            return
        self.canvas.delete("all")
        self._tile_images.clear()
        self._draw_tiles()
        if not self.points:
            return
        coords = [value for point in self.points for value in self.geo_to_canvas(point)]
        self.canvas.create_polygon(*coords, fill=GOLD, outline=GOLD, width=3, stipple="gray50", tags="polygon")
        for index, point in enumerate(self.points):
            x, y = self.geo_to_canvas(point)
            self.canvas.create_oval(x - 6, y - 6, x + 6, y + 6, fill="#ffffff", outline="#9c6f00", width=2, tags=("vertex", f"v{index}"))
        perimeter = sum(haversine_miles(self.points[i], self.points[(i + 1) % len(self.points)]) for i in range(len(self.points)))
        self.status.set(
            f"{len(self.points)} vertices   Area: {polygon_area_sq_miles(self.points):.1f} sq mi   "
            f"Perimeter: {perimeter:.1f} mi   Drag vertices • Double-click edge to add • Right-click vertex to remove"
        )

    def _draw_tiles(self) -> None:
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        cx, cy = self._center_world()
        left, top = cx - width / 2, cy - height / 2
        x0, y0 = math.floor(left / TILE_SIZE), math.floor(top / TILE_SIZE)
        x1, y1 = math.floor((left + width) / TILE_SIZE), math.floor((top + height) / TILE_SIZE)
        limit = 2**self.zoom
        for ty in range(y0, y1 + 1):
            if not 0 <= ty < limit:
                continue
            for tx_raw in range(x0, x1 + 1):
                tx = tx_raw % limit
                x = tx_raw * TILE_SIZE - left
                y = ty * TILE_SIZE - top
                cached = self._tile_dir / str(self.zoom) / str(tx) / f"{ty}.png"
                if cached.exists():
                    try:
                        image = Image.open(cached).convert("RGB")
                        photo = ImageTk.PhotoImage(image)
                        self._tile_images.append(photo)
                        self.canvas.create_image(x, y, image=photo, anchor="nw")
                        continue
                    except OSError:
                        cached.unlink(missing_ok=True)
                self.canvas.create_rectangle(x, y, x + TILE_SIZE, y + TILE_SIZE, fill="#d9dee1", outline="#c5cbd0")
                key = (self.zoom, tx, ty)
                if key not in self._requested:
                    self._requested.add(key)
                    threading.Thread(target=self._fetch_tile, args=key, daemon=True).start()

    def _fetch_tile(self, zoom: int, x: int, y: int) -> None:
        image: Image.Image | None = None
        try:
            response = self._session.get(TILE_URL.format(z=zoom, x=x, y=y), timeout=12)
            response.raise_for_status()
            raw = response.content
            target = self._tile_dir / str(zoom) / str(x) / f"{y}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            image = Image.open(io.BytesIO(raw)).convert("RGB")
        except (requests.RequestException, OSError):
            pass
        self._tile_queue.put((zoom, x, y, image))

    def _drain_tiles(self) -> None:
        changed = False
        try:
            while True:
                zoom, x, y, image = self._tile_queue.get_nowait()
                self._requested.discard((zoom, x, y))
                if image is not None and zoom == self.zoom:
                    changed = True
        except queue.Empty:
            pass
        if changed:
            self.redraw()
        self.after(150, self._drain_tiles)

    def _nearest_vertex(self, x: float, y: float, radius: float = 14) -> int | None:
        nearest, distance = None, radius
        for index, point in enumerate(self.points):
            px, py = self.geo_to_canvas(point)
            candidate = math.hypot(px - x, py - y)
            if candidate < distance:
                nearest, distance = index, candidate
        return nearest

    def _nearest_segment(self, x: float, y: float) -> int:
        best_index, best_distance = len(self.points) - 1, float("inf")
        for index in range(len(self.points)):
            ax, ay = self.geo_to_canvas(self.points[index])
            bx, by = self.geo_to_canvas(self.points[(index + 1) % len(self.points)])
            dx, dy = bx - ax, by - ay
            t = 0 if dx == dy == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
            distance = math.hypot(x - (ax + t * dx), y - (ay + t * dy))
            if distance < best_distance:
                best_index, best_distance = index, distance
        return best_index

    def _press(self, event: tk.Event) -> None:
        self._drag_index = self._nearest_vertex(event.x, event.y)
        if self._drag_index is None:
            self._pan_start = (event.x, event.y)

    def _motion(self, event: tk.Event) -> None:
        if self._drag_index is not None:
            self.points[self._drag_index] = self.canvas_to_geo(event.x, event.y)
            self.redraw()
        elif self._pan_start:
            old_x, old_y = self._pan_start
            cx, cy = self._center_world()
            cx -= event.x - old_x
            cy -= event.y - old_y
            self.center = (world_y_to_lat(cy, self.zoom), world_x_to_lon(cx, self.zoom))
            self._pan_start = (event.x, event.y)
            self.redraw()

    def _release(self, _event: tk.Event) -> None:
        self._drag_index = None
        self._pan_start = None

    def _add_vertex(self, event: tk.Event) -> None:
        point = self.canvas_to_geo(event.x, event.y)
        if len(self.points) < 2:
            self.points.append(point)
        else:
            self.points.insert(self._nearest_segment(event.x, event.y) + 1, point)
        self.redraw()

    def _remove_vertex(self, event: tk.Event) -> None:
        index = self._nearest_vertex(event.x, event.y)
        if index is not None and len(self.points) > 3:
            self.points.pop(index)
            self.redraw()

    def _wheel(self, event: tk.Event) -> None:
        self.zoom_by(1 if event.delta > 0 else -1)
