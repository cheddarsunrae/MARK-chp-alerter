# CHP Alerter

CHP Alerter polls the public California Highway Patrol CAD page for the **Border Communications Center**, filters incidents to the Station 36 operational service area, and sends qualifying incidents through **Pushover emergency alerts**.

It is intended to provide earlier situational awareness when CHP publishes a relevant incident before the local fire dispatch path reaches the station.

> **Supplemental awareness only.** This is not an official CAD terminal, station alerting system, pager, radio, or replacement for agency dispatch. Public webpages, geocoding, networks, and third-party push services can fail or change.

## Alert criteria

An incident must satisfy both conditions:

1. CHP call type is exactly one of:
   - `Trfc Collision-1141Enrt`
   - `Trfc Collision-Unkn Inj`
   - `Report of Fire`
2. The location matches the configured operational area through explicit Jamul/Dulzura text, coordinates, or geocoding.

Current operational geometry:

- Station reference: `14145 Campo Rd, Jamul, CA 91935`
- Approximately 2 miles west of the station
- Approximately 7 miles north of the station
- Approximately 3 miles east of Dulzura
- Southwest taper to the Otay Lakes Road / Chula Vista operational edge

The polygon is operational geometry, not a legal district boundary.

## Features

- Polls CHP about every 65 seconds.
- Selects Border Communications Center directly.
- Deduplicates incidents across restarts.
- Primes already-active incidents without alerting on first startup by default.
- Optionally alerts when a relevant incident changes.
- Uses cached and rate-limited Nominatim geocoding for ambiguous intersections.
- Sends Pushover priority-2 emergency alerts with retry and expiry.
- Includes a manual `--test-pushover` command that does not poll CHP.
- Includes a hardened systemd service.

## Requirements

- Linux
- Python 3.10 or newer
- Internet access to CHP CAD, Pushover, and optionally Nominatim
- Pushover user key and application API token

## Local installation

```bash
git clone https://github.com/cheddarsunrae/chp-alerter.git
cd chp-alerter
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
```

Edit `.env` and set:

```dotenv
CHP_ALERT_GEOCODER=nominatim
CHP_ALERT_CONTACT=mailto:you@example.com
PUSHOVER_APP_TOKEN=your_application_api_token
PUSHOVER_USER_KEY=your_user_key
```

Load the environment:

```bash
set -a
. ./.env
set +a
```

## Test Pushover

Send a test without polling CHP:

```bash
python chp_jamul_alert.py --test-pushover
```

Default emergency profile:

```dotenv
PUSHOVER_PRIORITY=2
PUSHOVER_RETRY_SECONDS=30
PUSHOVER_EXPIRE_SECONDS=1800
PUSHOVER_SOUND=siren
```

Priority 2 repeats until acknowledged or expired. A quieter one-time setup test can be sent with:

```bash
python chp_jamul_alert.py --test-pushover --pushover-priority 0
```

## Dry-run CHP polling

Fetch and classify current incidents without sending notifications:

```bash
python chp_jamul_alert.py --once --dry-run --alert-existing
```

Run continuously in the foreground:

```bash
python chp_jamul_alert.py
```

## Production systemd installation

Create a restricted service account:

```bash
sudo useradd --system --home-dir /var/lib/chp-jamul-alert \
  --create-home --shell /usr/sbin/nologin chp-alert
```

On Fedora, use `/sbin/nologin` if `/usr/sbin/nologin` is absent.

Install the application:

```bash
sudo mkdir -p /opt/chp-alerter
sudo cp chp_jamul_alert.py requirements.txt service_area.geojson /opt/chp-alerter/
sudo python3 -m venv /opt/chp-alerter/.venv
sudo /opt/chp-alerter/.venv/bin/python -m pip install --upgrade pip
sudo /opt/chp-alerter/.venv/bin/python -m pip install -r /opt/chp-alerter/requirements.txt
sudo chown -R root:root /opt/chp-alerter
sudo chmod 755 /opt/chp-alerter/chp_jamul_alert.py
```

Install the protected configuration:

```bash
sudo cp .env.example /etc/chp-alerter.env
sudo chmod 600 /etc/chp-alerter.env
sudo chown root:root /etc/chp-alerter.env
sudoedit /etc/chp-alerter.env
```

Required values:

```dotenv
CHP_ALERT_GEOCODER=nominatim
CHP_ALERT_CONTACT=mailto:you@example.com
PUSHOVER_APP_TOKEN=your_application_api_token
PUSHOVER_USER_KEY=your_user_key
```

Test Pushover using systemd's environment-file support:

