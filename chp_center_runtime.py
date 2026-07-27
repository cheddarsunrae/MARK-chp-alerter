#!/usr/bin/env python3
"""Configurable CHP communications-center support for MARK.

This keeps the older Border/Jamul-oriented modules usable while allowing the
runtime to fetch any CHP communications center selected in the GUI/profile.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

import chp_detail_alert as detail
import chp_jamul_alert as core

ROOT = Path(__file__).resolve().parent
CENTERS_FILE = ROOT / "data" / "chp_communications_centers.json"
DEFAULT_CENTER_CODE = "BCCC"
DEFAULT_CENTER_NAME = "Border"


def _load_center_map() -> dict[str, str]:
    try:
        payload = json.loads(CENTERS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {DEFAULT_CENTER_CODE: DEFAULT_CENTER_NAME}
    centers = payload.get("centers", [])
    values: dict[str, str] = {}
    if isinstance(centers, list):
        for item in centers:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code", "")).strip()
            name = str(item.get("name", "")).strip()
            if code and name:
                values[code] = name
    values.setdefault(DEFAULT_CENTER_CODE, DEFAULT_CENTER_NAME)
    return values


def configured_center_code() -> str:
    code = os.getenv("CHP_ALERT_COMM_CENTER", DEFAULT_CENTER_CODE).strip().upper()
    return code or DEFAULT_CENTER_CODE


def configured_center_name() -> str:
    centers = _load_center_map()
    code = configured_center_code()
    explicit = os.getenv("CHP_ALERT_COMM_CENTER_NAME", "").strip()
    return explicit or centers.get(code, code)


def selected_center_url(code: str | None = None) -> str:
    selected = (code or configured_center_code()).strip().upper() or DEFAULT_CENTER_CODE
    return core.BASE_URL.replace("Traffic.aspx", "traffic.aspx") + "?" + urlencode(
        {"__EVENTTARGET": "ddlComCenter", "ddlComCenter": selected}
    )


def _successful_controls(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if form is None:
        raise RuntimeError("CHP page did not contain the expected ASP.NET form")
    payload: dict[str, str] = {}
    for field in form.find_all(["input", "select", "textarea"]):
        name = field.get("name")
        if not name or field.has_attr("disabled"):
            continue
        if field.name == "input":
            field_type = str(field.get("type", "text")).casefold()
            if field_type in {"button", "file", "image", "reset", "submit"}:
                continue
            if field_type in {"checkbox", "radio"} and not field.has_attr("checked"):
                continue
            payload[str(name)] = str(field.get("value", "on" if field_type in {"checkbox", "radio"} else ""))
        elif field.name == "select":
            option = field.find("option", selected=True) or field.find("option")
            if option is not None:
                payload[str(name)] = str(option.get("value", option.get_text(" ", strip=True)))
        else:
            payload[str(name)] = field.get_text("", strip=False)
    return payload


def is_selected_center_page(html: str) -> bool:
    text = core.normalize_space(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))
    return "Number of Incidents:" in text and "Communications Center" in text


def fetch_chp_center_page(session: requests.Session, timeout: float) -> tuple[str, str]:
    """Fetch the configured CHP communications center listing page."""
    code = configured_center_code()
    direct = selected_center_url(code)
    response = session.get(direct, timeout=timeout)
    response.raise_for_status()
    if is_selected_center_page(response.text):
        return response.text, str(response.url)

    front = session.get(core.BASE_URL, timeout=timeout)
    front.raise_for_status()
    payload = _successful_controls(front.text)
    payload["__EVENTTARGET"] = "ddlComCenter"
    payload["ddlComCenter"] = code
    posted = session.post(core.BASE_URL, data=payload, timeout=timeout)
    posted.raise_for_status()
    if not is_selected_center_page(posted.text):
        raise RuntimeError(f"CHP did not return {configured_center_name()} Communications Center data")
    return posted.text, str(posted.url)


def parse_detailed_incidents(html: str) -> list[detail.DetailedIncident]:
    """Parse incidents from any CHP communications-center listing."""
    soup = BeautifulSoup(html, "html.parser")
    text = core.normalize_space(soup.get_text(" ", strip=True))
    if "Number of Incidents:" not in text:
        raise ValueError("response is not a CHP communications-center incident listing")
    updated = re.search(
        r"Updated\s+as\s+of\s+(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s+[AP]M)",
        text,
        re.I,
    )
    page_updated = core.normalize_space(updated.group(1)) if updated else ""
    incidents: list[detail.DetailedIncident] = []
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
            match = detail.POSTBACK_PATTERN.search(str(anchor.get("href", "")))
            if match:
                postback = match.group("argument")
        incidents.append(
            detail.DetailedIncident(
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


def _detailed_identity(self: detail.DetailedIncident) -> str:
    parsed = core.parse_chp_datetime(self.page_updated)
    page_date = parsed.date().isoformat() if parsed else datetime.now().date().isoformat()
    return f"{configured_center_code()}:{page_date}:{self.number}"


def _summary_signature(summary: detail.DetailedIncident) -> str:
    """Return a stable listing-row signature that ignores the page refresh time."""
    data = asdict(summary)
    data.pop("page_updated", None)
    data.pop("details", None)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _safe_skip_detail_fetch(previous: dict[str, Any] | None, summary_signature: str) -> bool:
    """Return True when an unchanged, previously outside-boundary call can be skipped."""
    return bool(
        previous
        and previous.get("skip_detail_fetch")
        and previous.get("summary_signature") == summary_signature
    )


def _should_skip_future_details(match: core.MatchResult) -> bool:
    """Only cache geography-based rejections, never boring in-area call types."""
    reason = (match.reason or "").casefold()
    return bool(
        not match.relevant
        and "outside" in reason
        and "within boundary buffer" not in reason
    )


def process_once(
    session: requests.Session,
    state: dict[str, Any],
    geocode_cache: core.GeocodeCache,
    args: Any,
) -> int:
    html, source_url = core.fetch_border_page(session, args.timeout)
    incidents = detail.parse_incidents(html)
    records: dict[str, Any] = state.setdefault("incidents", {})
    first_run = not records
    now = datetime.now(timezone.utc).isoformat()
    alerts = discarded = detail_fetches = cached_skips = 0

    for summary in incidents:
        if detail.is_discarded_area(summary.area):
            discarded += 1
            detail.LOG.debug("Discarded incident %s immediately by AREA=%s", summary.number, summary.area)
            continue

        summary_signature = _summary_signature(summary)
        previous = records.get(summary.identity)
        if _safe_skip_detail_fetch(previous, summary_signature):
            previous["last_seen"] = now
            cached_skips += 1
            detail.LOG.debug(
                "Skipped incident %s detail fetch using cached rejection: %s",
                summary.number,
                previous.get("reason", "previous nonmatch"),
            )
            continue

        incident = summary
        if summary.detail_postback:
            try:
                incident = detail.DetailedIncident(
                    **{
                        **asdict(summary),
                        "details": detail.fetch_details(
                            session,
                            html,
                            summary.detail_postback,
                            args.timeout,
                            incident_number=summary.number,
                        ),
                    }
                )
                detail_fetches += 1
            except TypeError:
                incident = detail.DetailedIncident(
                    **{
                        **asdict(summary),
                        "details": detail.fetch_details(session, html, summary.detail_postback, args.timeout),
                    }
                )
                detail_fetches += 1
            except requests.RequestException as exc:
                detail.LOG.warning("Could not fetch details for incident %s: %s", summary.number, exc)

        previous = records.get(incident.identity)
        is_new = previous is None
        changed = previous is not None and previous.get("fingerprint") != incident.fingerprint
        detail_changed = previous is None or previous.get("detail_fingerprint") != incident.detail_fingerprint
        if detail_changed:
            detail.append_detail_log(detail.DETAIL_LOG_FILE, incident, now)
            codes = detail.detail_codes(incident.details)
            if codes:
                detail.LOG.info("Incident %s detail codes: %s", incident.number, ", ".join(sorted(codes)))

        if first_run and not args.alert_existing:
            records[incident.identity] = {
                "fingerprint": incident.fingerprint,
                "detail_fingerprint": incident.detail_fingerprint,
                "summary_signature": summary_signature,
                "relevant": False,
                "reason": "primed without alert",
                "skip_detail_fetch": False,
                "last_seen": now,
            }
            continue
        if is_new or changed:
            match = detail.match_incident(
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
                detail.LOG.info(
                    "Incident %s changed; relevant=%s reason=%s",
                    incident.number,
                    match.relevant,
                    match.reason,
                )
            records[incident.identity] = {
                "fingerprint": incident.fingerprint,
                "detail_fingerprint": incident.detail_fingerprint,
                "summary_signature": summary_signature,
                "relevant": match.relevant,
                "reason": match.reason,
                "skip_detail_fetch": _should_skip_future_details(match),
                "last_seen": now,
            }
        else:
            previous["last_seen"] = now
            previous["summary_signature"] = summary_signature

    detail.LOG.info(
        "Parsed %d %s incidents; discarded %d by AREA; fetched %d details; "
        "skipped %d cached outside-boundary nonmatches; sent %d alerts",
        len(incidents),
        configured_center_name(),
        discarded,
        detail_fetches,
        cached_skips,
        alerts,
    )
    core.prune_state(state, args.retention_hours)
    core.atomic_write_json(args.state_file, state)
    return alerts


def install() -> None:
    """Install center-aware fetching and parsing."""
    code = configured_center_code()
    core.BORDER_URL = selected_center_url(code)
    core.fetch_border_page = fetch_chp_center_page
    core.is_border_page = is_selected_center_page
    detail.parse_incidents = parse_detailed_incidents
    detail.is_discarded_area = lambda _area: False
    detail.process_once = process_once
    detail.DetailedIncident.identity = property(_detailed_identity)  # type: ignore[assignment]

    try:
        import mark_detail_runtime

        mark_detail_runtime._ORIGINAL_PARSE_INCIDENTS = parse_detailed_incidents
    except Exception:
        pass
