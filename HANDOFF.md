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

Before changing code, verify local and GitHub `main` HEAD and read `README.md`, `RELEASE_README.md`, `MARK_QUICK_START_GUIDE.md`, `MARK_TECHNICAL_USER_GUIDE.md`, `docs/RELEASE_PACKAGING.md`, and `docs/BETA_RELEASE_CHECKLIST.md`.

## Product purpose

MARK polls the public CHP CAD page, performs a fast listing prefilter, opens selected incident details through CHP's ASP.NET GridView postback, confirms location from the CAD-provided `Lat/Lon:` header, checks the active GeoJSON service-area polygon, and sends qualifying alerts through configured notification providers.

MARK is supplemental awareness, not an official dispatch or CAD system.

## Current accepted state

The Windows application previously launched and polled successfully after the final detail-postback correction. Later work added update checks, multi-provider notification configuration, generic service-area wording, CHP center selection, center smoke-test maps, release packaging, a first-run helper, saved/recent map loading, automatic last-map reopening, and a scrollable configuration pane. Those later GUI/runtime/release changes still require local acceptance after pull.

The Windows application provides:

- MARK branding and versioned window title;
- first-run beta helper;
- scrollable middle Configuration column;
- visible **CHP Region / Service-Area Map** panel;
- CHP communications-center selector;
- visible service-area map field and Browse button;
- **Saved / Recent Service-Area Maps** picker;
- **Load Selected Map**, **Import Existing Map**, and **Reload Last Used** controls;
- automatic startup reload of the last saved `CHP_ALERT_SERVICE_AREA_FILE` map;
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
- CAD `Lat/Lon:` polygon confirmation without address geocoding.

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

## Release packaging

Release packaging files:

- `VERSION` — user-visible beta version.
- `RELEASE_README.md` — first file to read in a ZIP package.
- `RELEASE_NOTES.md` — beta release notes.
- `scripts/validate_release.py` — required-file, JSON, and Python compile validation.
- `scripts/build_release.py` — clean ZIP builder with manifest and SHA256 checksum.
- `docs/RELEASE_PACKAGING.md` — packaging workflow.
- `docs/BETA_RELEASE_CHECKLIST.md` — clean beta acceptance checklist.

Build commands:

```powershell
.\.venv\Scripts\python.exe .\scripts\validate_release.py
.\.venv\Scripts\python.exe .\scripts\build_release.py
```

Expected output:

```text
dist/MARK-<version>.zip
dist/MARK-<version>.zip.sha256
dist/MARK-<version>/release-manifest.json
```

The release builder excludes `.env`, `runtime/`, virtual environments, `.git/`, logs, state files, ZIP/checksum outputs, and private runtime data.

## Current configuration

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

`CHP_ALERT_SERVICE_AREA_LABEL` controls human-readable match text. Leave it blank for generic wording such as `outside active service-area polygon`, or set it to a station/agency/profile name.

Never commit `.env`, credentials, runtime logs, state files, captured CHP pages, recent-map runtime lists, or private operational profile content.

## CHP center and smoke-test maps

- Center catalog: `data/chp_communications_centers.json`
- Smoke-test bbox catalog: `data/chp_center_smoke_boundaries.json`
- Static San Diego smoke-test map: `test_maps/san_diego_region_smoke_test.geojson`
- Recent/saved runtime map list: `runtime/recent_service_area_maps.json` (ignored runtime data)

The GUI can generate a broad smoke-test map for any cataloged CHP center. Generated maps go to `runtime/test_maps/` and set `CHP_ALERT_AREA_PREFIXES=*` so all listed AREA rows in the selected center can exercise the pipeline. Type fragments remain on the fixed default operational trigger set.

Smoke-test maps are intentionally broad and must not be used as operational response boundaries.

## Notifications

`notification_runtime.py` currently supports:

- `pushover`
- `ntfy`
- `gotify`
- `webhook`

The GUI exposes `NOTIFY_PROVIDERS`, severity, delivery mode, retry/expiration, ntfy settings, Gotify settings, webhook settings, and a selected-provider test button. Multiple providers are comma-separated.

Severity values: `low`, `medium`, `high`, `critical`.

Delivery values: `notify_once`, `notify_on_update`, `until_acknowledged`, `until_expiration`.

Provider capability matters. MARK must not claim acknowledgement for providers that cannot report acknowledgement state. Current non-Pushover providers send delivery notifications and log capability warnings for acknowledgement-like modes.

## Service-area wording fix

The active geographic decision uses the loaded GeoJSON polygon. Legacy Station 36 language remains in some historical filenames/comments, but active match reasons are patched in `mark_backend.install_generic_coordinate_match()` and should now read from the configured service-area label or generic active-service-area wording.

Expected examples:

```text
inside active service-area polygon
outside active service-area polygon
inside Jamul Fire Station 36 service-area polygon
outside Jamul Fire Station 36 service-area polygon
```

## Fast first-pass filtering

### AREA

MARK compares only the first two characters of the CHP `AREA` value, case-insensitively. Example Border-area profile:

```dotenv
CHP_ALERT_AREA_PREFIXES=Bo,El
```

`*`, `all`, or `any` matches all AREAs for smoke testing.

### Type

MARK searches the CHP `Type` column for case-insensitive fragments:

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

The GUI intentionally keeps Type fragments on the fixed operational default set so smoke-test maps do not make every CAD category alertable.

Detail-log `codes`, `contains_alert_code`, and `contains_11_82` are only the legacy 11-78 through 11-82 detector, not every Type/detail fragment match.

