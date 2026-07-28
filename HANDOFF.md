# MARK canonical handoff

## Repository

- Project: **MARK — Map-Aware Roadway Knowledge**
- Repository: `cheddarsunrae/MARK-chp-alerter`
- Previous repository name/path used in older docs: `cheddarsunrae/chp-alerter`
- Default branch: `main`
- Primary Windows checkout: `C:\Users\Shane\Documents\GitHub\chp-alerter`
- Current version file: `VERSION`
- Windows launcher: `start-chp-alerter.ps1`
- macOS/Linux launcher: `start-chp-alerter.sh`
- Current GUI entry point: `mark_region_reload_entry.py`
- Backend entry point: `mark_backend.py`
- Minimum poll interval: **30 seconds**

Before changing code, verify local and GitHub `main` HEAD and read `README.md`, `RELEASE_README.md`, `MARK_QUICK_START_GUIDE.md`, `MARK_TECHNICAL_USER_GUIDE.md`, `docs/RELEASE_PACKAGING.md`, `docs/BETA_RELEASE_CHECKLIST.md`, and `docs/MAP_LOADING_WORKFLOW.md`.

## Product purpose

MARK polls the public CHP CAD page, performs a fast listing prefilter, opens selected incident details through CHP's ASP.NET GridView postback, confirms location from the CAD-provided `Lat/Lon:` header, checks the active GeoJSON service-area polygon, and sends qualifying alerts through configured notification providers.

MARK is supplemental awareness, not an official dispatch, CAD, radio, paging, or station-alerting system.

## Current accepted state

The Windows application previously launched and polled successfully after the final detail-postback correction. Later work added update checks, multi-provider notification configuration, generic service-area wording, CHP center selection, center smoke-test maps, release packaging, a first-run helper, saved/recent map tracking, automatic last-map reopening, a scrollable configuration pane, displayed-map status, and a single user-facing **Load Map** workflow.

Latest user-accepted finding: the old direct **Import Existing Map** file-picker path worked, while **Load Selected Map** did not reliably change the displayed map. The UI has therefore been simplified so the working file-picker path is now the primary **Load Map** action and the old separate import/load-selected distinction is removed from the visible workflow.

## Current GUI map workflow

User-facing map loading should be:

1. Open **CHP Region / Service-Area Map**.
2. Click **Load Map**.
3. Choose a `.geojson` or `.json` Polygon file.
4. Confirm the right map pane visibly changes.
5. Confirm the visible status line updates, for example:

```text
Displayed map: <path> • <vertex count> vertices • Loaded service-area map
```

`mark_region_reload_entry.py` still remembers recent maps in ignored runtime state at:

```text
runtime/recent_service_area_maps.json
```

That recent list is informational. The reliable user action for selecting a different map is **Load Map**.

Startup behavior remains: the last saved `CHP_ALERT_SERVICE_AREA_FILE` reloads automatically when MARK opens.

## Windows application capabilities

The Windows application provides:

- MARK branding and versioned window title;
- first-run beta helper;
- scrollable middle Configuration column;
- visible **CHP Region / Service-Area Map** panel;
- CHP communications-center selector;
- visible service-area map field and **Load Map** button;
- recent service-area map display for reference;
- automatic startup reload of the last saved `CHP_ALERT_SERVICE_AREA_FILE` map;
- visible **Displayed map** status and **Refit Map View** button;
- generated smoke-test map loading for all cataloged CHP centers;
- monitor start/stop, dry poll, config/map reload;
- update check and safe `git pull --ff-only` install controls;
- visible notification-provider and alert-policy controls;
- provider test button for selected providers;
- live backend log;
- OpenStreetMap service-area editor;
- draggable waypoints;
- anchored zone-extension workflow;
- named profiles;
- configurable AREA prefixes and fixed default Type fragments;
- wildcard `*` smoke-test AREA support;
- conservative boundary simplification;
- direct waypoint-to-waypoint cleanup;
- GUI startup-error logging to `runtime/mark-gui-error.log`;
- successful selected-incident detail retrieval;
- CAD `Lat/Lon:` polygon confirmation without active-path address geocoding.

macOS and Linux install paths exist, but native acceptance testing is still required.

## Runtime chain

```text
platform launcher
  -> mark_region_reload_entry.py
      -> mark_region_entry.py
          -> mark_update_entry.py
          -> mark_gui_entry.SafeMarkApp
              -> chp_gui.py + mark_app.py
                  -> mark_backend.py
                      -> chp_center_runtime.install()
                      -> mark_detail_runtime.install()
                      -> mark_filter_runtime.install()
                      -> mark_postback_runtime.install()
                      -> notification_runtime.install()
                      -> service_area_runtime.apply_to_core()
                      -> mark_backend.install_generic_coordinate_match()
                      -> chp_detail_alert.main()
                          -> chp_jamul_alert.main()
```

Patch installation order matters. `chp_center_runtime.install()` must run before detail/filter patches so the selected center replaces the old Border-only fetch path. `mark_filter_runtime.install()` must run after `mark_detail_runtime.install()` so wildcard `*` AREA filters override the default filter helpers. `mark_postback_runtime.install()` must run after `mark_detail_runtime.install()`. `install_generic_coordinate_match()` must run after the GeoJSON map has been applied so active polygon reasons use the loaded map/profile label instead of legacy Station 36 wording.

