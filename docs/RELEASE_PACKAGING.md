# MARK release packaging

This document describes how to build a clean MARK beta package for nontechnical users.

## Release goals

A release package should be safe to hand to firefighters, medics, dispatchers, or station staff who do not know GitHub, PowerShell, Terminal, or Python.

The package must include the application, launchers, guides, sample/test-map data, and configuration templates. It must not include local secrets or runtime data.

## Files intentionally excluded

Do not include:

- `.env`
- `runtime/`
- `.venv/` or `venv/`
- `.git/`
- local logs
- detail JSONL logs
- saved state files
- private operational service-area maps unless specifically approved for that release
- notification tokens, user keys, API keys, passwords, or phone numbers

## Build commands

From the repository root:

```powershell
.\.venv\Scripts\python.exe .\scripts\validate_release.py
.\.venv\Scripts\python.exe .\scripts\build_release.py
```

On macOS/Linux:

```bash
python3 scripts/validate_release.py
python3 scripts/build_release.py
```

The build script writes artifacts under `dist/`:

```text
MARK-<version>.zip
MARK-<version>.zip.sha256
MARK-<version>/release-manifest.json
```

The ZIP contains a top-level `MARK-<version>/` folder.

## Versioning

The user-visible version is stored in:

```text
VERSION
```

For beta builds, use a clear pre-release format such as:

```text
0.9.0-beta.1
```

Increment the version before handing a new package to users.

## Validation before release

Run:

```bash
python scripts/validate_release.py
```

This confirms required files exist, required JSON files parse, and key Python entry points compile.

## Windows smoke test from ZIP

Use a clean folder, not your development checkout.

1. Extract `MARK-<version>.zip`.
2. Open the extracted `MARK-<version>` folder.
3. Double-click `Install MARK - Windows.bat`.
4. Confirm MARK opens.
5. Confirm the Configuration panel shows **CHP Region / Service-Area Map**.
6. Pick a CHP center.
7. Click **Load Center Test Map**.
8. Click **Test Selected Providers** after configuring notifications.
9. Run **One Poll (Dry Run)**.
10. Confirm no `.env` or runtime data was packaged originally; those should only be created locally after first run.

## macOS/Linux status

The shared code and launchers support macOS and Linux, but native acceptance testing is still required before presenting those as fully validated end-user releases.

## Release handoff checklist

Give beta users:

- the ZIP
- the `.sha256` checksum file
- the Quick-Start guide
- notification credentials or instructions
- the correct operational service-area map, if they should not draw/load their own
- a reminder that MARK is supplemental awareness only

## Future improvement

The next packaging milestone should be signed installer artifacts or a signed update manifest so ZIP-only users can update without GitHub/Git credentials.
