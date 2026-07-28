# MARK map loading workflow

## Current UX

Use **CHP Region / Service-Area Map → Load Map** to choose a `.geojson` or `.json` service-area Polygon.

The previous distinction between **Load Selected Map** and **Import Existing Map** has been removed from the user-facing workflow because the direct file-picker path was the reliable path during Windows acceptance testing.

## What Load Map does

When a map is chosen, `mark_region_reload_entry.py` should:

1. Parse the selected GeoJSON with `mark_app.load_polygon()`.
2. Set `CHP_ALERT_SERVICE_AREA_FILE` to the selected file path.
3. Replace `self.map_payload`, `self.map_points`, and `self.map_path`.
4. Clear stale selected-waypoint, extension, and direct-line editing state.
5. Redraw the polygon in the map pane.
6. Refit the map view to the loaded polygon.
7. Update the visible **Displayed map** line with the map path and vertex count.
8. Save the region/map configuration.
9. Remember the map under ignored runtime state in `runtime/recent_service_area_maps.json`.

## Startup behavior

On startup, MARK still reloads the last saved `CHP_ALERT_SERVICE_AREA_FILE` value. The recent-map list is informational and helps the user see what has been used, but the primary user action for choosing a different file is **Load Map**.

## Acceptance check

After choosing a map with **Load Map**, the right map pane should visibly change and the status line should read approximately:

```text
Displayed map: <path> • <vertex count> vertices • Loaded service-area map
```

If that status line changes but the polygon does not, use **Refit Map View** once and inspect the live log for the exact file path and vertex count.
