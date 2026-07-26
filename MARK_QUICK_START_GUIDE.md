# MARK Quick-Start Guide

## For firefighters, medics, dispatchers, and station personnel

This guide assumes you have never used GitHub, PowerShell, Terminal, Python, or command-line tools. You do not need to understand any of them to use MARK.

MARK watches the public California Highway Patrol incident page, checks selected calls against your service-area map, and sends notifications through the alert services configured by your administrator.

> MARK is a supplemental awareness tool. It is not an official dispatch system and must not replace radio, CAD, pager, or agency procedures.

## Before you begin

You need:

- A Windows, macOS, or Linux computer that can stay powered on.
- An internet connection.
- The MARK download folder supplied by your administrator.
- Notification credentials supplied by your administrator, such as Pushover or ntfy.
- A service-area map file, normally ending in `.geojson`.

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

## First-time setup

1. Open **Configuration**.
2. Choose the service-area map supplied by your administrator.
3. Open **Profiles / Regions / Incident Types**.
4. Choose or create the profile for your station or agency.
5. Confirm the communications center, AREA values, and incident types.
6. Enter the notification settings supplied by your administrator.
7. Click **Save**.
8. Click **Test Notification**.
9. Confirm the test reaches the intended phone or group.
10. Click **Start Monitor**.

## Normal daily use

1. Open MARK.
2. Confirm the correct profile and map are loaded.
3. Click **Start Monitor**.
4. Leave the computer powered on and connected to the internet.
5. Do not close MARK while it is monitoring.
6. Use **Stop** before changing profiles, maps, or alert settings.
7. Restart the monitor after saving changes.

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

## Troubleshooting

### MARK does not open

- Restart the computer.
- Run the platform installer again.
- On Windows, send `runtime\mark-gui-error.log` to your MARK administrator.

### No alerts arrive

- Confirm MARK says it is running.
- Click **Test Notification**.
- Check the computer's internet connection.
- Confirm the correct profile, map, and recipient settings are loaded.

### The computer goes to sleep

Change its power settings so it remains awake while MARK is operating. Closing a laptop lid normally stops monitoring unless configured otherwise.

## Safe use

- Do not treat MARK as dispatch.
- Do not rely on MARK as the only alerting path.
- Protect notification tokens and passwords.
- Test each profile before operational use.
- Report repeated CHP parsing errors to the administrator.
