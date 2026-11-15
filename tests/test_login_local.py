import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from login_local import LoginManager


class LoginTests(unittest.TestCase):
    def exercise(self, valid=True, cancelled=False):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "private").mkdir()
            cookie = root / "private/yuanbao-cookie"
            cookie.write_text("old-test-session")
            def parse(*args):
                if not valid:
                    raise ValueError("invalid test session")
                return {}
            api = types.SimpleNamespace(parse_share_url=parse, split_playable_url=lambda p: ("test-id", "test-token"), get_feed_info=lambda *a: {}, normalize_response=lambda *a: {"data": {"url": "https://test.qq.com/video"}})
            def spawn(args, **kwargs):
                if not cancelled:
                    pathlib.Path(args[2]).write_text("new-test-session")
                return types.SimpleNamespace(wait=lambda **k: 0)
            manager = LoginManager(root, api)
            with patch("login_local.subprocess.Popen", side_effect=spawn):
                manager.worker()
            self.assertEqual(cookie.read_text(), "new-test-session" if valid and not cancelled else "old-test-session")
            self.assertEqual(list((root / "private").glob("login-candidate-*")), [])
            return manager.status()["status"], cookie.stat().st_mode & 0o777

    def test_success_replaces_only_validated_cookie(self):
        status, mode = self.exercise()
        self.assertEqual(status, "success")
        self.assertEqual(mode, 0o600)

    def test_failure_preserves_previous_cookie(self):
        self.assertEqual(self.exercise(valid=False)[0], "error")

    def test_cancel_preserves_previous_cookie(self):
        self.assertEqual(self.exercise(cancelled=True)[0], "cancelled")


if __name__ == "__main__":
    unittest.main()
