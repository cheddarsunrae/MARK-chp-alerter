# MARK Statewide and Multi-Channel Expansion

## Status

This document defines the next implementation phase. The current accepted release monitors CHP Border data and delivers Pushover notifications. The items below are approved expansion requirements, not all current-release features.

## Notification providers

Implement a provider interface with independent enabled/disabled state and a test action for each provider:

1. Pushover
2. ntfy
3. Gotify
4. Generic JSON webhook
5. Optional later providers: email, Teams, Slack, Discord, SMS

No provider should be mandatory. One incident may be routed to multiple enabled providers.

## Common alert policy

Expose plain-language settings rather than provider-specific numeric values:

- Severity: low, medium, high, critical
- Delivery mode:
  - notify once
  - notify on important update
  - repeat until acknowledged
  - repeat until expiration
- Retry interval
- Expiration time
- Cooldown / duplicate suppression
- Quiet hours
- Critical override of quiet hours
- Escalation delay
- Per-call-type policy
- Per-profile recipient routing

Provider adapters translate the common policy to supported provider features. Unsupported behavior must be reported clearly rather than silently ignored.

## Acknowledgement model

Pushover emergency messages provide a receipt and acknowledgement state. For providers without equivalent acknowledgement, MARK needs its own acknowledgement mechanism before claiming persistent-until-acknowledged behavior.

Store:

- alert ID
- incident identity
- provider message ID or receipt
- sent time
- severity
- policy
- acknowledgement state and time
- expiration time
- retry count

## California-wide center catalog

The CHP CAD communications-center dropdown captured on 2026-07-25 contains:

| Code | Center |
|---|---|
| BFCC | Bakersfield |
| BSCC | Barstow |
| BICC | Bishop |
| BCCC | Border |
| CCCC | Capitol |
| CHCC | Chico |
| ECCC | El Centro |
| FRCC | Fresno |
| GGCC | Golden Gate |
| HMCC | Humboldt |
| ICCC | Indio |
| INCC | Inland |
| LACC | Los Angeles |
| MRCC | Merced |
| MYCC | Monterey |
| OCCC | Orange |
| RDCC | Redding |
| SACC | Sacramento |
| SLCC | San Luis Obispo |
| SKCCSTCC | Stockton |
| SUCC | Susanville |
| TKCC | Truckee |
| UKCC | Ukiah |
| VTCC | Ventura |
| YKCC | Yreka |

The application should parse this dropdown dynamically so a future CHP change does not require a code release.

## AREA discovery

The `AREA` column values differ by communications center. Do not depend solely on a manually maintained statewide list.

Use a layered approach:

1. Seed the catalog from CHP's official Area Offices by Dispatch Center pages.
2. Record AREA values observed in live CAD rows for each center.
3. Present discovered values in the profile editor.
4. Allow manual entry for uncommon or newly introduced values.
5. Mark source and last-seen date for every catalog entry.
6. Never delete a previously known area automatically; mark it inactive after a configurable period.

## Statewide polling behavior

- A profile selects one or more communications centers.
- Each selected center is fetched independently.
- Apply center-specific AREA allowlists and service-area polygons.
- Keep incident identity namespaced by center to prevent collisions.
- Rate-limit requests and add small jitter.
- Isolate failures so one unavailable center does not stop others.
- Display per-center health, last poll, incident count, and error state.

## Proposed configuration

```dotenv
CHP_ALERT_CENTERS=BCCC
CHP_ALERT_AREA_PREFIXES=BC,El
CHP_ALERT_TYPE_FRAGMENTS=Unk,1140,1141,Min,Maj,1179,1180,1178,un w,Repo

NOTIFY_PROVIDERS=pushover
ALERT_SEVERITY=critical
ALERT_DELIVERY_MODE=until_acknowledged
ALERT_RETRY_SECONDS=30
ALERT_EXPIRE_SECONDS=1800
ALERT_COOLDOWN_SECONDS=300

NTFY_SERVER=https://ntfy.sh
NTFY_TOPIC=
NTFY_TOKEN=

GOTIFY_URL=
GOTIFY_APP_TOKEN=

WEBHOOK_URL=
WEBHOOK_BEARER_TOKEN=
```

## Recommended implementation order

1. Extract the current Pushover sender behind a provider interface.
2. Add ntfy.
3. Add generic webhook.
4. Add Gotify.
5. Add common severity and one-time/update policies.
6. Add durable alert receipts and acknowledgement state.
7. Add persistent and escalation policies.
8. Replace hard-coded Border fetch logic with dynamic center selection.
9. Add the statewide center catalog and AREA discovery store.
10. Update GUI, tests, README, user guide, and handoff.

## Official research basis

The center list was confirmed against the live CHP CAD communications-center dropdown. CHP's official Public Safety Dispatcher statewide-locations page identifies the geographic divisions and dispatch/communications centers. CHP's official Area Offices by Dispatch Center page maps area offices to dispatch centers.
