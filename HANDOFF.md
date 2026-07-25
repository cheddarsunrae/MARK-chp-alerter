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

MARK polls the public CHP Border Communications Center CAD page, performs a fast listing prefilter, opens selected incident details through CHP's ASP.NET GridView postback, confirms location from the CAD-provided `Lat/Lon:` header, checks the active GeoJSON service-area polygon, and sends qualifying Pushover alerts containing the available notes.

MARK is supplemental awareness, not an official dispatch or CAD system.

## Current accepted state

As of 2026-07-25, the user confirmed that MARK **runs fine** after the final detail-postback correction.

The accepted Windows application provides:

- MARK branding and status cards;
- monitor start/stop, test Pushover, dry poll, config/map reload;
- live backend log;
- OpenStreetMap service-area editor;
- draggable waypoints;
- anchored zone-extension workflow;
- named profiles;
- configurable AREA prefixes and Type fragments;
- conservative boundary simplification;
- GUI startup-error logging to `runtime/mark-gui-error.log`;
- successful selected-incident detail retrieval;
- CAD `Lat/Lon:` polygon confirmation without address geocoding.

Fedora support remains required, but the newest GUI changes have not been natively acceptance-tested on Fedora.

## Runtime chain

```text
start-chp-alerter.ps1
  -> mark_gui_entry.py
      -> chp_gui.py + mark_app.py
          -> mark_backend.py
              -> mark_detail_runtime.install()
              -> mark_postback_runtime.install()
              -> service_area_runtime.apply_to_core()
              -> chp_detail_alert.main()
                  -> chp_jamul_alert.main()
```

Patch installation order matters: `mark_postback_runtime.install()` must run after `mark_detail_runtime.install()` because it replaces the detail-fetch function with the browser-faithful implementation.

## Current configuration

```dotenv
CHP_ALERT_INTERVAL=30
CHP_ALERT_TIMEOUT=20
CHP_ALERT_STATE_FILE=runtime/state.json
CHP_ALERT_DETAIL_LOG_FILE=runtime/details.jsonl
CHP_ALERT_RETENTION_HOURS=72
CHP_ALERT_LOG_LEVEL=INFO
CHP_ALERT_SERVICE_AREA_FILE=service_area.geojson
CHP_ALERT_EXISTING=0
CHP_ALERT_UPDATES=0
CHP_ALERT_PROFILE=
CHP_ALERT_AREA_PREFIXES=BC,El
CHP_ALERT_TYPE_FRAGMENTS=Unk,1140,1141,Min,Maj,1179,1180,1178,un w,Repo
PUSHOVER_APP_TOKEN=
PUSHOVER_USER_KEY=
PUSHOVER_PRIORITY=2
PUSHOVER_RETRY_SECONDS=30
PUSHOVER_EXPIRE_SECONDS=1800
PUSHOVER_SOUND=alien
```

Legacy geocoder, ignored-area, and exact-incident-name keys may remain in older `.env` files, but the current authoritative filter keys are `CHP_ALERT_AREA_PREFIXES` and `CHP_ALERT_TYPE_FRAGMENTS`. MARK's active geographic decision uses CHP detail coordinates, not address geocoding.

Never commit `.env`, credentials, runtime logs, state files, captured CHP pages, or private operational profile content.

## Fast first-pass filtering

### AREA

Known CHP `AREA` possibilities:

- `San Diego`
- `Temecula`
- `Oceanside`
- `El Cajon`
- `BC`

MARK compares only the first two characters, case-insensitively. Station 36 defaults to `BC,El`, retaining Border Communications and El Cajon rows while rejecting San Diego, Temecula, and Oceanside before detail fetches.

### Type

MARK searches the CHP `Type` column for these case-insensitive fragments:

```text
Unk
1140
1141
Min
Maj
1179
1180
1178
un w
Repo
```

This is substring-based, not exact-name matching.

## Profiles

Profiles save:

- a private GeoJSON map copy;
- AREA prefixes to monitor;
- Type fragments to monitor;
- poll interval;
- alert-existing behavior;
- alert-update behavior.

Storage:

```text
profiles/profiles.json
profiles/maps/
```

Restart the backend after loading or changing a profile.

## Confirmed incident-detail defects and fixes

### Defect 1: unrelated incident rows leaked into details

CHP detail responses can include the selected incident panel together with the complete all-incidents listing. The original parser accepted every timestamped listing row, causing unrelated calls to appear in each incident's detail array.

`mark_detail_runtime.py` now:

- rejects ordinary all-incidents rows;
- retains genuine CAD/operator notes;
- extracts `Lat/Lon:` from the entire response, not only table rows;
- stores the coordinate as a canonical detail line;
- uses the CAD coordinate directly against the service-area polygon;
- does not fall back to address geocoding.

