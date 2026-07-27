# MARK Technical User Guide

## Purpose

MARK is a cross-platform Python/Tkinter application for map-aware monitoring of the public California Highway Patrol CAD traffic page. It supports Windows, macOS, and Linux from the same `main` branch. Separate operating-system branches are unnecessary; platform-specific installers and launchers live in one codebase.

> MARK is supplemental awareness only. It is not an official CAD terminal, pager, radio, or dispatch replacement.

## Versioning

The application version is stored in:

```text
VERSION
```

The normal GUI displays the version in the window title when launched through `mark_region_entry.py`.

## Supported platforms

### Windows

- Windows 10 or 11
- Python 3
- PowerShell
- Tkinter
- Launch with `Install MARK - Windows.bat` or `start-chp-alerter.ps1`

### macOS

- Current supported macOS release
- Python 3 distribution that includes Tk
- Install with `Install MARK - macOS.command`
- Launch later with `Start MARK.command`

### Linux

- Fedora/RHEL, Ubuntu/Debian, openSUSE, or Arch-family systems
- Python 3, venv, and Tk
- Install with `install-mark-linux.sh`
- Launch with `start-chp-alerter.sh` or the generated desktop entry

## Distribution

The development repository is private. Nontechnical users should receive a versioned ZIP or installer from an approved release page or department-controlled location rather than being asked to use Git or GitHub.

A release package should contain the application, platform installers, `.env.example`, profile/test-map data, both user guides, release notes, a manifest, and a checksum file.

## Runtime chain

```text
platform launcher
  -> mark_region_entry.py
      -> mark_update_entry.py
      -> mark_gui_entry.py
          -> mark_backend.py
              -> chp_center_runtime.install()
              -> mark_detail_runtime.install()
              -> mark_filter_runtime.install()
              -> mark_postback_runtime.install()
              -> notification_runtime.install()
              -> service-area loading
              -> generic coordinate-match label / boundary-buffer patch
              -> chp_detail_alert.main()
```

## Installation

### Windows

```powershell
cd C:\path\to\MARK
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start-chp-alerter.ps1
```

### macOS

```bash
cd /path/to/MARK
chmod +x "Install MARK - macOS.command" start-chp-alerter.sh
./"Install MARK - macOS.command"
```

### Linux

```bash
cd /path/to/MARK
chmod +x install-mark-linux.sh start-chp-alerter.sh
./install-mark-linux.sh
```

## Release packaging

Validate the tree:

```bash
python scripts/validate_release.py
```

Build a clean ZIP:

```bash
python scripts/build_release.py
```

Artifacts are written under `dist/`:

```text
MARK-<version>.zip
MARK-<version>.zip.sha256
MARK-<version>/release-manifest.json
```

The release builder excludes `.env`, `runtime/`, virtual environments, `.git/`, logs, state files, and build outputs.

## Core configuration

```dotenv
CHP_ALERT_INTERVAL=30
CHP_ALERT_TIMEOUT=20
CHP_ALERT_STATE_FILE=runtime/state.json
CHP_ALERT_DETAIL_LOG_FILE=runtime/details.jsonl
CHP_ALERT_RETENTION_HOURS=72
CHP_ALERT_LOG_LEVEL=INFO
CHP_ALERT_COMM_CENTER=BCCC
CHP_ALERT_COMM_CENTER_NAME=Border
CHP_ALERT_SERVICE_AREA_FILE=service_area.geojson
CHP_ALERT_SERVICE_AREA_LABEL=
CHP_ALERT_BOUNDARY_BUFFER_METERS=0
CHP_ALERT_ADDRESS_BOX_ADDRESS=
CHP_ALERT_ADDRESS_BOX_HALF_SIZE_METERS=3000
CHP_ALERT_PROFILE=
CHP_ALERT_AREA_PREFIXES=Bo,El
CHP_ALERT_TYPE_FRAGMENTS=Unk,1140,1141,Min,Maj,1179,1180,1178,un w,Repo
CHP_ALERT_EXISTING=0
CHP_ALERT_UPDATES=0
```

`CHP_ALERT_SERVICE_AREA_LABEL` controls human-readable match text. Leave it blank for generic `active service-area polygon` wording or set a profile/station/agency label.

`CHP_ALERT_BOUNDARY_BUFFER_METERS` controls near-boundary alerts. `0` means strict inside-polygon only. A positive value alerts for qualifying incidents that are outside the polygon but within that many metres of the active boundary. For example, `12000` is about 7.5 miles.

`CHP_ALERT_ADDRESS_BOX_ADDRESS` and `CHP_ALERT_ADDRESS_BOX_HALF_SIZE_METERS` store the last address-box helper inputs. The generated GeoJSON is stored under `runtime/address_maps/`; runtime output is intentionally excluded from release ZIPs and Git.

`CHP_ALERT_AREA_PREFIXES=*` is a smoke-test setting that searches all AREA rows in the selected CHP center. `CHP_ALERT_TYPE_FRAGMENTS` should remain at the fixed default trigger set; old beta configs that saved `*` for Type are normalized back to defaults so low-value categories such as Traffic Hazard do not become alert triggers.

## CHP center and AREA selection

The GUI exposes **CHP Region / Service-Area Map** at the top of Configuration.

The center catalog is stored at:

```text
data/chp_communications_centers.json
```

The broad smoke-test boundary catalog is stored at:

```text
data/chp_center_smoke_boundaries.json
```

The **CHP AREA Prefixes** panel includes checkbox indicators plus larger toggle buttons. Select every CHP AREA that overlaps the active map. For BCCC / San Diego County, MARK always includes `Bo` as the regional AREA prefix in addition to selected subareas such as `Sa`, `El`, `Oc`, or `Te`.