```bash
sudo systemd-run --wait --pipe \
  --property=EnvironmentFile=/etc/chp-alerter.env \
  --uid=chp-alert \
  /opt/chp-alerter/.venv/bin/python \
  /opt/chp-alerter/chp_jamul_alert.py --test-pushover
```

Install and start the service:

```bash
sudo cp chp-alerter.service /etc/systemd/system/chp-alerter.service
sudo systemctl daemon-reload
sudo systemctl enable --now chp-alerter.service
```

Verify:

```bash
sudo systemctl status chp-alerter.service
sudo journalctl -u chp-alerter.service -f
```

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `CHP_ALERT_INTERVAL` | `65` | Poll interval; values below 60 are rejected. |
| `CHP_ALERT_TIMEOUT` | `20` | HTTP timeout in seconds. |
| `CHP_ALERT_STATE_FILE` | user-local path | Persistent deduplication state. Production uses `/var/lib/chp-jamul-alert/state.json`. |
| `CHP_ALERT_RETENTION_HOURS` | `72` | Retain unseen incident state this long. |
| `CHP_ALERT_GEOCODER` | `none` | `none` or `nominatim`. |
| `CHP_ALERT_CONTACT` | blank | Identifying contact required for Nominatim. |
| `CHP_ALERT_EXISTING` | `0` | Alert for already-active incidents on first launch. Normally leave off. |
| `CHP_ALERT_UPDATES` | `0` | Alert again when a relevant incident row changes. |
| `CHP_ALERT_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR`. |
| `PUSHOVER_APP_TOKEN` | blank | Pushover application token. |
| `PUSHOVER_USER_KEY` | blank | Pushover recipient user/group key. |
| `PUSHOVER_PRIORITY` | `2` | Emergency priority. |
| `PUSHOVER_RETRY_SECONDS` | `30` | Retry interval for priority 2. |
| `PUSHOVER_EXPIRE_SECONDS` | `1800` | Stop retrying after this many seconds. |
| `PUSHOVER_SOUND` | `siren` | Pushover sound name. |

Command-line arguments override environment values.

## Pushover phone setup

1. Install Pushover and sign in.
2. Copy the account **User Key**.
3. Create an application/API token named `CHP Alerter`.
4. Put both values in `/etc/chp-alerter.env` or local `.env`.
5. Run `--test-pushover`.
6. Confirm the emergency alert sounds and can be acknowledged.
7. Allow Pushover through phone Do Not Disturb and verify its notification channel can make sound.

A correctly delivered alert can still be silenced by phone-level DND, Bluetooth routing, or notification volume. Technology remains committed to being technically correct at the least useful moment.

## Updating

```bash
cd /path/to/chp-alerter
git pull
sudo cp chp_jamul_alert.py service_area.geojson /opt/chp-alerter/
sudo systemctl restart chp-alerter.service
sudo journalctl -u chp-alerter.service -n 50 --no-pager
```

If dependencies changed:

```bash
sudo cp requirements.txt /opt/chp-alerter/
sudo /opt/chp-alerter/.venv/bin/python -m pip install -r /opt/chp-alerter/requirements.txt
sudo systemctl restart chp-alerter.service
```

## State and reset

State is stored at the configured `CHP_ALERT_STATE_FILE`. To inspect it:

```bash
sudo python3 -m json.tool /var/lib/chp-jamul-alert/state.json | less
```

To deliberately reset deduplication:

```bash
sudo systemctl stop chp-alerter.service
sudo cp /var/lib/chp-jamul-alert/state.json /var/lib/chp-jamul-alert/state.json.backup
sudo rm /var/lib/chp-jamul-alert/state.json
sudo systemctl start chp-alerter.service
```

The next start primes currently active incidents without alerting unless `CHP_ALERT_EXISTING=1`.

## Troubleshooting

### Pushover test fails

Confirm both credentials are present and not reversed. Do not paste their values into issues or chat.

### Alert arrives silently

- Confirm priority 2 and a valid sound.
- Allow Pushover through DND.
- Check Pushover quiet hours.
- Check notification volume and Bluetooth output.

### Service exits immediately

```bash
sudo journalctl -u chp-alerter.service -n 100 --no-pager
```

Common causes: missing environment file, only one Pushover credential, invalid priority-2 retry/expiry, or Nominatim enabled without `CHP_ALERT_CONTACT`.

### Relevant road does not match

Roads may continue outside the polygon, so most road-name-only incidents require geocoding. Enable Nominatim and inspect logs at `DEBUG` level.

## Repository files

- `chp_jamul_alert.py` — monitor, filtering, deduplication, geocoding, and Pushover delivery
- `service_area.geojson` — operational service-area polygon
- `chp-alerter.service` — hardened systemd unit
- `.env.example` — configuration template without credentials
- `requirements.txt` — Python dependencies
