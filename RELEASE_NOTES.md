# MARK release notes

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
