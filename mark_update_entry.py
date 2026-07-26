#!/usr/bin/env python3
"""MARK GUI entry point with safe GitHub update discovery and installation."""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

import mark_gui_entry
import update_runtime


ROOT = Path(__file__).resolve().parent


class UpdatingMarkApp(mark_gui_entry.SafeMarkApp):
    """Add non-blocking update checks without changing the monitor process."""

    def __init__(self) -> None:
        self.update_status_text: tk.StringVar | None = None
        self._update_check_running = False
        self._update_install_running = False
        super().__init__()
        self.after(3500, lambda: self.check_for_updates(notify_when_current=False))

    def _build_config(self, frame: ttk.Frame) -> None:
        super()._build_config(frame)
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

    def _finish_update_check(
        self,
        status: update_runtime.UpdateStatus,
        notify_when_current: bool,
    ) -> None:
        self._update_check_running = False
        self.check_update_button.configure(state="normal")
        self._set_status(status.message)
        self.append_log(status.message)

        can_install = (
            status.supported
            and status.update_available
            and not status.dirty
            and not status.ahead_count
        )
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
            except Exception as exc:  # surfaced to GUI; updater itself is conservative
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
        messagebox.showinfo(
            "MARK updated",
            message + "\n\nMARK will now restart.",
            parent=self,
        )
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
