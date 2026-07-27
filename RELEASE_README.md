# MARK beta release package

This folder contains MARK — Map-Aware Roadway Knowledge.

MARK watches the public California Highway Patrol incident page, checks selected incidents against a configured service-area map, and sends notifications through the configured alert provider.

> MARK is a supplemental awareness tool. It does not replace dispatch, CAD, radio, paging, or agency procedures.

## Start here

For nontechnical users, open:

- `MARK_QUICK_START_GUIDE.md`

For technical setup, validation, or troubleshooting, open:

- `MARK_TECHNICAL_USER_GUIDE.md`

## Windows

1. Extract this ZIP folder.
2. Open the extracted folder.
3. Double-click `Install MARK - Windows.bat`.
4. If Python is missing, install Python 3 from python.org, check **Add Python to PATH**, then run the installer again.

## macOS

1. Extract this ZIP folder.
2. Control-click `Install MARK - macOS.command`.
3. Choose **Open**.
4. After installation, use `Start MARK.command`.

## Linux

Open a terminal in this folder and run:

```bash
chmod +x install-mark-linux.sh
./install-mark-linux.sh
```

## First-run smoke test

Use the **CHP Region / Service-Area Map** box in MARK:

1. Choose a CHP center.
2. Click **Load Center Test Map**.
3. Confirm that MARK loads a broad test-only polygon.
4. Start the monitor.

Smoke-test maps are deliberately broad. They are not operational service-area boundaries.

## Operational setup

Before real use:

1. Load or draw the actual station/agency service-area map.
2. Set the correct CHP center.
3. Set AREA and Type filters for the profile.
4. Configure notifications.
5. Send a test notification.
6. Run one dry poll.
7. Start the monitor.

## Private files

Release ZIPs should not contain `.env`, runtime logs, saved state, private service-area maps, or notification tokens. Those are created or supplied separately during local setup.
