# CHP Alerter

CHP Alerter polls the public California Highway Patrol CAD page, filters incidents to **a specified service area**, retrieves the associated incident-detail updates, and sends qualifying incidents through Pushover.

> **Supplemental awareness only.** This is not an official CAD terminal, station alerting system, pager, radio, or replacement for agency dispatch. Public webpages, geocoding, networks, and third-party push services can fail or change.

The repository includes a Station 36/Jamul sample configuration, but the monitor and desktop interface are designed so other stations can select or create their own GeoJSON service-area file.

## Current alert logic

Normal alerts require both a geographic match and one of these CHP call types:

- `Trfc Collision-1141Enrt`
- `Trfc Collision-Unkn Inj`
- `Report of Fire`

Incident details are fetched through the CHP ASP.NET `gvIncidents / Select$n` postback. Detail codes `11-78`, `11-79`, `11-80`, and `11-81` can promote another call type into the normal geographically filtered alert path. `11-82` is logged but does not yet send its future separate alert category.

Rows with `AREA` containing Oceanside or Temecula are discarded before a detail request is made.

## Cross-platform desktop interface

The same Tkinter interface runs on Windows and Fedora/Linux. It provides:

- Start and stop controls
- Pushover testing
- One-poll dry runs
- Live logs and poll summaries
- Configuration editing and reload
- Service-area GeoJSON selection, validation, and reload
- A polygon map editor
- Windows and Linux launchers

The backend reads the service-area map when it starts. **Reload Map** validates and saves the selected file, then offers to restart a running monitor so the new boundary takes effect.

## Windows quick start

From PowerShell:

```powershell
cd C:\Users\Shane\Documents\GitHub\chp-alerter
git pull
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start-chp-alerter.ps1
```

The launcher creates `.venv`, installs dependencies, creates `.env` from `.env.example` when needed, and starts the GUI.

## Fedora quick start

Install Python and Tkinter once:

```bash
sudo dnf install -y python3 python3-tkinter
```

Then:

```bash
cd /path/to/chp-alerter
git pull
chmod +x start-chp-alerter.sh
./start-chp-alerter.sh
```

## Required configuration

Enter these values in the GUI's **Configuration** tab:

```dotenv
CHP_ALERT_CONTACT=mailto:you@example.com
PUSHOVER_APP_TOKEN=your_application_api_token
PUSHOVER_USER_KEY=your_user_or_group_key
```

The default emergency profile is:

```dotenv
PUSHOVER_PRIORITY=2
PUSHOVER_RETRY_SECONDS=30
PUSHOVER_EXPIRE_SECONDS=1800
PUSHOVER_SOUND=alien
```

`alien`, `climb`, `echo`, `updown`, and `persistent` are the longer built-in Pushover choices exposed by the interface.

## Service-area files

The active map is configured with:

```dotenv
CHP_ALERT_SERVICE_AREA_FILE=service_area.geojson
```

The file must be valid GeoJSON containing at least one Polygon feature. Point features may be included as operational references. Standard GeoJSON coordinate order is:

```text
[longitude, latitude]
```

The supplied `service_area.geojson` is a sample operational polygon, not a legal district boundary.

### Map editor

Press **Edit Map** in the desktop interface.

- Drag a red vertex to move it.
- Double-click near an edge to insert a vertex.
- Right-click a vertex to remove it.
- Use **Save As** to create separate maps for coworkers or stations.
- Use **Reload Map** in the controller after saving.

The editor validates the resulting GeoJSON before replacing the selected file. It is a coordinate editor, not yet a full online street-tile GIS editor.

## Command-line operation

The map-aware backend entry point is:

```text
chp_crossplatform.py
```

Test Pushover:

```bash
python chp_crossplatform.py --test-pushover
```

One safe poll without sending incident notifications:

```bash
python chp_crossplatform.py --once --dry-run --alert-existing --log-level DEBUG
```

Continuous foreground operation:

```bash
python chp_crossplatform.py
```

## Fedora/systemd installation

Install these application files in `/opt/chp-alerter`:

```text
chp_crossplatform.py
chp_detail_alert.py
chp_jamul_alert.py
service_area_runtime.py
service_area.geojson
requirements.txt
```

Set production paths in `/etc/chp-alerter.env`:

```dotenv
CHP_ALERT_STATE_FILE=/var/lib/chp-jamul-alert/state.json
CHP_ALERT_DETAIL_LOG_FILE=/var/lib/chp-jamul-alert/details.jsonl
CHP_ALERT_SERVICE_AREA_FILE=/opt/chp-alerter/service_area.geojson
```

Install and start the service:

```bash
sudo cp chp-alerter.service /etc/systemd/system/chp-alerter.service
sudo systemctl daemon-reload
sudo systemctl enable --now chp-alerter.service
sudo journalctl -u chp-alerter.service -f
```

## Important files

- `chp_crossplatform.py` — map-aware production entry point
- `chp_detail_alert.py` — incident details and 11-code handling
- `chp_jamul_alert.py` — CHP polling, geocoding, state, and Pushover core
- `chp_gui_crossplatform.py` — Windows/Fedora desktop controller
- `service_area_editor.py` — GeoJSON polygon editor
- `service_area_runtime.py` — map validation and runtime loader
- `service_area.geojson` — supplied sample service area
- `start-chp-alerter.ps1` — Windows launcher
- `start-chp-alerter.sh` — Fedora/Linux launcher
- `chp-alerter.service` — hardened Linux systemd service

## Security

Never commit `.env`, Pushover credentials, or recipient keys. The repository's `.gitignore` excludes local configuration and runtime state.
