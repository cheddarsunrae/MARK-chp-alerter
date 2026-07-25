# MARK — Map-Aware Roadway Knowledge

MARK polls the public California Highway Patrol Border Communications Center CAD page, performs a fast first-pass listing filter, retrieves each selected call through CHP's ASP.NET GridView postback, confirms location from the CAD-supplied `Lat/Lon:` value, checks the active GeoJSON service-area polygon, and sends qualifying incidents through Pushover.

> **Supplemental awareness only.** MARK is not an official CAD terminal, station alerting system, pager, radio, or replacement for agency dispatch. Public webpages, networks, and third-party push services can fail or change.

## Current accepted status

The Windows application is launching and polling successfully. The final live defect was resolved by reproducing the complete browser form submission for CHP detail selection. The monitor now receives the selected incident panel instead of the incident listing again.

## Fast filtering pipeline

MARK avoids fetching details for every CHP row.

### AREA-prefix allowlist

Only the first two characters of the CHP `AREA` value are compared, case-insensitively.

Known values are `San Diego`, `Temecula`, `Oceanside`, `El Cajon`, and `BC`.

Station 36 defaults:

```dotenv
CHP_ALERT_AREA_PREFIXES=BC,El
```

This retains `BC` and `El Cajon` rows while rejecting San Diego, Temecula, and Oceanside before detail requests.

### Type-fragment search

MARK searches the CHP `Type` column for case-insensitive substrings instead of exact full names.

```dotenv
CHP_ALERT_TYPE_FRAGMENTS=Unk,1140,1141,Min,Maj,1179,1180,1178,un w,Repo
```

### Browser-faithful detail retrieval

For each retained listing row, `mark_postback_runtime.py`:

1. reads the form's actual `action` URL;
2. collects all successful `input`, `select`, and `textarea` controls;
3. preserves the selected communications center and dropdown values;
4. submits the GridView `__EVENTTARGET` and `Select$n` argument;
5. receives the selected incident detail response.

Submitting only ASP.NET hidden fields returns the listing again and is not sufficient.

### CAD coordinate confirmation

The selected call's detail header contains `Lat/Lon:`. MARK treats that CAD-supplied coordinate as authoritative and checks it directly against the service-area polygon. Address geocoding is not part of MARK's active decision path.

## Detail parsing and alerts

CHP detail responses may contain the selected incident panel together with the complete all-incidents table. `mark_detail_runtime.py` rejects ordinary listing rows and retains the selected call's canonical coordinate line and genuine CAD/operator notes.

Detail codes `11-78`, `11-79`, `11-80`, and `11-81` remain alert-promoting codes. `11-82` is logged but does not currently create its own alert category.

## Windows quick start

```powershell
cd C:\Users\Shane\Documents\GitHub\chp-alerter
git pull
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start-chp-alerter.ps1
```

The launcher creates `.venv`, installs dependencies, creates `.env` from `.env.example` when needed, performs syntax checks, and starts MARK.

Hidden GUI startup failures are written to `runtime\mark-gui-error.log`.

## Fedora quick start

```bash
sudo dnf install -y python3 python3-tkinter
cd /path/to/chp-alerter
git pull
chmod +x start-chp-alerter.sh
./start-chp-alerter.sh
```

## Profiles

Named profiles save:

- a service-area map copy;
- AREA prefixes to monitor;
- Type fragments to monitor;
- poll interval;
- alert-existing behavior;
- alert-update behavior.

Profile storage:

```text
profiles/profiles.json
profiles/maps/
```

Restart a running backend after loading or changing a profile.

## Map editor

Use **Configuration → Service Area File → …** to load a `.geojson` or `.json` Polygon. GeoJSON uses `[longitude, latitude]`; MARK internally uses `(latitude, longitude)`.

### Extend a zone

1. Enable editing.
2. Select an existing waypoint.
3. Click **Start Extension**.
4. Add at least two clicks.
5. Click **Finish Extension**.
6. MARK replaces the final temporary click with the nearest existing waypoint and replaces the shorter old boundary path.

### Simplify a boundary

**Simplify Boundary** removes near-collinear intermediate waypoints using a user-selected tolerance. The default is 25 metres. This improves readability and editing; it is not a meaningful runtime performance optimization. Review the changed boundary before saving.

## Configuration reference

```dotenv
CHP_ALERT_INTERVAL=30
CHP_ALERT_TIMEOUT=20
CHP_ALERT_STATE_FILE=runtime/state.json
CHP_ALERT_DETAIL_LOG_FILE=runtime/details.jsonl
CHP_ALERT_RETENTION_HOURS=72
CHP_ALERT_LOG_LEVEL=INFO
CHP_ALERT_SERVICE_AREA_FILE=service_area.geojson
CHP_ALERT_PROFILE=
CHP_ALERT_AREA_PREFIXES=BC,El
CHP_ALERT_TYPE_FRAGMENTS=Unk,1140,1141,Min,Maj,1179,1180,1178,un w,Repo
CHP_ALERT_EXISTING=0
CHP_ALERT_UPDATES=0
PUSHOVER_APP_TOKEN=
PUSHOVER_USER_KEY=
PUSHOVER_PRIORITY=2
PUSHOVER_RETRY_SECONDS=30
PUSHOVER_EXPIRE_SECONDS=1800
PUSHOVER_SOUND=alien
```

Legacy geocoder and exact-name filter keys may remain in older `.env` files for compatibility, but they are not authoritative for the current MARK runtime.

Never commit `.env`, credentials, runtime state, captured CAD pages, or private operational profile files.

## Validation

Syntax check:

```powershell
.\.venv\Scripts\python.exe -m py_compile `
  .\chp_jamul_alert.py `
  .\chp_detail_alert.py `
  .\mark_detail_runtime.py `
  .\mark_postback_runtime.py `
  .\mark_backend.py `
  .\chp_gui.py `
  .\mark_gui_entry.py `
  .\geometry_utils.py
```

Unit tests:

```powershell
.\.venv\Scripts\python.exe -m unittest .\tests\test_mark_runtime.py -v
```

Safe dry poll:

```powershell
.\.venv\Scripts\python.exe .\mark_backend.py `
  --once `
  --dry-run `
  --alert-existing `
  --log-level DEBUG
```

Expected successful geographic decisions include `CHP detail Lat/Lon` in the reason.

## Important files

- `mark_gui_entry.py` — safe Tk startup, profile filter manager, boundary simplification
- `chp_gui.py` — branding, anchored zone extension, waypoint dragging
- `mark_app.py` — shared dashboard and subprocess controller
- `mark_backend.py` — runtime entry point and patch installation order
- `mark_postback_runtime.py` — complete browser-faithful CHP detail form submission
- `mark_detail_runtime.py` — AREA/type prefilter, strict detail parser, CAD-coordinate match
- `chp_detail_alert.py` — detail model, codes, JSONL logging, alert formatting
- `chp_jamul_alert.py` — CHP fetch, state, polygon match, and Pushover
- `service_area_runtime.py` — GeoJSON validation and polygon installation
- `geometry_utils.py` — near-collinear waypoint removal
- `HANDOFF.md` — canonical continuation guide
