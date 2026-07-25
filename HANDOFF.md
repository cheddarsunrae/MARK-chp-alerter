# MARK project handoff

## Purpose

This document is the canonical continuation guide for **MARK — Map-Aware Roadway Knowledge** in `cheddarsunrae/chp-alerter`. A new thread or developer should read this file, `README.md`, and `MARK_GUI.md` before changing code.

## Repository and working environment

- Repository: `cheddarsunrae/chp-alerter`
- Default branch: `main`
- User's Windows checkout: `C:\Users\Shane\Documents\GitHub\chp-alerter`
- Primary launch command: `.\start-chp-alerter.ps1`
- Fedora/Linux launch command: `./start-chp-alerter.sh`
- GUI entry point: `mark_gui_entry.py`
- Backend entry point: `mark_backend.py`
- Minimum poll interval: **30 seconds**

Always verify the current local and GitHub `main` HEAD before making changes.

## Product intent

MARK watches the public CHP Border Communications Center CAD page, retrieves incident details, filters calls by service-area polygon, ignored CHP regions, configured incident types, and selected CAD codes, then sends qualifying Pushover alerts containing all available notes.

MARK is supplemental situational awareness. It is not an official dispatch or CAD system.

## Current accepted user-facing behavior

### Dashboard

The Windows GUI is launching successfully and has been accepted by the user as working. It includes:

- MARK logo and **Map-Aware Roadway Knowledge** subtitle;
- monitor controls and live status;
- live backend log;
- Pushover test and one-poll dry run;
- configuration editor;
- monitoring profile manager;
- OpenStreetMap polygon editor;
- zone-extension workflow;
- draggable existing waypoints;
- conservative boundary simplification;
- hidden-startup error reporting to `runtime/mark-gui-error.log`.

### Polling

Both GUI and backend accept values of 30 seconds or greater. The old 60-second conflict was resolved by using `mark_backend.py`, which replaces the legacy validator.

### Profiles

Profiles save:

- service-area map copy;
- ignored CHP `AREA` regions;
- incident types;
- poll interval;
- alert-existing setting;
- alert-updates setting.

Storage:

```text
profiles/profiles.json
profiles/maps/
```

The `.env` keys are:

```dotenv
CHP_ALERT_PROFILE=
CHP_ALERT_IGNORED_AREAS=Oceanside,Temecula
CHP_ALERT_INCIDENT_TYPES=Trfc Collision-1141Enrt,Trfc Collision-Unkn Inj,Report of Fire
```

A running monitor must be restarted after profile or map changes.

## Important incident-detail defect and correction

### Defect observed on 2026-07-25

The CHP detail postback returned the selected incident detail panel **and the entire incident listing table**. The legacy `parse_detail_lines` function accepted every timestamped row, causing each incident's `details` array to contain unrelated incidents.

Observed examples included incident `0009` (`Report of Fire`, Proctor Valley Rd / Northwoods Dr) and incident `0047` (`Trfc Collision-1141 Enrt`, SR94 / Otay Lakes Rd). Their detail logs contained summaries for unrelated Oceanside, Temecula, San Diego, El Cajon, and BC calls.

### Current correction

`mark_detail_runtime.py` is installed by `mark_backend.py` before the monitor starts. It:

1. rejects ordinary all-incidents listing rows;
2. retains genuine CAD/operator notes;
3. retains any detail/header row containing coordinates;
4. treats latitude/longitude from the selected detail header as the preferred geographic confirmation;
5. falls back to the legacy text/geocoder flow only when detail coordinates are absent.

The correction is currently layered over `chp_detail_alert.py` to minimize risk. A future cleanup may merge the corrected implementation directly into `chp_detail_alert.py` after fixture-based acceptance tests exist.

### Critical assumption supplied by the user

**The details header for every CHP call contains latitude/longitude.** Matching should rely on those coordinates as confirmation whenever they are present. Do not make third-party geocoding the primary path.

## Alert logic

For each listing incident:

