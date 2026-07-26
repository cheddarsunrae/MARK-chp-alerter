#!/usr/bin/env python3
"""Reliable MARK GUI entry point.

This initializes Tk before Tk variables are created, records otherwise-hidden
pythonw startup failures, adds conservative and manual boundary cleanup, and
exposes profile AREA-prefix and type-fragment filters.
"""
from __future__ import annotations

import json
import re
import sys
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

import mark_app
from chp_gui import BrandedMarkApp, PROFILE_MAP_DIR, PROFILES_FILE, slug, split_csv
from geometry_utils import remove_shorter_path_between, simplify_closed_polygon
from mark_app import DEFAULT_MAP, MarkApp, replace_polygon

ROOT = Path(__file__).resolve().parent
ERROR_LOG = ROOT / "runtime" / "mark-gui-error.log"
DEFAULT_AREA_PREFIXES = "BC,El"
DEFAULT_TYPE_FRAGMENTS = "Unk,1140,1141,Min,Maj,1179,1180,1178,un w,Repo"
AREA_NAMES = ("San Diego", "Temecula", "Oceanside", "El Cajon", "BC")


class SafeMarkApp(BrandedMarkApp):
    """Initialize non-Tk state first, then let MarkApp create the Tk root."""

    def __init__(self) -> None:
        self.profiles = self._read_profiles()
        self.selected_vertex_index: int | None = None
        self.direct_line_start_index: int | None = None
        self.zone_active = False
        self.zone_start_index: int | None = None
        self.zone_points: list[tuple[float, float]] = []
        self.zone_markers: list = []
        self.zone_path = None
        self._press_xy: tuple[int, int] | None = None
        self._dragging = False
        MarkApp.__init__(self)

    def _defaults(self) -> dict[str, str]:
        values = super()._defaults()
        values["CHP_ALERT_AREA_PREFIXES"] = DEFAULT_AREA_PREFIXES
        values["CHP_ALERT_TYPE_FRAGMENTS"] = DEFAULT_TYPE_FRAGMENTS
        return values

    def _build_config(self, frame: ttk.Frame) -> None:
        super()._build_config(frame)
        defaults = self._defaults()
        self.vars.setdefault(
            "CHP_ALERT_AREA_PREFIXES",
            tk.StringVar(value=defaults["CHP_ALERT_AREA_PREFIXES"]),
        )
        self.vars.setdefault(
            "CHP_ALERT_TYPE_FRAGMENTS",
            tk.StringVar(value=defaults["CHP_ALERT_TYPE_FRAGMENTS"]),
        )

    def save_configuration(self, quiet: bool = False) -> bool:
        if not super().save_configuration(quiet=True):
            return False
        try:
            with mark_app.ENV_FILE.open("a", encoding="utf-8") as handle:
                handle.write("\n# MARK fast listing filters\n")
                handle.write(
                    f"CHP_ALERT_AREA_PREFIXES={self.vars['CHP_ALERT_AREA_PREFIXES'].get().strip()}\n"
                )
                handle.write(
                    f"CHP_ALERT_TYPE_FRAGMENTS={self.vars['CHP_ALERT_TYPE_FRAGMENTS'].get().strip()}\n"
                )
        except OSError as exc:
            messagebox.showerror("Configuration error", str(exc), parent=self)
            return False
        if not quiet:
            messagebox.showinfo("Saved", "Configuration saved.", parent=self)
        return True

    def open_profile_manager(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("MARK Monitoring Profiles")
        dialog.geometry("610x650")
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
        combo.pack(fill="x", pady=(4, 12))

        ttk.Label(
            body,
            text="AREA prefixes to monitor",
            style="PanelHead.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            body,
            text=(
                "MARK compares only the first two characters. Known Border AREA values: "
                + ", ".join(AREA_NAMES)
                + ". Default profile values are BC and El."
            ),
            wraplength=570,
        ).pack(anchor="w", pady=(3, 4))
        area_prefixes = tk.StringVar(
            value=self.vars["CHP_ALERT_AREA_PREFIXES"].get() or DEFAULT_AREA_PREFIXES
        )
        ttk.Entry(body, textvariable=area_prefixes).pack(fill="x")

        ttk.Separator(body).pack(fill="x", pady=14)
        ttk.Label(
            body,
            text="TYPE fragments to monitor",
            style="PanelHead.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            body,
            text=(
                "Case-insensitive substring matching. Defaults: Unk, 1140, 1141, Min, "
                "Maj, 1179, 1180, 1178, un w, Repo."
            ),
            wraplength=570,
        ).pack(anchor="w", pady=(3, 4))
        type_fragments = tk.StringVar(
            value=self.vars["CHP_ALERT_TYPE_FRAGMENTS"].get() or DEFAULT_TYPE_FRAGMENTS
        )
        ttk.Entry(body, textvariable=type_fragments).pack(fill="x")

        ttk.Separator(body).pack(fill="x", pady=14)
        ttk.Label(
            body,
            text="The map coordinates in each selected call's detail header remain the final service-area confirmation.",
            wraplength=570,
            style="PanelHead.TLabel",
        ).pack(anchor="w")

        def apply_choices() -> bool:
            prefixes = split_csv(area_prefixes.get())
            fragments = split_csv(type_fragments.get())
            if not prefixes:
                messagebox.showerror("No AREA prefixes", "Enter at least one AREA prefix.", parent=dialog)
                return False
            if not fragments:
                messagebox.showerror("No TYPE fragments", "Enter at least one TYPE fragment.", parent=dialog)
                return False
            self.vars["CHP_ALERT_AREA_PREFIXES"].set(",".join(dict.fromkeys(prefixes)))
            self.vars["CHP_ALERT_TYPE_FRAGMENTS"].set(",".join(dict.fromkeys(fragments)))
            self.vars["CHP_ALERT_PROFILE"].set(profile_name.get().strip())
            return True

        def load_profile() -> None:
            profile = self.profiles.get(profile_name.get().strip())
            if not profile:
                return
            self.vars["CHP_ALERT_AREA_PREFIXES"].set(
                ",".join(profile.get("area_prefixes", ["BC", "El"]))
            )
            self.vars["CHP_ALERT_TYPE_FRAGMENTS"].set(
                ",".join(profile.get("type_fragments", split_csv(DEFAULT_TYPE_FRAGMENTS)))
            )
            self.vars["CHP_ALERT_INTERVAL"].set(str(profile.get("poll_interval", "30")))
            self.vars["CHP_ALERT_EXISTING"].set(str(profile.get("alert_existing", "0")))
            self.vars["CHP_ALERT_UPDATES"].set(str(profile.get("alert_updates", "0")))
            raw = Path(str(profile.get("map_file", DEFAULT_MAP)))
            map_path = raw if raw.is_absolute() else ROOT / raw
            self.vars["CHP_ALERT_SERVICE_AREA_FILE"].set(str(map_path))
            self.vars["CHP_ALERT_PROFILE"].set(profile_name.get().strip())
            self.map_path = map_path
            self.reload_map(prompt=False)
            self.save_configuration(quiet=True)
            self.append_log(f"Loaded profile {profile_name.get().strip()}")
            dialog.destroy()

        def save_profile() -> None:
            if not apply_choices():
                return
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
                    "area_prefixes": split_csv(self.vars["CHP_ALERT_AREA_PREFIXES"].get()),
                    "type_fragments": split_csv(self.vars["CHP_ALERT_TYPE_FRAGMENTS"].get()),
                    "poll_interval": self.vars["CHP_ALERT_INTERVAL"].get(),
                    "alert_existing": self.vars["CHP_ALERT_EXISTING"].get(),
                    "alert_updates": self.vars["CHP_ALERT_UPDATES"].get(),
                }
                PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
                PROFILES_FILE.write_text(
                    json.dumps(self.profiles, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
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
            if messagebox.askyesno("Delete profile", f"Delete '{name}'?", parent=dialog):
                self.profiles.pop(name)
                PROFILES_FILE.write_text(
                    json.dumps(self.profiles, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                profile_name.set("")
                combo.configure(values=sorted(self.profiles))

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(20, 0))
        ttk.Button(
            buttons,
            text="Apply",
            command=lambda: dialog.destroy() if apply_choices() else None,
        ).pack(side="left", padx=3)
        ttk.Button(buttons, text="Load Profile", command=load_profile).pack(side="left", padx=3)
        ttk.Button(buttons, text="Save as Profile", command=save_profile).pack(side="left", padx=3)
        ttk.Button(buttons, text="Delete", command=delete_profile).pack(side="left", padx=3)

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

        direct_bar = ttk.Frame(frame, style="Panel.TFrame")
        direct_bar.pack(fill="x", pady=(5, 0))
        ttk.Button(
            direct_bar,
            text="Set Line Start",
            command=self.set_direct_line_start,
        ).pack(side="left")
        ttk.Button(
            direct_bar,
            text="Remove Between Start + Selected",
            command=self.remove_between_direct_line,
        ).pack(side="left", padx=4)
        ttk.Button(
            direct_bar,
            text="Clear Line Start",
            command=self.clear_direct_line_start,
        ).pack(side="left")
        self.direct_line_status = ttk.Label(
            direct_bar,
            text="Direct line: no start selected",
            style="PanelHead.TLabel",
        )
        self.direct_line_status.pack(side="left", padx=8)

    def reload_map(self, prompt: bool = True) -> None:
        self.direct_line_start_index = None
        super().reload_map(prompt=prompt)
        self._refresh_direct_line_status()

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
        self.direct_line_start_index = None
        if hasattr(self, "anchor_status"):
            self.anchor_status.configure(text="Anchor: none")
        self._refresh_direct_line_status()
        self._draw_polygon(False)
        self.append_log(
            f"Simplified boundary: removed {removed} waypoint(s) at {tolerance:g} m tolerance"
        )

    def set_direct_line_start(self) -> None:
        if not getattr(self, "map_edit_enabled", tk.BooleanVar(value=False)).get():
            messagebox.showinfo("Enable editing", "Enable map editing first.", parent=self)
            return
        if self.selected_vertex_index is None:
            messagebox.showinfo(
                "Select waypoint",
                "Click the first waypoint before setting the direct-line start.",
                parent=self,
            )
            return
        self.direct_line_start_index = self.selected_vertex_index
        self._refresh_direct_line_status()
        self.append_log(f"Direct-line cleanup start set to waypoint {self.direct_line_start_index + 1}")

    def clear_direct_line_start(self) -> None:
        self.direct_line_start_index = None
        self._refresh_direct_line_status()

    def _refresh_direct_line_status(self) -> None:
        if not hasattr(self, "direct_line_status"):
            return
        if self.direct_line_start_index is None:
            self.direct_line_status.configure(text="Direct line: no start selected")
            return
        self.direct_line_status.configure(text=f"Direct line start: {self.direct_line_start_index + 1}")

    def remove_between_direct_line(self) -> None:
        if not getattr(self, "map_edit_enabled", tk.BooleanVar(value=False)).get():
            messagebox.showinfo("Enable editing", "Enable map editing first.", parent=self)
            return
        if self.zone_active:
            messagebox.showinfo(
                "Finish extension first",
                "Finish or cancel the active zone extension before direct-line cleanup.",
                parent=self,
            )
            return
        if self.direct_line_start_index is None:
            messagebox.showinfo(
                "No line start",
                "Select the first waypoint and click Set Line Start.",
                parent=self,
            )
            return
        if self.selected_vertex_index is None:
            messagebox.showinfo(
                "No endpoint",
                "Click the second waypoint before removing the points between them.",
                parent=self,
            )
            return
        start = self.direct_line_start_index
        end = self.selected_vertex_index
        try:
            revised, removed, selected = remove_shorter_path_between(self.map_points, start, end)
        except (IndexError, ValueError) as exc:
            messagebox.showerror("Cannot remove between waypoints", str(exc), parent=self)
            return
        if not messagebox.askyesno(
            "Remove intermediate waypoints?",
            f"Remove {removed} waypoint(s) between waypoint {start + 1} and waypoint {end + 1} "
            "and replace that boundary section with one direct line?\n\n"
            "Review the resulting boundary before pressing Save Map.",
            parent=self,
        ):
            return
        self.map_points = revised
        self.selected_vertex_index = selected
        self.direct_line_start_index = None
        self._refresh_direct_line_status()
        if hasattr(self, "anchor_status"):
            lat, lon = self.map_points[self.selected_vertex_index]
            self.anchor_status.configure(
                text=f"Anchor: {self.selected_vertex_index + 1} ({lat:.5f}, {lon:.5f})"
            )
        self._draw_polygon(False)
        self.append_log(
            f"Direct-line cleanup: removed {removed} waypoint(s) between old waypoints {start + 1} and {end + 1}"
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
