# MARK canonical handoff

## Repository

- Project: **MARK — Map-Aware Roadway Knowledge**
- Repository: `cheddarsunrae/chp-alerter`
- Default branch: `main`
- Primary Windows checkout: `C:\Users\Shane\Documents\GitHub\chp-alerter`
- Windows launcher: `start-chp-alerter.ps1`
- Linux launcher: `start-chp-alerter.sh`
- GUI entry point: `mark_gui_entry.py`
- Backend entry point: `mark_backend.py`
- Minimum poll interval: **30 seconds**

Before changing code, verify local and GitHub `main` HEAD and read `README.md` and `MARK_GUI.md`.

## Product purpose

MARK polls the public CHP Border Communications Center CAD page, retrieves selected-call details, filters incidents by service-area polygon, ignored CHP `AREA` regions, incident types, and selected CAD codes, then sends qualifying Pushover alerts containing the available notes.

MARK is supplemental awareness, not an official dispatch or CAD system.

## Current accepted state

The Windows GUI launches successfully and has been user-accepted as working. It currently provides:

- MARK branding and status cards;
- monitor start/stop, test Pushover, dry poll, config/map reload;
- live backend log;
- OpenStreetMap service-area editor;
- draggable waypoints;
- anchored zone-extension workflow;
- named profiles;
- configurable ignored regions and incident types;
- conservative boundary simplification;
- GUI startup-error logging to `runtime/mark-gui-error.log`.

Fedora support remains required, but native Fedora acceptance has not yet been performed for the newest GUI changes.

## Runtime chain

```text
start-chp-alerter.ps1
  -> mark_gui_entry.py
      -> chp_gui.py + mark_app.py
          -> mark_backend.py
              -> mark_detail_runtime.install()
              -> service_area_runtime.apply_to_core()
              -> chp_detail_alert.main()
                  -> chp_jamul_alert.main()
```

## Current configuration model

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

Never commit `.env`, credentials, runtime logs, state files, or private operational profile content.

## Profiles

Profiles save:

- a private GeoJSON map copy;
- ignored CHP regions;
- monitored incident types;
- poll interval;
- alert-existing behavior;
- alert-update behavior.

Storage:

```text
profiles/profiles.json
profiles/maps/
```

Restart the backend after loading or changing a profile.

## Incident-detail defect discovered on 2026-07-25

CHP detail postbacks can return both:

1. the selected incident's detail header and CAD/operator notes; and
2. the complete all-incidents listing table.

The legacy parser accepted every timestamped row, so each incident's `details` array could contain unrelated incidents. Real examples included incident `0009` (`Report of Fire`, Proctor Valley Rd / Northwoods Dr) and `0047` (`Trfc Collision-1141 Enrt`, SR94 / Otay Lakes Rd).

## Current detail correction

`mark_detail_runtime.py` patches the legacy detail module at startup. It:

- rejects ordinary all-incidents rows;
- retains genuine note rows;
- retains coordinate-bearing detail-header rows;
- treats latitude/longitude from the selected call's detail header as the preferred geographic confirmation;
- falls back to the existing text/geocoder chain only when detail coordinates are unavailable.

The user confirmed that every call's details header includes latitude/longitude. That coordinate should remain the primary location source. Nominatim is a fallback.

The correction is layered over `chp_detail_alert.py` to minimize regression risk. Consolidate it into the legacy module only after real-response acceptance and fixture coverage are complete.

## Alert logic

For each incident:

1. Discard it when its `AREA` matches a configured ignored region.
2. Fetch the selected incident detail postback.
3. Remove unrelated all-incidents rows.
4. Retain selected-call header/notes.
5. Require a configured incident type or qualifying detail code.
6. Prefer detail-header latitude/longitude.
7. Check the coordinate against the active GeoJSON polygon.
8. Send a Pushover alert when relevant and eligible under state/update rules.
9. Write detail changes to JSONL.

Default alert types:

- `Trfc Collision-1141Enrt`
- `Trfc Collision-Unkn Inj`
- `Report of Fire`

Alert-promoting codes: `11-78`, `11-79`, `11-80`, `11-81`.

Log-only code: `11-82`.

## Map workflow

### Load a map

Use **Configuration → Service Area File → …** and choose a `.geojson` or `.json` file containing a Polygon. GeoJSON stores `[longitude, latitude]`; MARK internally uses `(latitude, longitude)`.

### Extend a zone

1. Enable editing.
2. Select an existing waypoint; it turns red.
3. Click **Start Extension**.
4. Add at least two clicks.
5. The final click is only an endpoint hint.
6. Click **Finish Extension**.
7. MARK replaces the final hint with the nearest old waypoint and replaces the shorter old boundary path.
8. Review and save.

