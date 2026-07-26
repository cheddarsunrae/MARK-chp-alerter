#!/usr/bin/env python3
"""MARK GUI entry point with updates and provider-neutral notification controls."""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.parse import quote

import requests

import mark_app
import mark_gui_entry
import update_runtime


ROOT = Path(__file__).resolve().parent
PUSHOVER_URL = "https://api.pushover.net/1/messages.json"
SEVERITIES = ("low", "medium", "high", "critical")
DELIVERY_MODES = ("notify_once", "notify_on_update", "until_acknowledged", "until_expiration")
PROVIDERS = ("pushover", "ntfy", "gotify", "webhook")


class UpdatingMarkApp(mark_gui_entry.SafeMarkApp):
    """Add update checks and visible multi-provider notification controls."""

    def __init__(self) -> None:
        self.update_status_text: tk.StringVar | None = None
        self._update_check_running = False
        self._update_install_running = False
        self._notification_test_running = False
        super().__init__()
        self.after(3500, lambda: self.check_for_updates(notify_when_current=False))

    def _defaults(self) -> dict[str, str]:
        values = super()._defaults()
        values.update(
            {
                "CHP_ALERT_INTERVAL": "30",
                "NOTIFY_PROVIDERS": "pushover",
                "ALERT_SEVERITY": "critical",
                "ALERT_DELIVERY_MODE": "until_acknowledged",
                "ALERT_RETRY_SECONDS": "30",
                "ALERT_EXPIRE_SECONDS": "1800",
                "ALERT_COOLDOWN_SECONDS": "300",
                "CHP_ALERT_SERVICE_AREA_LABEL": "",
                "NTFY_SERVER": "https://ntfy.sh",
                "NTFY_TOPIC": "",
                "NTFY_TOKEN": "",
                "GOTIFY_URL": "",
                "GOTIFY_APP_TOKEN": "",
                "WEBHOOK_URL": "",
                "WEBHOOK_BEARER_TOKEN": "",
            }
        )
        return values

    def _ensure_notification_vars(self) -> None:
        defaults = self._defaults()
        for key, value in defaults.items():
            self.vars.setdefault(key, tk.StringVar(value=value))

    def _build_config(self, frame: ttk.Frame) -> None:
        super()._build_config(frame)
        self._ensure_notification_vars()
        self._build_notification_panel(frame)
        self._build_update_panel(frame)

    def _build_notification_panel(self, frame: ttk.Frame) -> None:
        panel = ttk.LabelFrame(frame, text="Notification Providers and Alert Policy", padding=8)
        panel.pack(fill="x", pady=(10, 0))
        ttk.Label(
            panel,
            text=(
                "Choose one or more providers. Separate multiple providers with commas: "
                "pushover, ntfy, gotify, webhook. Pushover credentials are in the main "
                "configuration fields above."
            ),
            wraplength=360,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        def add_field(row: int, key: str, label: str, *, secret: bool = False, values: tuple[str, ...] | None = None) -> None:
            ttk.Label(panel, text=label).grid(row=row, column=0, sticky="w", pady=3)
            if values:
                widget = ttk.Combobox(panel, textvariable=self.vars[key], values=values, state="readonly")
            else:
                widget = ttk.Entry(panel, textvariable=self.vars[key], show="•" if secret else "")
            widget.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=3)

        add_field(1, "NOTIFY_PROVIDERS", "Providers")
        add_field(2, "ALERT_SEVERITY", "Severity", values=SEVERITIES)
        add_field(3, "ALERT_DELIVERY_MODE", "Delivery Mode", values=DELIVERY_MODES)
        add_field(4, "ALERT_RETRY_SECONDS", "Retry Seconds")
        add_field(5, "ALERT_EXPIRE_SECONDS", "Expire Seconds")
        add_field(6, "CHP_ALERT_SERVICE_AREA_LABEL", "Map/Profile Label")
        add_field(7, "NTFY_SERVER", "ntfy Server")
        add_field(8, "NTFY_TOPIC", "ntfy Topic")
        add_field(9, "NTFY_TOKEN", "ntfy Token", secret=True)
        add_field(10, "GOTIFY_URL", "Gotify URL")
        add_field(11, "GOTIFY_APP_TOKEN", "Gotify App Token", secret=True)
        add_field(12, "WEBHOOK_URL", "Webhook URL")
        add_field(13, "WEBHOOK_BEARER_TOKEN", "Webhook Bearer Token", secret=True)
        panel.columnconfigure(1, weight=1)
        ttk.Button(panel, text="Test Selected Providers", command=self.test_selected_notifications).grid(row=14, column=0, columnspan=3, sticky="ew", pady=(8, 0))

    def _build_update_panel(self, frame: ttk.Frame) -> None:
        self.update_status_text = tk.StringVar(value="Update status: not checked")
        panel = ttk.LabelFrame(frame, text="MARK Updates", padding=8)
        panel.pack(fill="x", pady=(10, 0))
        ttk.Label(
            panel,
            textvariable=self.update_status_text,
            wraplength=340,
        ).pack(anchor="w", fill="x")
        buttons = ttk.Frame(panel)
        buttons.pack(fill="x", pady=(7, 0))
        self.check_update_button = ttk.Button(
            buttons,
            text="Check for Updates",
            command=lambda: self.check_for_updates(notify_when_current=True),
        )
        self.check_update_button.pack(side="left", padx=(0, 5))
        self.install_update_button = ttk.Button(
            buttons,
            text="Install Update",
            command=self.install_available_update,
            state="disabled",
        )
        self.install_update_button.pack(side="left")

    def _providers(self, values: dict[str, str] | None = None) -> list[str]:
        source = values or {key: var.get() for key, var in self.vars.items()}
        providers = [item.strip().casefold() for item in source.get("NOTIFY_PROVIDERS", "").replace(";", ",").split(",") if item.strip()]
        return list(dict.fromkeys(providers))

    def collect_configuration(self) -> dict[str, str]:
        self._ensure_notification_vars()
        values = {key: var.get().strip() for key, var in self.vars.items()}
        providers = self._providers(values)
        unknown = [provider for provider in providers if provider not in PROVIDERS]
        if unknown:
            raise ValueError("Unknown notification provider(s): " + ", ".join(unknown))
        if not providers:
            raise ValueError("Choose at least one notification provider.")
        if float(values["CHP_ALERT_INTERVAL"]) < 30:
            raise ValueError("Poll interval must be at least 30 seconds")
        if values["ALERT_SEVERITY"] not in SEVERITIES:
            raise ValueError("Choose a valid alert severity")
        if values["ALERT_DELIVERY_MODE"] not in DELIVERY_MODES:
            raise ValueError("Choose a valid delivery mode")
        if int(values["ALERT_RETRY_SECONDS"]) < 30:
            raise ValueError("Alert retry must be at least 30 seconds")
        if not 1 <= int(values["ALERT_EXPIRE_SECONDS"]) <= 10800:
            raise ValueError("Alert expiration must be between 1 and 10800 seconds")
        if "pushover" in providers and (not values.get("PUSHOVER_APP_TOKEN") or not values.get("PUSHOVER_USER_KEY")):
            raise ValueError("Pushover is selected; enter both Pushover token and user key.")
        if "ntfy" in providers and not values.get("NTFY_TOPIC"):
            raise ValueError("ntfy is selected; enter an ntfy topic.")
        if "gotify" in providers and (not values.get("GOTIFY_URL") or not values.get("GOTIFY_APP_TOKEN")):
            raise ValueError("Gotify is selected; enter the Gotify URL and app token.")
        if "webhook" in providers and not values.get("WEBHOOK_URL"):
            raise ValueError("Webhook is selected; enter the webhook URL.")
        for key in ("CHP_ALERT_STATE_FILE", "CHP_ALERT_DETAIL_LOG_FILE"):
            Path(values[key]).expanduser().parent.mkdir(parents=True, exist_ok=True)
        values["NOTIFY_PROVIDERS"] = ",".join(providers)
        return values

    def save_configuration(self, quiet: bool = False) -> bool:
        try:
            values = self.collect_configuration()
            self._write_full_env(values)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Configuration error", str(exc), parent=self)
            return False
        self.append_log("Saved MARK configuration")
        if not quiet:
            messagebox.showinfo("Saved", "Configuration saved.", parent=self)
        return True

    def _write_full_env(self, values: dict[str, str]) -> None:
        groups = (
            (
                "Polling and state",
                (
                    "CHP_ALERT_INTERVAL",
                    "CHP_ALERT_TIMEOUT",
                    "CHP_ALERT_STATE_FILE",
                    "CHP_ALERT_DETAIL_LOG_FILE",
                    "CHP_ALERT_RETENTION_HOURS",
                    "CHP_ALERT_LOG_LEVEL",
                    "CHP_ALERT_SERVICE_AREA_FILE",
                    "CHP_ALERT_PROFILE",
                    "CHP_ALERT_SERVICE_AREA_LABEL",
                ),
            ),
            ("Filtering", ("CHP_ALERT_AREA_PREFIXES", "CHP_ALERT_TYPE_FRAGMENTS", "CHP_ALERT_EXISTING", "CHP_ALERT_UPDATES")),
            ("Notification policy", ("NOTIFY_PROVIDERS", "ALERT_SEVERITY", "ALERT_DELIVERY_MODE", "ALERT_RETRY_SECONDS", "ALERT_EXPIRE_SECONDS", "ALERT_COOLDOWN_SECONDS")),
            ("Pushover", ("PUSHOVER_APP_TOKEN", "PUSHOVER_USER_KEY", "PUSHOVER_PRIORITY", "PUSHOVER_RETRY_SECONDS", "PUSHOVER_EXPIRE_SECONDS", "PUSHOVER_SOUND")),
            ("ntfy", ("NTFY_SERVER", "NTFY_TOPIC", "NTFY_TOKEN")),
            ("Gotify", ("GOTIFY_URL", "GOTIFY_APP_TOKEN")),
            ("Webhook", ("WEBHOOK_URL", "WEBHOOK_BEARER_TOKEN")),
        )
        lines: list[str] = []
        for title, keys in groups:
            lines.append(f"# {title}")
            for key in keys:
                lines.append(f"{key}={values.get(key, '')}")
            lines.append("")
        mark_app.ENV_FILE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def test_pushover(self) -> None:
        self.test_selected_notifications()

    def test_selected_notifications(self) -> None:
        if self._notification_test_running:
            return
        try:
            values = self.collect_configuration()
        except ValueError as exc:
            messagebox.showerror("Notification configuration", str(exc), parent=self)
            return
        self._notification_test_running = True
        self.append_log("Testing selected notification provider(s)...")

        def worker() -> None:
            try:
                results = self._send_test_notifications(values)
            except Exception as exc:
                self.after(0, lambda: self._finish_notification_test(False, str(exc)))
                return
            self.after(0, lambda: self._finish_notification_test(True, results))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_notification_test(self, ok: bool, message: str) -> None:
        self._notification_test_running = False
        self.append_log(message)
        if ok:
            messagebox.showinfo("Notification test", message, parent=self)
        else:
            messagebox.showerror("Notification test failed", message, parent=self)

    def _send_test_notifications(self, values: dict[str, str]) -> str:
        session = requests.Session()
        timeout = float(values.get("CHP_ALERT_TIMEOUT", "20") or 20)
        title = "MARK notification test"
        message = "MARK notification providers are configured. This is a manual test, not a CHP incident."
        source_url = "https://cad.chp.ca.gov/Traffic.aspx"
        delivered: list[str] = []
        failures: list[str] = []
        for provider in self._providers(values):
            try:
                if provider == "pushover":
                    payload = {
                        "token": values["PUSHOVER_APP_TOKEN"],
                        "user": values["PUSHOVER_USER_KEY"],
                        "title": title,
                        "message": message,
                        "priority": "0",
                        "url": source_url,
                        "url_title": "Open CHP CAD",
                    }
                    if values.get("PUSHOVER_SOUND"):
                        payload["sound"] = values["PUSHOVER_SOUND"]
                    response = session.post(PUSHOVER_URL, data=payload, timeout=timeout)
                    response.raise_for_status()
                elif provider == "ntfy":
                    server = values.get("NTFY_SERVER") or "https://ntfy.sh"
                    headers = {"Title": title, "Priority": "3", "Tags": "bell", "Click": source_url}
                    if values.get("NTFY_TOKEN"):
                        headers["Authorization"] = f"Bearer {values['NTFY_TOKEN']}"
                    response = session.post(
                        f"{server.rstrip('/')}/{quote(values['NTFY_TOPIC'].strip(), safe='')}",
                        data=message.encode("utf-8"),
                        headers=headers,
                        timeout=timeout,
                    )
                    response.raise_for_status()
                elif provider == "gotify":
                    response = session.post(
                        f"{values['GOTIFY_URL'].rstrip('/')}/message",
                        params={"token": values["GOTIFY_APP_TOKEN"]},
                        json={"title": title, "message": message, "priority": 4},
                        timeout=timeout,
                    )
                    response.raise_for_status()
                elif provider == "webhook":
                    headers = {"Content-Type": "application/json"}
                    if values.get("WEBHOOK_BEARER_TOKEN"):
                        headers["Authorization"] = f"Bearer {values['WEBHOOK_BEARER_TOKEN']}"
                    response = session.post(
                        values["WEBHOOK_URL"],
                        headers=headers,
                        data=json.dumps({"source": "MARK", "title": title, "message": message, "source_url": source_url}),
                        timeout=timeout,
                    )
                    response.raise_for_status()
                delivered.append(provider)
            except Exception as exc:
                failures.append(f"{provider}: {exc}")
        if delivered and not failures:
            return "Notification test sent through: " + ", ".join(delivered)
        if delivered:
            return "Notification test partially succeeded. Sent: " + ", ".join(delivered) + ". Failed: " + "; ".join(failures)
        raise RuntimeError("No notification provider accepted the test: " + "; ".join(failures))

    def _set_status(self, text: str) -> None:
        if self.update_status_text is not None:
            self.update_status_text.set(text)

    def _set_update_controls(self, checking: bool) -> None:
        state = "disabled" if checking else "normal"
        self.check_update_button.configure(state=state)
        if checking:
            self.install_update_button.configure(state="disabled")

    def check_for_updates(self, *, notify_when_current: bool) -> None:
        if self._update_check_running or self._update_install_running:
            return
        self._update_check_running = True
        self._set_update_controls(True)
        self._set_status("Checking GitHub for a newer MARK version...")

        def worker() -> None:
            status = update_runtime.check_for_update(ROOT)
            self.after(0, lambda: self._finish_update_check(status, notify_when_current))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_update_check(self, status: update_runtime.UpdateStatus, notify_when_current: bool) -> None:
        self._update_check_running = False
        self.check_update_button.configure(state="normal")
        self._set_status(status.message)
        self.append_log(status.message)
        can_install = status.supported and status.update_available and not status.dirty and not status.ahead_count
        self.install_update_button.configure(state="normal" if can_install else "disabled")
        if status.update_available:
            extra = ""
            if status.dirty:
                extra = "\n\nLocal file changes were detected, so automatic installation is disabled."
            elif status.ahead_count:
                extra = "\n\nThis checkout contains unpublished commits, so automatic installation is disabled."
            elif not status.supported:
                extra = "\n\nUse the approved release package to update this installation."
            messagebox.showinfo("MARK update available", status.message + extra, parent=self)
        elif notify_when_current:
            messagebox.showinfo("MARK updates", status.message, parent=self)

    def install_available_update(self) -> None:
        if self._update_install_running:
            return
        if self.process is not None and self.process.poll() is None:
            messagebox.showwarning(
                "Stop monitoring first",
                "Stop the MARK monitor before installing an update.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Install MARK update?",
            "MARK will download a fast-forward-only update from GitHub. "
            "Your .env settings, profiles, maps, logs, and runtime state will not be replaced.\n\n"
            "MARK will restart after the update succeeds. Continue?",
            parent=self,
        ):
            return
        self._update_install_running = True
        self.check_update_button.configure(state="disabled")
        self.install_update_button.configure(state="disabled")
        self._set_status("Installing MARK update...")
        self.append_log("Installing MARK update with git pull --ff-only")

        def worker() -> None:
            try:
                result = update_runtime.install_update(ROOT)
            except Exception as exc:
                self.after(0, lambda: self._finish_update_install_error(str(exc)))
                return
            self.after(0, lambda: self._finish_update_install_success(result))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_update_install_error(self, message: str) -> None:
        self._update_install_running = False
        self.check_update_button.configure(state="normal")
        self._set_status(f"Update failed: {message}")
        self.append_log(f"Update failed: {message}")
        messagebox.showerror("MARK update failed", message, parent=self)

    def _finish_update_install_success(self, message: str) -> None:
        self._set_status(message)
        self.append_log(message)
        messagebox.showinfo("MARK updated", message + "\n\nMARK will now restart.", parent=self)
        self.update_idletasks()
        os.execl(sys.executable, sys.executable, str(Path(__file__).resolve()))


def main() -> int:
    try:
        UpdatingMarkApp().mainloop()
        return 0
    except Exception:
        mark_gui_entry.report_startup_failure()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
