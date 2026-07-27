#!/usr/bin/env python3
"""MARK GUI entry point with visible CHP center and service-area controls."""
from __future__ import annotations

import json
import os
import re
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import address_box_runtime
import mark_app
import mark_gui_entry
import mark_update_entry

ROOT = Path(__file__).resolve().parent
CENTERS_FILE = ROOT / "data" / "chp_communications_centers.json"
BOUNDARIES_FILE = ROOT / "data" / "chp_center_smoke_boundaries.json"
VERSION_FILE = ROOT / "VERSION"
QUICK_START_GUIDE = ROOT / "MARK_QUICK_START_GUIDE.md"
FIRST_RUN_FLAG = ROOT / "runtime" / "first-run-helper-dismissed"
DEFAULT_CENTER_CODE = "BCCC"
DEFAULT_CENTER_NAME = "Border"
DEFAULT_AREA_PREFIXES = "Bo,El"
DEFAULT_TYPE_FRAGMENTS = "Unk,1140,1141,Min,Maj,1179,1180,1178,un w,Repo"

# Some CHP centers cover a broad region/county AREA value that should always be
# included with any user-selected subareas. Border Communications Center is the
# San Diego County example: keep Bo/Border in scope even when the user also
# selects San Diego, El Cajon, etc.
CENTER_REQUIRED_AREA_PREFIXES: dict[str, tuple[str, ...]] = {
    "BCCC": ("Bo",),
}

AREA_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Border / San Diego County region", "Bo"),
    ("San Diego", "Sa"),
    ("El Cajon", "El"),
    ("Oceanside", "Oc"),
    ("Temecula", "Te"),
)
AREA_NAME_ALIASES = {
    "all": "*",
    "any": "*",
    "*": "*",
    "border": "Bo",
    "bo": "Bo",
    "bc": "Bo",  # migration compatibility for older beta configs
    "bccc": "Bo",
    "san diego county": "Bo",
    "county": "Bo",
    "el cajon": "El",
    "el": "El",
    "san diego": "Sa",
    "sd": "Sa",
    "sa": "Sa",
    "oceanside": "Oc",
    "oc": "Oc",
    "temecula": "Te",
    "te": "Te",
}
TYPE_WILDCARD_VALUES = {"*", "all", "any"}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "center"


def _split_list(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;\n]+", value or "") if item.strip()]


def required_area_prefixes_for_center(center_code: str) -> tuple[str, ...]:
    """Return AREA prefixes that should always be included for a CHP center."""
    return CENTER_REQUIRED_AREA_PREFIXES.get((center_code or "").strip().upper(), ())


def normalize_area_token(value: str) -> str:
    """Normalize a user-entered AREA token or alias to CHP's two-character prefix."""
    folded = value.strip().casefold()
    alias = AREA_NAME_ALIASES.get(folded)
    if alias:
        return alias
    if len(value.strip()) == 2:
        stripped = value.strip()
        return stripped[0].upper() + stripped[1].lower()
    return value.strip()


def normalize_area_prefixes(value: str, required: tuple[str, ...] = ()) -> str:
    """Return stable comma-separated AREA prefixes for .env storage."""
    items = _split_list(value)
    if not items and not required:
        raise ValueError("Choose at least one CHP AREA prefix, such as Sa, El, Bo, or *.")
    normalized: list[str] = []
    for item in items:
        value_out = normalize_area_token(item)
        if value_out == "*":
            return "*"
        if value_out and value_out not in normalized:
            normalized.append(value_out)
    for item in required:
        value_out = normalize_area_token(item)
        if value_out == "*":
            return "*"
        if value_out and value_out not in normalized:
            normalized.insert(0, value_out)
    return ",".join(normalized)


