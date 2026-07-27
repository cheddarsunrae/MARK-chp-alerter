# MARK release notes

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
