#!/usr/bin/env python3
"""Add CHP incident-detail monitoring and CAD-code triage to CHP Alerter."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
from bs4 import BeautifulSoup

import chp_jamul_alert as core

LOG = logging.getLogger("chp-alerter.details")
DETAIL_LOG_FILE = Path(
    os.getenv(
        "CHP_ALERT_DETAIL_LOG_FILE",
        str(Path.home() / ".local/state/chp-alerter/details.jsonl"),
    )
)
DISCARDED_AREAS = ("oceanside", "temecula")
ALERT_CODES = frozenset({"11-78", "11-79", "11-80", "11-81"})
LOG_ONLY_CODES = frozenset({"11-82"})
CODE_PATTERN = re.compile(r"(?<!\d)11\s*[- ]?\s*(7[89]|8[012])(?!\d)", re.I)
POSTBACK_PATTERN = re.compile(
    r"__doPostBack\(\s*['\"]gvIncidents['\"]\s*,\s*['\"](?P<argument>Select\$\d+)['\"]\s*\)",
    re.I,
)


@dataclass(frozen=True)
class DetailedIncident:
    number: str
    time_text: str
    incident_type: str
    location: str
    location_description: str
    area: str
    page_updated: str
    detail_postback: str | None = None
    details: tuple[str, ...] = ()

    @property
    def searchable_text(self) -> str:
        return " | ".join(
            part
            for part in (
                self.incident_type,
                self.location,
                self.location_description,
                self.area,
                *self.details,
            )
            if part
        )

    @property
    def identity(self) -> str:
        parsed = core.parse_chp_datetime(self.page_updated)
        page_date = parsed.date().isoformat() if parsed else datetime.now().date().isoformat()
        return f"{page_date}:{self.number}"

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(asdict(self), sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @property
    def detail_fingerprint(self) -> str:
        canonical = json.dumps(self.details, ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def is_discarded_area(area: str) -> bool:
    normalized = core.normalize_space(area).casefold()
    return any(name in normalized for name in DISCARDED_AREAS)


def hidden_fields(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    return {
        str(field.get("name")): str(field.get("value", ""))
        for field in soup.select("input[name]")
    }


def parse_incidents(html: str) -> list[DetailedIncident]:
    soup = BeautifulSoup(html, "html.parser")
    text = core.normalize_space(soup.get_text(" ", strip=True))
    if "Border Communications Center" not in text:
        raise ValueError("response is not the Border Communications Center page")
    updated = re.search(
        r"Updated\s+as\s+of\s+(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s+[AP]M)",
        text,
        re.I,
    )
    page_updated = core.normalize_space(updated.group(1)) if updated else ""
    incidents: list[DetailedIncident] = []
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False) or row.find_all(["td", "th"])
        values = [core.normalize_space(cell.get_text(" ", strip=True)) for cell in cells]
        if len(values) < 7:
            continue
        offset = 1 if values[0].casefold().startswith("details") else 0
        if len(values) < offset + 6:
            continue
        number, time_text = values[offset], values[offset + 1]
        if not re.fullmatch(r"\d{3,5}", number):
            continue
        if not re.fullmatch(r"\d{1,2}:\d{2}\s+[AP]M", time_text, re.I):
            continue
        postback = None
        anchor = cells[0].find("a") if cells else None
        if anchor:
            match = POSTBACK_PATTERN.search(str(anchor.get("href", "")))
            if match:
                postback = match.group("argument")
        incidents.append(
            DetailedIncident(
                number,
                time_text,
                values[offset + 2],
                values[offset + 3],
                values[offset + 4],
                values[offset + 5],
                page_updated,
                postback,
            )
        )
    expected = re.search(r"Number\s+of\s+Incidents:\s*(\d+)", text, re.I)
    if expected and int(expected.group(1)) and not incidents:
        raise ValueError("CHP page reports incidents but no rows parsed")
    return incidents


def parse_detail_lines(html: str) -> tuple[str, ...]:
    soup = BeautifulSoup(html, "html.parser")
    lines: list[str] = []
    for row in soup.find_all("tr"):
        values = [
            core.normalize_space(cell.get_text(" ", strip=True))
            for cell in row.find_all(["td", "th"], recursive=False)
        ]
        values = [value for value in values if value]
        if not values:
            continue
        joined = " | ".join(values)
        if joined.casefold().startswith("details | no. | time"):
            continue
        if (
            CODE_PATTERN.search(joined)
            or re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M\b", joined, re.I)
            or re.search(r"\b(?:unit|caller|vehicle|party|incident|location|fire)\b", joined, re.I)
        ):
            lines.append(joined)
    return tuple(dict.fromkeys(lines))


def fetch_details(
    session: requests.Session,
    listing_html: str,
    argument: str,
    timeout: float,
) -> tuple[str, ...]:
    payload = hidden_fields(listing_html)
    payload["__EVENTTARGET"] = "gvIncidents"
    payload["__EVENTARGUMENT"] = argument
    payload["ddlComCenter"] = "BCCC"
    response = session.post(core.BASE_URL, data=payload, timeout=timeout)
    response.raise_for_status()
    return parse_detail_lines(response.text)


def detail_codes(details: Iterable[str]) -> frozenset[str]:
    return frozenset(
        f"11-{match.group(1)}"
        for line in details
        for match in CODE_PATTERN.finditer(line)
    )


def append_detail_log(path: Path, incident: DetailedIncident, observed_at: str) -> None:
    codes = sorted(detail_codes(incident.details))
    record = {
        "observed_at": observed_at,
        "identity": incident.identity,
        "number": incident.number,
        "time": incident.time_text,
        "incident_type": incident.incident_type,
        "location": incident.location,
        "location_description": incident.location_description,
        "area": incident.area,
        "details": list(incident.details),
        "codes": codes,
        "contains_alert_code": bool(set(codes) & ALERT_CODES),
        "contains_11_82": "11-82" in codes,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def match_incident(
    incident: DetailedIncident,
    *,
    geocoder: str,
    session: requests.Session,
    geocode_cache: core.GeocodeCache,
    geocode_contact: str | None,
    timeout: float,
) -> core.MatchResult:
    codes = detail_codes(incident.details)
    alert_codes = sorted(codes & ALERT_CODES)
    type_allowed = core.is_alertable_incident_type(incident.incident_type)
    if not type_allowed and not alert_codes:
        if codes & LOG_ONLY_CODES:
            return core.MatchResult(False, "11-82 detail code logged only", "high")
        return core.MatchResult(False, f"excluded incident type: {incident.incident_type or 'blank'}", "high")

    trigger = (
        f"detail code {', '.join(alert_codes)}"
        if alert_codes
        else f"target call type {incident.incident_type}"
    )
    coordinates = core.extract_coordinates(incident.searchable_text)
    if coordinates:
        result = core.coordinate_match(coordinates)
        return core.MatchResult(
            result.relevant,
            f"{trigger}; {result.reason}",
            result.confidence,
            result.latitude,
            result.longitude,
            result.distance_km,
        )
    for label, pattern in core.TEXT_RULES:
        if pattern.search(incident.searchable_text):
            return core.MatchResult(True, f"{trigger}; text match: {label}", "medium")
    if geocoder == "nominatim" and geocode_contact:
        coordinates = core.geocode_incident(
            incident,
            session=session,
            cache=geocode_cache,
            contact=geocode_contact,
            timeout=timeout,
        )
        if coordinates:
            result = core.coordinate_match(coordinates)
            return core.MatchResult(
                result.relevant,
                f"{trigger}; {result.reason}",
                result.confidence,
                result.latitude,
                result.longitude,
                result.distance_km,
            )
        return core.MatchResult(False, f"{trigger}; address could not be geocoded", "low")
    return core.MatchResult(False, f"{trigger}; no text/coordinate match; geocoder disabled", "low")


def build_alert_message(incident: DetailedIncident, match: core.MatchResult) -> tuple[str, str]:
    codes = sorted(detail_codes(incident.details) & ALERT_CODES)
    suffix = f" [{', '.join(codes)}]" if codes else ""
    title = f"CHP CAD: {incident.incident_type}{suffix}"[:250]
    lines = [f"{incident.time_text} • {incident.location}"]
    if incident.location_description:
        lines.append(incident.location_description)
    lines.append(f"Area: {incident.area} • Incident #{incident.number}")
    if incident.details:
        lines.append("Details:")
        lines.extend(incident.details)
    else:
        lines.append("Details: not yet available")
    lines.append(f"Matched: {match.reason}")
    return title, "\n".join(lines)


def process_once(
    session: requests.Session,
    state: dict[str, Any],
    geocode_cache: core.GeocodeCache,
    args: Any,
) -> int:
    html, source_url = core.fetch_border_page(session, args.timeout)
    incidents = parse_incidents(html)
    records: dict[str, Any] = state.setdefault("incidents", {})
    first_run = not records
    now = datetime.now(timezone.utc).isoformat()
    alerts = discarded = detail_fetches = 0

    for summary in incidents:
        if is_discarded_area(summary.area):
            discarded += 1
            LOG.debug("Discarded incident %s immediately by AREA=%s", summary.number, summary.area)
            continue
        incident = summary
        if summary.detail_postback:
            try:
                incident = DetailedIncident(
                    **{**asdict(summary), "details": fetch_details(session, html, summary.detail_postback, args.timeout)}
                )
                detail_fetches += 1
            except requests.RequestException as exc:
                LOG.warning("Could not fetch details for incident %s: %s", summary.number, exc)

        previous = records.get(incident.identity)
        is_new = previous is None
        changed = previous is not None and previous.get("fingerprint") != incident.fingerprint
        detail_changed = previous is None or previous.get("detail_fingerprint") != incident.detail_fingerprint
        if detail_changed:
            append_detail_log(DETAIL_LOG_FILE, incident, now)
            codes = detail_codes(incident.details)
            if codes:
                LOG.info("Incident %s detail codes: %s", incident.number, ", ".join(sorted(codes)))

        if first_run and not args.alert_existing:
            records[incident.identity] = {
                "fingerprint": incident.fingerprint,
                "detail_fingerprint": incident.detail_fingerprint,
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
            should_alert = match.relevant and (
                is_new or not was_relevant or (changed and args.alert_updates)
            )
            if should_alert:
                core.emit_alert(session, incident, match, source_url, args)
                alerts += 1
            elif changed:
                LOG.info(
                    "Incident %s changed; relevant=%s reason=%s",
                    incident.number,
                    match.relevant,
                    match.reason,
                )
            records[incident.identity] = {
                "fingerprint": incident.fingerprint,
                "detail_fingerprint": incident.detail_fingerprint,
                "relevant": match.relevant,
                "reason": match.reason,
                "last_seen": now,
            }
        else:
            previous["last_seen"] = now

    LOG.info(
        "Parsed %d Border incidents; discarded %d by AREA; fetched %d details; sent %d alerts",
        len(incidents),
        discarded,
        detail_fetches,
        alerts,
    )
    core.prune_state(state, args.retention_hours)
    core.atomic_write_json(args.state_file, state)
    return alerts


def main(argv: Iterable[str] | None = None) -> int:
    core.process_once = process_once
    core.build_alert_message = build_alert_message
    return core.main(argv)


if __name__ == "__main__":
    sys.exit(main())
