# MARK User Guide

**Map-Aware Roadway Knowledge**  
Version: July 2026

> MARK is a supplemental awareness tool. It is not an official dispatch system, CAD terminal, pager, radio, or replacement for agency communications. Always follow your agency's policies and official dispatch channels.

## 1. What MARK does

MARK watches the public California Highway Patrol traffic incident page and looks for calls that match your selected criteria. It can:

- Watch selected CHP communications-center regions.
- Filter calls by incident-type words or codes.
- Check the CHP-provided latitude and longitude against your service-area map.
- Send qualifying alerts through Pushover.
- Keep a local record of incidents and detail updates.
- Let you create, load, edit, simplify, and save service-area maps.
- Save different monitoring profiles for different stations, crews, or response areas.

The current release uses Pushover. Support for ntfy, Gotify, generic webhooks, and additional alert policies is planned and is described in Section 13.

## 2. Before you begin

You need:

- A Windows computer with internet access.
- Permission to install and run software on the computer.
- A Pushover account, application token, and user or group key.
- A GeoJSON service-area map, or permission to create one in MARK.

MARK should remain running on a computer that stays awake and connected to the internet.

## 3. Starting MARK on Windows

1. Open **PowerShell**.
2. Go to the MARK folder:

   `C:\Users\Shane\Documents\GitHub\chp-alerter`

