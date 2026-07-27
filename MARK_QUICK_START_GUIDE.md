# MARK Quick-Start Guide

## For firefighters, medics, dispatchers, and station personnel

This guide assumes you have never used GitHub, PowerShell, Terminal, Python, or command-line tools. You do not need to understand any of them to use MARK.

MARK watches the public California Highway Patrol incident page, checks selected calls against your service-area map, and sends notifications through the alert services configured by your administrator.

> MARK is a supplemental awareness tool. It is not an official dispatch system and must not replace radio, CAD, pager, or agency procedures.

## Before you begin

You need:

- A Windows, macOS, or Linux computer that can stay powered on.
- An internet connection.
- The MARK ZIP package supplied by your administrator.
- Notification credentials supplied by your administrator, such as Pushover or ntfy.
- A service-area map file, normally ending in `.geojson`, unless you are only doing a smoke test.

Do not download random copies of MARK from search results. Use the download link or package supplied by your department, station, or MARK administrator.

## Windows installation

1. Download the MARK ZIP file supplied by your administrator.
2. Open your Downloads folder.
3. Right-click the ZIP file and choose **Extract All**.
4. Open the newly extracted MARK folder.
5. Double-click **Install MARK - Windows.bat**.
6. If Windows asks whether the file may make changes, choose **Yes**.
7. If Python is missing, the installer will tell you where to obtain it. Install Python, make sure **Add Python to PATH** is checked, and run the installer again.
8. MARK opens when installation is complete.

## macOS installation

1. Download the MARK ZIP file supplied by your administrator.
2. Open **Downloads** and double-click the ZIP file.
3. Open the extracted MARK folder.
4. Control-click **Install MARK - macOS.command** and choose **Open**.
5. Choose **Open** again if macOS displays a security warning.
6. Follow the instructions in the installer window.
7. If macOS reports that Python is missing, install the current Python 3 package from `python.org`, then run the installer again.
8. When installation is complete, double-click **Start MARK.command**.

## Linux installation

1. Download and extract the MARK ZIP file supplied by your administrator.
2. Open the extracted MARK folder.
3. Right-click inside the folder and choose **Open in Terminal**.
4. Run:

```bash
chmod +x install-mark-linux.sh
./install-mark-linux.sh
```

5. Enter your computer password if asked.
6. The installer adds **MARK CHP Alerter** to your application menu and opens MARK.

## First launch

The first time MARK opens, it may show a welcome helper. Use it to open this guide, configure notifications, or load a broad test map.

The window title shows the MARK version. Send that version number to your administrator when reporting a problem.

## Fast smoke test

A smoke test confirms MARK can poll CHP, retrieve incident details, read the CAD coordinate, check a map, and attempt alerts.

1. Open **Configuration**.
2. Find **CHP Region / Service-Area Map** near the top.
3. Choose the correct **CHP center**.
4. Click **Load Center Test Map**.
5. Confirm that MARK warns the map is for testing only.
6. Configure notifications with **Notification Settings**.
7. Click **Test Selected Providers**.
8. Click **One Poll (Dry Run)**.

Smoke-test maps are intentionally broad and are not operational response boundaries.

## Operational setup

Before real use:

1. Stop the monitor if it is running.
2. Open **Configuration**.
3. In **CHP Region / Service-Area Map**, choose the CHP center.
4. Click **Browse** next to **Service-area map** and select the real station or agency map.
5. Open **Profiles / Regions / Incident Types**.
6. Confirm AREA values and incident type fragments.
7. Open **Notification Settings**.
8. Enter the notification settings supplied by your administrator.
9. Click **Save Region/Map** or **Save**.
10. Click **Test Selected Providers**.
11. Confirm the test reaches the intended phone or group.
12. Click **Start Monitor**.

## Normal daily use

1. Open MARK.
2. Confirm the correct CHP center, profile, and map are loaded.
3. Click **Start Monitor**.
4. Leave the computer powered on and connected to the internet.
5. Do not close MARK while it is monitoring.
6. Use **Stop** before changing profiles, maps, alert settings, or installing an update.
7. Restart the monitor after saving changes.

## Updating MARK

MARK checks for updates shortly after it opens.

When a newer version is available:

1. MARK displays an **Update available** message.
2. Stop the monitor.
3. Open **Configuration** and find **MARK Updates**.
4. Click **Install Update**.
5. Confirm the update.
6. MARK downloads the approved update and restarts itself.

The updater does not replace your saved settings, profiles, service-area maps, logs, or incident history.

Some copies of MARK are installed from a ZIP file rather than through Git. Those copies can report that automatic updating is unavailable. In that case, obtain the newest approved MARK package from your administrator and follow the same installation steps used originally.

When the updater reports local file changes or unpublished changes, do not force the update. Send the message to your MARK administrator.

## Alert levels

- **Low**: informational.
- **Medium**: routine operational attention.
- **High**: urgent and prominent.
- **Critical**: strongest alert treatment.

Delivery options may include notify once, notify on update, repeat until acknowledged, or repeat until expiration. Not every notification provider supports acknowledgement.

## Simplifying an existing map

1. Stop the monitor.
2. Load the map.
3. Click **Simplify Boundary**.
4. Start with 10 or 25 metres.
5. Review the proposed change.
6. Save to a new filename before replacing the original.

## Removing waypoints between two points

1. Stop the monitor.
2. Enable map editing.
3. Click the first waypoint.
4. Click **Set Line Start**.
5. Click the second waypoint.
6. Click **Remove Between Start + Selected**.
7. Review the new straight boundary segment.
8. Save only if the boundary is correct.

## Troubleshooting

### MARK does not open

- Restart the computer.
- Run the platform installer again.
- On Windows, send `runtime\mark-gui-error.log` to your MARK administrator.

### No alerts arrive

- Confirm MARK says it is running.
- Click **Test Selected Providers**.
- Check the computer's internet connection.
- Confirm the correct CHP center, profile, map, and recipient settings are loaded.

### Update check fails

- Confirm the computer is online.
- Try **Check for Updates** again.
- Private GitHub installations require the computer's existing Git access to the MARK repository.
- ZIP installations must be updated with a new approved package.
- Do not delete `.env`, profiles, or maps while troubleshooting an update.

### The computer goes to sleep

Change its power settings so it remains awake while MARK is operating. Closing a laptop lid normally stops monitoring unless configured otherwise.

## Safe use

- Do not treat MARK as dispatch.
- Do not rely on MARK as the only alerting path.
- Protect notification tokens and passwords.
- Test each profile before operational use.
- Switch from smoke-test maps to real service-area maps before operational use.
- Report repeated CHP parsing errors to the administrator.
