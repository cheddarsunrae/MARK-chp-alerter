#!/usr/bin/env python3
"""Browser-faithful CHP ASP.NET GridView detail postbacks for MARK.

The CHP incident listing form includes normal select controls in addition to
ASP.NET hidden state fields. Submitting only the hidden fields causes CHP to
return the listing again instead of selecting the requested incident. This
module installs a complete successful-controls postback and posts to the form's
actual action URL.
"""
from __future__ import annotations

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import chp_detail_alert as detail
import chp_jamul_alert as core
import mark_detail_runtime


EXCLUDED_INPUT_TYPES = {
    "button",
    "file",
    "image",
    "reset",
    "submit",
}


def successful_form_controls(html: str) -> tuple[str, dict[str, str]]:
    """Return the form action and browser-like successful form controls."""
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if form is None:
        raise ValueError("CHP response does not contain a form")

    payload: dict[str, str] = {}

    for field in form.find_all(["input", "select", "textarea"]):
        name = field.get("name")
        if not name or field.has_attr("disabled"):
            continue

        if field.name == "input":
            field_type = str(field.get("type", "text")).casefold()
            if field_type in EXCLUDED_INPUT_TYPES:
                continue
            if field_type in {"checkbox", "radio"} and not field.has_attr("checked"):
                continue
            payload[str(name)] = str(field.get("value", "on" if field_type in {"checkbox", "radio"} else ""))
            continue

        if field.name == "select":
            option = field.find("option", selected=True)
            if option is None:
                option = field.find("option")
            if option is not None:
                payload[str(name)] = str(option.get("value", option.get_text(" ", strip=True)))
            continue

        payload[str(name)] = field.get_text("", strip=False)

    action = str(form.get("action") or core.BASE_URL)
    return urljoin(core.BASE_URL, action), payload


def fetch_details(
    session: requests.Session,
    listing_html: str,
    argument: str,
    timeout: float,
    incident_number: str | None = None,
) -> tuple[str, ...]:
    """Select one GridView incident using the complete CHP form submission."""
    action_url, payload = successful_form_controls(listing_html)
    payload["__EVENTTARGET"] = "gvIncidents"
    payload["__EVENTARGUMENT"] = argument
    payload["__LASTFOCUS"] = ""

    # Preserve the listing's selected communications center and other dropdowns.
    payload.setdefault("ddlComCenter", "BCCC")
    payload.setdefault("ddlSearches", "Choose One")
    payload.setdefault("ddlResources", "Choose One")

    response = session.post(
        action_url,
        data=payload,
        timeout=timeout,
        headers={"Referer": core.BASE_URL},
    )
    response.raise_for_status()

    coordinates = mark_detail_runtime.extract_detail_coordinates(response.text)
    if not coordinates:
        visible = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
        listing_again = "Number of Incidents:" in visible and "Lat/Lon" not in visible
        detail.LOG.error(
            "Incident %s CHP postback returned %s; action=%s event=%s",
            incident_number or "unknown",
            "the incident listing again" if listing_again else "a response without Lat/Lon",
            action_url,
            argument,
        )

    return mark_detail_runtime.parse_detail_lines(response.text, incident_number)


def install() -> None:
    """Install the browser-faithful detail postback after detail runtime patches."""
    detail.fetch_details = fetch_details
