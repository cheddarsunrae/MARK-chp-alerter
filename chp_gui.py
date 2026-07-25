#!/usr/bin/env python3
"""MARK desktop launcher with profiles and zone-extension map editing."""
from __future__ import annotations

import json
import math
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

import mark_app
from mark_app import COLORS, DEFAULT_MAP, MarkApp, load_polygon, replace_polygon

ROOT = Path(__file__).resolve().parent
mark_app.BACKEND = ROOT / "mark_backend.py"
PROFILES_FILE = ROOT / "profiles" / "profiles.json"
PROFILE_MAP_DIR = ROOT / "profiles" / "maps"
MIN_POLL_INTERVAL = 30.0
REGIONS = ("Oceanside", "Temecula", "San Diego")
INCIDENT_TYPES = (
    "Trfc Collision-1141Enrt",
    "Trfc Collision-Unkn Inj",
    "Report of Fire",
)


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;\n]+", value or "") if item.strip()]


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "profile"


class BrandedMarkApp(MarkApp):
    """Branded MARK dashboard with selectable profiles and polygon extensions."""

    def __init__(self) -> None:
        self.profiles = self._read_profiles()
        self.active_profile = tk.StringVar(value="")
        self.selected_vertex_index: int | None = None
        self.zone_active = False
        self.zone_start_index: int | None = None
        self.zone_points: list[tuple[float, float]] = []
        self.zone_markers: list = []
        self.zone_path = None
        self._press_xy: tuple[int, int] | None = None
        self._dragging = False
        super().__init__()

    def _defaults(self) -> dict[str, str]:
        values = super()._defaults()
        values.update(
            {
                "CHP_ALERT_INTERVAL": "30",
                "CHP_ALERT_IGNORED_AREAS": "Oceanside,Temecula",
                "CHP_ALERT_INCIDENT_TYPES": ",".join(INCIDENT_TYPES),
                "CHP_ALERT_PROFILE": "",
            }
        )
        return values

    def _read_profiles(self) -> dict[str, dict]:
        try:
            value = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}

    def _write_profiles(self) -> None:
        PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROFILES_FILE.write_text(
            json.dumps(self.profiles, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def collect_configuration(self) -> dict[str, str]:
        values = {key: var.get().strip() for key, var in self.vars.items()}
        if not values["PUSHOVER_APP_TOKEN"] or not values["PUSHOVER_USER_KEY"]:
            raise ValueError("Enter both Pushover credentials")
        if float(values["CHP_ALERT_INTERVAL"]) < MIN_POLL_INTERVAL:
            raise ValueError("Poll interval must be at least 30 seconds")
        if int(values["PUSHOVER_PRIORITY"]) == 2 and int(values["PUSHOVER_RETRY_SECONDS"]) < 30:
            raise ValueError("Priority 2 retry must be at least 30 seconds")
        if not split_csv(values["CHP_ALERT_INCIDENT_TYPES"]):
            raise ValueError("Select at least one incident type")
        for key in ("CHP_ALERT_STATE_FILE", "CHP_ALERT_DETAIL_LOG_FILE"):
            Path(values[key]).expanduser().parent.mkdir(parents=True, exist_ok=True)
        return values

    def save_configuration(self, quiet: bool = False) -> bool:
        try:
            values = self.collect_configuration()
            mark_app.write_env(mark_app.ENV_FILE, values)
            with mark_app.ENV_FILE.open("a", encoding="utf-8") as handle:
                handle.write("\n# MARK filtering profile\n")
                for key in (
                    "CHP_ALERT_IGNORED_AREAS",
                    "CHP_ALERT_INCIDENT_TYPES",
                    "CHP_ALERT_PROFILE",
                ):
                    handle.write(f"{key}={values[key]}\n")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Configuration error", str(exc), parent=self)
            return False
        self.append_log("Saved MARK configuration")
        if not quiet:
            messagebox.showinfo("Saved", "Configuration saved.", parent=self)
        return True

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
        ttk.Label(
            words,
            text="Real-time CHP incident monitoring and map-aware notifications.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 0))
        cards = ttk.Frame(header)
        cards.pack(side="right")
        self.status_card_value = self._card(cards, "STATUS", self.status)
        self._card(cards, "LAST POLL", self.last_poll)
        self._card(cards, "LATEST SUMMARY", self.latest_summary, width=28)

    def _build_config(self, frame: ttk.Frame) -> None:
        super()._build_config(frame)
        defaults = self._defaults()
        self.vars["CHP_ALERT_IGNORED_AREAS"] = tk.StringVar(
            value=defaults["CHP_ALERT_IGNORED_AREAS"]
        )
        self.vars["CHP_ALERT_INCIDENT_TYPES"] = tk.StringVar(
            value=defaults["CHP_ALERT_INCIDENT_TYPES"]
        )
        self.vars["CHP_ALERT_PROFILE"] = tk.StringVar(value="")
        ttk.Button(
            frame,
            text="Profiles / Regions / Incident Types",
            command=self.open_profile_manager,
        ).pack(fill="x", pady=(8, 0))

    def open_profile_manager(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("MARK Monitoring Profiles")
        dialog.geometry("560x610")
        dialog.transient(self)
        dialog.grab_set()
        body = ttk.Frame(dialog, padding=14)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="Saved profile", style="PanelHead.TLabel").pack(anchor="w")
        profile_name = tk.StringVar(value=self.vars["CHP_ALERT_PROFILE"].get())
        combo = ttk.Combobox(
            body,
            textvariable=profile_name,
            values=sorted(self.profiles),
            state="readonly",
        )
        combo.pack(fill="x", pady=(4, 10))

        ttk.Label(body, text="Ignore CHP AREA regions", style="PanelHead.TLabel").pack(anchor="w")
        ignored_now = {item.casefold() for item in split_csv(self.vars["CHP_ALERT_IGNORED_AREAS"].get())}
        region_vars = {
            name: tk.BooleanVar(value=name.casefold() in ignored_now)
            for name in REGIONS
        }
        for name in REGIONS:
            ttk.Checkbutton(body, text=name, variable=region_vars[name]).pack(anchor="w")
        known_regions = {name.casefold() for name in REGIONS}
        other_regions = tk.StringVar(
            value=",".join(
                item
                for item in split_csv(self.vars["CHP_ALERT_IGNORED_AREAS"].get())
                if item.casefold() not in known_regions
            )
        )
        ttk.Label(body, text="Other ignored regions (comma-separated)").pack(anchor="w", pady=(8, 2))
        ttk.Entry(body, textvariable=other_regions).pack(fill="x")

        ttk.Separator(body).pack(fill="x", pady=12)
        ttk.Label(body, text="Incident types to monitor", style="PanelHead.TLabel").pack(anchor="w")
        selected_now = {item.casefold() for item in split_csv(self.vars["CHP_ALERT_INCIDENT_TYPES"].get())}
        type_vars = {
            name: tk.BooleanVar(value=name.casefold() in selected_now)
            for name in INCIDENT_TYPES
        }
        for name in INCIDENT_TYPES:
            ttk.Checkbutton(body, text=name, variable=type_vars[name]).pack(anchor="w")
        known_types = {name.casefold() for name in INCIDENT_TYPES}
        other_types = tk.StringVar(
            value=",".join(
                item
                for item in split_csv(self.vars["CHP_ALERT_INCIDENT_TYPES"].get())
                if item.casefold() not in known_types
            )
        )
        ttk.Label(body, text="Other exact CHP incident names (comma-separated)").pack(anchor="w", pady=(8, 2))
        ttk.Entry(body, textvariable=other_types).pack(fill="x")

        def apply_choices() -> None:
            ignored = [name for name, var in region_vars.items() if var.get()]
            ignored.extend(split_csv(other_regions.get()))
            selected = [name for name, var in type_vars.items() if var.get()]
            selected.extend(split_csv(other_types.get()))
            if not selected:
                messagebox.showerror("No incident types", "Select at least one incident type.", parent=dialog)
                return
            self.vars["CHP_ALERT_IGNORED_AREAS"].set(",".join(dict.fromkeys(ignored)))
            self.vars["CHP_ALERT_INCIDENT_TYPES"].set(",".join(dict.fromkeys(selected)))
            self.vars["CHP_ALERT_PROFILE"].set(profile_name.get().strip())

        def load_profile() -> None:
            profile = self.profiles.get(profile_name.get().strip())
            if not profile:
                return
            self.vars["CHP_ALERT_IGNORED_AREAS"].set(",".join(profile.get("ignored_areas", [])))
            self.vars["CHP_ALERT_INCIDENT_TYPES"].set(",".join(profile.get("incident_types", [])))
            self.vars["CHP_ALERT_INTERVAL"].set(str(profile.get("poll_interval", "30")))
            self.vars["CHP_ALERT_EXISTING"].set(str(profile.get("alert_existing", "0")))
            self.vars["CHP_ALERT_UPDATES"].set(str(profile.get("alert_updates", "0")))
            raw = Path(str(profile.get("map_file", DEFAULT_MAP)))
            map_path = raw if raw.is_absolute() else ROOT / raw
            self.vars["CHP_ALERT_SERVICE_AREA_FILE"].set(str(map_path))
            self.vars["CHP_ALERT_PROFILE"].set(profile_name.get().strip())
            self.map_path = map_path
            self.reload_map(prompt=False)
            dialog.destroy()
            self.save_configuration(quiet=True)
            self.append_log(f"Loaded profile {profile_name.get().strip()}")

        def save_profile() -> None:
            apply_choices()
            name = simpledialog.askstring(
                "Save profile",
                "Profile name:",
                initialvalue=profile_name.get(),
                parent=dialog,
            )
            if not name or not name.strip():
                return
            name = name.strip()
            try:
                PROFILE_MAP_DIR.mkdir(parents=True, exist_ok=True)
                map_file = PROFILE_MAP_DIR / f"{slug(name)}.geojson"
                payload = replace_polygon(
                    json.loads(json.dumps(self.map_payload)),
                    self.map_points,
                )
                map_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
                self.profiles[name] = {
                    "map_file": str(map_file.relative_to(ROOT)),
                    "ignored_areas": split_csv(self.vars["CHP_ALERT_IGNORED_AREAS"].get()),
                    "incident_types": split_csv(self.vars["CHP_ALERT_INCIDENT_TYPES"].get()),
                    "poll_interval": self.vars["CHP_ALERT_INTERVAL"].get(),
                    "alert_existing": self.vars["CHP_ALERT_EXISTING"].get(),
                    "alert_updates": self.vars["CHP_ALERT_UPDATES"].get(),
                }
                self._write_profiles()
                self.vars["CHP_ALERT_PROFILE"].set(name)
                profile_name.set(name)
                combo.configure(values=sorted(self.profiles))
                self.save_configuration(quiet=True)
                self.append_log(f"Saved profile {name}")
            except Exception as exc:
                messagebox.showerror("Profile save failed", str(exc), parent=dialog)

        def delete_profile() -> None:
            name = profile_name.get().strip()
            if not name or name not in self.profiles:
                return
            if messagebox.askyesno("Delete profile", f"Delete “{name}”?", parent=dialog):
                self.profiles.pop(name)
                self._write_profiles()
                profile_name.set("")
                combo.configure(values=sorted(self.profiles))

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(18, 0))
        ttk.Button(buttons, text="Apply", command=lambda: (apply_choices(), dialog.destroy())).pack(side="left", padx=3)
        ttk.Button(buttons, text="Load Profile", command=load_profile).pack(side="left", padx=3)
        ttk.Button(buttons, text="Save as Profile", command=save_profile).pack(side="left", padx=3)
        ttk.Button(buttons, text="Delete", command=delete_profile).pack(side="left", padx=3)

    def _build_map(self, frame: ttk.Frame) -> None:
        self.map_edit_enabled = tk.BooleanVar(value=False)
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
            canvas.bind("<ButtonPress-1>", self._map_press, add="+")
            canvas.bind("<B1-Motion>", self._map_drag, add="+")
            canvas.bind("<ButtonRelease-1>", self._map_release, add="+")
        else:
            self.map_widget = tk.Canvas(frame, bg="#d9d3c7", highlightthickness=0)
            self.map_widget.pack(fill="both", expand=True, pady=(8, 6))

        ttk.Label(
            frame,
            text=(
                "Enable editing, click an existing waypoint to select the start, then "
                "start an extension and click at least two points. The final click is "
                "replaced by the nearest existing waypoint."
            ),
            style="PanelHead.TLabel",
            wraplength=650,
        ).pack(anchor="w")

        controls = ttk.Frame(frame, style="Panel.TFrame")
        controls.pack(fill="x", pady=(5, 0))
        ttk.Checkbutton(
            controls,
            text="Enable editing",
            variable=self.map_edit_enabled,
            command=self._editing_changed,
        ).pack(side="left")
        ttk.Button(controls, text="Start Extension", command=self.start_extension).pack(side="left", padx=3)
        ttk.Button(controls, text="Finish Extension", command=self.finish_extension).pack(side="left", padx=3)
        ttk.Button(controls, text="Cancel", command=self.cancel_extension).pack(side="left", padx=3)
        ttk.Button(controls, text="Delete Selected", command=self.delete_selected).pack(side="left", padx=3)

        status = ttk.Frame(frame, style="Panel.TFrame")
        status.pack(fill="x", pady=(4, 0))
        self.zone_status = ttk.Label(status, text="Extension: inactive", style="PanelHead.TLabel")
        self.zone_status.pack(side="left")
        self.anchor_status = ttk.Label(status, text="Anchor: none", style="PanelHead.TLabel")
        self.anchor_status.pack(side="right", padx=8)
        self.map_stats = ttk.Label(status, text="0 vertices", style="PanelHead.TLabel")
        self.map_stats.pack(side="right")

    @staticmethod
    def _control_click(x: int, y: int) -> bool:
        return x <= 72 and y <= 145

    def _editing_changed(self) -> None:
        if not self.map_edit_enabled.get():
            self.cancel_extension()
        self.append_log(f"Map editing {'enabled' if self.map_edit_enabled.get() else 'disabled'}")

    def _nearest_vertex(self, x: int, y: int, radius: float = 30.0) -> int | None:
        best = None
        distance = radius
        for index, marker in enumerate(self.map_markers):
            try:
                mx, my = marker.get_canvas_pos(marker.position)
            except Exception:
                continue
            current = math.hypot(mx - x, my - y)
            if current <= distance:
                best, distance = index, current
        return best

    def select_vertex(self, index: int) -> None:
        if not 0 <= index < len(self.map_points):
            return
        self.selected_vertex_index = index
        lat, lon = self.map_points[index]
        self.anchor_status.configure(text=f"Anchor: {index + 1} ({lat:.5f}, {lon:.5f})")
        self._draw_polygon(False)

    def start_extension(self) -> None:
        if not self.map_edit_enabled.get():
            messagebox.showinfo("Enable editing", "Enable map editing first.", parent=self)
            return
        if self.selected_vertex_index is None:
            messagebox.showinfo("Select start", "Click an existing waypoint first.", parent=self)
            return
        self.zone_active = True
        self.zone_start_index = self.selected_vertex_index
        self.zone_points = []
        self.zone_status.configure(text=f"Extension: starts at {self.zone_start_index + 1}; click at least 2 points")
        self._draw_draft()

    def cancel_extension(self) -> None:
        self.zone_active = False
        self.zone_start_index = None
        self.zone_points = []
        if hasattr(self, "zone_status"):
            self.zone_status.configure(text="Extension: inactive")
        self._draw_draft()

    def finish_extension(self) -> None:
        if not self.zone_active or self.zone_start_index is None:
            messagebox.showinfo("No extension", "Start a zone extension first.", parent=self)
            return
        if len(self.zone_points) < 2:
            messagebox.showinfo(
                "More points needed",
                "Add at least two points; the last indicates the existing endpoint.",
                parent=self,
            )
            return
        start = self.zone_start_index
        hint = self.zone_points[-1]
        scale = math.cos(math.radians(hint[0]))
        choices = [i for i in range(len(self.map_points)) if i != start]
        end = min(
            choices,
            key=lambda i: math.hypot(
                (self.map_points[i][1] - hint[1]) * scale,
                self.map_points[i][0] - hint[0],
            ),
        )
        new_points = self.zone_points[:-1]
        n = len(self.map_points)
        clockwise = (end - start - 1) % n
        counter = (start - end - 1) % n
        remainder: list[tuple[float, float]] = []
        if clockwise <= counter:
            index = (end + 1) % n
            while index != start:
                remainder.append(self.map_points[index])
                index = (index + 1) % n
        else:
            index = (end - 1) % n
            while index != start:
                remainder.append(self.map_points[index])
                index = (index - 1) % n
        self.map_points = [self.map_points[start], *new_points, self.map_points[end], *remainder]
        self.selected_vertex_index = len(new_points) + 1
        self.cancel_extension()
        self.select_vertex(self.selected_vertex_index)
        self.append_log(f"Extended zone with {len(new_points)} new waypoint(s); endpoint snapped to old waypoint {end + 1}")

    def delete_selected(self) -> None:
        if self.selected_vertex_index is None:
            return
        if len(self.map_points) <= 3:
            messagebox.showerror("Cannot delete", "The polygon needs at least three vertices.", parent=self)
            return
        self.map_points.pop(self.selected_vertex_index)
        self.selected_vertex_index = min(self.selected_vertex_index, len(self.map_points) - 1)
        self.select_vertex(self.selected_vertex_index)

    def _map_press(self, event: tk.Event) -> None:
        self._press_xy = (event.x, event.y)
        self._dragging = False
        if not self.map_edit_enabled.get() or self._control_click(event.x, event.y):
            return
        nearest = self._nearest_vertex(event.x, event.y)
        if nearest is not None:
            self.select_vertex(nearest)
            if not self.zone_active:
                self._dragging = True

    def _map_drag(self, event: tk.Event) -> None:
        if not self.map_edit_enabled.get() or not self._dragging or self.zone_active:
            return
        if self.selected_vertex_index is None or self._control_click(event.x, event.y):
            return
        try:
            lat, lon = self.map_widget.convert_canvas_coords_to_decimal_coords(event.x, event.y)
        except Exception:
            return
        self.map_points[self.selected_vertex_index] = (float(lat), float(lon))
        self._draw_polygon(False)

    def _map_release(self, event: tk.Event) -> None:
        press = self._press_xy
        dragged = self._dragging
        self._press_xy = None
        self._dragging = False
        if (
            press is None
            or not self.map_edit_enabled.get()
            or self._control_click(event.x, event.y)
            or dragged
            or math.hypot(event.x - press[0], event.y - press[1]) > 5
        ):
            return
        if self._nearest_vertex(event.x, event.y) is not None or not self.zone_active:
            return
        try:
            lat, lon = self.map_widget.convert_canvas_coords_to_decimal_coords(event.x, event.y)
        except Exception:
            return
        self.zone_points.append((float(lat), float(lon)))
        self.zone_status.configure(
            text=f"Extension: {len(self.zone_points)} click(s); final click will snap to nearest old waypoint"
        )
        self._draw_draft()

    def _draw_draft(self) -> None:
        if not mark_app.tkintermapview or not hasattr(self, "map_widget"):
            return
        try:
            if self.zone_path:
                self.zone_path.delete()
            for marker in self.zone_markers:
                marker.delete()
        except Exception:
            pass
        self.zone_path = None
        self.zone_markers = []
        if not self.zone_active or self.zone_start_index is None or not self.zone_points:
            return
        points = [self.map_points[self.zone_start_index], *self.zone_points]
        try:
            self.zone_path = self.map_widget.set_path(points, color="#e4483f", width=4)
        except Exception:
            pass
        for index, point in enumerate(self.zone_points, 1):
            self.zone_markers.append(
                self.map_widget.set_marker(
                    *point,
                    text=f"N{index}",
                    marker_color_circle="#e4483f",
                    marker_color_outside="#ffffff",
                )
            )

    def reload_map(self, prompt: bool = True) -> None:
        try:
            variable = self.vars.get("CHP_ALERT_SERVICE_AREA_FILE")
            path = Path(variable.get() if variable else str(self.map_path or DEFAULT_MAP)).expanduser()
            self.map_payload, self.map_points = load_polygon(path)
            self.map_path = path
            self.selected_vertex_index = None
            self.cancel_extension()
            if hasattr(self, "anchor_status"):
                self.anchor_status.configure(text="Anchor: none")
            self._draw_polygon(True)
            self.append_log(f"Loaded map {path} ({len(self.map_points)} vertices)")
            if prompt and self.process and self.process.poll() is None:
                messagebox.showinfo("Restart required", "Restart the monitor to apply the map.", parent=self)
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
            self.map_polygon = self.map_widget.set_polygon(
                self.map_points,
                fill_color="#d99b20",
                outline_color="#ffc43d",
                border_width=3,
            )
        for index, point in enumerate(self.map_points):
            selected = index == self.selected_vertex_index
            self.map_markers.append(
                self.map_widget.set_marker(
                    *point,
                    text=str(index + 1),
                    marker_color_circle="#e4483f" if selected else "#ffc43d",
                    marker_color_outside="#ffffff" if selected else "#13243a",
                    command=lambda _marker, i=index: self.select_vertex(i),
                )
            )
        self._draw_draft()
        if refit and self.map_points:
            north = max(p[0] for p in self.map_points)
            south = min(p[0] for p in self.map_points)
            west = min(p[1] for p in self.map_points)
            east = max(p[1] for p in self.map_points)
            if north > south and east > west:
                self.map_widget.fit_bounding_box((north, west), (south, east))


def main() -> int:
    BrandedMarkApp().mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
