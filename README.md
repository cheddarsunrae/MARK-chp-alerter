# MARK — Map-Aware Roadway Knowledge

MARK polls the public California Highway Patrol CAD page, performs a fast first-pass listing filter, retrieves selected incident details, confirms location from the CAD-supplied `Lat/Lon:` value, checks an active GeoJSON service-area polygon, and sends qualifying incidents through configured notification providers.

> **Supplemental awareness only.** MARK is not an official CAD terminal, station alerting system, pager, radio, or replacement for agency dispatch. Public webpages, networks, and third-party push services can fail or change.

## Version

The current beta version is stored in:

```text
VERSION
```

The GUI title displays the version when launched through the normal region-aware entry point.

## Platform support

MARK uses one shared `main` branch for Windows, macOS, and Linux. Platform-specific branches are intentionally avoided because they would drift apart and make fixes harder to maintain.

Nontechnical installers:

- Windows: `Install MARK - Windows.bat`
- macOS: `Install MARK - macOS.command`
- Linux: `install-mark-linux.sh`

Launchers:

- Windows: `start-chp-alerter.ps1`
- macOS/Linux: `start-chp-alerter.sh`
- macOS installer also creates `Start MARK.command`
- Linux installer creates a desktop-menu entry

The Windows version is live-accepted. Native macOS and Linux acceptance testing is still required before those packages should be described as fully validated releases.

## User manuals

- `RELEASE_README.md` — first file to read in a release ZIP.
- `MARK_QUICK_START_GUIDE.md` — for users who do not know GitHub, PowerShell, Terminal, or Python.
- `MARK_TECHNICAL_USER_GUIDE.md` — installation, configuration, providers, validation, and troubleshooting.
- `USER_GUIDE.md` — earlier general operating guide retained for compatibility.
- `docs/RELEASE_PACKAGING.md` — clean ZIP build process.
- `docs/BETA_RELEASE_CHECKLIST.md` — acceptance checklist before sending a beta package to users.
- `docs/STATEWIDE_NOTIFICATION_EXPANSION.md` — statewide and multi-provider architecture.
- `data/chp_communications_centers.json` — CHP communications-center catalog.

Nontechnical operational users should receive a versioned ZIP or installer from an approved department or MARK release location. They should not be expected to clone a GitHub repository.

## Current accepted status

The Windows application launches and polls successfully. The final live defect was resolved by reproducing the complete browser form submission for CHP detail selection. The monitor now receives the selected incident panel instead of the incident listing again.

## Release packaging

Validate and build a clean beta release ZIP with:

```powershell
.\.venv\Scripts\python.exe .\scripts\validate_release.py
.\.venv\Scripts\python.exe .\scripts\build_release.py
```

The build writes:

```text
dist/MARK-<version>.zip
dist/MARK-<version>.zip.sha256
dist/MARK-<version>/release-manifest.json
```

The release builder excludes `.env`, `runtime/`, `.venv/`, `.git/`, logs, state files, and build outputs.

## First-run helper

The normal GUI entry point is:

```text
mark_region_entry.py
```

On first launch, the beta helper explains the recommended setup sequence, links to the Quick-Start guide, and offers shortcuts for notification settings and center smoke-test map loading. It stores its dismissed state under `runtime/`, which is intentionally not packaged.

## Update checking

MARK checks the configured GitHub remote shortly after startup and also provides **Check for Updates** and **Install Update** controls.

Automatic installation is intentionally conservative:

- available only when MARK is installed as a Git checkout;
- uses the computer's existing Git credentials, which matters while the repository is private;
- runs `git fetch` for discovery and `git pull --ff-only` for installation;
- refuses to install when local file changes or unpublished commits are present;
- requires the monitor to be stopped;
- refreshes Python dependencies after a successful pull;
- restarts MARK after the update;
- does not replace ignored operational files such as `.env`, profiles, private maps, logs, or runtime state.

ZIP-only installations receive a clear manual-update message. A future signed release-package channel is still needed for fully automatic updates on non-Git installations.

## CHP center and smoke-test maps

The GUI exposes **CHP Region / Service-Area Map** at the top of the Configuration pane.

It includes:

- CHP communications-center selector
- visible service-area map field
- Browse button
- **Load Center Test Map**
- **Save Region/Map**

Center smoke-test boundaries are generated from:

```text
data/chp_center_smoke_boundaries.json
```

Generated maps are written under:

```text
runtime/test_maps/
```

Smoke-test maps set `CHP_ALERT_AREA_PREFIXES=*` and `CHP_ALERT_TYPE_FRAGMENTS=*` so any listed incident in the selected center can validate the polling/detail/alert pipeline. They are intentionally broad and must not be used as operational service-area boundaries.

## Notification runtime and GUI controls

