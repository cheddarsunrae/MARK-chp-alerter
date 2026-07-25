# MARK desktop dashboard

MARK uses one cross-platform Tkinter dashboard on Windows and Fedora/Linux. The GUI controls the profile-aware `mark_backend.py` process.

## Launch

### Windows

```powershell
cd C:\Users\Shane\Documents\GitHub\chp-alerter
git pull
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start-chp-alerter.ps1
```

### Fedora/Linux

```bash
sudo dnf install -y python3 python3-tkinter
cd /path/to/chp-alerter
git pull
chmod +x start-chp-alerter.sh
./start-chp-alerter.sh
```

The Windows launcher performs a Python preflight and starts `mark_gui_entry.py` through `pythonw.exe`. Startup failures are written to `runtime/mark-gui-error.log` and displayed in a native error box.

## Dashboard layout

- MARK logo and **Map-Aware Roadway Knowledge** title
- monitor status, last poll, and latest summary cards
- Start Monitor, Stop, Test Pushover, One Poll, Reload Config, and Reload Map
- color-coded live log
- configuration editor
- monitoring profile manager
- OpenStreetMap service-area editor
- footer with poll interval and uptime

## Logo lookup order

1. `assets/mark_logo.png`
2. `Mark Logo.png` in the repository root
3. `mark_logo_ui.png` in the repository root

A text wordmark is used when no image exists.

## Configuration

The visible fields include Pushover credentials, sound, poll interval, state file, detail log, service-area file, and Nominatim contact.

The **Profiles / Regions / Incident Types** dialog controls:

- active profile name;
- ignored CHP `AREA` regions;
- monitored incident types;
- saved profile load/save/delete.

A profile also preserves poll interval, alert-existing, alert-updates, and a private map copy under `profiles/maps/`.

Configuration and profile changes require a monitor restart before the backend process sees them.

## Loading a map

1. Find **Service Area File** in Configuration.
2. Click `…`.
3. Select a `.geojson` or `.json` file containing a Polygon.
4. MARK loads and displays it.
5. Press **Save** in Configuration.
6. Restart the running monitor.

## Safe map editing

Editing is off by default. This prevents zooming, panning, and map-control clicks from creating waypoints.

### Select and move a waypoint

- Enable editing.
- Click a numbered waypoint; it turns red.
- Drag it to a new position while no zone extension is active.
- Press **Save Map** only after reviewing the result.

### Extend the boundary

1. Enable editing.
2. Select an existing start waypoint.
3. Click **Start Extension**.
4. Add at least two clicks outside or inside the existing polygon.
5. Treat the final click as an endpoint hint near the desired old waypoint.
6. Click **Finish Extension**.

MARK removes the final temporary point and reconnects to the nearest pre-existing waypoint. It replaces the shorter old boundary path between the selected start and snapped endpoint.

### Simplify the boundary

Click **Simplify Boundary**, enter a tolerance in metres, and confirm the proposed number of removals.

The simplifier repeatedly removes a waypoint only when it lies within the chosen tolerance of the direct segment between its two neighbours. It never reduces a polygon below three vertices.

Use 10–25 m for conservative cleanup. Larger tolerances may materially change the operational boundary. Simplification mainly improves readability and editing reliability; point-in-polygon computation is already fast for the small polygons MARK uses.

## Profiles

Profiles are stored in:

```text
profiles/profiles.json
profiles/maps/
```

A saved profile contains:

- map file;
- ignored areas;
- incident types;
- polling interval;
- alert-existing setting;
- alert-updates setting.

Do not commit private operational profiles unless deliberately intended for repository users.

## Road basemap

The editor uses `tkintermapview` and OpenStreetMap tiles. Internet access is required to load tiles. The GeoJSON file remains authoritative even if map tiles are temporarily unavailable.

## Troubleshooting

### GUI closes immediately

Read:

```text
runtime\mark-gui-error.log
```

Then run the syntax check documented in `README.md`.

### Monitor exits immediately

The live log shows the backend error. Common causes are:

- poll interval below 30 seconds;
- missing Pushover credential pair;
- missing Nominatim contact while Nominatim is enabled;
- invalid or missing GeoJSON Polygon;
- empty incident-type selection.

### New map/profile does not affect alerts

Stop and restart the monitor. The backend loads maps and profile filters only at process startup.

## Acceptance status

The dashboard has been exercised successfully on the user's Windows system. Native Fedora acceptance remains desirable after major Tkinter changes.