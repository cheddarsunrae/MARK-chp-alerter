#!/usr/bin/env python3
"""MARK runtime corrections and fast first-pass CHP filtering.

CHP detail postbacks can return the selected incident panel together with the
complete incident listing. This module installs a strict parser, treats the CHP
``Lat/Lon:`` detail-header value as authoritative, and avoids unnecessary detail
requests by filtering listing rows with configurable AREA prefixes and Type
fragments.
"""
from __future__ import annotations

import html as html_module
import os
import re
from typing import Any

import requests
from bs4 import BeautifulSoup

import chp_detail_alert as detail
import chp_jamul_alert as core


DEFAULT_AREA_PREFIXES = ("BC", "El")
DEFAULT_TYPE_FRAGMENTS = (
    "Unk",
    "1140",
    "1141",
    "Min",
    "Maj",
    "1179",
    "1180",
    "1178",
    "un w",
    "Repo",
)

TIME_PATTERN = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M", re.I)
LISTING_ROW_PATTERN = re.compile(
    r"^Details\s*\|\s*\d{3,5}\s*\|\s*"
    r"\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M\s*\|",
    re.I,
)

# CHP's selected-call header uses a Lat/Lon label. The two coordinates may be
# separated by slash, comma, pipe, semicolon, whitespace, HTML markup, or short
# labels. Capture the first two decimal numbers following the label rather than
# depending on a specific table layout.
LAT_LON_LABEL = re.compile(r"\bLat\s*/\s*Lon\b\s*:?", re.I)
COORD_NUMBER = re.compile(
    r"(?P<number>[+-]?(?:\d{1,3}(?:\.\d+)?|\.\d+))\s*"
    r"(?P<direction>[NSEW])?",
    re.I,
)
SEPARATE_LAT_LON_PATTERN = re.compile(
    r"\bLat(?:itude)?\s*:?\s*"
    r"(?P<lat>[+-]?(?:\d{1,3}(?:\.\d+)?|\.\d+))\s*(?P<lat_dir>[NS])?"
    r".{0,160}?"
    r"\bLon(?:gitude)?\s*:?\s*"
    r"(?P<lon>[+-]?(?:\d{1,3}(?:\.\d+)?|\.\d+))\s*(?P<lon_dir>[EW])?",
    re.I | re.S,
)
DETAIL_LANGUAGE = re.compile(
    r"\b(?:unit|caller|vehicle|party|incident|location|fire|reported|advised|"
    r"enrt|en route|arrived|scene|tow|lane|blocked|closure|transferred|medic|"
    r"engine|patrol|officer|ambulance|patient|injury|traffic|hazard|roadway|"
    r"shoulder|dispatch|witness|subject|occupant|driver|passenger|request|"
    r"responding|staging|cancelled|canceled|clear|cleared|latitude|longitude|"
    r"lat|lon|gps)\b",
    re.I,
)


def split_config(value: str | None) -> tuple[str, ...]:
    return tuple(
        item.strip()
        for item in re.split(r"[,;\n]+", value or "")
        if item.strip()
    )


def configured_area_prefixes() -> tuple[str, ...]:
    values = split_config(os.getenv("CHP_ALERT_AREA_PREFIXES"))
    return values or DEFAULT_AREA_PREFIXES


def configured_type_fragments() -> tuple[str, ...]:
    values = split_config(os.getenv("CHP_ALERT_TYPE_FRAGMENTS"))
    return values or DEFAULT_TYPE_FRAGMENTS


def area_matches(area: str) -> bool:
    normalized = core.normalize_space(area).casefold()
    return any(
        normalized.startswith(prefix.casefold()[:2])
        for prefix in configured_area_prefixes()
        if prefix
    )


def type_matches(incident_type: str) -> bool:
    normalized = core.normalize_space(incident_type).casefold()
    return any(
        fragment.casefold() in normalized
        for fragment in configured_type_fragments()
    )