1. Ignore it immediately when its `AREA` matches a configured ignored region.
2. Fetch its CHP detail postback.
3. Parse only selected-call header/note rows.
4. Determine whether its incident type is configured or a detail code promotes it.
5. Prefer coordinates from the detail header.
6. Check those coordinates against the active service-area polygon.
7. Send a Pushover alert when relevant and new/eligible for update notification.
8. Write detail changes to the JSONL detail log.

Default incident types:

- `Trfc Collision-1141Enrt`
- `Trfc Collision-Unkn Inj`
- `Report of Fire`

Alert-promoting codes:

- `11-78`
- `11-79`
- `11-80`
- `11-81`

Log-only code:

- `11-82`

## Map editor

### Loading maps

The Configuration panel's **Service Area File** field and adjacent `…` button load `.geojson` or `.json` files. The file must contain a GeoJSON Polygon. GeoJSON stores `[longitude, latitude]`; MARK internally uses `(latitude, longitude)`.

### Zone extension

1. Enable editing.
2. Click an old waypoint to select the starting anchor.
3. Click **Start Extension**.
4. Add at least two new clicks.
5. The final click is only an endpoint hint.
6. Click **Finish Extension**.
7. MARK substitutes the nearest old waypoint for that final hint and replaces the shorter old boundary path.

### Simplification

`geometry_utils.py` contains `simplify_closed_polygon`. `mark_gui_entry.py` exposes it through **Simplify Boundary**.

The simplifier removes a waypoint only if it lies within a user-selected tolerance of the direct line segment between its neighbours. It repeats until stable and never reduces below three vertices.

The default tolerance is 25 m. This is a readability and editing aid, not an important runtime optimization. Point-in-polygon checks are already negligible for the small number of vertices involved. Too much simplification can move the operational boundary; require review before Save Map.

## Architecture and file ownership

### Runtime chain

```text
start-chp-alerter.ps1
  -> mark_gui_entry.py
      -> chp_gui.py / mark_app.py
          -> mark_backend.py
              -> mark_detail_runtime.install()
              -> service_area_runtime.apply_to_core()
              -> chp_detail_alert.main()
                  -> chp_jamul_alert.main()
```

### Files

- `start-chp-alerter.ps1`: Windows venv/dependency/preflight/GUI launcher
- `start-chp-alerter.sh`: Linux launcher
- `mark_gui_entry.py`: safe Tk initialization, crash logging, map simplification
- `chp_gui.py`: branding, profiles, zone extensions, drag editing
- `mark_app.py`: shared dashboard controls, config, map base, subprocess handling
- `mark_backend.py`: 30-second policy, selected profile filters, service-area load
- `mark_detail_runtime.py`: strict detail parser and coordinate priority
- `chp_detail_alert.py`: detail incident model, codes, logs, message formatting, polling extension
- `chp_jamul_alert.py`: base page fetch, state, geocoder, polygon match, Pushover
- `service_area_runtime.py`: GeoJSON validation and core polygon installation
- `geometry_utils.py`: near-collinear point removal
- `service_area.geojson`: default sample boundary
- `.env.example`: configuration template
- `README.md`: operator and developer overview
- `MARK_GUI.md`: detailed GUI instructions
- `HANDOFF.md`: this continuation document

## Configuration keys

```dotenv
CHP_ALERT_INTERVAL=30
CHP_ALERT_TIMEOUT=20
CHP_ALERT_STATE_FILE=runtime/state.json
CHP_ALERT_DETAIL_LOG_FILE=runtime/details.jsonl
CHP_ALERT_RETENTION_HOURS=72
CHP_ALERT_LOG_LEVEL=INFO
CHP_ALERT_SERVICE_AREA_FILE=service_area.geojson
CHP_ALERT_GEOCODER=nominatim
CHP_ALERT_CONTACT=mailto:you@example.com
CHP_ALERT_EXISTING=0
CHP_ALERT_UPDATES=0
CHP_ALERT_PROFILE=
CHP_ALERT_IGNORED_AREAS=Oceanside,Temecula
CHP_ALERT_INCIDENT_TYPES=Trfc Collision-1141Enrt,Trfc Collision-Unkn Inj,Report of Fire
PUSHOVER_APP_TOKEN=
PUSHOVER_USER_KEY=
PUSHOVER_PRIORITY=2
PUSHOVER_RETRY_SECONDS=30
PUSHOVER_EXPIRE_SECONDS=1800
PUSHOVER_SOUND=alien
```

