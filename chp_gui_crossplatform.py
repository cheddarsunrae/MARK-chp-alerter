#!/usr/bin/env python3
"""Cross-platform desktop controller for CHP Alerter."""

from __future__ import annotations

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

from service_area_runtime import ServiceAreaError, load_service_area

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
BACKEND = ROOT / "chp_crossplatform.py"
EDITOR = ROOT / "service_area_editor.py"
DEFAULT_MAP = ROOT / "service_area.geojson"
APP_TITLE = "CHP Alerter — Station 36"
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
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_env(path: Path, values: dict[str, str]) -> None:
    groups = [
        ("# Polling and state", ("CHP_ALERT_INTERVAL", "CHP_ALERT_TIMEOUT", "CHP_ALERT_STATE_FILE", "CHP_ALERT_DETAIL_LOG_FILE", "CHP_ALERT_RETENTION_HOURS", "CHP_ALERT_LOG_LEVEL")),
        ("# Service-area GeoJSON", ("CHP_ALERT_SERVICE_AREA_FILE",)),
        ("# Geocoding", ("CHP_ALERT_GEOCODER", "CHP_ALERT_CONTACT")),
        ("# Startup and update behaviour", ("CHP_ALERT_EXISTING", "CHP_ALERT_UPDATES")),
        ("# Pushover", ("PUSHOVER_APP_TOKEN", "PUSHOVER_USER_KEY", "PUSHOVER_PRIORITY", "PUSHOVER_RETRY_SECONDS", "PUSHOVER_EXPIRE_SECONDS", "PUSHOVER_SOUND")),
    ]
    lines: list[str] = []
    for heading, keys in groups:
        if lines:
            lines.append("")
        lines.append(heading)
        lines.extend(f"{key}={values[key]}" for key in keys)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class Controller(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1120x800")
        self.minsize(900, 640)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.process: subprocess.Popen[str] | None = None
        self.output: queue.Queue[tuple[str, str]] = queue.Queue()
        self.vars: dict[str, tk.StringVar] = {}
        self.status = tk.StringVar(value="STOPPED")
        self.last_poll = tk.StringVar(value="Never")
        self.last_summary = tk.StringVar(value="No poll completed yet")
        self.map_summary = tk.StringVar(value="Map not loaded")
        self._build_ui()
        self.reload_configuration(restart=False, quiet=True)
        self.after(100, self._drain_output)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text=APP_TITLE, font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Label(header, textvariable=self.status, font=("Segoe UI", 12, "bold")).pack(side="right")

        controls = ttk.Frame(outer, padding=(0, 10, 0, 8))
        controls.pack(fill="x")
        self.start_button = ttk.Button(controls, text="START MONITOR", command=self.start_monitor)
        self.start_button.pack(side="left", padx=(0, 6))
        self.stop_button = ttk.Button(controls, text="STOP", command=self.stop_monitor, state="disabled")
        self.stop_button.pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Test Pushover", command=self.test_pushover).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="One Poll (Dry Run)", command=self.dry_poll).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Reload Config", command=self.reload_configuration).pack(side="left", padx=(12, 6))
        ttk.Button(controls, text="Reload Map", command=self.reload_map).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Edit Map", command=self.edit_map).pack(side="left")

        summary = ttk.LabelFrame(outer, text="Monitor status", padding=8)
        summary.pack(fill="x", pady=(0, 8))
        ttk.Label(summary, text="Last successful poll:").grid(row=0, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.last_poll).grid(row=0, column=1, sticky="w", padx=(8, 25))
        ttk.Label(summary, text="Latest summary:").grid(row=1, column=0, sticky="nw")
        ttk.Label(summary, textvariable=self.last_summary, wraplength=820).grid(row=1, column=1, sticky="w", padx=(8, 0))
        ttk.Label(summary, text="Service area:").grid(row=2, column=0, sticky="nw")
        ttk.Label(summary, textvariable=self.map_summary, wraplength=820).grid(row=2, column=1, sticky="w", padx=(8, 0))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        live = ttk.Frame(notebook, padding=8)
        settings = ttk.Frame(notebook, padding=10)
        notebook.add(live, text="Live log")
        notebook.add(settings, text="Configuration")

        self.log = tk.Text(live, wrap="word", state="disabled", font=("Consolas", 9), background="#101418", foreground="#e8edf2")
        scroll = ttk.Scrollbar(live, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._build_settings(settings)

    def _build_settings(self, frame: ttk.Frame) -> None:
        data = default_data_dir()
        fields = [
            ("PUSHOVER_APP_TOKEN", "Pushover application token", "", True),
            ("PUSHOVER_USER_KEY", "Pushover user/group key", "", True),
            ("PUSHOVER_SOUND", "Alert sound", "alien", False),
            ("PUSHOVER_PRIORITY", "Priority", "2", False),
            ("PUSHOVER_RETRY_SECONDS", "Emergency retry seconds", "30", False),
            ("PUSHOVER_EXPIRE_SECONDS", "Emergency expiry seconds", "1800", False),
            ("CHP_ALERT_INTERVAL", "Poll interval seconds", "65", False),
            ("CHP_ALERT_TIMEOUT", "HTTP timeout seconds", "20", False),
            ("CHP_ALERT_CONTACT", "Nominatim contact", "mailto:you@example.com", False),
            ("CHP_ALERT_STATE_FILE", "State file", str(data / "state.json"), False),
            ("CHP_ALERT_DETAIL_LOG_FILE", "Detail log", str(data / "details.jsonl"), False),
            ("CHP_ALERT_SERVICE_AREA_FILE", "Service-area GeoJSON", str(DEFAULT_MAP), False),
        ]
        for row, (key, label, default, secret) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=default)
            self.vars[key] = var
            if key == "PUSHOVER_SOUND":
                widget = ttk.Combobox(frame, textvariable=var, values=SOUNDS, state="readonly", width=44)
            elif key == "PUSHOVER_PRIORITY":
                widget = ttk.Combobox(frame, textvariable=var, values=("-2", "-1", "0", "1", "2"), state="readonly", width=44)
            else:
                widget = ttk.Entry(frame, textvariable=var, width=78, show="•" if secret else "")
            widget.grid(row=row, column=1, sticky="ew", padx=(10, 5), pady=4)
            if key == "CHP_ALERT_SERVICE_AREA_FILE":
                ttk.Button(frame, text="Browse…", command=self.choose_map).grid(row=row, column=2, padx=(4, 0))
            elif key == "CHP_ALERT_DETAIL_LOG_FILE":
                ttk.Button(frame, text="Open", command=self.open_detail_log).grid(row=row, column=2, padx=(4, 0))

        defaults = {
            "CHP_ALERT_RETENTION_HOURS": "72",
            "CHP_ALERT_LOG_LEVEL": "INFO",
            "CHP_ALERT_GEOCODER": "nominatim",
            "CHP_ALERT_EXISTING": "0",
            "CHP_ALERT_UPDATES": "0",
        }
        for key, value in defaults.items():
            self.vars[key] = tk.StringVar(value=value)

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(fields), column=0, columnspan=3, sticky="w", pady=(14, 0))
        ttk.Button(buttons, text="Save Configuration", command=self.save_configuration).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Reload from .env", command=self.reload_configuration).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Validate Map", command=self.validate_map).pack(side="left")
        frame.columnconfigure(1, weight=1)

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def collect_configuration(self) -> dict[str, str]:
        values = {key: var.get().strip() for key, var in self.vars.items()}
        if not values["PUSHOVER_APP_TOKEN"] or not values["PUSHOVER_USER_KEY"]:
            raise ValueError("Enter both Pushover credentials.")
        priority = int(values["PUSHOVER_PRIORITY"])
        if priority == 2 and int(values["PUSHOVER_RETRY_SECONDS"]) < 30:
            raise ValueError("Priority-2 retry must be at least 30 seconds.")
        if priority == 2 and not 1 <= int(values["PUSHOVER_EXPIRE_SECONDS"]) <= 10800:
            raise ValueError("Priority-2 expiry must be between 1 and 10,800 seconds.")
        if float(values["CHP_ALERT_INTERVAL"]) < 60:
            raise ValueError("The CHP polling interval must be at least 60 seconds.")
        for key in ("CHP_ALERT_STATE_FILE", "CHP_ALERT_DETAIL_LOG_FILE"):
            Path(values[key]).expanduser().parent.mkdir(parents=True, exist_ok=True)
        load_service_area(Path(values["CHP_ALERT_SERVICE_AREA_FILE"]).expanduser())
        return values

    def save_configuration(self, quiet: bool = False) -> bool:
        try:
            values = self.collect_configuration()
            write_env(ENV_FILE, values)
        except (OSError, ValueError, ServiceAreaError) as exc:
            messagebox.showerror("Configuration error", str(exc), parent=self)
            return False
        self.append_log(f"Saved configuration to {ENV_FILE}")
        if not quiet:
            messagebox.showinfo("Configuration saved", "Settings were saved to .env.", parent=self)
        return True

    def reload_configuration(self, restart: bool = True, quiet: bool = False) -> None:
        values = parse_env(ENV_FILE)
        for key, var in self.vars.items():
            if key in values:
                var.set(values[key])
        if os.name == "nt":
            data = default_data_dir()
            for key, filename in (("CHP_ALERT_STATE_FILE", "state.json"), ("CHP_ALERT_DETAIL_LOG_FILE", "details.jsonl")):
                value = self.vars[key].get()
                if value.startswith("/var/") or value.startswith("/home/"):
                    self.vars[key].set(str(data / filename))
        self.validate_map(quiet=True)
        self.append_log(f"Reloaded configuration from {ENV_FILE}")
        if restart and self.is_running():
            if messagebox.askyesno("Restart monitor", "Configuration changed. Restart the monitor now?", parent=self):
                self.restart_monitor()
        elif not quiet:
            messagebox.showinfo("Configuration reloaded", "The .env file was reloaded.", parent=self)

    def validate_map(self, quiet: bool = False) -> bool:
        path = Path(self.vars["CHP_ALERT_SERVICE_AREA_FILE"].get()).expanduser()
        try:
            area = load_service_area(path)
        except ServiceAreaError as exc:
            self.map_summary.set(f"INVALID: {exc}")
            if not quiet:
                messagebox.showerror("Invalid map", str(exc), parent=self)
            return False
        self.map_summary.set(f"{path} — {len(area['polygon'])} vertices")
        if not quiet:
            messagebox.showinfo("Map valid", self.map_summary.get(), parent=self)
        return True

    def choose_map(self) -> None:
        current = Path(self.vars["CHP_ALERT_SERVICE_AREA_FILE"].get()).expanduser()
        selected = filedialog.askopenfilename(parent=self, title="Choose service-area GeoJSON", initialdir=current.parent, filetypes=[("GeoJSON", "*.geojson *.json"), ("All files", "*.*")])
        if selected:
            self.vars["CHP_ALERT_SERVICE_AREA_FILE"].set(selected)
            self.reload_map()

    def reload_map(self) -> None:
        if not self.validate_map():
            return
        if not self.save_configuration(quiet=True):
            return
        if self.is_running():
            if messagebox.askyesno("Restart monitor", "The map is read when the backend starts. Restart now to apply it?", parent=self):
                self.restart_monitor()
        else:
            self.append_log("Map reloaded and will be used on the next monitor start.")

    def edit_map(self) -> None:
        if not EDITOR.exists():
            messagebox.showerror("Editor missing", f"Cannot find {EDITOR}", parent=self)
            return
        path = Path(self.vars["CHP_ALERT_SERVICE_AREA_FILE"].get()).expanduser()
        subprocess.Popen([sys.executable, str(EDITOR), str(path)], cwd=ROOT)

    def environment(self) -> dict[str, str]:
        values = self.collect_configuration()
        env = os.environ.copy()
        env.update(values)
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def is_running(self) -> bool:
        return bool(self.process and self.process.poll() is None)

    def launch(self, arguments: list[str], mode: str) -> None:
        if self.is_running():
            messagebox.showwarning("Already running", "A monitor or test is already running.", parent=self)
            return
        if not self.save_configuration(quiet=True):
            return
        command = [sys.executable, "-u", str(BACKEND), *arguments]
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        try:
            self.process = subprocess.Popen(command, cwd=ROOT, env=self.environment(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=flags)
        except OSError as exc:
            messagebox.showerror("Launch failed", str(exc), parent=self)
            return
        self.status.set(mode)
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.append_log(f"[{datetime.now():%H:%M:%S}] Started: {' '.join(command)}")
        threading.Thread(target=self._read_process, args=(self.process,), daemon=True).start()

    def _read_process(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            self.output.put(("line", line.rstrip()))
        self.output.put(("exit", str(process.wait())))

    def _drain_output(self) -> None:
        try:
            while True:
                kind, payload = self.output.get_nowait()
                if kind == "line":
                    self.append_log(payload)
                    if "Parsed " in payload and "Border incidents" in payload:
                        self.last_poll.set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        self.last_summary.set(payload.split(": ", 1)[-1])
                else:
                    self.append_log(f"Process exited with code {payload}")
                    self.process = None
                    self.status.set("STOPPED" if payload == "0" else "ERROR")
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._drain_output)

    def start_monitor(self) -> None:
        self.launch([], "RUNNING")

    def dry_poll(self) -> None:
        self.launch(["--once", "--dry-run", "--alert-existing", "--log-level", "DEBUG"], "DRY RUN")

    def test_pushover(self) -> None:
        if messagebox.askyesno("Send Pushover test", f"Send a priority-{self.vars['PUSHOVER_PRIORITY'].get()} test using {self.vars['PUSHOVER_SOUND'].get()}?\n\nPriority 2 repeats until acknowledged or expired.", parent=self):
            self.launch(["--test-pushover"], "TESTING")

    def stop_monitor(self) -> None:
        if not self.is_running():
            return
        assert self.process is not None
        self.status.set("STOPPING")
        try:
            if os.name == "nt":
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self.process.terminate()
        except (OSError, ValueError):
            self.process.terminate()
        self.after(4000, self._force_stop)

    def _force_stop(self) -> None:
        if self.is_running():
            assert self.process is not None
            self.process.kill()
            self.append_log("Backend did not stop gracefully and was terminated.")

    def restart_monitor(self) -> None:
        was_running = self.is_running()
        if was_running:
            self.stop_monitor()
            self.after(1200, self._restart_when_stopped)
        else:
            self.start_monitor()

    def _restart_when_stopped(self) -> None:
        if self.is_running():
            self.after(300, self._restart_when_stopped)
        else:
            self.start_monitor()

    def open_detail_log(self) -> None:
        path = Path(self.vars["CHP_ALERT_DETAIL_LOG_FILE"].get()).expanduser()
        if not path.exists():
            messagebox.showinfo("No detail log yet", f"The file does not exist yet:\n{path}", parent=self)
            return
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as exc:
            messagebox.showerror("Could not open log", str(exc), parent=self)

    def on_close(self) -> None:
        if self.is_running() and not messagebox.askyesno("Exit CHP Alerter", "Stop the monitor and exit?", parent=self):
            return
        if self.is_running():
            self.stop_monitor()
        self.destroy()


def main() -> int:
    app = Controller()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