3. Run:

   `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

4. Run:

   `.\start-chp-alerter.ps1`

The first startup may take longer because MARK creates its private Python environment and installs required components.

## 4. Main screen

The main screen contains:

- **Start Monitor** - begins watching CHP incidents.
- **Stop** - stops monitoring.
- **Test Pushover** - sends a test notification.
- **One Poll** - performs one safe check and shows the result.
- **Reload Config** - reloads saved settings.
- **Reload Map** - reloads the current service-area file.
- **Live Log** - shows what MARK is doing.
- **Configuration** - stores notification and file settings.
- **Profiles / Regions / Incident Types** - controls what MARK watches.
- **Map Editor** - displays and edits the service-area boundary.

## 5. First-time setup

### 5.1 Enter Pushover credentials

In **Configuration**, enter:

- **Pushover Token** - your MARK application token.
- **Pushover User Key** - your personal or group recipient key.
- **Sound** - the alert sound to use.
- **Poll Interval** - how often MARK checks CHP. The minimum is 30 seconds.

Press **Save**.

### 5.2 Test notifications

Press **Test Pushover**.

A successful test confirms that the token, user key, internet connection, and Pushover service are working. A test message is not a real CHP incident.

### 5.3 Choose a service-area map

1. Find **Service Area File** in Configuration.
2. Press the **...** button.
3. Select a `.geojson` or `.json` map file.
4. Confirm that the boundary appears on the map.
5. Press **Save**.

## 6. Monitoring profiles

Profiles let different users or stations keep separate settings.

A profile stores:

- Service-area map.
- CHP AREA prefixes.
- Incident-type search fragments.
- Poll interval.
- Whether existing incidents should alert on startup.
- Whether changed incidents should alert again.

### Load a profile

1. Open **Profiles / Regions / Incident Types**.
2. Select the profile.
3. Press **Load Profile**.
4. Restart the monitor if it is already running.

### Save a profile

1. Set the desired map and filters.
2. Open the profile manager.
3. Press **Save as Profile**.
4. Enter a clear name, such as `Station 36`, `Medic 231`, or `Wildland East Zone`.

## 7. CHP AREA filtering

MARK can reject unrelated incidents before requesting their detail pages.

For the Station 36 profile, the default AREA prefixes are:

- `BC` - Border Communications Center area.
- `El` - El Cajon.

MARK compares the first two letters without regard to capitalization.

Examples:

- `El` matches `El Cajon`.
- `Sa` matches `San Diego`.
- `Oc` matches `Oceanside`.
- `Te` matches `Temecula`.

Statewide center selection is planned. The expansion will let users choose a CHP communications center by name instead of editing codes manually.

## 8. Incident-type filtering

MARK currently searches the CHP **Type** field for these default fragments:

- `Unk`
- `1140`
- `1141`
- `Min`
- `Maj`
- `1179`
- `1180`
- `1178`
- `un w`
- `Repo`

The search is not case-sensitive. A fragment can match several wording variations.

Examples:

- `Unk` can match unknown-injury collision wording.
- `1141` can match a collision with an ambulance en route.
- `Repo` can match Report of Fire.

Use broad fragments carefully. An overly broad fragment may create unwanted alerts.

## 9. How location matching works

For every incident that passes the first filter, MARK opens the CHP detail view. CHP provides a `Lat/Lon:` value in the selected incident's detail header.

MARK uses that CHP-provided coordinate directly. It does not need to look up the street address through a third-party geocoder.

The coordinate is checked against the active service-area polygon:

- Inside the polygon: the location requirement passes.
- Outside the polygon: no alert is sent.
- Missing or unreadable coordinate: MARK records a parser error and does not guess.

## 10. Editing the service-area map

### Move an existing waypoint

1. Enable map editing.
2. Click a numbered waypoint.
3. Drag it to the desired location.
4. Review the entire boundary.
5. Press **Save Map**.

### Extend part of the boundary

1. Enable editing.
2. Select the existing waypoint where the new section should begin.
3. Press **Start Extension**.
4. Click the new route points.
5. Make the last click near the old waypoint where the extension should end.
6. Press **Finish Extension**.
7. MARK snaps the end to the nearest existing waypoint.
8. Review and save.

### Simplify or optimize an existing map

1. Load the map.
2. Ensure no extension is active.
3. Press **Simplify Boundary**.
4. Enter a tolerance in metres.
5. Review the number of points MARK proposes to remove.
6. Confirm the change.
7. Inspect the new boundary carefully.
8. Use **Save As** first to preserve the original.

Suggested tolerances:

- **10 m** - very conservative.
- **25 m** - normal starting point.
- **50 m** - more aggressive.

Simplification mainly makes the map cleaner and easier to maintain. It does not provide a major speed increase for normal-sized polygons.

## 11. Starting and stopping monitoring

### Start

Press **Start Monitor**. The log should show:

- The loaded profile.
- The selected map and vertex count.
- AREA prefixes and Type fragments.
- Poll results.

### Stop

Press **Stop** before changing important settings, maps, or profiles.

Restart after changing:

- Service-area file.
- Profile.
- AREA prefixes.
- Type fragments.
- Poll interval.
- Notification settings.

## 12. Understanding alert behavior

Current Pushover behavior is controlled by priority, retry, and expiration settings.

- **Normal / one-time** alerts notify once.
- **High** alerts can receive stronger attention treatment but do not repeat indefinitely.
- **Emergency / persistent** alerts repeat according to the retry interval until acknowledged or until the expiration time is reached.

The current release exposes Pushover's priority settings. A future alert-policy screen will replace raw numbers with plain-language choices.

Recommended future choices:

- **Low** - quiet informational message.
- **Medium** - standard alert.
- **High** - prominent one-time alert.
- **Critical** - repeats until acknowledged or expired.

Additional planned controls:

- Notify once.
- Notify again only when important details change.
- Persistent until acknowledged.
- Escalate if not acknowledged after a set time.
- Quiet hours with critical-alert override.
- Per-call-type priority rules.
- Per-recipient routing.
- Duplicate suppression and cooldown periods.

## 13. Planned notification services

The next notification expansion is planned to support:

### Pushover

Best for simple reliable push and true acknowledged emergency alerts.

### ntfy

Supports HTTP-based push, priorities, tags, click links, and action buttons. It can use the public ntfy service or a self-hosted server.

### Gotify

A self-hosted notification server with application tokens and numeric message priorities.

### Generic webhook

Lets MARK send structured incident data to services such as automation platforms, station dashboards, or custom agency systems.

### Possible later additions

- Email.
- Microsoft Teams.
- Slack.
- Discord.
- SMS through a separately configured provider.
- Local desktop sound and visual pop-up.

Credentials for each provider should remain stored locally and must never be committed to GitHub.

## 14. California-wide expansion

The CHP CAD page currently exposes these communications-center selections:

- Bakersfield
- Barstow
- Bishop
- Border
- Capitol
- Chico
- El Centro
- Fresno
- Golden Gate
- Humboldt
- Indio
- Inland
- Los Angeles
- Merced
- Monterey
- Orange
- Redding
- Sacramento
- San Luis Obispo
- Stockton
- Susanville
- Truckee
- Ukiah
- Ventura
- Yreka

The statewide version will:

1. Let the user choose one or more communications centers by name.
2. Load the correct CHP center code automatically.
3. Learn or display the AREA values used within that center.
4. Save center and AREA choices in each profile.
5. Use a center-specific service-area map.
6. Keep the same Type-fragment and CHP Lat/Lon matching process.

## 15. Reading the log

Common messages:

- **Fast prefilter retained X of Y incidents** - the listing filter is working.
- **CHP detail Lat/Lon** - MARK found and used the CAD coordinate.
- **Inside configured polygon** - the incident is geographically relevant.
- **Outside configured polygon** - the incident is outside the selected response area.
- **Dry-run mode** - MARK evaluated the call but intentionally did not send a notification.
- **Postback returned the incident listing again** - CHP did not open the selected detail; restart MARK and check for updates.

## 16. Troubleshooting

### MARK does not open

Look for:

`runtime\mark-gui-error.log`

Run the launcher from PowerShell so errors remain visible.

### No Pushover notification

- Press **Test Pushover**.
- Check both token and user key.
- Check the internet connection.
- Confirm that Pushover notifications are enabled on the receiving device.
- Review priority and sound settings.

### Expected call did not alert

Check the log for:

- AREA-prefix rejection.
- Type-fragment rejection.
- Outside-polygon result.
- Existing-call priming.
- Update alerts disabled.
- Missing CHP detail coordinate.

### Too many alerts

- Make Type fragments more specific.
- Narrow AREA prefixes.
- Tighten the service-area polygon.
- Disable alerting on minor updates.

### Map looks too complicated

Use **Simplify Boundary** with 10 m or 25 m and save to a new file first.

## 17. Safe use and maintenance

- Keep the computer awake and connected.
- Pull software updates before beginning a new deployment.
- Back up `.env`, profiles, and custom map files securely.
- Never share Pushover, ntfy, Gotify, or webhook credentials.
- Review maps after every edit.
- Test notifications after changing providers or recipient groups.
- Continue monitoring official radio, CAD, pager, and dispatch channels.

## 18. Updating MARK

From PowerShell:

`cd C:\Users\Shane\Documents\GitHub\chp-alerter`

`git pull`

Then restart MARK:

`.\start-chp-alerter.ps1`

## 19. Getting useful support information

When reporting a problem, provide:

- The time the problem occurred.
- Incident number, when available.
- The relevant log lines.
- The selected profile and communications center.
- Whether the call appeared on the CHP site.
- Whether a test notification worked.

Do not include notification tokens, user keys, passwords, or private webhook URLs.
