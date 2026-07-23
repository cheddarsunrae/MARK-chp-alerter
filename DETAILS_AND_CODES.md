# CHP Details and CAD-Code Triage

`chp_detail_alert.py` is the production entry point. It imports the proven geofence, state, and Pushover implementation from `chp_jamul_alert.py`, then adds CHP WebForms detail-page monitoring.

## Processing order

1. Fetch the Border Communications Center incident list.
2. Read the `AREA` column.
3. Immediately discard rows whose area contains `Oceanside` or `Temecula`.
4. For every remaining row, submit the row's ASP.NET postback, such as:

   ```text
   __EVENTTARGET=gvIncidents
   __EVENTARGUMENT=Select$8
   ddlComCenter=BCCC
   ```

5. Parse the current detail lines.
6. Append a JSON record whenever the detail snapshot changes.
7. Apply call-type, CAD-code, and Station 36 service-area filtering.
8. Include the first available detail lines in the initial Pushover alert.

## CAD-code rules

| Detail code | Current behaviour |
|---|---|
| `11-78` | Can trigger the normal Station 36 Pushover alert path |
| `11-79` | Can trigger the normal Station 36 Pushover alert path |
| `11-80` | Can trigger the normal Station 36 Pushover alert path |
| `11-81` | Can trigger the normal Station 36 Pushover alert path |
| `11-82` | Logged only; no special Pushover category yet |

Codes accept common CHP formatting variants such as `11-78`, `11 78`, and `1178` only where the parser can unambiguously identify the code boundary.

A code does not bypass the geographic filter. It promotes the incident into the existing Station 36 location-matching path.

## Detail logging

Default production path:

```text
/var/lib/chp-jamul-alert/details.jsonl
```

Override it with:

```dotenv
CHP_ALERT_DETAIL_LOG_FILE=/var/lib/chp-jamul-alert/details.jsonl
```

Each line is an independent JSON object containing:

- observation timestamp;
- CHP incident identity and number;
- summary call type, location, description, and area;
- the current detail lines;
- detected CAD codes;
- whether the snapshot contains an alert code;
- whether it contains `11-82`.

Inspect recent entries:

```bash
tail -n 20 /var/lib/chp-jamul-alert/details.jsonl | python3 -m json.tool
```

For a stream that remains valid JSONL, use:

```bash
tail -f /var/lib/chp-jamul-alert/details.jsonl
```

## Alert-update behaviour

Details are logged whenever they change.

By default, an already-alerted incident does **not** send another emergency Pushover merely because the dispatcher added another note:

```dotenv
CHP_ALERT_UPDATES=0
```

To page again on relevant incident/detail changes:

```dotenv
CHP_ALERT_UPDATES=1
```

Use that carefully. Dispatcher notes can change frequently, and repeated priority-2 alerts would become tiresome with impressive speed.

## Installation or update

Copy both Python files into the production directory:

```bash
sudo cp chp_jamul_alert.py chp_detail_alert.py /opt/chp-alerter/
sudo cp chp-alerter.service /etc/systemd/system/chp-alerter.service
sudo systemctl daemon-reload
sudo systemctl restart chp-alerter.service
```

The service now runs:

```text
/opt/chp-alerter/chp_detail_alert.py
```

Confirm startup and detail activity:

```bash
sudo systemctl status chp-alerter.service
sudo journalctl -u chp-alerter.service -f
```

Expected poll summary:

```text
Parsed N Border incidents; discarded N by AREA; fetched N details; sent N alerts
```

## Validation

Run unit tests from the repository root:

```bash
python -m unittest discover -s tests -v
```

Then run a non-notifying live poll:

```bash
set -a
. ./.env
set +a
python chp_detail_alert.py --once --dry-run --alert-existing --log-level DEBUG
```

Before production use, inspect the output and JSONL log against several live CHP incidents. The unit tests prove the expected WebForms payload, parser, code rules, area discard, and alert-message construction; the CHP site can still change its markup because apparently stability was considered too luxurious.
