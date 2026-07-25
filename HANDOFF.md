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

MARK polls the public CHP Border Communications Center CAD page, performs a fast listing prefilter, retrieves selected-call details, confirms location from the detail-header latitude/longitude, checks the active GeoJSON service-area polygon, and sends qualifying Pushover alerts containing the available notes.

MARK is supplemental awareness, not an official dispatch or CAD system.

## Current accepted state

The Windows GUI launches successfully and has been accepted by the user. It currently provides:

- MARK branding and status cards;
- monitor start/stop, test Pushover, dry poll, config/map reload;
- live backend log;
- OpenStreetMap service-area editor;
- draggable waypoints;
- anchored zone-extension workflow;
- named profiles;
- configurable AREA prefixes and Type fragments;
- conservative boundary simplification;
- GUI startup-error logging to `runtime/mark-gui-error.log`.

Fedora support remains required, but the newest GUI changes still need native Fedora acceptance.

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

## Current configuration

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
CHP_ALERT_AREA_PREFIXES=BC,El
CHP_ALERT_TYPE_FRAGMENTS=Unk,1140,1141,Min,Maj,1179,1180,1178,un w,Repo
PUSHOVER_APP_TOKEN=
PUSHOVER_USER_KEY=
PUSHOVER_PRIORITY=2
PUSHOVER_RETRY_SECONDS=30
PUSHOVER_EXPIRE_SECONDS=1800
PUSHOVER_SOUND=alien
```

Legacy `CHP_ALERT_IGNORED_AREAS` and `CHP_ALERT_INCIDENT_TYPES` remain in `.env.example` only for migration compatibility. The AREA-prefix and Type-fragment keys are authoritative.

Never commit `.env`, credentials, runtime logs, state files, or private operational profile content.

## Fast first-pass filtering

### AREA

The CHP `AREA` possibilities currently known are:

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

This is deliberately substring-based, not exact-name matching. It reduces detail-postback traffic and tolerates CHP wording variations.

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

## Incident-detail defect discovered on 2026-07-25

CHP detail postbacks can return both:

1. the selected incident's detail header and CAD/operator notes; and
2. the complete all-incidents listing table.

The legacy parser accepted every timestamped row, so each incident's `details` array could contain unrelated incidents. Real examples included incident `0009` (`Report of Fire`, Proctor Valley Rd / Northwoods Dr) and `0047` (`Trfc Collision-1141 Enrt`, SR94 / Otay Lakes Rd).

## Current detail correction

`mark_detail_runtime.py` patches the legacy detail module at startup. It:

- filters the listing by AREA prefix and Type fragment before details are requested;
- rejects ordinary all-incidents rows in detail responses;
- retains genuine note rows;
- retains coordinate-bearing detail-header rows;
- treats latitude/longitude from the selected call's detail header as the preferred geographic confirmation;
- falls back to the existing text/geocoder chain only when detail coordinates are unavailable.

The user confirmed that every call's details header includes latitude/longitude. That coordinate must remain the primary location source. Nominatim is fallback-only.

The correction is layered over `chp_detail_alert.py` to minimize regression risk. Consolidate it into the legacy module only after real-response acceptance and fixture coverage are complete.

## Alert logic

For each listing incident:

1. Reject it if its AREA does not start with an allowed two-character prefix.
2. Reject it if its Type contains none of the configured fragments.
3. Fetch the selected incident detail postback.
4. Remove unrelated all-incidents rows.
5. Retain selected-call coordinate header and notes.
6. Prefer detail-header latitude/longitude.
7. Check the coordinate against the active GeoJSON polygon.
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

This improves readability and editing reliability. It is not a meaningful performance optimization for MARK's small polygons. Excessive tolerance can move the operational boundary, so require visual review before Save Map.

## File map

- `start-chp-alerter.ps1` — Windows venv, dependency, syntax preflight, GUI launch
- `start-chp-alerter.sh` — Linux launcher; intentionally avoids Bash pipefail
- `mark_gui_entry.py` — safe Tk startup, profile filter manager, simplification UI
- `chp_gui.py` — branding, zone-extension editor, waypoint dragging
- `mark_app.py` — dashboard base, subprocess management, shared config/map functions
- `mark_backend.py` — 30-second policy, profile/map initialization, runtime patch install
- `mark_detail_runtime.py` — AREA/type prefilter, strict detail parser, coordinate priority
- `chp_detail_alert.py` — legacy detail model, codes, JSONL logging, alert formatting
- `chp_jamul_alert.py` — polling, state, base parser, geocoder, polygon check, Pushover
- `service_area_runtime.py` — GeoJSON validation and core polygon installation
- `geometry_utils.py` — near-collinear waypoint removal
- `tests/test_mark_runtime.py` — detail parser, filters, and simplification regression tests
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

### Unit tests

```powershell
.\.venv\Scripts\python.exe -m unittest .\tests\test_mark_runtime.py -v
```

Tests cover:

- rejection of ordinary all-incidents rows;
- retention of a coordinate-bearing detail header;
- retention of a genuine operator note;
- Station 36 AREA defaults `BC,El`;
- first-two-character AREA matching;
- case-insensitive Type-fragment matching;
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

- the fast-prefilter log shows AREA prefixes and Type fragments;
- only retained listing rows receive detail requests;
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
- profile manager shows AREA prefixes and Type fragments;
- Station 36 defaults are `BC,El` and the ten supplied fragments;
- monitor starts at 30 seconds;
- zone-extension workflow works;
- Simplify Boundary previews and applies only after confirmation.

## Remaining work

1. Run the real CHP dry poll and inspect actual coordinate-header formatting.
2. Confirm incidents shaped like `0009` and `0047` qualify when their detail coordinates lie inside the polygon.
3. Confirm nonmatching AREA/Type rows do not generate detail POST requests.
4. Confirm the JSONL log no longer contains unrelated listing rows.
5. Add sanitized real CHP HTML fixtures after acceptance.
6. Add tests proving coordinate matching occurs before Nominatim.
7. Perform native Fedora GUI acceptance.
8. Consider consolidating `mark_detail_runtime.py` into `chp_detail_alert.py` after regression coverage is mature.

## Known risks

- CHP can change its public HTML or ASP.NET postback structure.
- Coordinate text must match `core.extract_coordinates`; capture a sanitized real header if it does not.
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
- Keep launchers straightforward; avoid `set -o pipefail`.

## Continuation point

The repository now contains coordinate-first detail matching, strict detail parsing, fast AREA-prefix and Type-fragment prefiltering, profile support for those filters, the zone editor, boundary simplifier, updated documentation, and regression tests. The immediate next step is a real dry-poll acceptance test followed by inspection of `runtime/details.jsonl` and confirmation that only retained rows generate detail POST requests.
