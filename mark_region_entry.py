#!/usr/bin/env python3
"""MARK GUI entry point with visible CHP center and service-area controls."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import mark_app
import mark_gui_entry
import mark_update_entry

ROOT = Path(__file__).resolve().parent
CENTERS_FILE = ROOT / "data" / "chp_communications_centers.json"
BOUNDARIES_FILE = ROOT / "data" / "chp_center_smoke_boundaries.json"
DEFAULT_CENTER_CODE = "BCCC"
DEFAULT_CENTER_NAME = "Border"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "center"


def load_centers() -> list[dict[str, str]]:
    try:
        payload = json.loads(CENTERS_FILE.read_text(encoding="utf-8"))
        centers = payload.get("centers", [])
    except (OSError, json.JSONDecodeError):
        centers = []
    values: list[dict[str, str]] = []
    if isinstance(centers, list):
        for item in centers:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code", "")).strip().upper()
            name = str(item.get("name", "")).strip()
            if code and name:
                values.append({"code": code, "name": name})
    if not any(item["code"] == DEFAULT_CENTER_CODE for item in values):
        values.append({"code": DEFAULT_CENTER_CODE, "name": DEFAULT_CENTER_NAME})
    return sorted(values, key=lambda item: item["name"])


def center_label(center: dict[str, str]) -> str:
    return f"{center['name']} ({center['code']})"


def label_to_center(label: str, centers: list[dict[str, str]]) -> dict[str, str]:
    for center in centers:
        if label == center_label(center) or label.strip().upper() == center["code"]:
            return center
    code = DEFAULT_CENTER_CODE
    match = re.search(r"\(([A-Z0-9]+)\)", label or "")
    if match:
        code = match.group(1)
    for center in centers:
        if center["code"] == code:
            return center
    return {"code": code, "name": code}


class RegionMarkApp(mark_update_entry.UpdatingMarkApp):
    """Add obvious center and service-area map controls to the existing GUI."""

    def __init__(self) -> None:
        self.region_status_text: tk.StringVar | None = None
        self.center_options = load_centers()
        super().__init__()

    def _defaults(self) -> dict[str, str]:
        values = super()._defaults()
        values.update(
            {
                "CHP_ALERT_COMM_CENTER": DEFAULT_CENTER_CODE,
                "CHP_ALERT_COMM_CENTER_NAME": DEFAULT_CENTER_NAME,
                "CHP_ALERT_COMM_CENTER_DISPLAY": f"{DEFAULT_CENTER_NAME} ({DEFAULT_CENTER_CODE})",
            }
        )
        return values

    def _ensure_region_vars(self) -> None:
        defaults = self._defaults()
        for key in (
            "CHP_ALERT_COMM_CENTER",
            "CHP_ALERT_COMM_CENTER_NAME",
            "CHP_ALERT_COMM_CENTER_DISPLAY",
            "CHP_ALERT_SERVICE_AREA_FILE",
            "CHP_ALERT_SERVICE_AREA_LABEL",
            "CHP_ALERT_AREA_PREFIXES",
            "CHP_ALERT_TYPE_FRAGMENTS",
        ):
            self.vars.setdefault(key, tk.StringVar(value=defaults.get(key, "")))

    def load_configuration(self) -> None:
        super().load_configuration()
        self._ensure_region_vars()
        self._sync_center_display_from_code()
        self._refresh_region_summary()

    def _build_config(self, frame: ttk.Frame) -> None:
        super()._build_config(frame)
        self._ensure_region_vars()
        self._insert_region_map_panel(frame)

    def _insert_region_map_panel(self, frame: ttk.Frame) -> None:
        self.region_status_text = tk.StringVar(value=self._region_summary())
        panel = ttk.LabelFrame(frame, text="CHP Region / Service-Area Map", padding=8)
        existing = frame.pack_slaves()
        if existing:
            panel.pack(fill="x", pady=(0, 10), before=existing[0])
        else:
            panel.pack(fill="x", pady=(0, 10))

        ttk.Label(panel, textvariable=self.region_status_text, wraplength=360).pack(anchor="w", fill="x")

        row1 = ttk.Frame(panel)
        row1.pack(fill="x", pady=(7, 0))
        ttk.Label(row1, text="CHP center").pack(side="left")
        labels = [center_label(center) for center in self.center_options]
        combo = ttk.Combobox(
            row1,
            textvariable=self.vars["CHP_ALERT_COMM_CENTER_DISPLAY"],
            values=labels,
            state="readonly",
        )
        combo.pack(side="left", fill="x", expand=True, padx=(8, 0))
        combo.bind("<<ComboboxSelected>>", lambda _event: self._center_selection_changed())

        row2 = ttk.Frame(panel)
        row2.pack(fill="x", pady=(7, 0))
        ttk.Label(row2, text="Service-area map").pack(side="left")
        ttk.Entry(row2, textvariable=self.vars["CHP_ALERT_SERVICE_AREA_FILE"]).pack(
            side="left", fill="x", expand=True, padx=(8, 4)
        )
        ttk.Button(row2, text="Browse", command=self.browse_service_area_map).pack(side="left")

        row3 = ttk.Frame(panel)
        row3.pack(fill="x", pady=(7, 0))
        ttk.Button(row3, text="Load Center Test Map", command=self.load_center_smoke_test_map).pack(side="left")
        ttk.Button(row3, text="Save Region/Map", command=self.save_configuration).pack(side="left", padx=(6, 0))
        ttk.Label(
            row3,
            text="Test maps use AREA=* and Type=* so any listed incident can validate the path.",
            wraplength=330,
        ).pack(side="left", padx=(8, 0))

    def _sync_center_display_from_code(self) -> None:
        code = self.vars.get("CHP_ALERT_COMM_CENTER", tk.StringVar(value=DEFAULT_CENTER_CODE)).get().strip().upper()
        name = self.vars.get("CHP_ALERT_COMM_CENTER_NAME", tk.StringVar(value="")).get().strip()
        center = next((item for item in self.center_options if item["code"] == code), None)
        if center is None:
            center = {"code": code or DEFAULT_CENTER_CODE, "name": name or code or DEFAULT_CENTER_NAME}
        if name:
            center = {"code": center["code"], "name": name}
        self.vars["CHP_ALERT_COMM_CENTER_DISPLAY"].set(center_label(center))

    def _center_selection_changed(self) -> None:
        center = label_to_center(self.vars["CHP_ALERT_COMM_CENTER_DISPLAY"].get(), self.center_options)
        self.vars["CHP_ALERT_COMM_CENTER"].set(center["code"])
        self.vars["CHP_ALERT_COMM_CENTER_NAME"].set(center["name"])
        self._refresh_region_summary()

    def _region_summary(self) -> str:
        try:
            center = label_to_center(self.vars["CHP_ALERT_COMM_CENTER_DISPLAY"].get(), self.center_options)
            map_file = self.vars["CHP_ALERT_SERVICE_AREA_FILE"].get() or "not selected"
            area = self.vars["CHP_ALERT_AREA_PREFIXES"].get() or "default"
            types = self.vars["CHP_ALERT_TYPE_FRAGMENTS"].get() or "default"
            return f"Center: {center['name']} ({center['code']}) • Map: {Path(map_file).name} • AREA: {area} • Type: {types}"
        except Exception:
            return "Center/map not configured"

    def _refresh_region_summary(self) -> None:
        if self.region_status_text is not None:
            self.region_status_text.set(self._region_summary())

    def browse_service_area_map(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Select MARK service-area GeoJSON",
            initialdir=str(ROOT),
            filetypes=(
                ("GeoJSON files", "*.geojson *.json"),
                ("All files", "*.*"),
            ),
        )
        if not path:
            return
        self.vars["CHP_ALERT_SERVICE_AREA_FILE"].set(path)
        self.map_path = Path(path).expanduser()
        self.reload_map(prompt=False)
        self._refresh_region_summary()

    def _center_test_geojson(self, code: str, name: str) -> dict:
        payload = json.loads(BOUNDARIES_FILE.read_text(encoding="utf-8"))
        entry = payload.get("centers", {}).get(code)
        if not entry:
            raise ValueError(f"No smoke-test boundary is defined for {code}")
        west, south, east, north = [float(value) for value in entry["bbox"]]
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "name": f"{name} CHP Center Smoke-Test Boundary",
                        "purpose": "Testing only - broad approximate polygon intended to confirm MARK polling/detail/alert flow for this CHP communications center.",
                        "warning": "Not an official CHP or agency boundary. Do not use for operational response filtering.",
                        "chp_center_code": code,
                        "chp_center_name": name,
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [west, south],
                                [east, south],
                                [east, north],
                                [west, north],
                                [west, south],
                            ]
                        ],
                    },
                }
            ],
        }

    def load_center_smoke_test_map(self) -> None:
        self._center_selection_changed()
        center = label_to_center(self.vars["CHP_ALERT_COMM_CENTER_DISPLAY"].get(), self.center_options)
        if not messagebox.askyesno(
            "Load broad test map?",
            "This will load a broad smoke-test map for the selected CHP center and set AREA=* and Type=* so any listed incident can test the pipeline.\n\n"
            "This is not an operational service-area boundary. Continue?",
            parent=self,
        ):
            return
        try:
            payload = self._center_test_geojson(center["code"], center["name"])
            out_dir = ROOT / "runtime" / "test_maps"
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{_slug(center['name'])}-{center['code'].casefold()}-smoke-test.geojson"
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            self.vars["CHP_ALERT_SERVICE_AREA_FILE"].set(str(path))
            self.vars["CHP_ALERT_SERVICE_AREA_LABEL"].set(f"{center['name']} CHP center smoke-test boundary")
            self.vars["CHP_ALERT_AREA_PREFIXES"].set("*")
            self.vars["CHP_ALERT_TYPE_FRAGMENTS"].set("*")
            self.map_path = path
            self.reload_map(prompt=False)
            self.save_configuration(quiet=True)
            self._refresh_region_summary()
            self.append_log(f"Loaded {center['name']} smoke-test map: {path}")
        except Exception as exc:
            messagebox.showerror("Could not load test map", str(exc), parent=self)

    def collect_configuration(self) -> dict[str, str]:
        self._ensure_region_vars()
        self._center_selection_changed()
        values = super().collect_configuration()
        center = label_to_center(values.get("CHP_ALERT_COMM_CENTER_DISPLAY", ""), self.center_options)
        values["CHP_ALERT_COMM_CENTER"] = center["code"]
        values["CHP_ALERT_COMM_CENTER_NAME"] = center["name"]
        values["CHP_ALERT_SERVICE_AREA_FILE"] = values.get("CHP_ALERT_SERVICE_AREA_FILE", "").strip()
        if not values["CHP_ALERT_SERVICE_AREA_FILE"]:
            raise ValueError("Select a service-area GeoJSON map.")
        return values

    def save_configuration(self, quiet: bool = False) -> bool:
        ok = super().save_configuration(quiet=quiet)
        if ok:
            self._sync_center_display_from_code()
            self._refresh_region_summary()
        return ok

    def _write_full_env(self, values: dict[str, str]) -> None:
        super()._write_full_env(values)
        with mark_app.ENV_FILE.open("a", encoding="utf-8") as handle:
            handle.write("\n# CHP communications center\n")
            handle.write(f"CHP_ALERT_COMM_CENTER={values.get('CHP_ALERT_COMM_CENTER', DEFAULT_CENTER_CODE)}\n")
            handle.write(f"CHP_ALERT_COMM_CENTER_NAME={values.get('CHP_ALERT_COMM_CENTER_NAME', DEFAULT_CENTER_NAME)}\n")


def main() -> int:
    try:
        RegionMarkApp().mainloop()
        return 0
    except Exception:
        mark_gui_entry.report_startup_failure()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
