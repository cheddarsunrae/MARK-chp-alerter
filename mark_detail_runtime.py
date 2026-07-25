#!/usr/bin/env python3
"""MARK runtime corrections for CHP incident-detail responses.

CHP detail postbacks can return the selected incident panel together with the
complete incident listing.  The legacy parser accepted every timestamped table
row, which attached unrelated incidents to each call.  This module installs a
strict parser at runtime and treats latitude/longitude in the selected detail
header as the authoritative geographic confirmation.
"""
from __future__ import annotations

import re
from typing import Any

import requests
from bs4 import BeautifulSoup

import chp_detail_alert as detail
import chp_jamul_alert as core


TIME_PATTERN = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M", re.I)
LISTING_ROW_PATTERN = re.compile(
    r"^Details\s*\|\s*\d{3,5}\s*\|\s*"
    r"\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M\s*\|",
    re.I,
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


def _row_values(row: Any) -> list[str]:
    cells = row.find_all(["td", "th"], recursive=False) or row.find_all(["td", "th"])
    return [
        value
        for value in (core.normalize_space(cell.get_text(" ", strip=True)) for cell in cells)
        if value
    ]


def _is_listing_row(values: list[str], joined: str) -> bool:
    """Identify an ordinary row from the all-incidents listing grid."""
    if LISTING_ROW_PATTERN.match(joined):
        return True
    if len(values) >= 5 and re.fullmatch(r"\d{3,5}", values[0]) and TIME_PATTERN.fullmatch(values[1]):
        return True
    return bool(
        len(values) >= 6
        and values[0].casefold() == "details"
        and re.fullmatch(r"\d{3,5}", values[1])
        and TIME_PATTERN.fullmatch(values[2])
    )


def parse_detail_lines(html: str, incident_number: str | None = None) -> tuple[str, ...]:
    """Return only the selected incident's header and genuine CAD notes.

    Coordinate-bearing rows are retained before generic row filtering because
    CHP places the selected call's latitude/longitude in its detail header.
    """
    soup = BeautifulSoup(html, "html.parser")
    lines: list[str] = []

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

        # Detail-header coordinates are the preferred geographic evidence.
        if core.extract_coordinates(joined):
            lines.append(joined)
            continue

        if _is_listing_row(values, joined):
            continue

        cleaned = list(values)
        if cleaned and cleaned[0].casefold() in {"details", "detail", "time", "timestamp"}:
            cleaned = cleaned[1:]
        if incident_number and cleaned and cleaned[0] == incident_number:
            cleaned = cleaned[1:]
        text = " | ".join(value for value in cleaned if value)
        if not text:
            continue

        if detail.CODE_PATTERN.search(text) or TIME_PATTERN.search(text) or DETAIL_LANGUAGE.search(text):
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
    return parse_detail_lines(response.text, incident_number)


_ORIGINAL_MATCH_INCIDENT = detail.match_incident


def match_incident(incident: Any, **kwargs: Any) -> Any:
    """Prefer selected-detail coordinates, then use the normal fallback chain."""
    coordinates = core.extract_coordinates(" | ".join(getattr(incident, "details", ())))
    if coordinates:
        codes = detail.detail_codes(incident.details)
        alert_codes = sorted(codes & detail.ALERT_CODES)
        trigger = (
            f"detail code {', '.join(alert_codes)}"
            if alert_codes
            else f"target call type {incident.incident_type}"
        )
        result = core.coordinate_match(coordinates)
        return core.MatchResult(
            result.relevant,
            f"{trigger}; detail-header coordinates; {result.reason}",
            "high",
            result.latitude,
            result.longitude,
            result.distance_km,
        )
    return _ORIGINAL_MATCH_INCIDENT(incident, **kwargs)


def install() -> None:
    """Install the corrected parser into the imported detail module."""
    detail.parse_detail_lines = parse_detail_lines
    detail.fetch_details = fetch_details
    detail.match_incident = match_incident
