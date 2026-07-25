# MARK — Map-Aware Roadway Knowledge

MARK polls the public California Highway Patrol CAD page, retrieves incident details, checks incidents against a configurable GeoJSON service area, and sends qualifying incidents through Pushover.

> **Supplemental awareness only.** MARK is not an official CAD terminal, pager, radio, station alerting system, or replacement for agency dispatch. Public webpages, networks, geocoding, and push services can fail or change.

## Current capabilities

- Cross-platform Tkinter dashboard for Windows and Fedora/Linux
- Minimum polling interval of 30 seconds
- Pushover emergency-priority notifications
- Incident-detail postback retrieval
- Detail-code handling for `11-78`, `11-79`, `11-80`, `11-81`, and log-only `11-82`
- GeoJSON service-area polygons on an OpenStreetMap basemap
- Zone-extension editing, draggable waypoints, and conservative boundary simplification
- Configurable ignored CHP `AREA` regions
- Configurable incident types
- Named profiles that save map, ignored regions, incident types, polling, and update behavior
- JSONL detail audit log and persistent incident state

## Alert decision order

For every non-ignored incident, MARK:

1. fetches the selected incident detail postback;
2. rejects ordinary all-incidents listing rows that CHP also returns in that response;
3. retains the selected incident's header and genuine CAD/operator notes;
4. checks the configured incident type or qualifying detail code;
5. uses latitude/longitude from the selected detail header as the preferred geographic confirmation;
6. falls back to embedded listing coordinates, configured text rules, then Nominatim geocoding;
7. checks the resulting coordinate against the active service-area polygon;
8. sends a Pushover alert containing the incident summary and available notes.

Coordinates in the detail header are treated as authoritative because they are supplied by CHP for the selected call. Third-party geocoding is a fallback, not the primary location source.

## Default incident types and codes

Default incident types:

- `Trfc Collision-1141Enrt`
- `Trfc Collision-Unkn Inj`
- `Report of Fire`

Configured values are stored in:

```dotenv
CHP_ALERT_INCIDENT_TYPES=Trfc Collision-1141Enrt,Trfc Collision-Unkn Inj,Report of Fire
```

Codes `11-78`, `11-79`, `11-80`, and `11-81` can promote another incident type into the normal geographically filtered alert path. `11-82` is recorded but does not generate its own alert.

## Ignored CHP regions

Ignored regions are profile-configurable rather than hard-coded:

```dotenv
CHP_ALERT_IGNORED_AREAS=Oceanside,Temecula
```

Examples:

- North County users might ignore `San Diego` but keep `Oceanside` and `Temecula`.
- East County users may ignore `Oceanside` and `Temecula` while retaining `El Cajon`, `BC`, and `San Diego`.
- An empty ignored-region list processes every CHP `AREA` value.

Matching is case-insensitive and substring-based.

## Windows quick start

```powershell
cd C:\Users\Shane\Documents\GitHub\chp-alerter
git pull
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start-chp-alerter.ps1
```

The launcher creates `.venv` when needed, installs requirements, creates `.env` from `.env.example`, performs a Python syntax preflight, and starts `mark_gui_entry.py` through `pythonw.exe`.

Hidden GUI startup failures are written to:

```text
runtime\mark-gui-error.log
```

## Fedora/Linux quick start

```bash
sudo dnf install -y python3 python3-tkinter
cd /path/to/chp-alerter
git pull
chmod +x start-chp-alerter.sh
./start-chp-alerter.sh
```

## Required configuration

Enter these values in the GUI:

```dotenv
CHP_ALERT_CONTACT=mailto:you@example.com
PUSHOVER_APP_TOKEN=your_application_api_token
PUSHOVER_USER_KEY=your_user_or_group_key
```

Default emergency settings:

```dotenv
PUSHOVER_PRIORITY=2
PUSHOVER_RETRY_SECONDS=30
PUSHOVER_EXPIRE_SECONDS=1800
PUSHOVER_SOUND=alien
```

## Monitoring profiles

