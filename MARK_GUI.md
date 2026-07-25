# MARK desktop dashboard

MARK now uses one cross-platform Tkinter dashboard on Windows and Fedora. The existing CHP monitor remains the backend process.

## Layout

The dashboard follows the approved dark navy/gold mockup:

- branded MARK header and status cards
- Start Monitor, Stop, Test Pushover, One Poll, Reload Config, and Reload Map controls
- live color-coded log
- configuration panel
- OpenStreetMap road basemap beneath the service-area polygon
- GeoJSON Save, Save As, Reset, add-vertex, and delete-last-vertex controls
- footer status and uptime

## Logo

The dashboard looks for the supplied logo in this order:

1. `assets/mark_logo.png`
2. `Mark Logo.png` in the repository root
3. `mark_logo_ui.png` in the repository root

When no logo file is present, MARK falls back to a text wordmark rather than failing to start.

## Windows

```powershell
cd C:\Users\Shane\Documents\GitHub\chp-alerter
git pull
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start-chp-alerter.ps1
```

The launcher creates `.venv`, installs dependencies, creates `.env` when needed, and opens `chp_gui.py` through `pythonw.exe`.

## Fedora

Install Tk support once if required:

```bash
sudo dnf install python3-tkinter
```

Then:

```bash
cd /path/to/chp-alerter
git pull
chmod +x start-chp-alerter.sh
./start-chp-alerter.sh
```

## Road basemap

The editor uses `tkintermapview` with OpenStreetMap tiles. Internet access is required for map tiles. The configured GeoJSON remains the authoritative service-area file used by the monitor.

Click the map to append a polygon vertex. `Delete Last Vertex` removes the most recently added point. `Save Map` updates the selected GeoJSON. Restart a running monitor after changing or reloading the map.

## Important

The GUI has been structurally reviewed, but it must still be acceptance-tested on the actual Windows and Fedora desktops because this development environment cannot display those native Tk windows.
