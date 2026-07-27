#!/usr/bin/env python3
"""Build a clean MARK beta release ZIP with checksums and a manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".vscode",
    ".idea",
    "runtime",
    "dist",
    "releases",
}

EXCLUDED_NAMES = {
    ".env",
    ".DS_Store",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
    ".jsonl",
    ".zip",
    ".sha256",
}

REQUIRED_IN_PACKAGE = (
    "VERSION",
    "RELEASE_README.md",
    "MARK_QUICK_START_GUIDE.md",
    "MARK_TECHNICAL_USER_GUIDE.md",
    ".env.example",
    "requirements.txt",
    "Install MARK - Windows.bat",
    "Install MARK - macOS.command",
    "install-mark-linux.sh",
    "start-chp-alerter.ps1",
    "start-chp-alerter.sh",
    "mark_region_entry.py",
    "mark_backend.py",
    "data/chp_communications_centers.json",
    "data/chp_center_smoke_boundaries.json",
)


def run_git(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def version() -> str:
    raw = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    return raw or "0.0.0-local"


def should_include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.name in EXCLUDED_NAMES:
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    if path.name.endswith(".manifest.json"):
        return False
    return True


def tracked_files() -> list[Path]:
    output = run_git(["ls-files"])
    if output:
        values = [ROOT / line for line in output.splitlines() if line.strip()]
    else:
        values = [path for path in ROOT.rglob("*") if path.is_file()]
    return sorted(path for path in values if path.exists() and should_include(path))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_files(staging: Path, files: list[Path]) -> list[dict[str, str | int]]:
    manifest_files: list[dict[str, str | int]] = []
    for source in files:
        relative = source.relative_to(ROOT)
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        manifest_files.append(
            {
                "path": str(relative).replace(os.sep, "/"),
                "bytes": source.stat().st_size,
                "sha256": sha256_file(source),
            }
        )
    return manifest_files


def write_manifest(staging: Path, files: list[dict[str, str | int]]) -> Path:
    commit = run_git(["rev-parse", "HEAD"])
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    dirty = bool(run_git(["status", "--porcelain"]))
    payload = {
        "application": "MARK - Map-Aware Roadway Knowledge",
        "version": version(),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": commit,
        "source_branch": branch,
        "source_dirty": dirty,
        "warning": "Supplemental awareness only; not a dispatch/CAD/radio replacement.",
        "excluded_private_files": [".env", "runtime/", ".venv/", "dist/", "releases/", "logs", "state files"],
        "files": files,
    }
    path = staging / "release-manifest.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def validate_package(staging: Path) -> None:
    missing = [relative for relative in REQUIRED_IN_PACKAGE if not (staging / relative).exists()]
    if missing:
        raise SystemExit("Release staging is missing required files: " + ", ".join(missing))
    forbidden = [".env", "runtime", ".git", ".venv", "venv"]
    present = [relative for relative in forbidden if (staging / relative).exists()]
    if present:
        raise SystemExit("Release staging contains private/dev paths: " + ", ".join(present))


def make_zip(staging: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    root_name = staging.name
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                arcname = Path(root_name) / path.relative_to(staging)
                archive.write(path, arcname.as_posix())


def build(output_dir: Path) -> tuple[Path, Path, Path]:
    current_version = version()
    package_name = f"MARK-{current_version}"
    staging = output_dir / package_name
    zip_path = output_dir / f"{package_name}.zip"
    checksum_path = output_dir / f"{package_name}.zip.sha256"

    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)

    source_files = tracked_files()
    manifest_files = copy_files(staging, source_files)
    manifest_path = write_manifest(staging, manifest_files)
    validate_package(staging)
    make_zip(staging, zip_path)
    checksum = sha256_file(zip_path)
    checksum_path.write_text(f"{checksum}  {zip_path.name}\n", encoding="utf-8")
    return zip_path, checksum_path, manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a clean MARK release ZIP")
    parser.add_argument("--output-dir", type=Path, default=DIST, help="Directory for release artifacts")
    parser.add_argument("--skip-validation", action="store_true", help="Skip scripts/validate_release.py")
    args = parser.parse_args(argv)

    if not args.skip_validation:
        validator = ROOT / "scripts" / "validate_release.py"
        subprocess.run([sys.executable, str(validator)], cwd=ROOT, check=True)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    zip_path, checksum_path, manifest_path = build(args.output_dir)
    print(f"Built: {zip_path}")
    print(f"Checksum: {checksum_path}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
