# MARK — Map-Aware Roadway Knowledge

MARK polls the public California Highway Patrol CAD page, performs a fast first-pass listing filter, retrieves selected incident details, confirms location from the CAD-supplied `Lat/Lon:` value, checks an active GeoJSON service-area polygon, and sends qualifying incidents through configured notification providers.

> **Supplemental awareness only.** MARK is not an official CAD terminal, station alerting system, pager, radio, or replacement for agency dispatch. Public webpages, networks, and third-party push services can fail or change.

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

- `MARK_QUICK_START_GUIDE.md` — for users who do not know GitHub, PowerShell, Terminal, or Python.
- `MARK_TECHNICAL_USER_GUIDE.md` — installation, configuration, providers, validation, and troubleshooting.
- `USER_GUIDE.md` — earlier general operating guide retained for compatibility.
- `docs/STATEWIDE_NOTIFICATION_EXPANSION.md` — statewide and multi-provider architecture.
- `data/chp_communications_centers.json` — CHP communications-center catalog.

Nontechnical operational users should receive a versioned ZIP or installer from an approved department or MARK release location. They should not be expected to clone a GitHub repository.

## Current accepted status

The Windows application launches and polls successfully. The final live defect was resolved by reproducing the complete browser form submission for CHP detail selection. The monitor now receives the selected incident panel instead of the incident listing again.

## Notification runtime

`notification_runtime.py` provides a common provider interface for:

- Pushover
- ntfy
- Gotify
- Generic JSON webhooks

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

## Fast filtering pipeline

MARK avoids fetching details for every CHP row.

### AREA-prefix allowlist

Only the first two characters of the CHP `AREA` value are compared, case-insensitively.

Station 36 defaults:

```dotenv
CHP_ALERT_AREA_PREFIXES=BC,El
```

### Type-fragment search

```dotenv
CHP_ALERT_TYPE_FRAGMENTS=Unk,1140,1141,Min,Maj,1179,1180,1178,un w,Repo
```

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
  .\mark_backend.py `
  .\notification_runtime.py `
  .\mark_detail_runtime.py `
  .\mark_postback_runtime.py `
  .\mark_gui_entry.py
```

```powershell
.\.venv\Scripts\python.exe -m unittest `
  .\tests\test_mark_runtime.py `
  .\tests\test_notification_runtime.py -v
```

## Important files

- `mark_gui_entry.py` — safe GUI entry, profiles, filters, map simplification
- `mark_backend.py` — runtime installation order and profile initialization
- `mark_postback_runtime.py` — browser-faithful CHP detail selection
- `mark_detail_runtime.py` — filtering, strict detail parsing, CAD-coordinate match
- `notification_runtime.py` — Pushover, ntfy, Gotify, and webhook adapters
- `service_area_runtime.py` — GeoJSON validation and polygon installation
- `HANDOFF.md` — canonical continuation guide
