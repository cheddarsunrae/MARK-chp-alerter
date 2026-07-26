from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

import notification_runtime as notify


class NotificationPolicyTests(unittest.TestCase):
    def test_defaults_preserve_emergency_pushover_behavior(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            policy = notify.configured_policy()
        self.assertEqual(policy.severity, "critical")
        self.assertEqual(policy.delivery_mode, "until_acknowledged")
        self.assertEqual(notify._pushover_priority(policy), 2)

    def test_ntfy_priority_mapping(self) -> None:
        self.assertEqual(notify._ntfy_priority("low"), "2")
        self.assertEqual(notify._ntfy_priority("critical"), "5")

    def test_ntfy_sends_expected_headers(self) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        session = Mock()
        session.post.return_value = response
        policy = notify.NotificationPolicy("high", "notify_once", 30, 1800)
        with patch.dict(
            os.environ,
            {"NTFY_SERVER": "https://ntfy.example", "NTFY_TOPIC": "station-36"},
            clear=True,
        ):
            notify.send_ntfy(
                session,
                title="MARK test",
                message="Incident message",
                source_url="https://cad.example",
                timeout=20,
                policy=policy,
            )
        call = session.post.call_args
        self.assertEqual(call.args[0], "https://ntfy.example/station-36")
        self.assertEqual(call.kwargs["headers"]["Priority"], "4")
        self.assertEqual(call.kwargs["headers"]["Click"], "https://cad.example")

    def test_webhook_payload_contains_common_policy(self) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        session = Mock()
        session.post.return_value = response
        policy = notify.NotificationPolicy("medium", "notify_on_update", 60, 900)
        with patch.dict(os.environ, {"WEBHOOK_URL": "https://hooks.example/mark"}, clear=True):
            notify.send_webhook(
                session,
                title="MARK test",
                message="Incident message",
                source_url="https://cad.example",
                timeout=20,
                policy=policy,
            )
        payload = session.post.call_args.kwargs["json"]
        self.assertEqual(payload["severity"], "medium")
        self.assertEqual(payload["delivery_mode"], "notify_on_update")
        self.assertEqual(payload["retry_seconds"], 60)

    def test_legacy_pushover_credentials_enable_provider(self) -> None:
        with patch.dict(
            os.environ,
            {"PUSHOVER_APP_TOKEN": "token", "PUSHOVER_USER_KEY": "user"},
            clear=True,
        ):
            self.assertEqual(notify.configured_providers(), ("pushover",))


if __name__ == "__main__":
    unittest.main()
