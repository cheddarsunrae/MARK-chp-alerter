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


def type_matches(incident_type: str) -> bool:
    fragments = mark_detail_runtime.configured_type_fragments()
    if _has_wildcard(fragments):
        return True
    normalized = core.normalize_space(incident_type).casefold()
    return any(fragment.casefold() in normalized for fragment in fragments)


def install() -> None:
    mark_detail_runtime.area_matches = area_matches
    mark_detail_runtime.type_matches = type_matches
    core.is_alertable_incident_type = type_matches
