import os
import socket
import tempfile
import threading
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

_TEST_ROOT = tempfile.TemporaryDirectory(prefix="dola-security-tests-")
os.environ.setdefault("DOLA_DB_PATH", str(Path(_TEST_ROOT.name) / "tasks.db"))
os.environ.setdefault("DOLA_POOL_DB_PATH", str(Path(_TEST_ROOT.name) / "pool_usage.db"))
os.environ.setdefault("DOLA_DOWNLOAD_DIR", str(Path(_TEST_ROOT.name) / "downloads"))

from fastapi import HTTPException
from pydantic import ValidationError

import auth_utils
import browser
import browser_pool
import config
import media
import store as store_module
import server as pool_module
from account_locks import account_execution
from chrome_profile_scanner import import_chrome_profile
from server import (
    VIDEO_NAME_RE,
    VideoGenRequest,
    _auth,
    _admin_auth,
    _require_pool_account,
    _signed_video_url,
    admin_flow_live_stream,
    admin_jev_live_stream,
    create_video,
    download_video,
    security_config_error,
    store,
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

    # ----- Finding 1: fail-open authentication -----

    async def test_missing_keys_and_non_loopback_bind_refuse_to_start(self):
        old = (config.HOST, config.ADMIN_KEY, config.API_KEYS, config.ALLOW_UNAUTHENTICATED)
        config.HOST, config.ADMIN_KEY, config.API_KEYS = "0.0.0.0", "", []
        config.ALLOW_UNAUTHENTICATED = False
        try:
            error = security_config_error()
        finally:
            config.HOST, config.ADMIN_KEY, config.API_KEYS, config.ALLOW_UNAUTHENTICATED = old
        self.assertIsNotNone(error)
        self.assertIn("DOLA_ADMIN_KEY", error)
        self.assertIn("DOLA_API_KEYS", error)

    async def test_loopback_without_explicit_opt_in_still_fails_closed(self):
        old = (config.HOST, config.ADMIN_KEY, config.API_KEYS, config.ALLOW_UNAUTHENTICATED)
        config.HOST, config.ADMIN_KEY, config.API_KEYS = "127.0.0.1", "", []
        config.ALLOW_UNAUTHENTICATED = False
        try:
            self.assertIsNotNone(security_config_error())
        finally:
            config.HOST, config.ADMIN_KEY, config.API_KEYS, config.ALLOW_UNAUTHENTICATED = old

    async def test_explicit_loopback_opt_in_enables_local_dev_mode(self):
        old = (config.HOST, config.ADMIN_KEY, config.API_KEYS, config.ALLOW_UNAUTHENTICATED)
        config.HOST, config.ADMIN_KEY, config.API_KEYS = "127.0.0.1", "", []
        config.ALLOW_UNAUTHENTICATED = True
        try:
            self.assertIsNone(security_config_error())
            self.assertIsNone(_admin_auth(None))
            self.assertEqual(_auth(None)["api_key_name"], "Anonymous")
        finally:
            config.HOST, config.ADMIN_KEY, config.API_KEYS, config.ALLOW_UNAUTHENTICATED = old

    async def test_dev_mode_flag_alone_cannot_unlock_a_remote_host(self):
        old = (config.HOST, config.ADMIN_KEY, config.API_KEYS, config.ALLOW_UNAUTHENTICATED)
        config.HOST, config.ADMIN_KEY, config.API_KEYS = "0.0.0.0", "", []
        config.ALLOW_UNAUTHENTICATED = True
        try:
            self.assertIsNotNone(security_config_error())
            with self.assertRaises(HTTPException) as caught:
                _admin_auth(None)
            self.assertEqual(caught.exception.status_code, 503)
        finally:
            config.HOST, config.ADMIN_KEY, config.API_KEYS, config.ALLOW_UNAUTHENTICATED = old

    async def test_non_loopback_without_keys_fails_closed(self):
        old = (config.HOST, config.ADMIN_KEY, config.API_KEYS, config.ALLOW_UNAUTHENTICATED)
        config.HOST, config.ADMIN_KEY, config.API_KEYS = "0.0.0.0", "", []
        config.ALLOW_UNAUTHENTICATED = False
        try:
            with self.assertRaises(HTTPException) as admin:
                _admin_auth(None)
            self.assertEqual(admin.exception.status_code, 503)
            with self.assertRaises(HTTPException) as client:
                await _auth(None)
            self.assertEqual(client.exception.status_code, 503)
        finally:
            config.HOST, config.ADMIN_KEY, config.API_KEYS, config.ALLOW_UNAUTHENTICATED = old

    # ----- Finding 2: media authorization and predictable names -----

    async def _seed_video_task(self, filename: str, api_key_hash: str | None) -> None:
        download_dir = Path(config.DOWNLOAD_DIR)
        download_dir.mkdir(parents=True, exist_ok=True)
        (download_dir / filename).write_bytes(b"\x00\x00\x00")
        task_id = "video_" + uuid.uuid4().hex
        store.create(
            task_id,
            "seedance-2.0",
            "prompt",
            "16:9",
            10,
            api_key_hash=api_key_hash,
            api_key_name="test",
        )
        store.update(task_id, status="completed", video_url=f"/videos/{filename}")

    async def _seed_legacy_jevvideo_task(self, filename: str) -> None:
        """Legacy Jev rows persisted a signed URL including ?token=..."""
        download_dir = Path(config.DOWNLOAD_DIR)
        download_dir.mkdir(parents=True, exist_ok=True)
        (download_dir / filename).write_bytes(b"\x00\x00\x00")
        task_id = "video_" + uuid.uuid4().hex
        store.create(task_id, "seedance-2.0", "prompt", "16:9", 10, api_key_hash=None)
        store.update(
            task_id,
            status="completed",
            video_url=f"/videos/{filename}?token=12345.deadbeef",
        )

    async def test_video_lookup_ignores_query_token_in_stored_url(self):
        old_admin = config.ADMIN_KEY
        config.ADMIN_KEY = "admin-secret"
        filename = "acc_20250101_000000_beefbeefbeefbeef.mp4"
        try:
            await self._seed_legacy_jevvideo_task(filename)
            signed = _signed_video_url(f"/videos/{filename}")
            token = signed.split("token=", 1)[1]
            response = await download_video(filename, token=token, authorization=None, x_admin_key=None)
            self.assertEqual(Path(response.path).name, filename)
        finally:
            config.ADMIN_KEY = old_admin
            (Path(config.DOWNLOAD_DIR) / filename).unlink(missing_ok=True)

    async def test_video_download_requires_ownership(self):
        old_admin, old_keys = config.ADMIN_KEY, config.API_KEYS
        config.ADMIN_KEY, config.API_KEYS = "admin-secret", ["sk-owner"]
        filename = "acc_20250101_000000_deadbeefdeadbeef.mp4"
        try:
            owner_hash = store_module.TaskStore.hash_api_key("sk-owner")
            await self._seed_video_task(filename, owner_hash)

            with self.assertRaises(HTTPException) as caught:
                await download_video(filename, token=None, authorization="Bearer sk-intruder", x_admin_key=None)
            self.assertEqual(caught.exception.status_code, 401)

            response = await download_video(
                filename, token=None, authorization="Bearer sk-owner", x_admin_key=None
            )
            self.assertEqual(Path(response.path).name, filename)

            with self.assertRaises(HTTPException) as anonymous:
                await download_video(filename, token=None, authorization=None, x_admin_key=None)
            self.assertEqual(anonymous.exception.status_code, 401)
        finally:
            config.ADMIN_KEY, config.API_KEYS = old_admin, old_keys
            (Path(config.DOWNLOAD_DIR) / filename).unlink(missing_ok=True)

    async def test_video_download_accepts_signed_link_and_rejects_tampering(self):
        old_admin, old_keys = config.ADMIN_KEY, config.API_KEYS
        config.ADMIN_KEY, config.API_KEYS = "admin-secret", ["sk-somebody"]
        filename = "acc_20250101_000000_feedfacefeedface.mp4"
        try:
            await self._seed_video_task(filename, None)
            signed = _signed_video_url(f"/videos/{filename}")
            self.assertIn("token=", signed)
            token = signed.split("token=", 1)[1]

            response = await download_video(filename, token=token, authorization=None, x_admin_key=None)
            self.assertEqual(Path(response.path).name, filename)

            with self.assertRaises(HTTPException) as tampered:
                await download_video(
                    filename, token=token + "0", authorization=None, x_admin_key=None
                )
            self.assertEqual(tampered.exception.status_code, 401)
        finally:
            config.ADMIN_KEY, config.API_KEYS = old_admin, old_keys
            (Path(config.DOWNLOAD_DIR) / filename).unlink(missing_ok=True)

    def test_video_name_regex_blocks_path_traversal(self):
        self.assertFalse(VIDEO_NAME_RE.match("../tasks.db"))
        self.assertFalse(VIDEO_NAME_RE.match(".hidden"))
        self.assertFalse(VIDEO_NAME_RE.match("a/b.mp4"))
        self.assertTrue(VIDEO_NAME_RE.match("acc_20250101_000000_abcdef0123456789.mp4"))

    # ----- Finding 3: resource limits -----

    def test_prompt_and_reference_count_are_bounded(self):
        with self.assertRaises(ValidationError):
            VideoGenRequest(prompt="x" * (config.PROMPT_MAX_LENGTH + 1))
        too_many = ["https://example.com/a.png"] * (config.REFERENCE_IMAGE_MAX_COUNT + 1)
        with self.assertRaises(ValidationError):
            VideoGenRequest(prompt="ok", reference_images=too_many)

    # ----- Finding 4: Chrome profile import traversal -----

    def test_chrome_profile_import_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            chrome_root = base / "chrome"
            (chrome_root / "Default").mkdir(parents=True)
            outside = base / "outside_secret"
            outside.mkdir()
            (outside / "Cookies").write_text("secret", encoding="utf-8")
            accounts = base / "accounts"

            with self.assertRaises(ValueError):
                import_chrome_profile(
                    directory="../outside_secret",
                    chrome_root=chrome_root,
                    accounts_dir=accounts,
                    db_path=str(base / "pool.db"),
                )
            self.assertFalse((accounts / "outside_secret").exists())

            with self.assertRaises(ValueError):
                import_chrome_profile(
                    directory="Default",
                    target_name="..",
                    chrome_root=chrome_root,
                    accounts_dir=accounts,
                    db_path=str(base / "pool.db"),
                )

    def test_chrome_profile_import_accepts_contained_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            chrome_root = base / "chrome"
            (chrome_root / "Default").mkdir(parents=True)
            (chrome_root / "Default" / "Preferences").write_text("{}", encoding="utf-8")
            accounts = base / "accounts"

            result = import_chrome_profile(
                directory="Default",
                target_name="acc_ok",
                chrome_root=chrome_root,
                accounts_dir=accounts,
                db_path=str(base / "pool.db"),
            )
            self.assertEqual(result["name"], "acc_ok")
            self.assertTrue((accounts / "acc_ok" / "Default" / "Preferences").exists())

    # ----- Finding 7: account validation and DNS pinning -----

    async def test_account_selection_rejects_path_like_names(self):
        for candidate in ("../etc", "..", "unknown-account-name"):
            with self.assertRaises(HTTPException) as caught:
                _require_pool_account(candidate)
            self.assertIn(caught.exception.status_code, (404, 400))

    async def test_sanitized_account_name_with_dots_stays_selectable(self):
        from chrome_profile_scanner import sanitize_account_name

        name = sanitize_account_name("foo..bar", set())
        with tempfile.TemporaryDirectory() as tmp:
            accounts = Path(tmp) / "accounts"
            (accounts / name / "Default").mkdir(parents=True)
            old_dir = pool_module.pool.accounts_dir
            pool_module.pool.accounts_dir = accounts
            try:
                self.assertEqual(_require_pool_account(name), name)
            finally:
                pool_module.pool.accounts_dir = old_dir

    async def test_account_verify_uses_shared_lock_and_reports_busy(self):
        with tempfile.TemporaryDirectory() as tmp:
            accounts = Path(tmp) / "accounts"
            (accounts / "acc_lock_test" / "Default").mkdir(parents=True)
            pool = browser_pool.BrowserPool(
                accounts_dir=str(accounts), db_path=str(Path(tmp) / "pool.db"), max_concurrency=1
            )
            old_timeout = browser_pool.LOCK_WAIT_TIMEOUT
            browser_pool.LOCK_WAIT_TIMEOUT = 0.2
            try:
                with patch.object(browser, "check_login_state", AsyncMock(return_value=True)):
                    async with account_execution("acc_lock_test"):
                        with self.assertRaises(RuntimeError):
                            await pool.verify_account("acc_lock_test")
                    self.assertTrue(await pool.verify_account("acc_lock_test"))
                with self.assertRaises(FileNotFoundError):
                    await pool.verify_account("../escape")
            finally:
                browser_pool.LOCK_WAIT_TIMEOUT = old_timeout

    async def test_ssrf_validation_blocks_private_hosts_and_pins_public_dns(self):
        with self.assertRaises(ValueError):
            await media.resolve_public_host("127.0.0.1")
        with self.assertRaises(ValueError):
            await media.resolve_public_host("10.0.0.5")
        # CGNAT / Tailscale / cloud metadata range: not private, not reserved, but not global.
        with self.assertRaises(ValueError):
            await media.resolve_public_host("100.100.100.200")
        with self.assertRaises(ValueError):
            await media.resolve_public_host("100.64.0.1")

        with patch.object(media, "awaitable_getaddrinfo", return_value=["93.184.216.34"]):
            url, host, addresses = await media._validate_and_resolve("https://rebind.example/img.png")
        self.assertEqual(host, "rebind.example")
        self.assertEqual(addresses, ["93.184.216.34"])

        resolver = media._PinnedResolver(host, addresses)
        pinned = await resolver.resolve(host, port=443)
        self.assertEqual([entry["host"] for entry in pinned], ["93.184.216.34"])
        with self.assertRaises(OSError):
            await resolver.resolve("other.example", port=443)

    async def test_ssrf_validation_rejects_rebinding_to_private_address(self):
        with patch.object(media, "awaitable_getaddrinfo", return_value=["127.0.0.1"]):
            with self.assertRaises(ValueError):
                await media._validate_and_resolve("https://rebind.example/img.png")

    async def test_reference_download_connects_to_pinned_address_without_reresolving(self):
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", (2, 2), "red").save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - http.server API
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(image_bytes)))
                self.end_headers()
                self.wfile.write(image_bytes)

            def log_message(self, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        old_proxy = config.PROXY
        config.PROXY = ""
        try:
            port = server.server_address[1]
            url = f"http://pinned.example:{port}/i.png"
            with patch.object(media, "resolve_public_host", AsyncMock(return_value=["127.0.0.1"])), \
                    patch.object(socket, "getaddrinfo", side_effect=AssertionError("re-resolved DNS")):
                root, paths = await media.download_reference_images([url], "pinned-test")
            self.assertEqual(len(paths), 1)
            self.assertEqual(Path(paths[0]).read_bytes(), image_bytes)
            self.assertIn(str(root), media._reserved_by_root)
            budget = media._byte_budget()
            self.assertGreater(budget._used, 0)

            await media.cleanup_reference_images(root)
            self.assertNotIn(str(root), media._reserved_by_root)
            self.assertEqual(budget._used, 0)
            self.assertFalse(root.exists())
        finally:
            config.PROXY = old_proxy
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
