from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import update_runtime


class UpdateRuntimeTests(unittest.TestCase):
    def test_zip_install_reports_manual_update_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch("update_runtime.shutil.which", return_value="git"):
                status = update_runtime.check_for_update(root)
        self.assertFalse(status.supported)
        self.assertFalse(status.update_available)
        self.assertIn("ZIP", status.message)

    def test_reports_remote_commits_as_update_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            responses = iter(
                [
                    "1111111111111111111111111111111111111111",  # HEAD
                    "main",  # branch
                    "",  # clean status
                    "",  # fetch
                    "2222222222222222222222222222222222222222",  # origin/main
                    "0\t3",  # ahead, behind
                ]
            )
            with patch("update_runtime.shutil.which", return_value="git"), patch(
                "update_runtime._run", side_effect=lambda *args, **kwargs: next(responses)
            ):
                status = update_runtime.check_for_update(root)
        self.assertTrue(status.supported)
        self.assertTrue(status.update_available)
        self.assertEqual(status.behind_count, 3)
        self.assertEqual(status.ahead_count, 0)
        self.assertFalse(status.dirty)

    def test_installer_refuses_dirty_checkout_before_pull(self) -> None:
        status = update_runtime.UpdateStatus(
            supported=True,
            update_available=True,
            current_commit="1" * 40,
            remote_commit="2" * 40,
            branch="main",
            behind_count=1,
            dirty=True,
            message="update available",
        )
        with patch("update_runtime.check_for_update", return_value=status), patch(
            "update_runtime._run"
        ) as run:
            with self.assertRaises(update_runtime.UpdateError):
                update_runtime.install_update(Path.cwd())
        run.assert_not_called()

    def test_installer_refuses_ahead_checkout(self) -> None:
        status = update_runtime.UpdateStatus(
            supported=True,
            update_available=False,
            current_commit="2" * 40,
            remote_commit="1" * 40,
            branch="main",
            ahead_count=2,
            message="ahead",
        )
        with patch("update_runtime.check_for_update", return_value=status):
            with self.assertRaises(update_runtime.UpdateError):
                update_runtime.install_update(Path.cwd())


if __name__ == "__main__":
    unittest.main()