## Confirmed incident-detail defects and fixes

### Defect 1: unrelated incident rows leaked into details

CHP detail responses can include the selected incident panel together with the complete all-incidents listing. `mark_detail_runtime.py` rejects ordinary listing rows, retains genuine CAD/operator notes, extracts `Lat/Lon:` from the entire response, stores the coordinate as a canonical detail line, and uses the CAD coordinate directly against the service-area polygon.

### Defect 2: detail request returned the listing again

A live capture of incident `0047` proved the saved detail response was actually the ordinary incident listing. `mark_postback_runtime.py` now performs browser-faithful ASP.NET form submission: action URL, successful controls, dropdowns, `__EVENTTARGET=gvIncidents`, and the selected row's `Select$n` argument.

## Map workflow

Use **CHP Region / Service-Area Map → Saved / Recent Service-Area Maps** to load a known map, **Import Existing Map** to import a `.geojson` or `.json` Polygon, or **Service-area map → Browse** to choose a file directly. GeoJSON stores `[longitude, latitude]`; MARK internally uses `(latitude, longitude)`.

The last saved `CHP_ALERT_SERVICE_AREA_FILE` map reloads on startup. New imports, generated smoke-test maps, address-box maps, and map-editor Save As outputs are added to the recent map picker.

**Simplify Boundary** removes near-collinear waypoints. Default tolerance is 25 m. Review before saving because excessive tolerance can move the operational boundary.

**Set Line Start** + **Remove Between Start + Selected** removes intermediate waypoints along the shorter path between two selected endpoints and replaces that section with a straight line.

## File map

- `start-chp-alerter.ps1` — Windows venv, dependency, syntax preflight, current GUI launch
- `start-chp-alerter.sh` — macOS/Linux launcher
- `Install MARK - Windows.bat` — nontechnical Windows installer
- `Install MARK - macOS.command` — nontechnical macOS installer
- `install-mark-linux.sh` — Linux installer and desktop entry creator
- `mark_region_reload_entry.py` — current GUI entry: scrollable configuration, saved/recent maps, import/reload controls, automatic last-map reopening
- `mark_region_entry.py` — version title, first-run helper, center/map controls, AREA picker, address-box helper
- `mark_update_entry.py` — update-aware GUI plus provider/policy controls
- `update_runtime.py` — safe Git update discovery and fast-forward installation
- `mark_gui_entry.py` — safe Tk startup, profile filter manager, simplification and direct-line UI
- `chp_gui.py` — branding, zone-extension editor, waypoint dragging
- `mark_app.py` — dashboard base, subprocess management, shared config/map functions
- `mark_backend.py` — 30-second policy, profile/map initialization, runtime patch order, generic service-area labels
- `chp_center_runtime.py` — selected CHP communications-center fetch/parse support
- `mark_filter_runtime.py` — wildcard-aware AREA/Type filter helpers
- `mark_postback_runtime.py` — browser-faithful CHP selected-detail submission
- `mark_detail_runtime.py` — AREA/type prefilter, strict parser, CAD-coordinate matching
- `notification_runtime.py` — Pushover, ntfy, Gotify, and webhook adapters
- `chp_detail_alert.py` — legacy detail model, codes, JSONL logging, alert formatting
- `chp_jamul_alert.py` — base page fetch, state, polygon helper functions, legacy Pushover sender
- `service_area_runtime.py` — GeoJSON validation and polygon installation
- `geometry_utils.py` — near-collinear waypoint removal and direct-line cleanup helper
- `scripts/validate_release.py` — release validation
- `scripts/build_release.py` — release ZIP/checksum/manifest builder
- `tests/test_mark_runtime.py` — parser, coordinate, filter, and simplification regression tests
- `tests/test_notification_runtime.py` — notification policy/provider tests
- `tests/test_update_runtime.py` — update discovery/refusal tests
- `RELEASE_README.md` — release package starting point
- `MARK_QUICK_START_GUIDE.md` — nontechnical installation/use guide
- `MARK_TECHNICAL_USER_GUIDE.md` — technical guide
- `README.md` — operator/developer overview
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

### GUI acceptance

```powershell
.\start-chp-alerter.ps1
```

Confirm after this update:

- GUI launches;
- middle Configuration column has a vertical scrollbar and no clipped bottom controls;
- window title shows version;
- first-run helper appears once and can be dismissed;
- **CHP Region / Service-Area Map** is visible at the top;
- CHP center dropdown works;
- **Saved / Recent Service-Area Maps** is visible near the top;
- **Load Selected Map**, **Import Existing Map**, and **Reload Last Used** work;
- last saved map reloads automatically on boot;
- Load Center Test Map generates and loads a broad test map;
- selected map loads;
- Notification settings are visible;
- ntfy/Gotify/webhook fields are visible;
- provider test button works for selected provider(s);
- map/profile label changes active match wording;
- monitor starts;
- wildcard smoke-test AREA filters work;
- normal AREA/Type filters work;
- browser-faithful detail selection works;
- active match reasons do not say Station 36 unless configured as the label.

## Remaining work

1. Native Windows acceptance of the latest scrollable config/saved-map GUI and release package.
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

The latest work makes the middle Configuration pane scrollable, adds **Saved / Recent Service-Area Maps**, tracks imported/generated/profile maps under ignored runtime state, and keeps boot-time last-map reload through `mark_region_reload_entry.py`. Start the next thread by pulling `main`, running syntax/tests, validating release packaging, and accepting the updated GUI on Windows.
