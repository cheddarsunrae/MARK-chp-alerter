#!/usr/bin/env python3
"""MARK cross-platform desktop dashboard.

The existing CHP monitor remains the backend. This module provides the branded
Windows/Fedora controller, live log, configuration editor, and GeoJSON editor
with an OpenStreetMap road basemap when tkintermapview is installed.
"""
from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover
    Image = ImageTk = None

try:
    import tkintermapview
except ImportError:  # pragma: no cover
    tkintermapview = None

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
BACKEND = ROOT / "chp_detail_alert.py"
DEFAULT_MAP = ROOT / "service_area.geojson"
APP_TITLE = "MARK — CHP Alerting & Monitoring Tool"
COLORS = {
    "bg": "#071527", "panel": "#0b1c30", "panel2": "#10243b",
    "border": "#27415d", "text": "#edf3f8", "muted": "#aebdcb",
    "gold": "#ffc43d", "green": "#65c83b", "red": "#d83a32",
    "blue": "#16558a", "log": "#06111f",
}
SOUNDS = ("alien", "climb", "echo", "updown", "persistent", "siren", "spacealarm", "tugboat", "bugle", "incoming", "mechanical", "pushover")


def default_data_dir() -> Path:
    if os.name == "nt" and os.getenv("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "CHPAlerter"
    return Path.home() / ".local" / "state" / "chp-alerter"


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_env(path: Path, values: dict[str, str]) -> None:
    groups = (
        ("Polling and state", ("CHP_ALERT_INTERVAL", "CHP_ALERT_TIMEOUT", "CHP_ALERT_STATE_FILE", "CHP_ALERT_DETAIL_LOG_FILE", "CHP_ALERT_SERVICE_AREA_FILE", "CHP_ALERT_RETENTION_HOURS", "CHP_ALERT_LOG_LEVEL")),
        ("Geocoding", ("CHP_ALERT_GEOCODER", "CHP_ALERT_CONTACT")),
        ("Startup and updates", ("CHP_ALERT_EXISTING", "CHP_ALERT_UPDATES")),
        ("Pushover", ("PUSHOVER_APP_TOKEN", "PUSHOVER_USER_KEY", "PUSHOVER_PRIORITY", "PUSHOVER_RETRY_SECONDS", "PUSHOVER_EXPIRE_SECONDS", "PUSHOVER_SOUND")),
    )
    lines: list[str] = []
    for title, keys in groups:
        lines.append(f"# {title}")
        lines.extend(f"{key}={values[key]}" for key in keys)
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def load_polygon(path: Path) -> tuple[dict, list[tuple[float, float]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", []) if payload.get("type") == "FeatureCollection" else [payload]
    for feature in features:
        geometry = feature.get("geometry", {})
        if geometry.get("type") == "Polygon":
            ring = geometry.get("coordinates", [[]])[0]
            points = [(float(lat), float(lon)) for lon, lat in ring]
            if points and points[0] == points[-1]:
                points.pop()
            if len(points) < 3:
                break
            return payload, points
    raise ValueError("GeoJSON does not contain a polygon with at least three vertices")


def replace_polygon(payload: dict, points: list[tuple[float, float]]) -> dict:
    if len(points) < 3:
        raise ValueError("A service area requires at least three vertices")
    ring = [[lon, lat] for lat, lon in points]
    ring.append(ring[0])
    features = payload.get("features", []) if payload.get("type") == "FeatureCollection" else [payload]
    for feature in features:
        geometry = feature.get("geometry", {})
        if geometry.get("type") == "Polygon":
            geometry["coordinates"] = [ring]
            return payload
    raise ValueError("No Polygon feature found")


class MarkApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1500x900")
        self.minsize(1120, 700)
        self.configure(bg=COLORS["bg"])
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.process: subprocess.Popen[str] | None = None
        self.output_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.vars: dict[str, tk.StringVar] = {}
        self.status = tk.StringVar(value="STOPPED")
        self.last_poll = tk.StringVar(value="Never")
        self.latest_summary = tk.StringVar(value="No poll completed yet")
        self.started_at: datetime | None = None
        self.map_path = DEFAULT_MAP
        self.map_payload: dict = {}
        self.map_points: list[tuple[float, float]] = []
        self.map_polygon = None
        self.map_markers: list = []
        self.logo_image = None

        self._style()
        self._build()
        self.load_configuration()
        self.reload_map(prompt=False)
        self.after(100, self._drain_output)
        self.after(1000, self._tick)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=COLORS["bg"], foreground=COLORS["text"], fieldbackground=COLORS["panel2"], bordercolor=COLORS["border"], font=("Segoe UI", 10))
        style.configure("Panel.TFrame", background=COLORS["panel"], relief="solid", borderwidth=1)
        style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["gold"], font=("Segoe UI", 27, "bold"))
        style.configure("Subtitle.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI", 14, "bold"))
        style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"])
        style.configure("Card.TFrame", background=COLORS["panel"], relief="solid", borderwidth=1)
        style.configure("CardHead.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 9, "bold"))
        style.configure("CardValue.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI", 13, "bold"))
        style.configure("PanelHead.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI", 12, "bold"))
        style.configure("TButton", background=COLORS["blue"], foreground="white", padding=(12, 8), borderwidth=0)
        style.map("TButton", background=[("active", "#1f6da7"), ("disabled", "#33485c")])
        style.configure("Start.TButton", background="#2f8b35", font=("Segoe UI", 10, "bold"))
        style.map("Start.TButton", background=[("active", "#3aa444")])
        style.configure("Stop.TButton", background=COLORS["red"], font=("Segoe UI", 10, "bold"))
        style.map("Stop.TButton", background=[("active", "#ed4a41")])
        style.configure("TEntry", padding=7)
        style.configure("TCombobox", padding=7)

    def _build(self) -> None:
        root = ttk.Frame(self, style="Panel.TFrame", padding=14)
        root.pack(fill="both", expand=True)
        self._build_header(root)
        self._build_toolbar(root)

        panes = ttk.Panedwindow(root, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(10, 8))
        log_panel = ttk.Frame(panes, style="Panel.TFrame", padding=10)
        config_panel = ttk.Frame(panes, style="Panel.TFrame", padding=10)
        map_panel = ttk.Frame(panes, style="Panel.TFrame", padding=10)
        panes.add(log_panel, weight=3)
        panes.add(config_panel, weight=2)
        panes.add(map_panel, weight=4)
        self._build_log(log_panel)
        self._build_config(config_panel)
        self._build_map(map_panel)

        footer = ttk.Frame(root, style="Panel.TFrame", padding=(12, 8))
        footer.pack(fill="x")
        self.footer_status = ttk.Label(footer, text="● STOPPED", style="PanelHead.TLabel")
        self.footer_status.pack(side="left")
        self.footer_detail = ttk.Label(footer, text="Poll interval: 65 sec", style="PanelHead.TLabel")
        self.footer_detail.pack(side="left", padx=25)
        self.footer_uptime = ttk.Label(footer, text="Uptime: 00:00:00", style="PanelHead.TLabel")
        self.footer_uptime.pack(side="right")

    def _load_logo(self, parent: tk.Widget) -> None:
        candidates = (ROOT / "assets" / "mark_logo.png", ROOT / "Mark Logo.png", ROOT / "mark_logo_ui.png")
        path = next((item for item in candidates if item.exists()), None)
        if not path or Image is None:
            ttk.Label(parent, text="MARK", style="Title.TLabel").pack(side="left", padx=(0, 18))
            return
        try:
            image = Image.open(path).convert("RGBA")
            image.thumbnail((250, 150), Image.Resampling.LANCZOS)
            self.logo_image = ImageTk.PhotoImage(image)
            tk.Label(parent, image=self.logo_image, bg=COLORS["bg"], bd=0).pack(side="left", padx=(0, 18))
        except Exception:
            ttk.Label(parent, text="MARK", style="Title.TLabel").pack(side="left", padx=(0, 18))

    def _build_header(self, root: ttk.Frame) -> None:
        header = ttk.Frame(root)
        header.pack(fill="x")
        brand = ttk.Frame(header)
        brand.pack(side="left", fill="x", expand=True)
        self._load_logo(brand)
        words = ttk.Frame(brand)
        words.pack(side="left", anchor="center")
        ttk.Label(words, text="MARK", style="Title.TLabel").pack(anchor="w")
        ttk.Label(words, text="CHP Alerting & Monitoring Tool", style="Subtitle.TLabel").pack(anchor="w")
        ttk.Label(words, text="Real-time CHP incident monitoring and map-aware notifications.", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

        cards = ttk.Frame(header)
        cards.pack(side="right")
        self.status_card_value = self._card(cards, "STATUS", self.status)
        self._card(cards, "LAST POLL", self.last_poll)
        self._card(cards, "LATEST SUMMARY", self.latest_summary, width=28)

    def _card(self, parent: ttk.Frame, heading: str, variable: tk.StringVar, width: int = 18) -> ttk.Label:
        card = ttk.Frame(parent, style="Card.TFrame", padding=11)
        card.pack(side="left", padx=5, fill="y")
        ttk.Label(card, text=heading, style="CardHead.TLabel").pack(anchor="w")
        label = ttk.Label(card, textvariable=variable, style="CardValue.TLabel", width=width, wraplength=230)
        label.pack(anchor="w", pady=(6, 0))
        return label

    def _build_toolbar(self, root: ttk.Frame) -> None:
        bar = ttk.Frame(root, style="Panel.TFrame", padding=8)
        bar.pack(fill="x", pady=(12, 0))
        self.start_button = ttk.Button(bar, text="▶  Start Monitor", style="Start.TButton", command=self.start_monitor)
        self.start_button.pack(side="left", fill="x", expand=True, padx=4)
        self.stop_button = ttk.Button(bar, text="■  Stop", style="Stop.TButton", command=self.stop_monitor, state="disabled")
        self.stop_button.pack(side="left", fill="x", expand=True, padx=4)
        for text, command in (("➤  Test Pushover", self.test_pushover), ("☁  One Poll (Dry Run)", self.run_dry_poll), ("↻  Reload Config", self.reload_config), ("▣  Reload Map", self.reload_map)):
            ttk.Button(bar, text=text, command=command).pack(side="left", fill="x", expand=True, padx=4)

    def _build_log(self, frame: ttk.Frame) -> None:
        head = ttk.Frame(frame, style="Panel.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="▤  Live Log", style="PanelHead.TLabel").pack(side="left")
        ttk.Button(head, text="Clear", command=self.clear_log).pack(side="right")
        self.log = tk.Text(frame, bg=COLORS["log"], fg=COLORS["text"], insertbackground="white", relief="flat", wrap="word", font=("Consolas", 9), state="disabled")
        self.log.pack(fill="both", expand=True, pady=(8, 6))
        self.log.tag_configure("info", foreground="#76d13b")
        self.log.tag_configure("warn", foreground=COLORS["gold"])
        self.log.tag_configure("error", foreground="#ff6b63")
        ttk.Button(frame, text="Open Detail Log", command=self.open_detail_log).pack(anchor="w")

    def _defaults(self) -> dict[str, str]:
        data = default_data_dir()
        return {
            "PUSHOVER_APP_TOKEN": "", "PUSHOVER_USER_KEY": "", "PUSHOVER_SOUND": "alien",
            "PUSHOVER_PRIORITY": "2", "PUSHOVER_RETRY_SECONDS": "30", "PUSHOVER_EXPIRE_SECONDS": "1800",
            "CHP_ALERT_INTERVAL": "65", "CHP_ALERT_TIMEOUT": "20", "CHP_ALERT_CONTACT": "mailto:you@example.com",
            "CHP_ALERT_STATE_FILE": str(data / "state.json"), "CHP_ALERT_DETAIL_LOG_FILE": str(data / "details.jsonl"),
            "CHP_ALERT_SERVICE_AREA_FILE": str(DEFAULT_MAP), "CHP_ALERT_RETENTION_HOURS": "72",
            "CHP_ALERT_LOG_LEVEL": "INFO", "CHP_ALERT_GEOCODER": "nominatim", "CHP_ALERT_EXISTING": "0", "CHP_ALERT_UPDATES": "0",
        }

    def _build_config(self, frame: ttk.Frame) -> None:
        head = ttk.Frame(frame, style="Panel.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="⚙  Configuration", style="PanelHead.TLabel").pack(side="left")
        ttk.Button(head, text="Save", command=self.save_configuration).pack(side="right")
        body = ttk.Frame(frame, style="Panel.TFrame")
        body.pack(fill="both", expand=True, pady=(8, 0))
        fields = (
            ("PUSHOVER_APP_TOKEN", "Pushover Token", "secret"), ("PUSHOVER_USER_KEY", "Pushover User Key", "secret"),
            ("PUSHOVER_SOUND", "Sound", "sound"), ("CHP_ALERT_INTERVAL", "Poll Interval (sec)", "text"),
            ("CHP_ALERT_STATE_FILE", "State File", "file"), ("CHP_ALERT_DETAIL_LOG_FILE", "Detail Log File", "file"),
            ("CHP_ALERT_SERVICE_AREA_FILE", "Service Area File", "map"), ("CHP_ALERT_CONTACT", "Nominatim Contact", "text"),
        )
        defaults = self._defaults()
        for row, (key, label, kind) in enumerate(fields):
            ttk.Label(body, text=label, style="PanelHead.TLabel").grid(row=row, column=0, sticky="w", pady=6)
            var = tk.StringVar(value=defaults[key]); self.vars[key] = var
            if kind == "sound":
                widget = ttk.Combobox(body, textvariable=var, values=SOUNDS, state="readonly")
            else:
                widget = ttk.Entry(body, textvariable=var, show="•" if kind == "secret" else "")
            widget.grid(row=row, column=1, sticky="ew", padx=(10, 5), pady=6)
            if kind in {"file", "map"}:
                ttk.Button(body, text="…", width=3, command=lambda k=key, m=(kind == "map"): self.choose_path(k, m)).grid(row=row, column=2, pady=6)
        for key in ("PUSHOVER_PRIORITY", "PUSHOVER_RETRY_SECONDS", "PUSHOVER_EXPIRE_SECONDS", "CHP_ALERT_TIMEOUT", "CHP_ALERT_RETENTION_HOURS", "CHP_ALERT_LOG_LEVEL", "CHP_ALERT_GEOCODER", "CHP_ALERT_EXISTING", "CHP_ALERT_UPDATES"):
            self.vars[key] = tk.StringVar(value=defaults[key])
        body.columnconfigure(1, weight=1)
        ttk.Button(frame, text="Reload .env", command=self.reload_config).pack(anchor="w", pady=(10, 0))

    def _build_map(self, frame: ttk.Frame) -> None:
        head = ttk.Frame(frame, style="Panel.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="▣  Map Editor", style="PanelHead.TLabel").pack(side="left")
        ttk.Button(head, text="Reset", command=self.reload_map).pack(side="right", padx=3)
        ttk.Button(head, text="Save As", command=lambda: self.save_map(save_as=True)).pack(side="right", padx=3)
        ttk.Button(head, text="Save Map", command=self.save_map).pack(side="right", padx=3)

        if tkintermapview:
            self.map_widget = tkintermapview.TkinterMapView(frame, corner_radius=0)
            self.map_widget.pack(fill="both", expand=True, pady=(8, 6))
            self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png", max_zoom=19)
            self.map_widget.add_left_click_map_command(self._map_click)
            self.map_notice = ttk.Label(frame, text="Click the road map to add a vertex. Use Delete Last to remove the newest vertex.", style="PanelHead.TLabel")
        else:
            self.map_widget = tk.Canvas(frame, bg="#d9d3c7", highlightthickness=0)
            self.map_widget.pack(fill="both", expand=True, pady=(8, 6))
            self.map_widget.create_text(20, 20, anchor="nw", text="Install tkintermapview for the road basemap", fill="#111827", font=("Segoe UI", 13, "bold"))
            self.map_notice = ttk.Label(frame, text="Basemap unavailable; polygon can still be loaded and saved.", style="PanelHead.TLabel")
        self.map_notice.pack(anchor="w")
        controls = ttk.Frame(frame, style="Panel.TFrame")
        controls.pack(fill="x", pady=(4, 0))
        ttk.Button(controls, text="Delete Last Vertex", command=self.delete_last_vertex).pack(side="left")
        self.map_stats = ttk.Label(controls, text="0 vertices", style="PanelHead.TLabel")
        self.map_stats.pack(side="right")

    def append_log(self, text: str) -> None:
        tag = "error" if " ERROR " in text or "failed" in text.lower() else "warn" if " WARNING " in text or "alert" in text.lower() else "info"
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self) -> None:
        self.log.configure(state="normal"); self.log.delete("1.0", "end"); self.log.configure(state="disabled")

    def load_configuration(self) -> None:
        values = self._defaults(); values.update(parse_env(ENV_FILE))
        if os.name == "nt":
            data = default_data_dir()
            for key, filename in (("CHP_ALERT_STATE_FILE", "state.json"), ("CHP_ALERT_DETAIL_LOG_FILE", "details.jsonl")):
                if values[key].startswith(("/var/", "/home/")):
                    values[key] = str(data / filename)
        for key, var in self.vars.items():
            var.set(values.get(key, var.get()))
        self.map_path = Path(values.get("CHP_ALERT_SERVICE_AREA_FILE", str(DEFAULT_MAP))).expanduser()
        self.append_log(f"[{datetime.now():%H:%M:%S}] Loaded configuration from {ENV_FILE}")

    def reload_config(self) -> None:
        self.load_configuration()
        if self.process and self.process.poll() is None:
            messagebox.showinfo("Restart required", "Configuration reloaded. Restart the monitor to apply it.", parent=self)

    def collect_configuration(self) -> dict[str, str]:
        values = {key: var.get().strip() for key, var in self.vars.items()}
        if not values["PUSHOVER_APP_TOKEN"] or not values["PUSHOVER_USER_KEY"]:
            raise ValueError("Enter both Pushover credentials")
        if float(values["CHP_ALERT_INTERVAL"]) < 60:
            raise ValueError("Poll interval must be at least 60 seconds")
        if int(values["PUSHOVER_PRIORITY"]) == 2 and int(values["PUSHOVER_RETRY_SECONDS"]) < 30:
            raise ValueError("Priority 2 retry must be at least 30 seconds")
        for key in ("CHP_ALERT_STATE_FILE", "CHP_ALERT_DETAIL_LOG_FILE"):
            Path(values[key]).expanduser().parent.mkdir(parents=True, exist_ok=True)
        return values

    def save_configuration(self, quiet: bool = False) -> bool:
        try:
            values = self.collect_configuration(); write_env(ENV_FILE, values)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Configuration error", str(exc), parent=self); return False
        self.append_log(f"[{datetime.now():%H:%M:%S}] Saved configuration")
        if not quiet: messagebox.showinfo("Saved", "Configuration saved.", parent=self)
        return True

    def choose_path(self, key: str, is_map: bool) -> None:
        selected = filedialog.askopenfilename(parent=self, filetypes=[("GeoJSON", "*.geojson *.json"), ("All files", "*.*")]) if is_map else filedialog.asksaveasfilename(parent=self)
        if selected:
            self.vars[key].set(selected)
            if is_map:
                self.map_path = Path(selected); self.reload_map(prompt=False)

    def _map_click(self, coords: tuple[float, float]) -> None:
        self.map_points.append((float(coords[0]), float(coords[1])))
        self._draw_polygon()

    def delete_last_vertex(self) -> None:
        if self.map_points:
            self.map_points.pop(); self._draw_polygon()

    def reload_map(self, prompt: bool = True) -> None:
        try:
            path = Path(self.vars.get("CHP_ALERT_SERVICE_AREA_FILE", tk.StringVar(value=str(self.map_path))).get()).expanduser()
            self.map_payload, self.map_points = load_polygon(path)
            self.map_path = path
            self._draw_polygon()
            self.append_log(f"[{datetime.now():%H:%M:%S}] Loaded map {path} ({len(self.map_points)} vertices)")
            if prompt and self.process and self.process.poll() is None:
                messagebox.showinfo("Restart required", "Map reloaded. Restart the monitor to apply it.", parent=self)
        except Exception as exc:
            messagebox.showerror("Map error", str(exc), parent=self)

    def _draw_polygon(self) -> None:
        self.map_stats.configure(text=f"{len(self.map_points)} vertices")
        if not tkintermapview or not hasattr(self, "map_widget"):
            return
        try:
            if self.map_polygon: self.map_polygon.delete()
            for marker in self.map_markers: marker.delete()
        except Exception:
            pass
        self.map_markers = []
        if self.map_points:
            self.map_widget.set_position(*self.map_points[0]); self.map_widget.set_zoom(11)
        if len(self.map_points) >= 3:
            self.map_polygon = self.map_widget.set_polygon(self.map_points, fill_color="#d99b20", outline_color="#ffc43d", border_width=3)
        for index, point in enumerate(self.map_points, start=1):
            self.map_markers.append(self.map_widget.set_marker(*point, text=str(index), marker_color_circle="#ffc43d", marker_color_outside="#13243a"))

    def save_map(self, save_as: bool = False) -> None:
        try:
            payload = replace_polygon(self.map_payload, self.map_points)
            path = self.map_path
            if save_as:
                selected = filedialog.asksaveasfilename(parent=self, defaultextension=".geojson", filetypes=[("GeoJSON", "*.geojson"), ("JSON", "*.json")])
                if not selected: return
                path = Path(selected)
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            self.map_path = path; self.vars["CHP_ALERT_SERVICE_AREA_FILE"].set(str(path))
            self.save_configuration(quiet=True)
            self.append_log(f"[{datetime.now():%H:%M:%S}] Saved map {path}")
        except Exception as exc:
            messagebox.showerror("Save map failed", str(exc), parent=self)

    def process_environment(self) -> dict[str, str]:
        env = os.environ.copy(); env.update(self.collect_configuration()); env["PYTHONUNBUFFERED"] = "1"; return env

    def launch(self, arguments: list[str], mode: str) -> None:
        if self.process is not None and self.process.poll() is None:
            messagebox.showwarning("Already running", "A monitor or test process is already running.", parent=self); return
        self.process = None
        if not self.save_configuration(quiet=True): return
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        try:
            self.process = subprocess.Popen([sys.executable, "-u", str(BACKEND), *arguments], cwd=ROOT, env=self.process_environment(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=flags)
        except OSError as exc:
            messagebox.showerror("Launch failed", str(exc), parent=self); return
        self.status.set(mode); self.started_at = datetime.now(); self.start_button.configure(state="disabled"); self.stop_button.configure(state="normal")
        self.append_log(f"[{datetime.now():%H:%M:%S}] Started {' '.join(arguments) or 'monitor'}")
        threading.Thread(target=self._read_process, args=(self.process,), daemon=True).start()

    def _read_process(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for line in process.stdout: self.output_queue.put(("line", line.rstrip()))
        self.output_queue.put(("exit", str(process.wait())))

    def _drain_output(self) -> None:
        try:
            while True:
                kind, payload = self.output_queue.get_nowait()
                if kind == "line":
                    self.append_log(payload)
                    if "Parsed " in payload and "Border incidents" in payload:
                        self.last_poll.set(datetime.now().strftime("%I:%M:%S %p")); self.latest_summary.set(payload.split(": ", 1)[-1])
                else:
                    self.append_log(f"Process exited with code {payload}"); self.process = None; self.status.set("STOPPED" if payload == "0" else "ERROR"); self.start_button.configure(state="normal"); self.stop_button.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._drain_output)

    def _tick(self) -> None:
        running = self.process is not None and self.process.poll() is None
        status = self.status.get(); self.footer_status.configure(text=f"● {status}", foreground=COLORS["green"] if running else COLORS["red"])
        self.footer_detail.configure(text=f"Poll interval: {self.vars.get('CHP_ALERT_INTERVAL', tk.StringVar(value='65')).get()} sec")
        if running and self.started_at:
            seconds = int((datetime.now() - self.started_at).total_seconds()); self.footer_uptime.configure(text=f"Uptime: {seconds//3600:02}:{seconds%3600//60:02}:{seconds%60:02}")
        self.after(1000, self._tick)

    def start_monitor(self) -> None: self.launch([], "RUNNING")
    def run_dry_poll(self) -> None: self.launch(["--once", "--dry-run", "--alert-existing", "--log-level", "DEBUG"], "DRY RUN")
    def test_pushover(self) -> None:
        if messagebox.askyesno("Test Pushover", f"Send a priority-{self.vars['PUSHOVER_PRIORITY'].get()} test using {self.vars['PUSHOVER_SOUND'].get()}?", parent=self): self.launch(["--test-pushover"], "TESTING")

    def stop_monitor(self) -> None:
        process = self.process
        if not process or process.poll() is not None: return
        self.status.set("STOPPING")
        try:
            process.send_signal(signal.CTRL_BREAK_EVENT) if os.name == "nt" else process.terminate()
        except (OSError, ValueError): process.terminate()
        self.after(4000, self._force_stop)

    def _force_stop(self) -> None:
        if self.process and self.process.poll() is None: self.process.kill(); self.append_log("Backend was force-stopped")

    def open_detail_log(self) -> None:
        path = Path(self.vars["CHP_ALERT_DETAIL_LOG_FILE"].get()).expanduser()
        if not path.exists(): messagebox.showinfo("No detail log", f"No log exists yet:\n{path}", parent=self); return
        try:
            if os.name == "nt": os.startfile(path)  # type: ignore[attr-defined]
            else: subprocess.Popen(["xdg-open", str(path)])
        except OSError as exc: messagebox.showerror("Open failed", str(exc), parent=self)

    def on_close(self) -> None:
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("Exit MARK", "Stop the monitor and exit?", parent=self): return
            self.stop_monitor()
        self.destroy()


def main() -> int:
    MarkApp().mainloop(); return 0