### Simplify a boundary

`geometry_utils.py` implements `simplify_closed_polygon`. `mark_gui_entry.py` exposes **Simplify Boundary**.

The simplifier removes a waypoint only when it lies within the chosen tolerance of the direct segment between its immediate neighbours. It repeats until stable and never reduces below three vertices.

Default tolerance: 25 m.

This mainly improves readability and editing reliability. It is not a meaningful performance optimization for MARK's small polygons; point-in-polygon checks are already fast. Excessive tolerance can move the operational boundary, so require visual review before Save Map.

## File map

- `start-chp-alerter.ps1` — Windows venv, dependency, syntax preflight, GUI launch
- `start-chp-alerter.sh` — Linux launcher; intentionally avoids Bash pipefail
- `mark_gui_entry.py` — safe Tk startup, error logging, simplification UI
- `chp_gui.py` — profiles, region/type selection, zone-extension editor
- `mark_app.py` — dashboard base, subprocess management, shared config/map functions
- `mark_backend.py` — 30-second policy, profile application, runtime patch install
- `mark_detail_runtime.py` — corrected selected-call detail parser and coordinate priority
- `chp_detail_alert.py` — legacy detail model, codes, JSONL logging, alert formatting
- `chp_jamul_alert.py` — polling, state, base parser, geocoder, polygon check, Pushover
- `service_area_runtime.py` — GeoJSON validation and core polygon installation
- `geometry_utils.py` — near-collinear waypoint removal
- `tests/test_mark_runtime.py` — baseline detail-parser and simplification regression tests
- `README.md` — operator/developer overview
- `MARK_GUI.md` — GUI instructions
- `HANDOFF.md` — this canonical continuation document

## Validation commands

### Pull

```powershell
cd C:\Users\Shane\Documents\GitHub\chp-alerter
git pull
```

### Syntax check

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

### Baseline unit tests

```powershell
.\.venv\Scripts\python.exe -m unittest .\tests\test_mark_runtime.py -v
```

Committed tests currently cover:

- rejection of ordinary all-incidents rows;
- retention of a coordinate-bearing detail header;
- retention of a genuine operator note;
- near-collinear waypoint removal;
- never reducing below three vertices.

### Safe live dry poll

```powershell
.\.venv\Scripts\python.exe .\mark_backend.py `
  --once `
  --dry-run `
  --alert-existing `
  --log-level DEBUG
```

Confirm:

- each detail record contains only its own header/notes;
- coordinate-header rows remain present;
- matching reasons include `detail-header coordinates`;
- incidents outside the polygon are rejected;
- no Pushover notification is delivered in dry-run mode.

### GUI acceptance

```powershell
.\start-chp-alerter.ps1
```

Confirm:

- GUI opens;
- map and profiles load;
- monitor starts at 30 seconds;
- zone-extension workflow works;
- Simplify Boundary previews and applies only after confirmation.

## Remaining work

1. Run the real CHP dry poll and inspect actual coordinate-header formatting.
2. Confirm incidents shaped like `0009` and `0047` qualify when their detail coordinates lie inside the polygon.
3. Confirm the JSONL log no longer contains unrelated listing rows.
4. Add sanitized real CHP HTML fixtures after acceptance.
5. Add tests proving coordinate matching occurs before Nominatim.
6. Add bent-boundary simplification tests.
7. Perform native Fedora GUI acceptance.
8. Consider consolidating `mark_detail_runtime.py` into `chp_detail_alert.py` after regression coverage is mature.

## Known risks

- CHP can change its public HTML or ASP.NET postback structure.
- Coordinate text must match `core.extract_coordinates`; capture a sanitized real header if it does not.
- Profile incident names are exact after normalization.
- Ignored area matching is case-insensitive substring matching.
- Pushover priority 2 repeats until acknowledged or expiration.
- Running processes do not automatically reload maps/profiles.
- Aggressive simplification can alter the service boundary.

## User preferences for future work

- Provide complete file replacements rather than partial edits when manual intervention is unavoidable.
- Accuracy over speed.
- Do not claim native testing that was not performed.
- Windows PowerShell is primary; Fedora support must remain intact.
- Keep launchers straightforward; avoid `set -o pipefail`.

## Continuation point

The repository is documented and contains the detail-runtime correction, coordinate priority, profile system, zone editor, boundary simplifier, and baseline tests. The immediate next step is a real dry-poll acceptance test followed by inspection of `runtime/details.jsonl`. Do not refactor the runtime patch into the legacy detail file until that acceptance succeeds.