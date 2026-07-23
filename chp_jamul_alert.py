#!/usr/bin/env python3
"""Monitor CHP Border CAD incidents and alert on Station 36-relevant calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import random
import re
import signal
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://cad.chp.ca.gov/Traffic.aspx"
BORDER_URL = (
    "https://cad.chp.ca.gov/traffic.aspx"
    "?__EVENTTARGET=ddlComCenter&ddlComCenter=BCCC"
)
PUSHOVER_URL = "https://api.pushover.net/1/messages.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

DEFAULT_INTERVAL = 65.0
DEFAULT_TIMEOUT = 20.0
DEFAULT_RETENTION_HOURS = 72
DEFAULT_STATE_FILE = Path.home() / ".local/state/chp-alerter/state.json"

STATION_ADDRESS = "14145 Campo Rd, Jamul, CA 91935"
STATION_COORDINATES = (32.711277, -116.865630)
DULZURA_COORDINATES = (32.6442247, -116.7814093)
OTAY_LAKES_CHULA_VISTA_EDGE = (32.647464, -116.931540)

# Final operational limits requested by the user:
# 2 miles west of Station 36, 7 miles north of Station 36,
# 3 miles east of Dulzura, with a southwest taper to Otay Lakes Road.
WEST_BOUNDARY_LONGITUDE = -116.89999
NORTH_BOUNDARY_LATITUDE = 32.81273
EAST_BOUNDARY_LONGITUDE = -116.72987
WEST_TAPER_LATITUDE = 32.6768367
SOUTH_EAST_LATITUDE = 32.6406052

SERVICE_AREA_POLYGON: tuple[tuple[float, float], ...] = (
    OTAY_LAKES_CHULA_VISTA_EDGE,
    (WEST_TAPER_LATITUDE, WEST_BOUNDARY_LONGITUDE),
    (NORTH_BOUNDARY_LATITUDE, WEST_BOUNDARY_LONGITUDE),
    (NORTH_BOUNDARY_LATITUDE, EAST_BOUNDARY_LONGITUDE),
    (SOUTH_EAST_LATITUDE, EAST_BOUNDARY_LONGITUDE),
)

ALLOWED_INCIDENT_TYPES = frozenset(
    {
        "trfc collision-1141enrt",
        "trfc collision-unkn inj",
        "report of fire",
    }
)

TEXT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Jamul", re.compile(r"\bJAMUL\b", re.I)),
    ("Dulzura", re.compile(r"\bDULZURA\b", re.I)),
    (
        "Peaceful Valley Ranch Road",
        re.compile(r"\bPEACEFUL\s+VALLEY\s+RANCH\b", re.I),
    ),
)

COORDINATE_PATTERNS = (
    re.compile(r"(?P<lat>3[12]\.\d{3,})\s*[,/ ]\s*(?P<lon>-11[67]\.\d{3,})", re.I),
    re.compile(
        r"LAT(?:ITUDE)?\s*[:=]\s*(?P<lat>3[12]\.\d{3,}).{0,40}?"
        r"LON(?:GITUDE)?\s*[:=]\s*(?P<lon>-11[67]\.\d{3,})",
        re.I | re.S,
    ),
)

LOG = logging.getLogger("chp-alerter")
STOP_REQUESTED = False
_CACHE_MISS = object()


@dataclass(frozen=True)
class Incident:
    number: str
    time_text: str
    incident_type: str
    location: str
    location_description: str
    area: str
    page_updated: str
    detail_url: str | None = None

    @property
    def searchable_text(self) -> str:
        return " | ".join(
            part
            for part in (
                self.incident_type,
                self.location,
                self.location_description,
                self.area,
            )
            if part
        )

    @property
    def identity(self) -> str:
        parsed = parse_chp_datetime(self.page_updated)
        page_date = parsed.date().isoformat() if parsed else datetime.now().date().isoformat()
        return f"{page_date}:{self.number}"

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(asdict(self), sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MatchResult:
    relevant: bool
    reason: str
    confidence: str
    latitude: float | None = None
    longitude: float | None = None
    distance_km: float | None = None


class GeocodeCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {}
        self.last_request = 0.0
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self.data = raw
            except (OSError, json.JSONDecodeError) as exc:
                LOG.warning("Ignoring unreadable geocode cache %s: %s", path, exc)

    def get(self, query: str) -> tuple[float, float] | None | object:
        if query not in self.data:
            return _CACHE_MISS
        value = self.data[query]
        if value is None:
            return None
        try:
            return float(value["lat"]), float(value["lon"])
        except (KeyError, TypeError, ValueError):
            return None

    def put(self, query: str, value: tuple[float, float] | None) -> None:
        self.data[query] = None if value is None else {"lat": value[0], "lon": value[1]}
        atomic_write_json(self.path, self.data)

    def rate_limit(self) -> None:
        elapsed = time.monotonic() - self.last_request
        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)
        self.last_request = time.monotonic()


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def normalize_incident_type(value: str) -> str:
    return normalize_space(value).rstrip(".").casefold()


def is_alertable_incident_type(value: str) -> bool:
    return normalize_incident_type(value) in ALLOWED_INCIDENT_TYPES


def parse_chp_datetime(value: str) -> datetime | None:
    value = normalize_space(value)
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %I:%M %p"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def parse_incidents(html: str, source_url: str = BORDER_URL) -> list[Incident]:
    soup = BeautifulSoup(html, "html.parser")
    page_text = normalize_space(soup.get_text(" ", strip=True))
    if "Border Communications Center" not in page_text:
        raise ValueError("response is not the Border Communications Center page")

    updated_match = re.search(
        r"Updated\s+as\s+of\s+(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s+[AP]M)",
        page_text,
        re.I,
    )
    page_updated = normalize_space(updated_match.group(1)) if updated_match else ""
    incidents: list[Incident] = []

    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False) or row.find_all(["td", "th"])
        values = [normalize_space(cell.get_text(" ", strip=True)) for cell in cells]
        if len(values) < 7:
            continue
        offset = 1 if values[0].lower().startswith("details") else 0
        if len(values) < offset + 6:
            continue
        number = values[offset]
        time_text = values[offset + 1]
        if not re.fullmatch(r"\d{3,5}", number):
            continue
        if not re.fullmatch(r"\d{1,2}:\d{2}\s+[AP]M", time_text, re.I):
            continue

        detail_url = None
        anchor = cells[0].find("a") if cells else None
        if anchor and anchor.get("href"):
            href = str(anchor["href"]).strip()
            if not href.lower().startswith("javascript:"):
                detail_url = urljoin(source_url, href)

        incidents.append(
            Incident(
                number=number,
                time_text=time_text,
                incident_type=values[offset + 2],
                location=values[offset + 3],
                location_description=values[offset + 4],
                area=values[offset + 5],
                page_updated=page_updated,
                detail_url=detail_url,
            )
        )

    expected = re.search(r"Number\s+of\s+Incidents:\s*(\d+)", page_text, re.I)
    if expected and int(expected.group(1)) and not incidents:
        raise ValueError("CHP page reports incidents but no rows parsed")
    return incidents


def is_border_page(html: str) -> bool:
    text = normalize_space(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))
    return "Border Communications Center" in text and "Number of Incidents:" in text


def fetch_border_page(session: requests.Session, timeout: float) -> tuple[str, str]:
    response = session.get(BORDER_URL, timeout=timeout)
    response.raise_for_status()
    if is_border_page(response.text):
        return response.text, str(response.url)

    front = session.get(BASE_URL, timeout=timeout)
    front.raise_for_status()
    soup = BeautifulSoup(front.text, "html.parser")
    form = soup.find("form")
    if form is None:
        raise RuntimeError("CHP page did not contain the expected ASP.NET form")
    payload: dict[str, str] = {}
    for field in form.find_all("input"):
        name = field.get("name")
        if name:
            payload[str(name)] = str(field.get("value", ""))
    payload["__EVENTTARGET"] = "ddlComCenter"
    payload["ddlComCenter"] = "BCCC"
    posted = session.post(BASE_URL, data=payload, timeout=timeout)
    posted.raise_for_status()
    if not is_border_page(posted.text):
        raise RuntimeError("CHP did not return Border Communications Center data")
    return posted.text, str(posted.url)


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    radius = 6371.0088
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def point_to_segment_km(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    ref_lat = math.radians(point[0])
    scale_x = 111.320 * math.cos(ref_lat)
    scale_y = 110.574
    px, py = point[1] * scale_x, point[0] * scale_y
    ax, ay = start[1] * scale_x, start[0] * scale_y
    bx, by = end[1] * scale_x, end[0] * scale_y
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def point_in_polygon(point: tuple[float, float]) -> bool:
    for index in range(len(SERVICE_AREA_POLYGON)):
        if point_to_segment_km(
            point,
            SERVICE_AREA_POLYGON[index],
            SERVICE_AREA_POLYGON[(index + 1) % len(SERVICE_AREA_POLYGON)],
        ) <= 0.02:
            return True
    y, x = point
    inside = False
    previous = SERVICE_AREA_POLYGON[-1]
    for current in SERVICE_AREA_POLYGON:
        y1, x1 = previous
        y2, x2 = current
        if (y1 > y) != (y2 > y):
            crossing = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing:
                inside = not inside
        previous = current
    return inside


def extract_coordinates(text: str) -> tuple[float, float] | None:
    for pattern in COORDINATE_PATTERNS:
        match = pattern.search(text)
        if match:
            return float(match.group("lat")), float(match.group("lon"))
    return None


def coordinate_match(coordinates: tuple[float, float]) -> MatchResult:
    distance = haversine_km(coordinates, STATION_COORDINATES)
    if point_in_polygon(coordinates):
        return MatchResult(True, "inside custom Station 36 service-area polygon", "high", coordinates[0], coordinates[1], distance)
    return MatchResult(False, "outside custom Station 36 service-area polygon", "high", coordinates[0], coordinates[1], distance)


def geocode_incident(
    incident: Incident,
    *,
    session: requests.Session,
    cache: GeocodeCache,
    contact: str,
    timeout: float,
) -> tuple[float, float] | None:
    parts = [incident.location, incident.location_description, incident.area, "San Diego County, California"]
    query = normalize_space(", ".join(part for part in parts if part))
    cached = cache.get(query)
    if cached is not _CACHE_MISS:
        return cached  # type: ignore[return-value]
    cache.rate_limit()
    response = session.get(
        NOMINATIM_URL,
        params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "us"},
        headers={"User-Agent": f"CHPAlerter/1.0 ({contact})"},
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    result = (float(body[0]["lat"]), float(body[0]["lon"])) if body else None
    cache.put(query, result)
    return result


def match_incident(
    incident: Incident,
    *,
    geocoder: str,
    session: requests.Session,
    geocode_cache: GeocodeCache,
    geocode_contact: str | None,
    timeout: float,
) -> MatchResult:
    if not is_alertable_incident_type(incident.incident_type):
        return MatchResult(False, f"excluded incident type: {incident.incident_type or 'blank'}", "high")

    coordinates = extract_coordinates(incident.searchable_text)
    if coordinates:
        return coordinate_match(coordinates)

    for label, pattern in TEXT_RULES:
        if pattern.search(incident.searchable_text):
            return MatchResult(True, f"text match: {label}", "medium")

    if geocoder == "nominatim" and geocode_contact:
        coordinates = geocode_incident(
            incident,
            session=session,
            cache=geocode_cache,
            contact=geocode_contact,
            timeout=timeout,
        )
        if coordinates:
            return coordinate_match(coordinates)
        return MatchResult(False, "address could not be geocoded", "low")

    return MatchResult(False, "no text/coordinate match; geocoder disabled", "low")


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "incidents": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read state file {path}: {exc}") from exc
    if not isinstance(state, dict) or not isinstance(state.get("incidents"), dict):
        raise RuntimeError(f"invalid state file structure: {path}")
    return state


def prune_state(state: dict[str, Any], retention_hours: int) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
    incidents = state.setdefault("incidents", {})
    for key, record in list(incidents.items()):
        try:
            last_seen = datetime.fromisoformat(record["last_seen"])
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
        except (KeyError, TypeError, ValueError):
            incidents.pop(key, None)
            continue
        if last_seen < cutoff:
            incidents.pop(key, None)


def send_pushover(
    session: requests.Session,
    *,
    token: str,
    user: str,
    title: str,
    message: str,
    source_url: str,
    priority: int,
    retry_seconds: int,
    expire_seconds: int,
    sound: str | None,
    timeout: float,
) -> None:
    payload = {
        "token": token,
        "user": user,
        "title": title[:250],
        "message": message,
        "priority": str(priority),
        "url": source_url,
        "url_title": "Open CHP CAD",
    }
    if priority == 2:
        payload["retry"] = str(retry_seconds)
        payload["expire"] = str(expire_seconds)
    if sound:
        payload["sound"] = sound
    response = session.post(PUSHOVER_URL, data=payload, timeout=timeout)
    response.raise_for_status()
    body = response.json()
    if body.get("status") != 1:
        raise RuntimeError(f"Pushover rejected message: {body}")


def build_alert_message(incident: Incident, match: MatchResult) -> tuple[str, str]:
    title = f"CHP CAD: {incident.incident_type}"[:250]
    lines = [f"{incident.time_text} • {incident.location}"]
    if incident.location_description:
        lines.append(incident.location_description)
    lines.append(f"Area: {incident.area} • Incident #{incident.number}")
    lines.append(f"Matched: {match.reason}")
    return title, "\n".join(lines)


def emit_alert(
    session: requests.Session,
    incident: Incident,
    match: MatchResult,
    source_url: str,
    args: argparse.Namespace,
) -> None:
    title, message = build_alert_message(incident, match)
    print(f"\n=== {title} ===\n{message}\nSource: {source_url}\n", flush=True)
    if args.dry_run:
        LOG.info("Dry-run mode: notification delivery skipped")
        return
    if not args.pushover_token:
        LOG.warning("No Pushover backend configured; alert printed only")
        return
    send_pushover(
        session,
        token=args.pushover_token,
        user=args.pushover_user,
        title=title,
        message=message,
        source_url=source_url,
        priority=args.pushover_priority,
        retry_seconds=args.pushover_retry,
        expire_seconds=args.pushover_expire,
        sound=args.pushover_sound,
        timeout=args.timeout,
    )
    LOG.info("Pushover alert sent for incident %s", incident.number)


def process_once(
    session: requests.Session,
    state: dict[str, Any],
    geocode_cache: GeocodeCache,
    args: argparse.Namespace,
) -> int:
    html, source_url = fetch_border_page(session, args.timeout)
    incidents = parse_incidents(html, source_url)
    records: dict[str, Any] = state.setdefault("incidents", {})
    first_run = not records
    now = datetime.now(timezone.utc).isoformat()
    alerts = 0

    target_count = sum(is_alertable_incident_type(item.incident_type) for item in incidents)
    LOG.info("Parsed %d Border incidents; %d target call types", len(incidents), target_count)

    for incident in incidents:
        previous = records.get(incident.identity)
        is_new = previous is None
        changed = previous is not None and previous.get("fingerprint") != incident.fingerprint

        if first_run and not args.alert_existing:
            records[incident.identity] = {
                "fingerprint": incident.fingerprint,
                "relevant": False,
                "reason": "primed without alert",
                "last_seen": now,
            }
            continue

        if is_new or changed:
            match = match_incident(
                incident,
                geocoder=args.geocoder,
                session=session,
                geocode_cache=geocode_cache,
                geocode_contact=args.geocode_contact,
                timeout=args.timeout,
            )
            was_relevant = bool(previous and previous.get("relevant"))
            if match.relevant and (is_new or not was_relevant or (changed and args.alert_updates)):
                emit_alert(session, incident, match, source_url, args)
                alerts += 1
            records[incident.identity] = {
                "fingerprint": incident.fingerprint,
                "relevant": match.relevant,
                "reason": match.reason,
                "last_seen": now,
            }
        else:
            previous["last_seen"] = now

    prune_state(state, args.retention_hours)
    atomic_write_json(args.state_file, state)
    return alerts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Alert on target CHP CAD incidents in the Station 36 service area.")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=float(os.getenv("CHP_ALERT_INTERVAL", DEFAULT_INTERVAL)))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("CHP_ALERT_TIMEOUT", DEFAULT_TIMEOUT)))
    parser.add_argument("--state-file", type=Path, default=Path(os.getenv("CHP_ALERT_STATE_FILE", str(DEFAULT_STATE_FILE))))
    parser.add_argument("--retention-hours", type=int, default=int(os.getenv("CHP_ALERT_RETENTION_HOURS", DEFAULT_RETENTION_HOURS)))
    parser.add_argument("--geocoder", choices=("none", "nominatim"), default=os.getenv("CHP_ALERT_GEOCODER", "none"))
    parser.add_argument("--geocode-contact", default=os.getenv("CHP_ALERT_CONTACT"))
    parser.add_argument("--alert-existing", action="store_true", default=os.getenv("CHP_ALERT_EXISTING", "0") == "1")
    parser.add_argument("--alert-updates", action="store_true", default=os.getenv("CHP_ALERT_UPDATES", "0") == "1")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test-pushover", action="store_true")
    parser.add_argument("--pushover-token", default=os.getenv("PUSHOVER_APP_TOKEN"))
    parser.add_argument("--pushover-user", default=os.getenv("PUSHOVER_USER_KEY"))
    parser.add_argument("--pushover-priority", type=int, default=int(os.getenv("PUSHOVER_PRIORITY", "2")))
    parser.add_argument("--pushover-retry", type=int, default=int(os.getenv("PUSHOVER_RETRY_SECONDS", "30")))
    parser.add_argument("--pushover-expire", type=int, default=int(os.getenv("PUSHOVER_EXPIRE_SECONDS", "1800")))
    parser.add_argument("--pushover-sound", default=os.getenv("PUSHOVER_SOUND", "siren"))
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default=os.getenv("CHP_ALERT_LOG_LEVEL", "INFO"))
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.interval < 60:
        raise SystemExit("--interval must be at least 60 seconds")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if bool(args.pushover_token) != bool(args.pushover_user):
        raise SystemExit("Pushover requires both PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY")
    if args.test_pushover and not args.pushover_token:
        raise SystemExit("--test-pushover requires Pushover credentials")
    if args.pushover_priority not in {-2, -1, 0, 1, 2}:
        raise SystemExit("PUSHOVER_PRIORITY must be -2, -1, 0, 1, or 2")
    if args.pushover_priority == 2:
        if args.pushover_retry < 30:
            raise SystemExit("PUSHOVER_RETRY_SECONDS must be at least 30")
        if not 1 <= args.pushover_expire <= 10800:
            raise SystemExit("PUSHOVER_EXPIRE_SECONDS must be between 1 and 10800")
    if args.geocoder == "nominatim" and not args.geocode_contact:
        raise SystemExit("Nominatim requires CHP_ALERT_CONTACT")


def handle_signal(signum: int, _frame: Any) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    LOG.info("Received signal %s; stopping", signum)


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    validate_args(args)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    session = requests.Session()
    session.headers.update({"User-Agent": "CHPAlerter/1.0", "Accept-Language": "en-US,en;q=0.8"})

    if args.test_pushover:
        try:
            send_pushover(
                session,
                token=args.pushover_token,
                user=args.pushover_user,
                title="CHP Alerter test",
                message="Pushover is configured correctly. This is a manual test, not a CHP incident.",
                source_url=BORDER_URL,
                priority=args.pushover_priority,
                retry_seconds=args.pushover_retry,
                expire_seconds=args.pushover_expire,
                sound=args.pushover_sound,
                timeout=args.timeout,
            )
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            LOG.error("Pushover test failed: %s", exc)
            return 1
        LOG.info("Pushover test sent successfully")
        return 0

    try:
        state = load_state(args.state_file)
    except RuntimeError as exc:
        LOG.error("%s", exc)
        return 2
    cache = GeocodeCache(args.state_file.with_name("geocode-cache.json"))
    backoff = 5.0

    while not STOP_REQUESTED:
        try:
            process_once(session, state, cache, args)
            backoff = 5.0
        except (requests.RequestException, RuntimeError, ValueError, OSError) as exc:
            LOG.error("Poll failed: %s", exc)
            if args.once:
                return 1
            delay = min(backoff, args.interval)
            time.sleep(delay)
            backoff = min(backoff * 2, args.interval)
            continue
        if args.once:
            break
        end = time.monotonic() + args.interval + random.uniform(0.0, 3.0)
        while not STOP_REQUESTED and time.monotonic() < end:
            time.sleep(min(1.0, end - time.monotonic()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