### Defect 2: detail request returned the listing again

A live capture of incident `0047` proved the saved “detail” response was actually the ordinary nine-row incident listing. The request had submitted only ASP.NET hidden fields and the GridView event.

The browser submits additional successful form controls and posts to the form's declared action URL.

`mark_postback_runtime.py` now:

1. locates the CHP form;
2. collects successful `input`, `select`, and `textarea` controls;
3. omits disabled and non-successful controls;
4. preserves `ddlComCenter`, `ddlSearches`, and `ddlResources`;
5. posts to the form's actual action URL;
6. sends `__EVENTTARGET=gvIncidents` and the row's `Select$n` event argument;
7. passes the selected detail response to `mark_detail_runtime.py`.

This was the final live blocker. The user confirmed the resulting application runs correctly.

## Alert logic

For each listing incident:

1. Reject it if its AREA does not start with an allowed two-character prefix.
2. Reject it if its Type contains none of the configured fragments.
3. Submit the complete browser-faithful GridView detail postback.
4. Reject unrelated all-incidents rows in the returned detail response.
5. Retain the selected call's coordinate header and CAD notes.
6. Parse the CHP `Lat/Lon:` coordinate.
7. Check that coordinate against the active GeoJSON polygon.
8. Send a Pushover alert when relevant and eligible under state/update rules.
9. Write detail changes to JSONL.

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

This improves readability and editing reliability. It is not a meaningful performance optimization for MARK's small polygons. Excessive tolerance can move the operational boundary, so review before Save Map.

## File map

- `start-chp-alerter.ps1` — Windows venv, dependency, syntax preflight, GUI launch
- `start-chp-alerter.sh` — Linux launcher
- `mark_gui_entry.py` — safe Tk startup, profile filter manager, simplification UI
- `chp_gui.py` — branding, zone-extension editor, waypoint dragging
- `mark_app.py` — dashboard base, subprocess management, shared config/map functions
- `mark_backend.py` — 30-second policy, profile/map initialization, runtime patch order
- `mark_postback_runtime.py` — browser-faithful CHP selected-detail submission
- `mark_detail_runtime.py` — AREA/type prefilter, strict parser, CAD-coordinate matching
- `chp_detail_alert.py` — legacy detail model, codes, JSONL logging, alert formatting
- `chp_jamul_alert.py` — base page fetch, state, polygon match, Pushover
- `service_area_runtime.py` — GeoJSON validation and polygon installation
- `geometry_utils.py` — near-collinear waypoint removal
- `tests/test_mark_runtime.py` — parser, coordinate, filter, and simplification regression tests
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
  .\mark_postback_runtime.py `
  .\mark_backend.py `
  .\chp_gui.py `
  .\mark_gui_entry.py `
  .\geometry_utils.py
```

### Unit tests

```powershell
.\.venv\Scripts\python.exe -m unittest .\tests\test_mark_runtime.py -v
```

### Safe live dry poll

```powershell
.\.venv\Scripts\python.exe .\mark_backend.py `
  --once `
  --dry-run `
  --alert-existing `
  --log-level DEBUG
```

Expected successful location reasons include `CHP detail Lat/Lon`.

### GUI acceptance

```powershell
.\start-chp-alerter.ps1
```

Confirmed on Windows by the user:

- GUI launches;
- selected map loads;
- configuration saves;
- monitor starts;
- fast prefilter runs;
- browser-faithful detail selection works;
- application runs normally.

## Remaining non-blocking work

The requested Windows project is functionally complete. Remaining items are optional hardening or portability work, not known blockers:

1. Native Fedora GUI acceptance.
2. Add a committed sanitized full ASP.NET form fixture for postback-control tests.
3. Add a unit test specifically for `successful_form_controls()` and form-action resolution.
4. Consolidate runtime patch modules into the legacy modules only if desired; current layering is working and lower risk.
5. Add CI for syntax and unit tests.

## Known risks

- CHP can change its public HTML or ASP.NET postback structure.
- Type fragments are broad by design and may require profile-specific refinement.
- AREA matching uses only the first two characters by design.
- Pushover priority 2 repeats until acknowledged or expiration.
- Running processes do not automatically reload maps/profiles.
- Aggressive simplification can alter the service boundary.

## User preferences for future work

- Provide complete file replacements rather than partial edits when manual intervention is unavoidable.
- Accuracy over speed.
- Do not claim native testing that was not performed.
- Windows PowerShell is primary; Fedora support must remain intact.
- Keep launchers straightforward.

## Continuation point

The requested Windows implementation is complete and live-accepted. The latest functional layer is `mark_postback_runtime.py`, installed after `mark_detail_runtime.py`. Another thread should begin by verifying `main`, reading this handoff, and running the syntax/tests only if making further changes. There is no known active Windows blocker.