Clicking **Load Center Test Map** writes a generated GeoJSON under `runtime/test_maps/`, sets `AREA=*`, resets the boundary buffer to `0`, and saves the configuration. That is a test mode only. Alert Type fragments are not changed by the test-map workflow.

## Region/map save behavior

Map, center, AREA, address-box, and boundary-buffer changes are read by the backend process when the monitor starts. A running monitor does not automatically inherit those changes unless it is restarted.

Use **Save Region/Map** after changing any of these settings. MARK backs up and clears the active state file before the next run so stale dedupe or relevance decisions from the old zone do not carry into the new zone. If the monitor is running, the GUI prompts to restart it immediately.

## Notification providers

The GUI exposes provider and alert-policy fields through **Notification Settings** near the top of the Configuration pane.

```dotenv
NOTIFY_PROVIDERS=pushover
ALERT_SEVERITY=critical
ALERT_DELIVERY_MODE=until_acknowledged
ALERT_RETRY_SECONDS=30
ALERT_EXPIRE_SECONDS=1800
ALERT_COOLDOWN_SECONDS=300
```

Provider identifiers are `pushover`, `ntfy`, `gotify`, and `webhook`. Multiple providers may be comma-separated, for example:

```dotenv
NOTIFY_PROVIDERS=pushover,ntfy
```

The GUI validates selected providers before saving and includes **Test Selected Providers**.

### Pushover

```dotenv
PUSHOVER_APP_TOKEN=
PUSHOVER_USER_KEY=
PUSHOVER_SOUND=alien
```

### ntfy

```dotenv
NTFY_SERVER=https://ntfy.sh
NTFY_TOPIC=
NTFY_TOKEN=
```

Use private topics or a self-hosted server. ntfy receives severity, title, tags, and a CHP click-through link.

### Gotify

```dotenv
GOTIFY_URL=
GOTIFY_APP_TOKEN=
```

### Generic webhook

```dotenv
WEBHOOK_URL=
WEBHOOK_BEARER_TOKEN=
```

## Alert policy

Severity values:

- `low`
- `medium`
- `high`
- `critical`

Delivery values:

- `notify_once`
- `notify_on_update`
- `until_acknowledged`
- `until_expiration`

Provider capability matters. Persistent acknowledgement is guaranteed only when a provider exposes acknowledgement state or MARK operates its own acknowledgement service.

## Map operations

MARK accepts GeoJSON Polygon files. GeoJSON order is `[longitude, latitude]`; MARK internally uses `(latitude, longitude)`.

### Address box maps

The GUI includes an **Address Box Map** helper under **CHP Region / Service-Area Map**.

Workflow:

1. Enter an address.
2. Enter a box half-size in metres.
3. Click **Build Address Box Map**.
4. MARK geocodes the address once, writes a square GeoJSON under `runtime/address_maps/`, loads it as the active service-area map, saves the configuration, clears stale state, and prompts for restart when needed.

The half-size is the distance from the geocoded center point to each side of the square. For example, `3000` creates an approximate 6 km by 6 km box. The map is a square approximation, not a circular radius, and must be visually reviewed before operational use.

Generated address maps reset `CHP_ALERT_BOUNDARY_BUFFER_METERS` to `0` so the selected box is the alerting footprint unless the user intentionally adds a buffer later.

### Boundary buffer / near-boundary alerting

The normal decision remains map-first:

```text
inside polygon = alert
outside polygon = no alert
```

When `CHP_ALERT_BOUNDARY_BUFFER_METERS` is positive, MARK also alerts for qualifying incidents outside the polygon but within that distance of the nearest polygon segment. The match reason explicitly states that the incident is outside the polygon but within the buffer, including both distance from the boundary and the configured buffer.

Use this for edge cases such as a relevant TC just outside a hand-drawn response boundary. Do not use a large buffer unless the operational users understand that it expands the alerting footprint.

### Broad smoke-test maps

The repository includes a static test-only broad San Diego/Border-region map:

```text
test_maps/san_diego_region_smoke_test.geojson
```

The GUI can also generate a broad smoke-test map for any cataloged CHP communications center. These maps are intentionally oversized and must not be used as real response boundaries.

### Conservative simplification

Use **Simplify Boundary** to remove near-collinear waypoints. Start with 10-25 metres, save to a new file, and visually inspect before replacing an operational map.

### Forced direct-line cleanup

Use **Set Line Start** and **Remove Between Start + Selected** when you want to force a straight segment between two waypoints:

1. Enable map editing.
2. Click the first waypoint.
3. Click **Set Line Start**.
4. Click the second waypoint.
5. Click **Remove Between Start + Selected**.
6. Review the new direct segment.
7. Save the map only after confirming the boundary is still correct.

MARK removes the intermediate waypoints along the shorter boundary path and keeps the two endpoints.

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

## Troubleshooting

- GUI startup errors: `runtime/mark-gui-error.log`
- Incident detail history: configured JSONL detail log
- State and deduplication: configured state JSON
- Notification failures: `chp-alerter.notifications` log entries
- Profile and map changes require monitor restart
- Active match reasons should no longer say Station 36 unless the label explicitly contains Station 36
- If a relevant call is just outside the polygon, set a conservative boundary buffer and re-test with a dry poll
- If Traffic Hazard or another non-alert category pages, confirm `CHP_ALERT_TYPE_FRAGMENTS` has been restored to the fixed default trigger list and restart the monitor

## Operational hardening before broad deployment

- Test the generated release ZIP from a clean folder.
- Add CI and automated release artifact generation.
- Add checksummed or signed downloads.
- Add a signed update manifest for ZIP-only users.
- Add durable acknowledgement state where providers lack it.
- Perform native acceptance testing on Windows, macOS, Fedora, and Ubuntu.
