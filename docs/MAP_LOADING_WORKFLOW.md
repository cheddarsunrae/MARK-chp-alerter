# MARK map loading workflow

## Current UX

Use **CHP Region / Service-Area Map → Load Map** to choose a `.geojson` or `.json` service-area Polygon.

The previous distinction between **Load Selected Map** and **Import Existing Map** has been removed from the user-facing workflow because the direct file-picker path was the reliable path during Windows acceptance testing.

## What Load Map does

When a map is chosen, the active GUI entry path should:

1. Parse the selected GeoJSON with `mark_app.load_polygon()`.
2. Set `CHP_ALERT_SERVICE_AREA_FILE` to the selected file path.
3. Set `CHP_ALERT_SERVICE_AREA_LABEL` from the GeoJSON feature `properties.name`, `title`, `label`, `service_area`, or `description`; if none exists, use the file stem.
4. Replace `self.map_payload`, `self.map_points`, and `self.map_path`.
5. Clear stale selected-waypoint, extension, and direct-line editing state.
6. Redraw the polygon in the map pane.
7. Refit the map view to the loaded polygon.
8. Update the visible **Displayed map** line with the map path and vertex count.
9. Save the region/map configuration.
10. Remember the map under ignored runtime state in `runtime/recent_service_area_maps.json`.

## Why the label sync matters

Alerts include a human-readable service-area reason such as:

```text
inside <service-area label> service-area polygon
```

Before the label sync, a newly loaded polygon could be active while the label still said something from an older address-box map, for example `Address box: 4353 felton st, 92104`. That was misleading because the alert text made it look like the wrong map was loaded. **Load Map** now updates the label with the loaded file so notification wording and the selected map stay aligned.

## Startup behavior

On startup, MARK still reloads the last saved `CHP_ALERT_SERVICE_AREA_FILE` value. The recent-map list is informational and helps the user see what has been used, but the primary user action for choosing a different file is **Load Map**.

## Acceptance check

After choosing a map with **Load Map**, the right map pane should visibly change and the status line should read approximately:

```text
Displayed map: <path> • <vertex count> vertices • Loaded service-area map
```

A subsequent alert should not keep an old address-box or smoke-test label unless that is the map that was just loaded. If the displayed-map status changes but the polygon does not, use **Refit Map View** once and inspect the live log for the exact file path and vertex count.
