import os
import tempfile
import unittest
from pathlib import Path

_TEST_ROOT = tempfile.TemporaryDirectory(prefix="dola-security-tests-")
os.environ.setdefault("DOLA_DB_PATH", str(Path(_TEST_ROOT.name) / "tasks.db"))
os.environ.setdefault("DOLA_POOL_DB_PATH", str(Path(_TEST_ROOT.name) / "pool_usage.db"))
os.environ.setdefault("DOLA_DOWNLOAD_DIR", str(Path(_TEST_ROOT.name) / "downloads"))

from fastapi import HTTPException

import auth_utils
import config
from server import (
    VideoGenRequest,
    admin_flow_live_stream,
    admin_jev_live_stream,
    create_video,
)


class SecurityRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_bogus_admin_header_does_not_bypass_api_key_auth(self):
        old_admin_key = config.ADMIN_KEY
        old_api_keys = config.API_KEYS
        config.ADMIN_KEY = ""
        config.API_KEYS = ["sk-real"]
        try:
            with self.assertRaises(HTTPException) as caught:
                await create_video(
                    VideoGenRequest(prompt="test", model="invalid-model"),
                    authorization=None,
                    x_admin_key="anything",
                )
            self.assertEqual(caught.exception.status_code, 401)
        finally:
            config.ADMIN_KEY = old_admin_key
            config.API_KEYS = old_api_keys

    async def test_admin_live_stream_rejects_missing_token_when_admin_key_enabled(self):
        old_admin_key = config.ADMIN_KEY
        config.ADMIN_KEY = "secret"
        try:
            with self.assertRaises(HTTPException) as caught:
                await admin_flow_live_stream(token=None)
            self.assertEqual(caught.exception.status_code, 401)
        finally:
            config.ADMIN_KEY = old_admin_key

    async def test_admin_live_stream_accepts_valid_short_lived_token(self):
        old_admin_key = config.ADMIN_KEY
        config.ADMIN_KEY = "secret"
        try:
            token = auth_utils.make_stream_token("secret", ttl=60)
            response = await admin_jev_live_stream(token=token)
            self.assertEqual(response.media_type, "text/event-stream")
        finally:
            config.ADMIN_KEY = old_admin_key

    def test_stream_token_rejects_tampering_and_expiry(self):
        now = 1_800_000_000
        token = auth_utils.make_stream_token("secret", ttl=60, now=now)
        self.assertTrue(auth_utils.is_stream_token_valid("secret", token, now=now + 30))
        self.assertFalse(auth_utils.is_stream_token_valid("secret", token + "x", now=now + 30))
        self.assertFalse(auth_utils.is_stream_token_valid("secret", token, now=now + 61))


if __name__ == "__main__":
    unittest.main()

