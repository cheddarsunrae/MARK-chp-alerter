# MARK test maps

This folder contains test-only service-area maps.

## Important warning

These maps are intentionally broad. They are for smoke testing the MARK polling, detail retrieval, coordinate matching, and notification path. They are not official CHP boundaries and must not be used as operational response areas.

## Included static map

- `san_diego_region_smoke_test.geojson` — broad San Diego / Border operating-region smoke test.

## Generated center maps

The GUI can generate a broad test map for any CHP communications center:

1. Open MARK.
2. Select a CHP center in **CHP Region / Service-Area Map**.
3. Click **Load Center Test Map**.

Generated maps are saved under:

```text
runtime/test_maps/
```

That runtime folder is intentionally ignored by Git and should not be included in release packages.

## Returning to operational use

After testing, load the real station or agency service-area map, restore the correct AREA and Type filters, save configuration, and restart the monitor.
