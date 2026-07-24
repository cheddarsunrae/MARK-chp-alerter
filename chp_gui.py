#!/usr/bin/env python3
"""Windows desktop controller for CHP Alerter.

Uses only the Python standard library. The existing detail-aware monitor remains the
backend process; this application manages configuration, startup, tests, and logs.
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
from typing import Callable

APP_TITLE = "CHP Alerter — Station 36"
ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
BACKEND = ROOT / "chp_detail_alert.py"
LONG_SOUNDS = {
    "alien": "Alien Alarm (long)",
    "climb": "Climb (long)",
    "echo": "Pushover Echo (long)",
    "updown": "Up Down (long)",
    "persistent": "Persistent (long)",
}
ALL_SOUNDS = {
    **LONG_SOUNDS,
    "siren": "Siren",
    "spacealarm": "Space Alarm",
    "tugboat": "Tug Boat",
    "bugle": "Bugle",
    "incoming": "Incoming",
    "mechanical": "Mechanical",
    "pushover": "Pushover default",
}


def default_data_dir() -> Path:
    local = os.getenv("LOCALAPPDATA")
    return Path(local) / "CHPAlerter" if local else Path.home() / ".chp-alerter"


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
    ordered = [
        ("# Polling and state", None),
        ("CHP_ALERT_INTERVAL", values["CHP_ALERT_INTERVAL"]),
        ("CHP_ALERT_TIMEOUT", values["CHP_ALERT_TIMEOUT"]),
        ("CHP_ALERT_STATE_FILE", values["CHP_ALERT_STATE_FILE"]),
        ("CHP_ALERT_DETAIL_LOG_FILE", values["CHP_ALERT_DETAIL_LOG_FILE"]),
        ("CHP_ALERT_RETENTION_HOURS", values["CHP_ALERT_RETENTION_HOURS"]),
        ("CHP_ALERT_LOG_LEVEL", values["CHP_ALERT_LOG_LEVEL"]),
        ("", None),
        ("# Geocoding", None),
        ("CHP_ALERT_GEOCODER", values["CHP_ALERT_GEOCODER"]),
        ("CHP_ALERT_CONTACT", values["CHP_ALERT_CONTACT"]),
        ("", None),
        ("# Startup and update behaviour", None),
        ("CHP_ALERT_EXISTING", values["CHP_ALERT_EXISTING"]),
        ("CHP_ALERT_UPDATES", values["CHP_ALERT_UPDATES"]),
        ("", None),
        ("# Pushover", None),
        ("PUSHOVER_APP_TOKEN", values["PUSHOVER_APP_TOKEN"]),
        ("PUSHOVER_USER_KEY", values["PUSHOVER_USER_KEY"]),
        ("PUSHOVER_PRIORITY", values["PUSHOVER_PRIORITY"]),
        ("PUSHOVER_RETRY_SECONDS", values["PUSHOVER_RETRY_SECONDS"]),
        ("PUSHOVER_EXPIRE_SECONDS", values["PUSHOVER_EXPIRE_SECONDS"]),
        ("PUSHOVER_SOUND", values["PUSHOVER_SOUND"]),
    ]
    lines: list[str] = []
    for key, value in ordered:
        if value is None:
            lines.append(key)
        else:
            lines.append(f"{key}={value}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


class CHPController(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1040x760")
        self.minsize(880, 620)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.process: subprocess.Popen[str] | None = None
        self.output_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.vars: dict[str, tk.Variable] = {}
        self.last_poll = tk.StringVar(value="Never")
        self.last_summary = tk.StringVar(value="No poll completed yet")
        self.status = tk.StringVar(value="STOPPED")
        self._build_style()
        self._build_ui()
        self.load_configuration()
        self.after(100, self._drain_output)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Start.TButton", font=("Segoe UI", 11, "bold"), padding=10)
        style.configure("Stop.TButton", font=("Segoe UI", 11, "bold"), padding=10)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").pack(side="left")
        self.status_label = ttk.Label(header, textvariable=self.status, style="Status.TLabel")
        self.status_label.pack(side="right")

        controls = ttk.Frame(outer, padding=(0, 12, 0, 8))
        controls.pack(fill="x")
        self.start_button = ttk.Button(controls, text="START MONITOR", style="Start.TButton", command=self.start_monitor)
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button = ttk.Button(controls, text="STOP", style="Stop.TButton", command=self.stop_monitor, state="disabled")
        self.stop_button.pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Test Pushover", command=self.test_pushover).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="One Poll (Dry Run)", command=self.run_dry_poll).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Open Detail Log", command=self.open_detail_log).pack(side="left")

        summary = ttk.LabelFrame(outer, text="Monitor status", padding=10)
        summary.pack(fill="x", pady=(0, 10))
        ttk.Label(summary, text="Last successful poll:").grid(row=0, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.last_poll).grid(row=0, column=1, sticky="w", padx=(8, 30))
        ttk.Label(summary, text="Latest summary:").grid(row=1, column=0, sticky="nw")
        ttk.Label(summary, textvariable=self.last_summary, wraplength=760).grid(row=1, column=1, sticky="w", padx=(8, 0))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        monitor_tab = ttk.Frame(notebook, padding=8)
        settings_tab = ttk.Frame(notebook, padding=12)
        notebook.add(monitor_tab, text="Live log")
        notebook.add(settings_tab, text="Configuration")

        self.log = tk.Text(monitor_tab, wrap="word", state="disabled", font=("Consolas", 9), bg="#101418", fg="#e8edf2")
        scroll = ttk.Scrollbar(monitor_tab, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self._build_settings(settings_tab)

    def _build_settings(self, frame: ttk.Frame) -> None:
        defaults = default_data_dir()
        definitions = [
            ("PUSHOVER_APP_TOKEN", "Pushover application token", "", True),
            ("PUSHOVER_USER_KEY", "Pushover user/group key", "", True),
            ("PUSHOVER_SOUND", "Alert sound", "alien", False),
            ("PUSHOVER_PRIORITY", "Priority", "2", False),
            ("PUSHOVER_RETRY_SECONDS", "Emergency retry seconds", "30", False),
            ("PUSHOVER_EXPIRE_SECONDS", "Emergency expiry seconds", "1800", False),
            ("CHP_ALERT_INTERVAL", "Poll interval seconds", "65", False),
            ("CHP_ALERT_TIMEOUT", "HTTP timeout seconds", "20", False),
            ("CHP_ALERT_CONTACT", "Nominatim contact", "mailto:you@example.com", False),
            ("CHP_ALERT_STATE_FILE", "State file", str(defaults / "state.json"), False),
            ("CHP_ALERT_DETAIL_LOG_FILE", "Detail log", str(defaults / "details.jsonl"), False),
        ]
        for row, (key, label, default, secret) in enumerate(definitions):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=default)
            self.vars[key] = var
            if key == "PUSHOVER_SOUND":
                widget = ttk.Combobox(frame, textvariable=var, values=list(ALL_SOUNDS), state="readonly", width=38)
            elif key == "PUSHOVER_PRIORITY":
                widget = ttk.Combobox(frame, textvariable=var, values=["-2", "-1", "0", "1", "2"], state="readonly", width=38)
            else:
                widget = ttk.Entry(frame, textvariable=var, width=72, show="•" if secret else "")
            widget.grid(row=row, column=1, sticky="ew", padx=(12, 6), pady=4)
            if key == "PUSHOVER_SOUND":
                ttk.Label(frame, textvariable=tk.StringVar(value="Long choices: alien, climb, echo, updown, persistent")).grid(row=row, column=2, sticky="w")

        for key, default in {
            "CHP_ALERT_RETENTION_HOURS": "72",
            "CHP_ALERT_LOG_LEVEL": "INFO",
            "CHP_ALERT_GEOCODER": "nominatim",
            "CHP_ALERT_EXISTING": "0",
            "CHP_ALERT_UPDATES": "0",
        }.items():
            self.vars[key] = tk.StringVar(value=default)

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(definitions), column=0, columnspan=3, sticky="w", pady=(14, 0))
        ttk.Button(buttons, text="Save Configuration", command=self.save_configuration).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Reload .env", command=self.load_configuration).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Choose Detail Log…", command=self.choose_detail_log).pack(side="left")
        frame.columnconfigure(1, weight=1)

    def append_log(self, text: str, tag: str = "") -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def load_configuration(self) -> None:
        values = parse_env(ENV_FILE)
        for key, var in self.vars.items():
            if key in values:
                var.set(values[key])
        # Replace Linux template paths when opened on Windows, but do not overwrite
        # an explicitly configured Windows path.
        if os.name == "nt":
            data = default_data_dir()
            for key, filename in (("CHP_ALERT_STATE_FILE", "state.json"), ("CHP_ALERT_DETAIL_LOG_FILE", "details.jsonl")):
                value = str(self.vars[key].get())
                if value.startswith("/var/") or value.startswith("/home/"):
                    self.vars[key].set(str(data / filename))
        self.append_log(f"Loaded configuration from {ENV_FILE}")

    def collect_configuration(self) -> dict[str, str]:
        values = {key: str(var.get()).strip() for key, var in self.vars.items()}
        if not values["PUSHOVER_APP_TOKEN"] or not values["PUSHOVER_USER_KEY"]:
            raise ValueError("Enter both Pushover credentials.")
        priority = int(values["PUSHOVER_PRIORITY"])
        retry = int(values["PUSHOVER_RETRY_SECONDS"])
        expire = int(values["PUSHOVER_EXPIRE_SECONDS"])
        interval = float(values["CHP_ALERT_INTERVAL"])
        if priority == 2 and retry < 30:
            raise ValueError("Pushover requires retry to be at least 30 seconds for priority 2.")
        if priority == 2 and not 1 <= expire <= 10800:
            raise ValueError("Priority-2 expiry must be between 1 and 10,800 seconds.")
        if interval < 60:
            raise ValueError("The CHP poll interval must be at least 60 seconds.")
        for key in ("CHP_ALERT_STATE_FILE", "CHP_ALERT_DETAIL_LOG_FILE"):
            Path(values[key]).expanduser().parent.mkdir(parents=True, exist_ok=True)
        return values

    def save_configuration(self, quiet: bool = False) -> bool:
        try:
            values = self.collect_configuration()
            write_env(ENV_FILE, values)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Configuration error", str(exc), parent=self)
            return False
        self.append_log(f"Saved configuration to {ENV_FILE}")
        if not quiet:
            messagebox.showinfo("Configuration saved", "Settings were saved to .env.", parent=self)
        return True

    def process_environment(self) -> dict[str, str]:
        values = self.collect_configuration()
        env = os.environ.copy()
        env.update(values)
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def launch(self, arguments: list[str], mode: str) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showwarning("Already running", "A monitor or test process is already running.", parent=self)
            return
        if not BACKEND.exists():
            messagebox.showerror("Backend missing", f"Cannot find {BACKEND}", parent=self)
            return
        if not self.save_configuration(quiet=True):
            return
        try:
            env = self.process_environment()
        except ValueError as exc:
            messagebox.showerror("Configuration error", str(exc), parent=self)
            return
        command = [sys.executable, "-u", str(BACKEND), *arguments]
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        try:
            self.process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=flags,
            )
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
            self.output_queue.put(("line", line.rstrip()))
        code = process.wait()
        self.output_queue.put(("exit", str(code)))

    def _drain_output(self) -> None:
        try:
            while True:
                kind, payload = self.output_queue.get_nowait()
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

    def run_dry_poll(self) -> None:
        self.launch(["--once", "--dry-run", "--alert-existing", "--log-level", "DEBUG"], "DRY RUN")

    def test_pushover(self) -> None:
        sound = self.vars["PUSHOVER_SOUND"].get()
        description = ALL_SOUNDS.get(sound, sound)
        if messagebox.askyesno(
            "Send Pushover test",
            f"Send a priority-{self.vars['PUSHOVER_PRIORITY'].get()} test using {description}?\n\n"
            "Priority 2 repeats until acknowledged or expired.",
            parent=self,
        ):
            self.launch(["--test-pushover"], "TESTING")

    def stop_monitor(self) -> None:
        process = self.process
        if not process or process.poll() is not None:
            return
        self.status.set("STOPPING")
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
        except (OSError, ValueError):
            process.terminate()
        self.after(4000, self._force_stop_if_needed)

    def _force_stop_if_needed(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.kill()
            self.append_log("Backend did not stop gracefully and was terminated.")

    def choose_detail_log(self) -> None:
        current = Path(str(self.vars["CHP_ALERT_DETAIL_LOG_FILE"].get()))
        selected = filedialog.asksaveasfilename(
            parent=self,
            title="Choose CHP detail log",
            initialdir=current.parent if current.parent.exists() else default_data_dir(),
            initialfile=current.name or "details.jsonl",
            defaultextension=".jsonl",
            filetypes=[("JSON Lines", "*.jsonl"), ("All files", "*.*")],
        )
        if selected:
            self.vars["CHP_ALERT_DETAIL_LOG_FILE"].set(selected)

    def open_detail_log(self) -> None:
        path = Path(str(self.vars["CHP_ALERT_DETAIL_LOG_FILE"].get())).expanduser()
        if not path.exists():
            messagebox.showinfo("No detail log yet", f"The file does not exist yet:\n{path}\n\nIt is created after a new or changed detail snapshot is logged.", parent=self)
            return
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except (AttributeError, OSError) as exc:
            messagebox.showerror("Could not open log", str(exc), parent=self)

    def on_close(self) -> None:
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("Exit CHP Alerter", "Stop the running monitor and exit?", parent=self):
                return
            self.stop_monitor()
        self.destroy()


def main() -> int:
    app = CHPController()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