Never commit `.env` or real credentials.

## Required validation after pulling this handoff state

### 1. Syntax check

```powershell
cd C:\Users\Shane\Documents\GitHub\chp-alerter
.\.venv\Scripts\python.exe -m py_compile `
  .\chp_jamul_alert.py `
  .\chp_detail_alert.py `
  .\mark_detail_runtime.py `
  .\mark_backend.py `
  .\chp_gui.py `
  .\mark_gui_entry.py `
  .\geometry_utils.py
```

### 2. GUI launch

```powershell
.\start-chp-alerter.ps1
```

Confirm:

- GUI opens;
- existing map loads;
- profile manager opens;
- Simplify Boundary dialog opens;
- Start Monitor works at 30 seconds.

### 3. Safe one-poll test

```powershell
.\.venv\Scripts\python.exe .\mark_backend.py `
  --once `
  --dry-run `
  --alert-existing `
  --log-level DEBUG
```

Confirm:

- each incident's detail array contains only its own selected-call header and notes;
- detail-header coordinates are detected;
- matching reason includes `detail-header coordinates` when coordinates exist;
- no notification is sent because `--dry-run` is active.

### 4. Detail-log inspection

Inspect the newest lines in the configured JSONL file. No record should contain a series of unrelated incident summaries in its `details` array.

## Tests still needed

The following should be added as committed fixtures/tests:

1. A synthetic detail response containing one selected detail panel plus an entire listing table.
2. Confirmation that ordinary rows such as `Details | 0047 | 12:53 AM | ...` are rejected.
3. Confirmation that a coordinate-bearing selected detail header is retained.
4. Confirmation that the retained coordinate is checked against the GeoJSON polygon before geocoding.
5. Regression cases for incident `0009` and incident `0047` shapes.
6. Polygon simplification tests for straight, bent, closed, and minimum-three-point cases.
7. Native Fedora GUI acceptance.

## Known risks and caveats

- CHP HTML and ASP.NET postback structure may change without notice.
- `mark_detail_runtime.py` patches the legacy module at runtime; future refactoring must preserve patch installation order.
- A detail-header coordinate format not recognized by `core.extract_coordinates` would fall back to geocoding. Capture a real sanitized header line if this happens and expand the coordinate patterns.
- Profile incident types require exact normalized CHP names.
- Ignored area matching is substring-based.
- Pushover priority 2 repeats until acknowledged or expired.
- Map changes are not applied to an already-running backend process.
- Very aggressive simplification can alter the service boundary.

## Recommended next work, in order

1. Run the dry poll and inspect real detail-header coordinate formatting.
2. Add regression fixtures using sanitized real responses.
3. Confirm incidents `0009` and `0047` would match based on detail coordinates.
4. Verify no all-incidents rows leak into detail logs.
5. Test Simplify Boundary at 10 m, 25 m, and 50 m on a copy of the map.
6. Consolidate `mark_detail_runtime.py` into `chp_detail_alert.py` only after tests pass.
7. Add visible backend PID and active profile to dashboard status if desired.

## User preferences relevant to continuation

- Provide complete file replacements rather than partial snippets when manual changes are required.
- Accuracy is more important than speed.
- Do not claim native GUI testing that was not performed.
- Windows PowerShell is the primary local environment; Fedora support must remain intact.
- Avoid Bash `set -o pipefail`; the Linux launcher intentionally uses simpler shell behavior.

## Current handoff statement

The GUI and profile/map workflows are operational on Windows. The newly added detail-runtime correction and boundary simplifier are committed and documented, but the detail correction still requires a real dry-poll acceptance test against CHP's current response. The next thread should begin by pulling `main`, running the syntax check and dry poll above, and reviewing the resulting detail JSONL before making further architectural changes.