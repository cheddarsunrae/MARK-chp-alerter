# CHP Alerter Windows Interface

`chp_gui.py` is a lightweight Windows controller for the existing CHP CAD monitor. It uses Python's built-in Tk interface and launches `chp_detail_alert.py` as a managed backend process.

## What the interface does

- Starts and stops continuous CHP monitoring.
- Runs a single dry poll without sending incident alerts.
- Sends a controlled Pushover test.
- Displays backend output in a live scrolling log.
- Shows the last successful poll and latest incident-count summary.
- Stores configuration in the repository-local `.env` file.
- Corrects Linux template paths to Windows `%LOCALAPPDATA%\CHPAlerter` paths.
- Opens the JSONL detail log from the interface.
- Provides a dropdown for Pushover sounds.

The monitor itself remains `chp_detail_alert.py`. Closing the GUI stops the backend process after confirmation.

## Start it

From PowerShell in the cloned repository:

```powershell
cd C:\Users\Shane\Documents\GitHub\chp-alerter
git pull
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start-chp-alerter.ps1
```

The launcher creates `.venv` when needed, installs `requirements.txt`, creates `.env` from `.env.example` when missing, and opens the controller without a console window.

After initial setup, this is sufficient:

```powershell
.\start-chp-alerter.ps1
```

The GUI can also be opened directly from an activated virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
python .\chp_gui.py
```

## First configuration

Open the **Configuration** tab and enter:

- Pushover application token
- Pushover user or delivery-group key
- A real contact address for Nominatim, such as `mailto:shane@example.com`

The default Windows files are:

```text
C:\Users\Shane\AppData\Local\CHPAlerter\state.json
C:\Users\Shane\AppData\Local\CHPAlerter\details.jsonl
```

Press **Save Configuration**.

## Sound choice

The interface defaults to `alien`, which Pushover describes as **Alien Alarm (long)**. Other long built-in sounds are:

- `climb`
- `echo`
- `updown`
- `persistent`

The currently selected sound is sent explicitly with each CHP alert, so it can remain distinct from PulsePoint alerts that use `persistent`.

Pushover priority `2` is the emergency mode. It repeats the notification at the configured retry interval until it is acknowledged or reaches its expiry. This repetition does not stretch one sound clip; each notification plays the selected sound normally.

## Safe test order

1. Select `alien` or another sound.
2. Press **Save Configuration**.
3. Press **Test Pushover**.
4. Acknowledge the priority-2 notification on the phone.
5. Press **One Poll (Dry Run)**.
6. Confirm the summary appears and no error is shown.
7. Press **START MONITOR**.

The dry-run command fetches live CHP incidents and details but suppresses Pushover incident delivery.

## Buttons

### START MONITOR

Starts continuous monitoring. Existing active incidents are normally primed without alerting when `CHP_ALERT_EXISTING=0`.

### STOP

Requests a graceful stop. If the backend fails to stop within four seconds, the controller terminates it.

### Test Pushover

Sends the backend's test notification using the selected priority and sound. Priority 2 repeats until acknowledged or expired.

### One Poll (Dry Run)

Runs one verbose CHP poll with `--dry-run --alert-existing`. This is intended for parser and connectivity testing, not routine monitoring.

### Open Detail Log

Opens the configured JSONL detail file in its associated Windows application. The file is created only after a new or changed CHP detail snapshot is logged.

## Updating

Stop the monitor and close the interface, then run:

```powershell
cd C:\Users\Shane\Documents\GitHub\chp-alerter
git pull
.\start-chp-alerter.ps1
```

The launcher installs any newly added Python dependencies before opening the interface.

## Troubleshooting

### The old Linux log path appears

The GUI automatically converts paths beginning with `/var/` or `/home/` to `%LOCALAPPDATA%\CHPAlerter`. Press **Save Configuration** to write the corrected Windows values into `.env`.

### The detail log does not exist

That is normal until a new or changed detail snapshot has been recorded. The live log still shows each polling summary.

### Pushover only chirps briefly

Choose one of the built-in long sounds from the dropdown. `alien` is the default distinct choice. Emergency priority controls repetition and acknowledgement, not the duration of an individual sound file.

### PowerShell blocks the launcher

Use a process-only bypass:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start-chp-alerter.ps1
```

This does not permanently weaken the machine-wide execution policy.

### The interface says another process is running

Only one backend process is allowed per GUI instance. Stop the current monitor or test before launching another operation.

## Security

`.env` contains Pushover credentials and is ignored by Git. Do not paste it into issues, screenshots, chat, or documentation. The GUI passes credentials to the child process through environment variables rather than command-line arguments.
