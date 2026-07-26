# MARK Technical User Guide

## Purpose

MARK is a cross-platform Python/Tkinter application for map-aware monitoring of the public California Highway Patrol CAD traffic page. It supports Windows, macOS, and Linux from the same `main` branch. Separate operating-system branches are unnecessary; platform-specific installers and launchers live in one codebase.

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

A release package should contain the application, platform installers, `.env.example`, profile templates, both user guides, and a checksum/version file.

## Runtime chain

```text
platform launcher
  -> mark_update_entry.py
      -> mark_gui_entry.py
          -> mark_backend.py
              -> mark_detail_runtime.install()
              -> mark_postback_runtime.install()
              -> notification_runtime.install()
              -> service-area loading
              -> generic coordinate-match label patch
              -> chp_detail_alert.main()
```

## Installation

### Windows

```powershell
cd C:\path\to\chp-alerter
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start-chp-alerter.ps1
```

### macOS

```bash
cd /path/to/chp-alerter
chmod +x "Install MARK - macOS.command" start-chp-alerter.sh
./"Install MARK - macOS.command"
```

### Linux

```bash
cd /path/to/chp-alerter
chmod +x install-mark-linux.sh start-chp-alerter.sh
./install-mark-linux.sh
```

## Core configuration

```dotenv
CHP_ALERT_INTERVAL=30
CHP_ALERT_TIMEOUT=20
CHP_ALERT_STATE_FILE=runtime/state.json
CHP_ALERT_DETAIL_LOG_FILE=runtime/details.jsonl
CHP_ALERT_RETENTION_HOURS=72
CHP_ALERT_LOG_LEVEL=INFO
CHP_ALERT_SERVICE_AREA_FILE=service_area.geojson
CHP_ALERT_SERVICE_AREA_LABEL=
CHP_ALERT_PROFILE=
CHP_ALERT_AREA_PREFIXES=BC,El
CHP_ALERT_TYPE_FRAGMENTS=Unk,1140,1141,Min,Maj,1179,1180,1178,un w,Repo
CHP_ALERT_EXISTING=0
CHP_ALERT_UPDATES=0
```

`CHP_ALERT_SERVICE_AREA_LABEL` controls human-readable match text. Leave it blank for generic `active service-area polygon` wording or set a profile/station/agency label.

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

## Profiles and statewide operation

Profiles should contain communications-center code and name, selected AREA values, Type fragments, service-area polygon, poll interval, alert-existing/update settings, and notification routing.

The statewide catalog is stored in `data/chp_communications_centers.json`. The durable design is to read the live CHP center dropdown and record AREA values observed per center.

## Map operations

MARK accepts GeoJSON Polygon files. GeoJSON order is `[longitude, latitude]`; MARK internally uses `(latitude, longitude)`.

### Broad smoke-test map

The repository includes a test-only broad San Diego/Border-region map:

```text
test_maps/san_diego_region_smoke_test.geojson
```

Use this to confirm that the polling, detail selection, CAD coordinate parsing, polygon check, and notification path are working without waiting for a call inside a small station polygon. It is intentionally oversized and must not be used as a real response boundary.

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

## Operational hardening before broad deployment

- Publish versioned release packages.
- Add CI and automated tests.
- Add checksummed or signed downloads.
- Add statewide center selection and AREA discovery.
- Add durable acknowledgement state where providers lack it.
- Perform native acceptance testing on Windows, macOS, Fedora, and Ubuntu.
