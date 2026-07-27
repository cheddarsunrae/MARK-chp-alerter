#!/usr/bin/env python3
"""Runtime filter helpers for profile and smoke-test modes."""
from __future__ import annotations

import chp_jamul_alert as core
import mark_detail_runtime

WILDCARDS = {"*", "all", "any"}


def _has_wildcard(values: tuple[str, ...]) -> bool:
    return any(value.strip().casefold() in WILDCARDS for value in values)


def area_matches(area: str) -> bool:
    prefixes = mark_detail_runtime.configured_area_prefixes()
    if _has_wildcard(prefixes):
        return True
    normalized = core.normalize_space(area).casefold()
    return any(
        normalized.startswith(prefix.casefold()[:2])
        for prefix in prefixes
        if prefix
    )


def _safe_type_fragments() -> tuple[str, ...]:
    """Return operational alert type fragments, never the old smoke-test wildcard.

    Earlier beta smoke-test configurations could persist CHP_ALERT_TYPE_FRAGMENTS=*,
    which makes every Type column alertable. AREA=* is still allowed for broad
    smoke testing, but Type=* is no longer treated as an alert trigger because it
    pages low-value categories such as Traffic Hazard.
    """
    fragments = mark_detail_runtime.configured_type_fragments()
    if _has_wildcard(fragments):
        return mark_detail_runtime.DEFAULT_TYPE_FRAGMENTS
    return fragments


def matched_type_fragments(incident_type: str) -> tuple[str, ...]:
    fragments = _safe_type_fragments()
    normalized = core.normalize_space(incident_type).casefold()
    return tuple(
        fragment
        for fragment in fragments
        if fragment and fragment.casefold() in normalized
    )


def type_matches(incident_type: str) -> bool:
    return bool(matched_type_fragments(incident_type))


def install() -> None:
    mark_detail_runtime.area_matches = area_matches
    mark_detail_runtime.type_matches = type_matches
    mark_detail_runtime.matched_type_fragments = matched_type_fragments
    core.is_alertable_incident_type = type_matches