def normalize_type_fragments(value: str) -> str:
    """Keep alert type fragments on the fixed operational defaults.

    Earlier beta smoke-test flows could save '*' into CHP_ALERT_TYPE_FRAGMENTS,
    which makes non-alertable categories such as Traffic Hazard alertable. Treat
    wildcard values as a request to restore the fixed default trigger set.
    """
    raw = (value or "").strip()
    if not raw:
        return DEFAULT_TYPE_FRAGMENTS
    if raw.casefold() in TYPE_WILDCARD_VALUES:
        return DEFAULT_TYPE_FRAGMENTS
    return raw


def read_version() -> str:
    try:
        value = VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        value = "0.0.0-local"
    return value or "0.0.0-local"


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
    """Add obvious center, CHP AREA, and service-area map controls to the GUI."""

    def __init__(self) -> None:
        self.app_version = read_version()
        self.region_status_text: tk.StringVar | None = None
        self.area_required_text: tk.StringVar | None = None
        self.area_prefix_checks: dict[str, tk.BooleanVar] = {}
        self.center_options = load_centers()
        super().__init__()
        self.title(f"{mark_app.APP_TITLE} v{self.app_version}")
        self.after(900, self._maybe_show_first_run_helper)

    def _defaults(self) -> dict[str, str]:
        values = super()._defaults()
        values.update(
            {
                "CHP_ALERT_COMM_CENTER": DEFAULT_CENTER_CODE,
                "CHP_ALERT_COMM_CENTER_NAME": DEFAULT_CENTER_NAME,
                "CHP_ALERT_COMM_CENTER_DISPLAY": f"{DEFAULT_CENTER_NAME} ({DEFAULT_CENTER_CODE})",
                "CHP_ALERT_AREA_PREFIXES": DEFAULT_AREA_PREFIXES,
                "CHP_ALERT_TYPE_FRAGMENTS": DEFAULT_TYPE_FRAGMENTS,
                "CHP_ALERT_BOUNDARY_BUFFER_METERS": "0",
                "CHP_ALERT_ADDRESS_BOX_ADDRESS": "",
                "CHP_ALERT_ADDRESS_BOX_HALF_SIZE_METERS": str(int(address_box_runtime.DEFAULT_HALF_SIZE_METERS)),
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
            "CHP_ALERT_BOUNDARY_BUFFER_METERS",
            "CHP_ALERT_ADDRESS_BOX_ADDRESS",
            "CHP_ALERT_ADDRESS_BOX_HALF_SIZE_METERS",
            "CHP_ALERT_AREA_PREFIXES",
            "CHP_ALERT_TYPE_FRAGMENTS",
        ):
            self.vars.setdefault(key, tk.StringVar(value=defaults.get(key, "")))

    def _open_local_file(self, path: Path) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                webbrowser.open(path.resolve().as_uri())
        except Exception as exc:
            messagebox.showerror("Could not open file", str(exc), parent=self)

    def _dismiss_first_run_helper(self, dialog: tk.Toplevel) -> None:
        try:
            FIRST_RUN_FLAG.parent.mkdir(parents=True, exist_ok=True)
            FIRST_RUN_FLAG.write_text("dismissed\n", encoding="utf-8")
        except OSError:
            pass
        dialog.destroy()

    def _maybe_show_first_run_helper(self) -> None:
        if FIRST_RUN_FLAG.exists():
            return
        dialog = tk.Toplevel(self)
        dialog.title("Welcome to MARK")
        dialog.geometry("640x470")
        dialog.minsize(580, 420)
        dialog.transient(self)

        body = ttk.Frame(dialog, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"Welcome to MARK {self.app_version}", style="PanelHead.TLabel").pack(anchor="w")
        ttk.Label(
            body,
            text=(
                "MARK is ready for beta setup. Start with a broad center smoke-test map "
                "to confirm the CHP polling/detail/notification path, then switch to a real "
                "station, address box, or agency service-area map before operational use."
            ),
            wraplength=590,
        ).pack(anchor="w", pady=(10, 0))
        ttk.Label(
            body,
            text="Supplemental awareness only: MARK does not replace dispatch, CAD, radio, paging, or agency procedures.",
            wraplength=590,
            style="PanelHead.TLabel",
        ).pack(anchor="w", pady=(12, 0))

        steps = ttk.LabelFrame(body, text="Suggested first-run steps", padding=10)
        steps.pack(fill="x", pady=(14, 0))
        for text in (
            "1. Pick the CHP communications center for the station, address, or agency.",
            "2. Select every CHP AREA prefix that overlaps the active map.",
            "3. Load a broad smoke-test map or build an address box map.",
            "4. Configure and test notifications.",
            "5. Save Region/Map and restart the monitor after map or AREA changes.",
        ):
            ttk.Label(steps, text=text, wraplength=560).pack(anchor="w", pady=2)

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(18, 0))
        ttk.Button(buttons, text="Open Quick Start", command=lambda: self._open_local_file(QUICK_START_GUIDE)).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Notification Settings", command=self.open_notification_settings).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Load Center Test Map", command=self.load_center_smoke_test_map).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Dismiss", command=lambda: self._dismiss_first_run_helper(dialog)).pack(side="right")

    def load_configuration(self) -> None:
        super().load_configuration()
        self._ensure_region_vars()
        self.vars["CHP_ALERT_TYPE_FRAGMENTS"].set(normalize_type_fragments(self.vars["CHP_ALERT_TYPE_FRAGMENTS"].get()))
        self._sync_center_display_from_code()
        self._sync_area_checkboxes_from_prefixes()
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

        ttk.Label(panel, textvariable=self.region_status_text, wraplength=390).pack(anchor="w", fill="x")

        row_center = ttk.Frame(panel)
        row_center.pack(fill="x", pady=(7, 0))
        ttk.Label(row_center, text="CHP center").pack(side="left")
        labels = [center_label(center) for center in self.center_options]
        combo = ttk.Combobox(row_center, textvariable=self.vars["CHP_ALERT_COMM_CENTER_DISPLAY"], values=labels, state="readonly")
        combo.pack(side="left", fill="x", expand=True, padx=(8, 0))
        combo.bind("<<ComboboxSelected>>", lambda _event: self._center_selection_changed())

        area_box = ttk.LabelFrame(panel, text="CHP AREA Prefixes", padding=8)
        area_box.pack(fill="x", pady=(9, 0))
        ttk.Label(
            area_box,
            text=(
                "Select all CHP AREA rows MARK should fetch and track inside this center. "
                "Required regional AREA prefixes are added automatically. Type fragments stay fixed."
            ),
            wraplength=390,
        ).pack(anchor="w", fill="x")
        self.area_required_text = tk.StringVar(value=self._required_area_message())
        ttk.Label(area_box, textvariable=self.area_required_text, wraplength=390).pack(anchor="w", fill="x", pady=(4, 0))

        checklist = ttk.Frame(area_box)
        checklist.pack(fill="x", pady=(7, 0))
        for index, (label, prefix) in enumerate(AREA_OPTIONS):
            var = tk.BooleanVar(value=False)
            self.area_prefix_checks[prefix] = var
            check = ttk.Checkbutton(
                checklist,
                text=f"{label} ({prefix})",
                variable=var,
                command=self._apply_area_checkbox_selection,
            )
            check.grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 16), pady=2)
        self.area_prefix_checks["*"] = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            checklist,
            text="All CHP Areas / smoke test (*)",
            variable=self.area_prefix_checks["*"],
            command=self._apply_area_checkbox_selection,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

        quick_buttons = ttk.Frame(area_box)
        quick_buttons.pack(fill="x", pady=(8, 0))
        for index, (label, prefix) in enumerate(AREA_OPTIONS):
            ttk.Button(
                quick_buttons,
                text=f"Toggle {label}",
                command=lambda p=prefix: self._toggle_area_prefix_button(p),
            ).grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 6), pady=2)
        ttk.Button(quick_buttons, text="All Areas", command=self._select_all_area_prefixes).grid(row=3, column=0, sticky="ew", padx=(0, 6), pady=2)
        ttk.Button(quick_buttons, text="Clear Optional", command=self._clear_optional_area_prefixes).grid(row=3, column=1, sticky="ew", padx=(0, 6), pady=2)
        quick_buttons.columnconfigure(0, weight=1)
        quick_buttons.columnconfigure(1, weight=1)

        row_area_value = ttk.Frame(area_box)
        row_area_value.pack(fill="x", pady=(7, 0))
        ttk.Label(row_area_value, text="Saved AREA prefixes").pack(side="left")
        ttk.Entry(row_area_value, textvariable=self.vars["CHP_ALERT_AREA_PREFIXES"]).pack(side="left", fill="x", expand=True, padx=(8, 4))
        ttk.Button(row_area_value, text="Apply Manual", command=self._manual_area_prefixes_changed).pack(side="left")
        ttk.Label(
            area_box,
            text="Examples: Sa for San Diego, El for El Cajon, Bo for Border/San Diego County region, or * for smoke testing.",
            wraplength=390,
        ).pack(anchor="w", pady=(6, 0))

        row_map = ttk.Frame(panel)
        row_map.pack(fill="x", pady=(9, 0))
        ttk.Label(row_map, text="Service-area map").pack(side="left")
        ttk.Entry(row_map, textvariable=self.vars["CHP_ALERT_SERVICE_AREA_FILE"]).pack(side="left", fill="x", expand=True, padx=(8, 4))
        ttk.Button(row_map, text="Browse", command=self.browse_service_area_map).pack(side="left")

        row_buffer = ttk.Frame(panel)
        row_buffer.pack(fill="x", pady=(7, 0))
        ttk.Label(row_buffer, text="Boundary buffer metres").pack(side="left")
        ttk.Entry(row_buffer, textvariable=self.vars["CHP_ALERT_BOUNDARY_BUFFER_METERS"], width=10).pack(side="left", padx=(8, 4))
        ttk.Label(row_buffer, text="0 = strict inside only; use a positive value to alert near-boundary calls.", wraplength=300).pack(side="left", padx=(6, 0))

        address_box = ttk.LabelFrame(panel, text="Address Box Map", padding=8)
        address_box.pack(fill="x", pady=(9, 0))
        ttk.Label(address_box, text="Generate a square service-area map centered on one address. Review the map visually before operational use.", wraplength=390).pack(anchor="w", fill="x")
        row_address = ttk.Frame(address_box)
        row_address.pack(fill="x", pady=(7, 0))
        ttk.Label(row_address, text="Address").pack(side="left")
        ttk.Entry(row_address, textvariable=self.vars["CHP_ALERT_ADDRESS_BOX_ADDRESS"]).pack(side="left", fill="x", expand=True, padx=(8, 0))
        row_size = ttk.Frame(address_box)
        row_size.pack(fill="x", pady=(7, 0))
        ttk.Label(row_size, text="Box half-size metres").pack(side="left")
        ttk.Entry(row_size, textvariable=self.vars["CHP_ALERT_ADDRESS_BOX_HALF_SIZE_METERS"], width=10).pack(side="left", padx=(8, 4))
        ttk.Button(row_size, text="Build Address Box Map", command=self.build_address_box_map).pack(side="left", padx=(6, 0))
        ttk.Label(row_size, text="Example: 3000 creates a box about 6 km wide by 6 km tall.", wraplength=250).pack(side="left", padx=(8, 0))

        row_actions = ttk.Frame(panel)
        row_actions.pack(fill="x", pady=(7, 0))
        ttk.Button(row_actions, text="Load Center Test Map", command=self.load_center_smoke_test_map).pack(side="left")
        ttk.Button(row_actions, text="Save Region/Map", command=self.save_region_map).pack(side="left", padx=(6, 0))
        ttk.Label(row_actions, text="Region/map saves clear stale dedupe state and can restart the running monitor.", wraplength=330).pack(side="left", padx=(8, 0))

        self._sync_area_checkboxes_from_prefixes()

    def _selected_center(self) -> dict[str, str]:
        return label_to_center(self.vars["CHP_ALERT_COMM_CENTER_DISPLAY"].get(), self.center_options)

    def _required_area_prefixes(self) -> tuple[str, ...]:
        return required_area_prefixes_for_center(self.vars.get("CHP_ALERT_COMM_CENTER", tk.StringVar(value=DEFAULT_CENTER_CODE)).get())

    def _required_area_message(self) -> str:
        required = self._required_area_prefixes()
        if required:
            return "Always included for this CHP center: " + ",".join(required)
        return "No required regional AREA prefix for this CHP center."

    def _sync_center_display_from_code(self) -> None:
        code = self.vars.get("CHP_ALERT_COMM_CENTER", tk.StringVar(value=DEFAULT_CENTER_CODE)).get().strip().upper()
        name = self.vars.get("CHP_ALERT_COMM_CENTER_NAME", tk.StringVar(value="")).get().strip()
        center = next((item for item in self.center_options if item["code"] == code), None)
        if center is None:
            center = {"code": code or DEFAULT_CENTER_CODE, "name": name or code or DEFAULT_CENTER_NAME}
        if name:
            center = {"code": center["code"], "name": name}
        self.vars["CHP_ALERT_COMM_CENTER_DISPLAY"].set(center_label(center))

    def _sync_area_checkboxes_from_prefixes(self) -> None:
        if not self.area_prefix_checks:
            return
        required = self._required_area_prefixes()
        normalized = normalize_area_prefixes(self.vars["CHP_ALERT_AREA_PREFIXES"].get() or DEFAULT_AREA_PREFIXES, required)
        self.vars["CHP_ALERT_AREA_PREFIXES"].set(normalized)
        star = normalized == "*"
        selected = set(_split_list(normalized))
        for prefix, var in self.area_prefix_checks.items():
            var.set(star if prefix == "*" else prefix in selected)
        if self.area_required_text is not None:
            self.area_required_text.set(self._required_area_message())

    def _apply_area_checkbox_selection(self) -> None:
        if self.area_prefix_checks.get("*") and self.area_prefix_checks["*"].get():
            self.vars["CHP_ALERT_AREA_PREFIXES"].set("*")
            self._sync_area_checkboxes_from_prefixes()
            self._refresh_region_summary()
            return
        selected = [prefix for _label, prefix in AREA_OPTIONS if self.area_prefix_checks.get(prefix) and self.area_prefix_checks[prefix].get()]
        normalized = normalize_area_prefixes(",".join(selected), self._required_area_prefixes())
        self.vars["CHP_ALERT_AREA_PREFIXES"].set(normalized)
        self._sync_area_checkboxes_from_prefixes()
        self._refresh_region_summary()

    def _toggle_area_prefix_button(self, prefix: str) -> None:
        if prefix not in self.area_prefix_checks:
            return
        if self.area_prefix_checks.get("*"):
            self.area_prefix_checks["*"].set(False)
        self.area_prefix_checks[prefix].set(not self.area_prefix_checks[prefix].get())
        self._apply_area_checkbox_selection()

    def _select_all_area_prefixes(self) -> None:
        self.vars["CHP_ALERT_AREA_PREFIXES"].set("*")
        self._sync_area_checkboxes_from_prefixes()
        self._refresh_region_summary()

    def _clear_optional_area_prefixes(self) -> None:
        normalized = normalize_area_prefixes("", self._required_area_prefixes())
        self.vars["CHP_ALERT_AREA_PREFIXES"].set(normalized)
        self._sync_area_checkboxes_from_prefixes()
        self._refresh_region_summary()

    def _manual_area_prefixes_changed(self) -> None:
        try:
            normalized = normalize_area_prefixes(self.vars["CHP_ALERT_AREA_PREFIXES"].get(), self._required_area_prefixes())
        except ValueError as exc:
            messagebox.showerror("CHP AREA prefixes", str(exc), parent=self)
            return
        self.vars["CHP_ALERT_AREA_PREFIXES"].set(normalized)
        self._sync_area_checkboxes_from_prefixes()
        self._refresh_region_summary()

    def _center_selection_changed(self) -> None:
        center = self._selected_center()
        self.vars["CHP_ALERT_COMM_CENTER"].set(center["code"])
        self.vars["CHP_ALERT_COMM_CENTER_NAME"].set(center["name"])
        self._sync_area_checkboxes_from_prefixes()
        self._refresh_region_summary()

    def _region_summary(self) -> str:
        try:
            center = label_to_center(self.vars["CHP_ALERT_COMM_CENTER_DISPLAY"].get(), self.center_options)
            map_file = self.vars["CHP_ALERT_SERVICE_AREA_FILE"].get() or "not selected"
            area = self.vars["CHP_ALERT_AREA_PREFIXES"].get() or DEFAULT_AREA_PREFIXES
            buffer_metres = self.vars.get("CHP_ALERT_BOUNDARY_BUFFER_METERS", tk.StringVar(value="0")).get() or "0"
            return f"Center: {center['name']} ({center['code']}) • Map: {Path(map_file).name} • AREA: {area} • Type fragments: fixed default • Buffer: {buffer_metres} m"
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
            filetypes=(("GeoJSON files", "*.geojson *.json"), ("All files", "*.*")),
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
                    "geometry": {"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]]},
                }
            ],
        }

    def load_center_smoke_test_map(self) -> None:
        self._center_selection_changed()
        center = self._selected_center()
        if not messagebox.askyesno(
            "Load broad test map?",
            "This will load a broad smoke-test map for the selected CHP center and set AREA=* so all listed AREA rows can test the pipeline.\n\n"
            "Alert Type fragments are not changed. This is not an operational service-area boundary. Continue?",
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
            self.vars["CHP_ALERT_BOUNDARY_BUFFER_METERS"].set("0")
            self.vars["CHP_ALERT_AREA_PREFIXES"].set("*")
            self.vars["CHP_ALERT_TYPE_FRAGMENTS"].set(normalize_type_fragments(self.vars["CHP_ALERT_TYPE_FRAGMENTS"].get()))
            self._sync_area_checkboxes_from_prefixes()
            self.map_path = path
            self.reload_map(prompt=False)
            self.save_configuration(quiet=True)
            self._backup_state_for_region_change()
            self._refresh_region_summary()
            self.append_log(f"Loaded {center['name']} smoke-test map: {path}")
            self._prompt_restart_after_region_change("Loaded center test map")
        except Exception as exc:
            messagebox.showerror("Could not load test map", str(exc), parent=self)

    def build_address_box_map(self) -> None:
        address = self.vars["CHP_ALERT_ADDRESS_BOX_ADDRESS"].get().strip()
        raw_half_size = self.vars["CHP_ALERT_ADDRESS_BOX_HALF_SIZE_METERS"].get().strip()
        try:
            half_size = address_box_runtime.parse_half_size_meters(raw_half_size)
        except address_box_runtime.AddressBoxError as exc:
            messagebox.showerror("Address box map", str(exc), parent=self)
            return
        if not address:
            messagebox.showerror("Address box map", "Enter an address before building an address box map.", parent=self)
            return
        width_km = (half_size * 2.0) / 1000.0
        if not messagebox.askyesno(
            "Build address box map?",
            f"MARK will geocode this address once and create a square map about {width_km:.2f} km wide by {width_km:.2f} km tall.\n\n"
            "Review the generated map visually and confirm the CHP AREA selections before operational use. Continue?",
            parent=self,
        ):
            return
        try:
            latitude, longitude, display_name = address_box_runtime.geocode_address(address, user_agent=f"MARK-chp-alerter/{self.app_version}")
            payload = address_box_runtime.build_address_box_geojson(
                address=address,
                latitude=latitude,
                longitude=longitude,
                half_size_meters=half_size,
                display_name=display_name,
            )
            path = address_box_runtime.generated_address_box_path(ROOT, address)
            address_box_runtime.write_address_box_geojson(path, payload)
            self.vars["CHP_ALERT_SERVICE_AREA_FILE"].set(str(path))
            self.vars["CHP_ALERT_SERVICE_AREA_LABEL"].set(f"Address box: {address}")
            self.vars["CHP_ALERT_BOUNDARY_BUFFER_METERS"].set("0")
            self.vars["CHP_ALERT_TYPE_FRAGMENTS"].set(normalize_type_fragments(self.vars["CHP_ALERT_TYPE_FRAGMENTS"].get()))
            self._sync_area_checkboxes_from_prefixes()
            self.map_path = path
            self.reload_map(prompt=False)
            self.save_configuration(quiet=True)
            self._backup_state_for_region_change()
            self._refresh_region_summary()
            self.append_log(f"Generated address box map: {path} centered at {latitude:.6f}, {longitude:.6f}")
            messagebox.showinfo(
                "Address box map loaded",
                f"Generated and loaded:\n{path}\n\nCenter:\n{display_name}\n\nConfirm the CHP AREA selections before starting the monitor.",
                parent=self,
            )
            self._prompt_restart_after_region_change("Generated address box map")
        except Exception as exc:
            messagebox.showerror("Could not build address box map", str(exc), parent=self)

    def _monitor_running(self) -> bool:
        return bool(self.process is not None and self.process.poll() is None)

    def _backup_state_for_region_change(self) -> None:
        raw_path = self.vars.get("CHP_ALERT_STATE_FILE", tk.StringVar(value="")).get().strip()
        if not raw_path:
            return
        path = Path(raw_path).expanduser()
        if not path.exists():
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"{path.name}.before-region-map-change-{stamp}.bak")
        try:
            path.replace(backup)
            self.append_log(f"Backed up and cleared stale monitor state: {backup}")
        except OSError as exc:
            messagebox.showwarning(
                "Could not clear stale state",
                f"The new region/map was saved, but MARK could not clear the old dedupe state:\n{exc}\n\nStop the monitor and delete the state file manually if stale alerts continue.",
                parent=self,
            )

    def save_region_map(self) -> bool:
        if not self.save_configuration(quiet=True):
            return False
        self._backup_state_for_region_change()
        self._refresh_region_summary()
        self._prompt_restart_after_region_change("Saved region/map")
        return True

    def _prompt_restart_after_region_change(self, action: str) -> None:
        if self._monitor_running():
            if messagebox.askyesno(
                "Restart monitor now?",
                f"{action}. The running monitor still has the old map/AREA settings in memory until it restarts.\n\nRestart it now?",
                parent=self,
            ):
                self.restart_monitor_after_region_change()
            else:
                messagebox.showwarning(
                    "Restart required",
                    "The new region/map is saved, but the current monitor process is still using the old settings. Stop and start the monitor before trusting alerts.",
                    parent=self,
                )
        else:
            messagebox.showinfo(
                "Region/map saved",
                f"{action}. Start the monitor to use the new map and AREA settings.",
                parent=self,
            )

    def restart_monitor_after_region_change(self) -> None:
        if not self._monitor_running():
            self.start_monitor()
            return
        self.append_log("Restarting monitor to apply region/map changes")
        self.stop_monitor()
        self.after(650, self._start_monitor_when_stopped)

    def _start_monitor_when_stopped(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.after(650, self._start_monitor_when_stopped)
            return
        self.start_monitor()

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
        required = required_area_prefixes_for_center(center["code"])
        values["CHP_ALERT_AREA_PREFIXES"] = normalize_area_prefixes(values.get("CHP_ALERT_AREA_PREFIXES", DEFAULT_AREA_PREFIXES), required)
        values["CHP_ALERT_TYPE_FRAGMENTS"] = normalize_type_fragments(values.get("CHP_ALERT_TYPE_FRAGMENTS", ""))
        self.vars["CHP_ALERT_AREA_PREFIXES"].set(values["CHP_ALERT_AREA_PREFIXES"])
        self.vars["CHP_ALERT_TYPE_FRAGMENTS"].set(values["CHP_ALERT_TYPE_FRAGMENTS"])
        self._sync_area_checkboxes_from_prefixes()

        raw_buffer = values.get("CHP_ALERT_BOUNDARY_BUFFER_METERS", "0").strip() or "0"
        try:
            buffer_value = float(raw_buffer)
        except ValueError as exc:
            raise ValueError("Boundary buffer metres must be a number, for example 0 or 12000.") from exc
        if buffer_value < 0:
            raise ValueError("Boundary buffer metres cannot be negative.")
        values["CHP_ALERT_BOUNDARY_BUFFER_METERS"] = str(int(buffer_value)) if buffer_value.is_integer() else str(buffer_value)

        address = values.get("CHP_ALERT_ADDRESS_BOX_ADDRESS", "").strip()
        half_size = values.get("CHP_ALERT_ADDRESS_BOX_HALF_SIZE_METERS", "").strip()
        if half_size:
            try:
                parsed_half_size = address_box_runtime.parse_half_size_meters(half_size)
            except address_box_runtime.AddressBoxError as exc:
                raise ValueError(str(exc)) from exc
            values["CHP_ALERT_ADDRESS_BOX_HALF_SIZE_METERS"] = str(int(parsed_half_size)) if parsed_half_size.is_integer() else str(parsed_half_size)
        values["CHP_ALERT_ADDRESS_BOX_ADDRESS"] = address
        return values

    def save_configuration(self, quiet: bool = False) -> bool:
        ok = super().save_configuration(quiet=quiet)
        if ok:
            self._sync_center_display_from_code()
            self._sync_area_checkboxes_from_prefixes()
            self._refresh_region_summary()
        return ok

    def _write_full_env(self, values: dict[str, str]) -> None:
        super()._write_full_env(values)
        with mark_app.ENV_FILE.open("a", encoding="utf-8") as handle:
            handle.write("\n# CHP communications center\n")
            handle.write(f"CHP_ALERT_COMM_CENTER={values.get('CHP_ALERT_COMM_CENTER', DEFAULT_CENTER_CODE)}\n")
            handle.write(f"CHP_ALERT_COMM_CENTER_NAME={values.get('CHP_ALERT_COMM_CENTER_NAME', DEFAULT_CENTER_NAME)}\n")
            handle.write("\n# Boundary buffer / near-boundary alerts\n")
            handle.write(f"CHP_ALERT_BOUNDARY_BUFFER_METERS={values.get('CHP_ALERT_BOUNDARY_BUFFER_METERS', '0')}\n")
            handle.write("\n# Address box map helper\n")
            handle.write(f"CHP_ALERT_ADDRESS_BOX_ADDRESS={values.get('CHP_ALERT_ADDRESS_BOX_ADDRESS', '')}\n")
            handle.write(f"CHP_ALERT_ADDRESS_BOX_HALF_SIZE_METERS={values.get('CHP_ALERT_ADDRESS_BOX_HALF_SIZE_METERS', str(int(address_box_runtime.DEFAULT_HALF_SIZE_METERS)))}\n")


def main() -> int:
    try:
        RegionMarkApp().mainloop()
        return 0
    except Exception:
        mark_gui_entry.report_startup_failure()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
