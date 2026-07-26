#!/usr/bin/env python3
"""Provider-neutral MARK notification delivery.

This module preserves Pushover compatibility while adding ntfy, Gotify, and
JSON webhook adapters behind one common severity/delivery policy.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

import chp_jamul_alert as core

LOG = logging.getLogger("chp-alerter.notifications")

SEVERITIES = {"low", "medium", "high", "critical"}
DELIVERY_MODES = {
    "notify_once",
    "notify_on_update",
    "until_acknowledged",
    "until_expiration",
}


@dataclass(frozen=True)
class NotificationPolicy:
    severity: str
    delivery_mode: str
    retry_seconds: int
    expire_seconds: int


def _split_csv(value: str | None) -> tuple[str, ...]:
    return tuple(item.strip().casefold() for item in (value or "").split(",") if item.strip())


def configured_providers() -> tuple[str, ...]:
    configured = _split_csv(os.getenv("NOTIFY_PROVIDERS"))
    if configured:
        return configured
    if os.getenv("PUSHOVER_APP_TOKEN") and os.getenv("PUSHOVER_USER_KEY"):
        return ("pushover",)
    return ()


def configured_policy() -> NotificationPolicy:
    severity = os.getenv("ALERT_SEVERITY", "critical").strip().casefold()
    delivery_mode = os.getenv("ALERT_DELIVERY_MODE", "until_acknowledged").strip().casefold()
    if severity not in SEVERITIES:
        raise ValueError(f"ALERT_SEVERITY must be one of {', '.join(sorted(SEVERITIES))}")
    if delivery_mode not in DELIVERY_MODES:
        raise ValueError(
            "ALERT_DELIVERY_MODE must be one of " + ", ".join(sorted(DELIVERY_MODES))
        )
    retry_seconds = int(os.getenv("ALERT_RETRY_SECONDS", os.getenv("PUSHOVER_RETRY_SECONDS", "30")))
    expire_seconds = int(os.getenv("ALERT_EXPIRE_SECONDS", os.getenv("PUSHOVER_EXPIRE_SECONDS", "1800")))
    if retry_seconds < 30:
        raise ValueError("ALERT_RETRY_SECONDS must be at least 30")
    if not 1 <= expire_seconds <= 10800:
        raise ValueError("ALERT_EXPIRE_SECONDS must be between 1 and 10800")
    return NotificationPolicy(severity, delivery_mode, retry_seconds, expire_seconds)


def _pushover_priority(policy: NotificationPolicy) -> int:
    if policy.delivery_mode in {"until_acknowledged", "until_expiration"}:
        return 2
    return {"low": -1, "medium": 0, "high": 1, "critical": 1}[policy.severity]


def _ntfy_priority(severity: str) -> str:
    return {"low": "2", "medium": "3", "high": "4", "critical": "5"}[severity]


def _gotify_priority(severity: str) -> int:
    return {"low": 2, "medium": 5, "high": 8, "critical": 10}[severity]


def send_pushover(
    session: requests.Session,
    *,
    title: str,
    message: str,
    source_url: str,
    timeout: float,
    policy: NotificationPolicy,
) -> None:
    token = os.getenv("PUSHOVER_APP_TOKEN", "").strip()
    user = os.getenv("PUSHOVER_USER_KEY", "").strip()
    if not token or not user:
        raise ValueError("Pushover is enabled but PUSHOVER_APP_TOKEN/PUSHOVER_USER_KEY are incomplete")
    core.send_pushover(
        session,
        token=token,
        user=user,
        title=title,
        message=message,
        source_url=source_url,
        priority=_pushover_priority(policy),
        retry_seconds=policy.retry_seconds,
        expire_seconds=policy.expire_seconds,
        sound=os.getenv("PUSHOVER_SOUND", "alien").strip() or None,
        timeout=timeout,
    )


def send_ntfy(
    session: requests.Session,
    *,
    title: str,
    message: str,
    source_url: str,
    timeout: float,
    policy: NotificationPolicy,
) -> None:
    server = os.getenv("NTFY_SERVER", "https://ntfy.sh").strip().rstrip("/")
    topic = os.getenv("NTFY_TOPIC", "").strip()
    if not topic:
        raise ValueError("ntfy is enabled but NTFY_TOPIC is blank")
    headers = {
        "Title": title[:250],
        "Priority": _ntfy_priority(policy.severity),
        "Tags": "rotating_light,ambulance",
        "Click": source_url,
    }
    token = os.getenv("NTFY_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if policy.delivery_mode in {"until_acknowledged", "until_expiration"}:
        LOG.warning(
            "ntfy does not expose provider acknowledgement to MARK; sending once for delivery_mode=%s",
            policy.delivery_mode,
        )
    response = session.post(
        f"{server}/{quote(topic, safe='')}",
        data=message.encode("utf-8"),
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()


def send_gotify(
    session: requests.Session,
    *,
    title: str,
    message: str,
    source_url: str,
    timeout: float,
    policy: NotificationPolicy,
) -> None:
    base_url = os.getenv("GOTIFY_URL", "").strip().rstrip("/")
    token = os.getenv("GOTIFY_APP_TOKEN", "").strip()
    if not base_url or not token:
        raise ValueError("Gotify is enabled but GOTIFY_URL/GOTIFY_APP_TOKEN are incomplete")
    if policy.delivery_mode in {"until_acknowledged", "until_expiration"}:
        LOG.warning(
            "Gotify has no MARK acknowledgement integration yet; sending once for delivery_mode=%s",
            policy.delivery_mode,
        )
    response = session.post(
        f"{base_url}/message",
        params={"token": token},
        json={
            "title": title[:250],
            "message": f"{message}\n\n{source_url}",
            "priority": _gotify_priority(policy.severity),
        },
        timeout=timeout,
    )
    response.raise_for_status()


def send_webhook(
    session: requests.Session,
    *,
    title: str,
    message: str,
    source_url: str,
    timeout: float,
    policy: NotificationPolicy,
) -> None:
    url = os.getenv("WEBHOOK_URL", "").strip()
    if not url:
        raise ValueError("webhook is enabled but WEBHOOK_URL is blank")
    headers = {"Content-Type": "application/json"}
    token = os.getenv("WEBHOOK_BEARER_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = session.post(
        url,
        headers=headers,
        json={
            "source": "MARK",
            "title": title,
            "message": message,
            "source_url": source_url,
            "severity": policy.severity,
            "delivery_mode": policy.delivery_mode,
            "retry_seconds": policy.retry_seconds,
            "expire_seconds": policy.expire_seconds,
        },
        timeout=timeout,
    )
    response.raise_for_status()


SENDERS = {
    "pushover": send_pushover,
    "ntfy": send_ntfy,
    "gotify": send_gotify,
    "webhook": send_webhook,
}


def deliver(
    session: requests.Session,
    *,
    title: str,
    message: str,
    source_url: str,
    timeout: float,
) -> int:
    providers = configured_providers()
    if not providers:
        LOG.warning("No notification providers configured; alert printed only")
        return 0
    policy = configured_policy()
    sent = 0
    errors: list[str] = []
    for provider in providers:
        sender = SENDERS.get(provider)
        if sender is None:
            errors.append(f"unknown provider {provider}")
            continue
        try:
            sender(
                session,
                title=title,
                message=message,
                source_url=source_url,
                timeout=timeout,
                policy=policy,
            )
            sent += 1
            LOG.info(
                "%s notification sent (severity=%s delivery=%s)",
                provider,
                policy.severity,
                policy.delivery_mode,
            )
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            errors.append(f"{provider}: {exc}")
            LOG.error("%s notification failed: %s", provider, exc)
    if sent == 0 and errors:
        raise RuntimeError("All notification providers failed: " + "; ".join(errors))
    return sent


def emit_alert(
    session: requests.Session,
    incident: Any,
    match: Any,
    source_url: str,
    args: Any,
) -> None:
    title, message = core.build_alert_message(incident, match)
    print(f"\n=== {title} ===\n{message}\nSource: {source_url}\n", flush=True)
    if args.dry_run:
        LOG.info("Dry-run mode: notification delivery skipped")
        return
    deliver(
        session,
        title=title,
        message=message,
        source_url=source_url,
        timeout=args.timeout,
    )


def install() -> None:
    """Install provider-neutral delivery without changing incident selection."""
    core.emit_alert = emit_alert