def _apply_direction(value: float, direction: str | None) -> float:
    if direction and direction.upper() in {"S", "W"}:
        return -abs(value)
    if direction and direction.upper() in {"N", "E"}:
        return abs(value)
    return value


def _valid_coordinates(latitude: float, longitude: float) -> bool:
    return -90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0


def extract_detail_coordinates(text: str) -> tuple[float, float] | None:
    """Extract CHP's authoritative coordinates from text or raw HTML.

    This intentionally searches the entire selected-detail response, not only
    table rows. CHP may render the header in a span, div, label, attribute, or
    another element outside the CAD-note table.
    """
    if not text:
        return None

    decoded = html_module.unescape(text)
    soup = BeautifulSoup(decoded, "html.parser")
    visible = soup.get_text(" ", strip=True)
    searchable = " | ".join((visible, decoded))

    label = LAT_LON_LABEL.search(searchable)
    if label:
        tail = searchable[label.end() : label.end() + 240]
        numbers = list(COORD_NUMBER.finditer(tail))
        if len(numbers) >= 2:
            latitude = _apply_direction(
                float(numbers[0].group("number")),
                numbers[0].group("direction"),
            )
            longitude = _apply_direction(
                float(numbers[1].group("number")),
                numbers[1].group("direction"),
            )
            if _valid_coordinates(latitude, longitude):
                return latitude, longitude

    separate = SEPARATE_LAT_LON_PATTERN.search(searchable)
    if separate:
        latitude = _apply_direction(
            float(separate.group("lat")), separate.group("lat_dir")
        )
        longitude = _apply_direction(
            float(separate.group("lon")), separate.group("lon_dir")
        )
        if _valid_coordinates(latitude, longitude):
            return latitude, longitude

    return None


def _lat_lon_diagnostic(html: str) -> str:
    """Return a short sanitized excerpt near a coordinate-looking header."""
    decoded = html_module.unescape(html)
    soup = BeautifulSoup(decoded, "html.parser")
    text = core.normalize_space(soup.get_text(" ", strip=True))
    match = re.search(r"(?i)lat.{0,20}lon|latitude|longitude|gps", text)
    if not match:
        return "no Lat/Lon-like label found in visible response text"
    start = max(0, match.start() - 80)
    end = min(len(text), match.end() + 180)
    excerpt = text[start:end]
    return re.sub(r"\s+", " ", excerpt)[:320]


def _row_values(row: Any) -> list[str]:
    cells = row.find_all(["td", "th"], recursive=False) or row.find_all(["td", "th"])
    return [
        value
        for value in (
            core.normalize_space(cell.get_text(" ", strip=True))
            for cell in cells
        )
        if value
    ]


def _is_listing_row(values: list[str], joined: str) -> bool:
    if LISTING_ROW_PATTERN.match(joined):
        return True
    if (
        len(values) >= 5
        and re.fullmatch(r"\d{3,5}", values[0])
        and TIME_PATTERN.fullmatch(values[1])
    ):
        return True
    return bool(
        len(values) >= 6
        and values[0].casefold() == "details"
        and re.fullmatch(r"\d{3,5}", values[1])
        and TIME_PATTERN.fullmatch(values[2])
    )


