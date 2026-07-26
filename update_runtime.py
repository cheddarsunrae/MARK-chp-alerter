#!/usr/bin/env python3
"""Safe update discovery and installation for MARK Git checkouts.

MARK never overwrites local work or operational configuration. Automatic updates
are offered only when the application directory is a clean Git checkout whose
configured remote can be accessed with the computer's existing Git credentials.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_REMOTE = "origin"
DEFAULT_BRANCH = "main"
COMMAND_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class UpdateStatus:
    supported: bool
    update_available: bool
    current_commit: str | None = None
    remote_commit: str | None = None
    branch: str | None = None
    behind_count: int = 0
    ahead_count: int = 0
    dirty: bool = False
    message: str = ""


class UpdateError(RuntimeError):
    """Raised when a requested update cannot be completed safely."""


def _run(root: Path, *arguments: str, timeout: int = COMMAND_TIMEOUT_SECONDS) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "Git command failed"
        raise UpdateError(detail)
    return completed.stdout.strip()


def _short(commit: str | None) -> str:
    return commit[:8] if commit else "unknown"


def check_for_update(
    root: Path,
    *,
    remote: str = DEFAULT_REMOTE,
    branch: str = DEFAULT_BRANCH,
) -> UpdateStatus:
    """Fetch remote metadata and report whether this checkout is behind.

    The function changes no tracked files. ``git fetch`` updates only repository
    metadata. Private repositories work when Git on the computer already has
    permission to access the configured remote.
    """
    root = root.resolve()
    if shutil.which("git") is None:
        return UpdateStatus(False, False, message="Git is not installed; use a release package to update MARK.")
    if not (root / ".git").exists():
        return UpdateStatus(False, False, message="This MARK copy was installed from a ZIP; automatic Git updates are unavailable.")

    try:
        current = _run(root, "rev-parse", "HEAD")
        current_branch = _run(root, "branch", "--show-current") or branch
        dirty = bool(_run(root, "status", "--porcelain"))
        _run(root, "fetch", "--quiet", remote, branch)
        remote_commit = _run(root, "rev-parse", f"{remote}/{branch}")
        counts = _run(root, "rev-list", "--left-right", "--count", f"HEAD...{remote}/{branch}")
        ahead_text, behind_text = counts.split()
        ahead_count = int(ahead_text)
        behind_count = int(behind_text)
    except (UpdateError, ValueError, subprocess.TimeoutExpired) as exc:
        return UpdateStatus(False, False, message=f"Update check failed: {exc}")

    if behind_count:
        message = (
            f"MARK update available: local {_short(current)}, "
            f"GitHub {_short(remote_commit)} ({behind_count} commit(s) newer)."
        )
    elif ahead_count:
        message = f"This checkout is {ahead_count} commit(s) ahead of GitHub; automatic update is disabled."
    else:
        message = f"MARK is up to date at {_short(current)}."

    return UpdateStatus(
        True,
        behind_count > 0,
        current,
        remote_commit,
        current_branch,
        behind_count,
        ahead_count,
        dirty,
        message,
    )


def install_update(
    root: Path,
    *,
    remote: str = DEFAULT_REMOTE,
    branch: str = DEFAULT_BRANCH,
) -> str:
    """Install a fast-forward-only update and refresh Python dependencies.

    Refuses to run with tracked or untracked working-tree changes, a divergent
    branch, or a non-Git installation. Ignored operational files such as ``.env``,
    profiles, maps, logs, and runtime state are not modified by ``git pull``.
    """
    root = root.resolve()
    status = check_for_update(root, remote=remote, branch=branch)
    if not status.supported:
        raise UpdateError(status.message)
    if status.dirty:
        raise UpdateError(
            "MARK has local file changes. The updater stopped without changing anything; "
            "commit, move, or discard those changes before updating."
        )
    if status.ahead_count:
        raise UpdateError("This checkout contains commits not present on GitHub; automatic update was refused.")
    if not status.update_available:
        return status.message

    before = status.current_commit
    try:
        _run(root, "pull", "--ff-only", remote, branch, timeout=180)
        after = _run(root, "rev-parse", "HEAD")
        python = root / ".venv" / ("Scripts/python.exe" if __import__("os").name == "nt" else "bin/python")
        requirements = root / "requirements.txt"
        if python.exists() and requirements.exists():
            completed = subprocess.run(
                [str(python), "-m", "pip", "install", "-r", str(requirements)],
                cwd=root,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300,
                check=False,
            )
            if completed.returncode != 0:
                raise UpdateError(
                    "Code updated, but dependency refresh failed. Restart the installer. "
                    + (completed.stderr.strip() or completed.stdout.strip())
                )
    except subprocess.TimeoutExpired as exc:
        raise UpdateError(f"Update timed out: {exc}") from exc

    return f"MARK updated from {_short(before)} to {_short(after)}."