`notification_runtime.py` provides a common provider interface for:

- Pushover
- ntfy
- Gotify
- Generic JSON webhooks

The GUI exposes provider and alert-policy settings through **Notification Settings** near the top of the Configuration pane. The visible settings include provider selection, severity, delivery mode, retry/expiration, ntfy server/topic/token, Gotify URL/token, webhook URL/token, and an optional map/profile label.

Common policy values:

```dotenv
NOTIFY_PROVIDERS=pushover
ALERT_SEVERITY=critical
ALERT_DELIVERY_MODE=until_acknowledged
ALERT_RETRY_SECONDS=30
ALERT_EXPIRE_SECONDS=1800
```

Severity values are `low`, `medium`, `high`, and `critical`. Delivery values are `notify_once`, `notify_on_update`, `until_acknowledged`, and `until_expiration`.

Provider capability matters. MARK does not claim acknowledgement for providers that cannot report it.

## Service-area wording

The active map is always the configured GeoJSON file. Legacy Station 36 text has been removed from the active coordinate-match reason. Logs now use the configured label when present or generic wording such as `outside active service-area polygon`.

Set this when a profile should have a human-readable name in logs:

```dotenv
CHP_ALERT_SERVICE_AREA_LABEL=Jamul Fire Station 36
```

Leave it blank for generic wording.

## Map cleanup tools

MARK has two cleanup modes:

1. **Simplify Boundary** removes near-collinear points using a conservative metre tolerance.
2. **Set Line Start** + **Remove Between Start + Selected** forces a direct line between two selected waypoints and removes the intermediate waypoints along the shorter boundary path.

For direct cleanup: enable map editing, click the first waypoint, click **Set Line Start**, click the second waypoint, then click **Remove Between Start + Selected**. Review the preview before pressing **Save Map**.

## Fast filtering pipeline

MARK avoids fetching details for every CHP row.

### AREA-prefix allowlist

Only the first two characters of the CHP `AREA` value are compared, case-insensitively. `*` means all AREAs.

Example Border-area profile:

```dotenv
CHP_ALERT_AREA_PREFIXES=BC,El
```

### Type-fragment search

```dotenv
CHP_ALERT_TYPE_FRAGMENTS=Unk,1140,1141,Min,Maj,1179,1180,1178,un w,Repo
```

`*` means all Types.

### Browser-faithful detail retrieval

For each retained listing row, `mark_postback_runtime.py` reads the form action, collects successful form controls, preserves dropdown values, submits the GridView event, and returns the selected incident response.

### CAD coordinate confirmation

MARK treats the selected call's `Lat/Lon:` header as authoritative and checks it directly against the service-area polygon. Address geocoding is not part of the active decision path.

## Technical quick start

### Windows

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start-chp-alerter.ps1
```

### macOS

```bash
chmod +x "Install MARK - macOS.command"
./"Install MARK - macOS.command"
```

### Linux

```bash
chmod +x install-mark-linux.sh
./install-mark-linux.sh
```

## Validation

```powershell
.\.venv\Scripts\python.exe -m py_compile `
  .\mark_region_entry.py `
  .\mark_backend.py `
  .\notification_runtime.py `
  .\update_runtime.py `
  .\mark_update_entry.py `
  .\mark_detail_runtime.py `
  .\mark_postback_runtime.py `
  .\mark_gui_entry.py
```

```powershell
.\.venv\Scripts\python.exe -m unittest `
  .\tests\test_mark_runtime.py `
  .\tests\test_notification_runtime.py `
  .\tests\test_update_runtime.py -v
```

## Important files

- `mark_region_entry.py` — current GUI entry: region selector, visible map controls, first-run helper, versioned window title.
- `mark_update_entry.py` — GUI update, notification-provider, and alert-policy controls.
- `update_runtime.py` — safe Git update discovery and fast-forward installation.
- `mark_gui_entry.py` — safe GUI entry, profiles, filters, simplification, and direct waypoint cleanup.
- `mark_backend.py` — runtime installation order and profile initialization.
- `chp_center_runtime.py` — selected CHP communications-center fetch/parse support.
- `mark_filter_runtime.py` — wildcard-aware AREA and Type filters.
- `mark_postback_runtime.py` — browser-faithful CHP detail selection.
- `mark_detail_runtime.py` — filtering, strict detail parsing, CAD-coordinate match.
- `notification_runtime.py` — Pushover, ntfy, Gotify, and webhook adapters.
- `service_area_runtime.py` — GeoJSON validation and polygon installation.
- `scripts/validate_release.py` — release preflight validation.
- `scripts/build_release.py` — clean release ZIP, manifest, and checksum builder.
- `test_maps/san_diego_region_smoke_test.geojson` — broad static test-only map.
- `HANDOFF.md` — canonical continuation guide.
