# MARK beta release checklist

Use this before sending MARK to additional firefighters, medics, dispatchers, stations, or agencies.

## 1. Source state

- [ ] Working branch is `main`.
- [ ] Local repo is pulled and clean.
- [ ] `VERSION` was incremented for this beta.
- [ ] `README.md`, `RELEASE_README.md`, and both user guides reflect the current UI.
- [ ] No private `.env`, runtime logs, state files, or private maps are staged or committed.

## 2. Static validation

Run:

```bash
python scripts/validate_release.py
```

- [ ] Required files exist.
- [ ] JSON catalog files parse.
- [ ] Python files compile.

## 3. Build package

Run:

```bash
python scripts/build_release.py
```

Confirm:

- [ ] `dist/MARK-<version>.zip` exists.
- [ ] `dist/MARK-<version>.zip.sha256` exists.
- [ ] `dist/MARK-<version>/release-manifest.json` exists.
- [ ] The ZIP does not contain `.env`, `runtime/`, `.venv/`, `.git/`, logs, or state.

## 4. Clean Windows acceptance

Use a folder outside the development checkout.

- [ ] Extract the ZIP.
- [ ] Double-click `Install MARK - Windows.bat`.
- [ ] Confirm MARK opens.
- [ ] Confirm the window title includes the version.
- [ ] Confirm the first-run helper appears once.
- [ ] Confirm **CHP Region / Service-Area Map** is visible at the top of Configuration.
- [ ] Select a CHP center.
- [ ] Click **Load Center Test Map**.
- [ ] Confirm map loads and AREA/Type become `*`.
- [ ] Configure at least one notification provider.
- [ ] Click **Test Selected Providers**.
- [ ] Run **One Poll (Dry Run)**.
- [ ] Start and stop monitor cleanly.

## 5. Operational profile acceptance

- [ ] Load real service-area map.
- [ ] Restore operational AREA prefixes.
- [ ] Restore operational Type fragments.
- [ ] Set notification policy.
- [ ] Save configuration.
- [ ] Restart monitor.
- [ ] Confirm logs use generic or intended service-area label.
- [ ] Confirm no stale Station 36 wording appears unless explicitly configured.

## 6. macOS/Linux acceptance

Before calling a release validated on these platforms:

- [ ] macOS installer launches MARK.
- [ ] `Start MARK.command` launches MARK after installation.
- [ ] Linux installer creates a desktop entry.
- [ ] Linux launcher opens MARK.
- [ ] Tkinter map view either works or fails gracefully.

## 7. User handoff

Give the user:

- [ ] ZIP file.
- [ ] SHA256 checksum.
- [ ] `MARK_QUICK_START_GUIDE.md`.
- [ ] Notification app instructions.
- [ ] Any approved operational map file.
- [ ] A clear reminder: MARK is supplemental awareness only.
