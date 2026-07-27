# MARK release notes

## 0.9.0-beta.7

Service-area map import/reload UX update.

### Added

- `mark_region_reload_entry.py`, a GUI entry point that wraps the Region panel with explicit map import/reload controls.
- **Import Existing Map** button for selecting an existing GeoJSON service-area map.
- **Reload Last Saved Map** button for reopening the map currently saved in `.env` as `CHP_ALERT_SERVICE_AREA_FILE`.

### Behavior

- The normal Windows, macOS, and Linux launchers now open the map-reload Region GUI entry point.
- On startup, MARK attempts to reload the last saved service-area map automatically so users do not have to re-import the same map each session.
- Importing an existing map saves it through the Region/Map save flow, clears stale dedupe state, and prompts for monitor restart when needed.

## 0.9.0-beta.6

Region/map restart and Traffic Hazard hardening update.

### Fixed

- Saved region/map changes now clear stale monitor dedupe state by backing up the active state file before the next run.
- The GUI now prompts to restart the running monitor after a region, AREA, address-box, or center-test map change, because the backend process reads map and AREA settings at launch.
- Old beta configs with `CHP_ALERT_TYPE_FRAGMENTS=*` are normalized back to the fixed default trigger set so non-alert categories such as Traffic Hazard do not become alertable.
- Runtime filter installation also treats Type wildcard as the fixed default trigger set, while still allowing `AREA=*` for broad smoke testing.

### Improved

- The CHP AREA panel now includes larger toggle buttons in addition to the checkbox indicators, making area selection easier on Windows/Tkinter.
- The **Save Region/Map** button now describes that it clears stale state and can restart the monitor.

## 0.9.0-beta.5

Multi-select CHP AREA prefix update.

### Added

- Multi-select CHP AREA checkboxes in **CHP Region / Service-Area Map**.
- Required regional AREA prefix enforcement for selected CHP centers.
- Border Communications Center / San Diego County now always includes `Bo` in addition to user-selected areas such as `Sa` or `El`.
- Runtime normalization that migrates older `BC` beta configs to `Bo` for Border-area matching.

### Behavior

- Users can select multiple CHP AREA prefixes instead of choosing only one preset.
- Selecting San Diego under BCCC stores `Bo,Sa`, so the regional Border/San Diego County AREA remains searched.
- Selecting El Cajon under BCCC stores `Bo,El`.
- Selecting smoke-test mode still stores `*` and searches all AREA rows.
- Alert Type fragments remain fixed default triggers and are not exposed as a normal area selector.

## 0.9.0-beta.4

CHP AREA prefix GUI update.

### Added

- **CHP AREA Prefixes** panel inside **CHP Region / Service-Area Map**.
- AREA preset selector for common configurations such as `San Diego`, `El Cajon`, `Border + El Cajon`, `San Diego + El Cajon`, and `All CHP Areas / smoke test`.
- Editable AREA prefix field for custom CHP AREA combinations.
- Validation and normalization for `CHP_ALERT_AREA_PREFIXES`, including aliases such as `San Diego` -> `Sa` and `El Cajon` -> `El`.

### Behavior

- CHP AREA prefixes are now easy to change when the active map changes, such as switching from an El Cajon/Border map to a home-address box in San Diego.
- Alert Type fragments remain hidden from the primary Region panel and are treated as stable alert triggers, not a normal end-user area selector.
- The Region summary now emphasizes AREA selection and describes Type fragments as fixed defaults.

## 0.9.0-beta.3

Address Box Map helper update.

### Added

- **Address Box Map** generator in the CHP Region / Service-Area Map panel.
- `address_box_runtime.py` for geocoding an address once and building a square GeoJSON service-area polygon around it.
- `CHP_ALERT_ADDRESS_BOX_ADDRESS` and `CHP_ALERT_ADDRESS_BOX_HALF_SIZE_METERS` settings to remember the helper inputs.
- Unit tests for generated address-box GeoJSON and half-size validation.

### Behavior

- The user enters an address and a box half-size in metres.
- MARK geocodes the address once, writes a square GeoJSON under `runtime/address_maps/`, loads it as the active service-area map, and saves the configuration.
- Generated address-box maps reset `CHP_ALERT_BOUNDARY_BUFFER_METERS` to `0`, so the generated box is the alerting footprint unless the user intentionally adds a buffer later.
- The address box is an approximate square, not a circular radius. Users must visually inspect the generated map before operational use.

## 0.9.0-beta.2

Boundary-buffer / near-boundary alerting update.

### Added

- Configurable `CHP_ALERT_BOUNDARY_BUFFER_METERS` setting.
- GUI field for **Boundary buffer metres** in the CHP Region / Service-Area Map panel.
- Near-boundary match reason that clearly says the incident is outside the polygon but within the configured buffer.
- Unit tests for strict outside behavior and near-boundary buffer alerting.

### Behavior

- `0` keeps the previous strict behavior: incidents must be inside the polygon to alert.
- A positive number of metres alerts for qualifying incidents outside but near the active service-area boundary.
- Match text includes both the distance from the boundary and the configured buffer.

## 0.9.0-beta.1

Initial broad beta packaging milestone.

### Included

- Region-aware MARK GUI entry point.
- CHP communications-center selector.
- Visible service-area map field and Browse control.
- Center smoke-test map generation for all cataloged CHP communications centers.
- CAD `Lat/Lon:` detail-coordinate matching.
- Browser-faithful CHP ASP.NET detail postback handling.
- Pushover, ntfy, Gotify, and generic webhook notification configuration.
- Alert severity and delivery-mode policy fields.
- Safe Git-based update checks and fast-forward-only update installation.
- Conservative boundary simplification.
- Direct waypoint-to-waypoint cleanup.
- Nontechnical Quick-Start guide.
- Technical User Guide.
- Release ZIP builder, manifest, and checksum generation.
- Release validation script.

### Known limitations

- MARK is supplemental awareness only and does not replace official dispatch, CAD, radio, paging, or agency procedures.
- ZIP-only installs receive update notices but cannot self-update through Git unless installed as a Git checkout.
- macOS and Linux launchers exist, but native acceptance testing is still required before they should be described as fully validated release targets.
- Smoke-test boundaries are deliberately broad approximate rectangles and are not operational boundaries.
- Provider acknowledgement depends on provider capability; MARK does not claim acknowledgement where a provider cannot report it.

### Operational cautions

Before operational use, replace smoke-test maps with real service-area maps, restore appropriate AREA/Type filters, configure notifications, and test alert delivery.