def parse_detail_lines(
    html: str,
    incident_number: str | None = None,
) -> tuple[str, ...]:
    """Return the selected incident's canonical coordinate header and CAD notes."""
    soup = BeautifulSoup(html, "html.parser")
    lines: list[str] = []

    coordinates = extract_detail_coordinates(html)
    if coordinates:
        lines.append(f"Lat/Lon: {coordinates[0]:.6f} / {coordinates[1]:.6f}")

    for row in soup.find_all("tr"):
        values = _row_values(row)
        if not values:
            continue
        joined = " | ".join(values)
        folded = joined.casefold()

        if folded.startswith(("details | no. | time", "no. | time")):
            continue
        if "number of incidents:" in folded:
            continue
        if _is_listing_row(values, joined):
            continue
        if extract_detail_coordinates(joined):
            continue  # already retained above in a stable canonical form

        cleaned = list(values)
        if cleaned and cleaned[0].casefold() in {
            "details",
            "detail",
            "time",
            "timestamp",
        }:
            cleaned = cleaned[1:]
        if incident_number and cleaned and cleaned[0] == incident_number:
            cleaned = cleaned[1:]
        text = " | ".join(value for value in cleaned if value)
        if not text:
            continue

        if (
            detail.CODE_PATTERN.search(text)
            or TIME_PATTERN.search(text)
            or DETAIL_LANGUAGE.search(text)
        ):
            lines.append(text)

    return tuple(dict.fromkeys(lines))


def fetch_details(
    session: requests.Session,
    listing_html: str,
    argument: str,
    timeout: float,
    incident_number: str | None = None,
) -> tuple[str, ...]:
    payload = detail.hidden_fields(listing_html)
    payload["__EVENTTARGET"] = "gvIncidents"
    payload["__EVENTARGUMENT"] = argument
    payload["ddlComCenter"] = "BCCC"
    response = session.post(core.BASE_URL, data=payload, timeout=timeout)
    response.raise_for_status()
    lines = parse_detail_lines(response.text, incident_number)
    if not extract_detail_coordinates(response.text):
        detail.LOG.error(
            "Incident %s detail response had no parseable Lat/Lon. Nearby response text: %s",
            incident_number or "unknown",
            _lat_lon_diagnostic(response.text),
        )
    return lines


_ORIGINAL_PARSE_INCIDENTS = detail.parse_incidents


def parse_incidents(html: str) -> list[Any]:
    """Filter the listing before any detail postback is requested."""
    incidents = _ORIGINAL_PARSE_INCIDENTS(html)
    selected: list[Any] = []
    for incident in incidents:
        if not area_matches(incident.area):
            detail.LOG.debug(
                "Discarded incident %s by AREA prefix: AREA=%s allowed=%s",
                incident.number,
                incident.area,
                ",".join(configured_area_prefixes()),
            )
            continue
        if not type_matches(incident.incident_type):
            detail.LOG.debug(
                "Discarded incident %s by TYPE fragment: TYPE=%s",
                incident.number,
                incident.incident_type,
            )
            continue
        selected.append(incident)
    detail.LOG.info(
        "Fast prefilter retained %d of %d incidents using AREA prefixes=%s and TYPE fragments=%s",
        len(selected),
        len(incidents),
        ",".join(configured_area_prefixes()),
        ",".join(configured_type_fragments()),
    )
    return selected


def match_incident(incident: Any, **kwargs: Any) -> Any:
    """Match exclusively from CHP's selected-detail coordinate."""
    detail_text = " | ".join(getattr(incident, "details", ()))
    coordinates = extract_detail_coordinates(detail_text)
    if not coordinates:
        return core.MatchResult(
            False,
            "selected detail missing or unparseable CHP Lat/Lon",
            "low",
        )

    codes = detail.detail_codes(incident.details)
    alert_codes = sorted(codes & detail.ALERT_CODES)
    trigger = (
        f"detail code {', '.join(alert_codes)}"
        if alert_codes
        else f"type fragment match: {incident.incident_type}"
    )
    result = core.coordinate_match(coordinates)
    return core.MatchResult(
        result.relevant,
        f"{trigger}; CHP detail Lat/Lon; {result.reason}",
        "high",
        result.latitude,
        result.longitude,
        result.distance_km,
    )


def install() -> None:
    """Install MARK's corrected parser and first-pass filters."""
    detail.parse_incidents = parse_incidents
    detail.parse_detail_lines = parse_detail_lines
    detail.fetch_details = fetch_details
    detail.match_incident = match_incident
    core.is_alertable_incident_type = type_matches