Open **Profiles / Regions / Incident Types** in the Configuration panel.

A profile saves:

- a private GeoJSON map copy;
- ignored CHP regions;
- incident types;
- poll interval;
- alert-existing behavior;
- alert-update behavior.

Profile metadata is stored in:

```text
profiles/profiles.json
profiles/maps/
```

Loading a profile updates the GUI and active `.env`. Restart a running monitor after loading or changing a profile.

## Loading a service-area map

In **Configuration**, locate **Service Area File**, click `…`, and choose a `.geojson` or `.json` file. The file must contain a GeoJSON `Polygon` with at least three unique vertices.

GeoJSON coordinate order is:

```text
[longitude, latitude]
```

MARK internally displays and processes points as `(latitude, longitude)`.

## Map editing

Editing is disabled by default so panning and zoom controls cannot alter the polygon.

### Extend an existing zone

1. Enable editing.
2. Click an existing numbered waypoint; it turns red.
3. Click **Start Extension**.
4. Click at least two new positions.
5. The final click acts as an endpoint hint.
6. Click **Finish Extension**.
7. MARK substitutes the nearest pre-existing waypoint for the final temporary point and replaces the shorter old boundary segment.
8. Review the result and press **Save Map**.

Existing waypoints may be dragged when no extension is active.

### Simplify Boundary

**Simplify Boundary** removes points that are nearly collinear with their immediate neighbours. The user chooses a tolerance in metres and confirms the number of points to remove before the map changes.

A 25 m default is intentionally conservative. Simplification can reduce redundant hand-drawn points and make the boundary easier to inspect and serialize, but it does **not meaningfully improve point-in-polygon performance at normal MARK polygon sizes**. The main benefit is a cleaner, less error-prone boundary. Excessive tolerance can move the boundary, so always review the preview before saving.

## Detail parsing and logs

`chp_detail_alert.py` contains the legacy detail workflow. `mark_detail_runtime.py` installs the corrected parser at startup.

The correction is necessary because CHP detail postbacks may contain:

- the selected incident detail header;
- genuine CAD/operator notes;
- the complete incident listing table.

The corrected parser keeps coordinate-bearing detail-header rows and real notes while rejecting ordinary listing rows. This prevents every incident from inheriting every other incident's summary.

Detail changes are stored in JSON Lines format at `CHP_ALERT_DETAIL_LOG_FILE`. Records include incident metadata, retained notes, and detected 11-codes.

## Safe command-line tests

Syntax check:

```powershell
.\.venv\Scripts\python.exe -m py_compile `
  .\chp_jamul_alert.py `
  .\chp_detail_alert.py `
  .\mark_detail_runtime.py `
  .\mark_backend.py `
  .\chp_gui.py `
  .\mark_gui_entry.py `
  .\geometry_utils.py
```

One dry poll:

```powershell
.\.venv\Scripts\python.exe .\mark_backend.py `
  --once `
  --dry-run `
  --alert-existing `
  --log-level DEBUG
```

The dry run prints qualifying alerts but does not deliver Pushover notifications.

## Important files

- `mark_gui_entry.py` — safe GUI entry point and boundary simplification
- `chp_gui.py` — profiles and zone-extension map editor
- `mark_app.py` — dashboard foundation and process controller
- `mark_backend.py` — production backend entry point and profile application
- `mark_detail_runtime.py` — corrected CHP detail parsing and coordinate priority
- `chp_detail_alert.py` — detail models, logs, codes, and alert formatting
- `chp_jamul_alert.py` — CHP polling, state, geocoding, polygon matching, and Pushover
- `geometry_utils.py` — conservative polygon simplification
- `service_area_runtime.py` — GeoJSON validation and runtime loading
- `service_area.geojson` — supplied sample map
- `.env.example` — configuration template
- `MARK_GUI.md` — GUI instructions
- `HANDOFF.md` — complete continuation state for another thread

## Security

Never commit `.env`, Pushover credentials, recipient keys, runtime state, or private operational profiles. Review `.gitignore` before adding profile data or logs.