# CHP center selection and smoke-test maps

MARK now has explicit GUI controls for the CHP communications center and service-area map.

## GUI location

At the top of the Configuration column, use **CHP Region / Service-Area Map**.

Visible controls:

- **CHP center**: selects the CHP communications center, such as Border, Orange, Los Angeles, Inland, etc.
- **Service-area map**: displays the active GeoJSON service-area file.
- **Browse**: choose any `.geojson` or `.json` service-area map.
- **Load Center Test Map**: generates and loads a broad testing-only GeoJSON for the selected CHP center.
- **Save Region/Map**: writes the selected center and map settings to `.env`.

## Runtime settings

```dotenv
CHP_ALERT_COMM_CENTER=BCCC
CHP_ALERT_COMM_CENTER_NAME=Border
CHP_ALERT_SERVICE_AREA_FILE=service_area.geojson
```

The center list is seeded from:

```text
data/chp_communications_centers.json
```

The broad smoke-test boundaries are stored as approximate bounding boxes in:

```text
data/chp_center_smoke_boundaries.json
```

## Smoke-test maps

Smoke-test maps are generated into:

```text
runtime/test_maps/
```

They are intentionally broad and approximate. They are useful for answering: “Is MARK fetching the selected CHP center, parsing incidents, fetching details, checking coordinates, and sending notifications?”

They are **not official CHP boundaries** and are **not operational station response boundaries**.

When a center smoke-test map is loaded, MARK also sets:

```dotenv
CHP_ALERT_AREA_PREFIXES=*
CHP_ALERT_TYPE_FRAGMENTS=*
```

That means every listed AREA and Type can pass the fast prefilter for testing. Switch back to a real station/agency map and production filters before operational use.

## Backend behavior

The runtime no longer assumes Border-only operation. `chp_center_runtime.py` patches the legacy Border-oriented fetch and parser path so the configured center is used for listing retrieval and detail postbacks. Incident state keys include the selected center code to reduce collisions when switching centers.