## Current configuration defaults

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
CHP_ALERT_EXISTING=0
CHP_ALERT_UPDATES=0
CHP_ALERT_PROFILE=
CHP_ALERT_AREA_PREFIXES=Bo,El
CHP_ALERT_TYPE_FRAGMENTS=Unk,1140,1141,Min,Maj,1179,1180,1178,un w,Repo
NOTIFY_PROVIDERS=pushover
ALERT_SEVERITY=critical
ALERT_DELIVERY_MODE=until_acknowledged
ALERT_RETRY_SECONDS=30
ALERT_EXPIRE_SECONDS=1800
ALERT_COOLDOWN_SECONDS=300
PUSHOVER_APP_TOKEN=
PUSHOVER_USER_KEY=
PUSHOVER_PRIORITY=2
PUSHOVER_RETRY_SECONDS=30
PUSHOVER_EXPIRE_SECONDS=1800
PUSHOVER_SOUND=alien
NTFY_SERVER=https://ntfy.sh
NTFY_TOPIC=
NTFY_TOKEN=
GOTIFY_URL=
GOTIFY_APP_TOKEN=
WEBHOOK_URL=
WEBHOOK_BEARER_TOKEN=
```

Never commit `.env`, credentials, runtime logs, state files, captured CHP pages, recent-map runtime lists, or private operational profile content.

## Important files

- `start-chp-alerter.ps1` — Windows venv, dependency, syntax preflight, current GUI launch.
- `start-chp-alerter.sh` — macOS/Linux launcher.
- `mark_region_reload_entry.py` — current GUI entry: scrollable configuration, single **Load Map** file-picker path, recent-map display, displayed-map status, import/reload compatibility callbacks, and automatic last-map reopening.
- `mark_region_entry.py` — version title, first-run helper, center/map controls, AREA picker, address-box helper.
- `mark_update_entry.py` — update-aware GUI plus provider/policy controls.
- `mark_gui_entry.py` — safe Tk startup, profile filter manager, simplification and direct-line UI.
- `chp_gui.py` — branding, zone-extension editor, waypoint dragging.
- `mark_app.py` — dashboard base, subprocess management, shared config/map functions.
- `mark_backend.py` — 30-second policy, profile/map initialization, runtime patch order, generic service-area labels.
- `chp_center_runtime.py` — selected CHP communications-center fetch/parse support.
- `mark_filter_runtime.py` — wildcard-aware AREA/Type filter helpers.
- `mark_postback_runtime.py` — browser-faithful CHP selected-detail submission.
- `mark_detail_runtime.py` — AREA/type prefilter, strict parser, CAD-coordinate matching.
- `notification_runtime.py` — Pushover, ntfy, Gotify, and webhook adapters.
- `service_area_runtime.py` — GeoJSON validation and polygon installation.
- `geometry_utils.py` — near-collinear waypoint removal and direct-line cleanup helper.
- `docs/MAP_LOADING_WORKFLOW.md` — current accepted map-loading UX.
- `README.md` — operator/developer overview.
- `HANDOFF.md` — this canonical continuation document.

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
  .\chp_center_runtime.py `
  .\mark_filter_runtime.py `
  .\mark_detail_runtime.py `
  .\mark_postback_runtime.py `
  .\notification_runtime.py `
  .\update_runtime.py `
  .\mark_update_entry.py `
  .\mark_region_entry.py `
  .\mark_region_reload_entry.py `
  .\mark_backend.py `
  .\chp_gui.py `
  .\mark_gui_entry.py `
  .\geometry_utils.py
```

### Unit tests

```powershell
.\.venv\Scripts\python.exe -m unittest `
  .\tests\test_mark_runtime.py `
  .\tests\test_notification_runtime.py `
  .\tests\test_update_runtime.py -v
```

### Release validation/build

```powershell
.\.venv\Scripts\python.exe .\scripts\validate_release.py
.\.venv\Scripts\python.exe .\scripts\build_release.py
```

### Safe live dry poll

```powershell
.\.venv\Scripts\python.exe .\mark_backend.py `
  --once `
  --dry-run `
  --alert-existing `
  --log-level DEBUG
```

Expected successful location reasons include `CHP detail Lat/Lon` and service-area wording should no longer be hard-coded to Station 36 unless the profile/label explicitly says so.

## GUI acceptance

```powershell
.\start-chp-alerter.ps1
```

Confirm after this update:

- GUI launches;
- middle Configuration column has a vertical scrollbar and no clipped bottom controls;
- **CHP Region / Service-Area Map** is visible near the top;
- the old separate **Load Selected Map** / **Import Existing Map** workflow is no longer visible;
- **Load Map** is visible and opens a file picker;
- choosing a `.geojson` with **Load Map** visibly changes the right map pane;
- the **Displayed map** status updates with the selected path and vertex count;
- the live log writes the selected path and vertex count;
- **Refit Map View** refits the currently displayed polygon;
- last saved map reloads automatically on boot;
- monitor starts and uses the saved map after restart.

## Remaining work

1. Native Windows acceptance of the latest single-Load-Map GUI.
2. Native macOS GUI acceptance.
3. Native Linux/Fedora GUI acceptance.
4. Clean ZIP install test from `dist/MARK-<version>.zip` outside the dev checkout.
5. Add CI for syntax/tests/release validation.
6. Add signed release packages or signed update manifest for ZIP-only nontechnical users.
7. Add durable acknowledgement service if non-Pushover providers need true acknowledgement tracking.

## User preferences for future work

- Provide complete file replacements rather than partial edits when manual intervention is unavoidable.
- Accuracy over speed.
- Do not claim native testing that was not performed.
- Windows PowerShell is primary; Fedora support must remain intact.
- Keep launchers straightforward.

## Continuation point

The latest work simplifies map loading to one reliable **Load Map** file-picker path, keeps recent maps as informational runtime state, preserves automatic startup reload of `CHP_ALERT_SERVICE_AREA_FILE`, and documents the accepted workflow in `docs/MAP_LOADING_WORKFLOW.md`. Start the next thread by pulling `main`, running syntax/tests, and accepting the updated GUI on Windows.
