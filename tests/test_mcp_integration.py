"""Unit and integration tests for Model Context Protocol (MCP) in Dola."""
import json
import unittest

import config
import mcp_integration
import server


class McpIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Clear test keys and usage files
        if mcp_integration.KEYS_FILE.exists():
            mcp_integration.KEYS_FILE.unlink()
        if mcp_integration.USAGE_FILE.exists():
            mcp_integration.USAGE_FILE.unlink()
        mcp_integration.RATE_WINDOWS.clear()

    async def asyncTearDown(self):
        if mcp_integration.KEYS_FILE.exists():
            mcp_integration.KEYS_FILE.unlink()
        if mcp_integration.USAGE_FILE.exists():
            mcp_integration.USAGE_FILE.unlink()

    def test_public_config_manifest(self):
        conf = mcp_integration.public_config()
        self.assertTrue(conf["ok"])
        self.assertEqual(conf["product"]["slug"], "dola-render-gateway")
        self.assertEqual(conf["protocolVersion"], "2025-03-26")
        self.assertEqual(conf["auth"]["header"], "x-api-key")
        self.assertIn("claude", conf["setupSnippets"])
        self.assertIn("cursor", conf["setupSnippets"])

    def test_key_creation_and_auth(self):
        # 1. Create a key
        created = mcp_integration.create_key("Test Assistant")
        self.assertTrue(created["ok"])
        api_key = created["apiKey"]
        key_id = created["key"]["id"]

        self.assertTrue(api_key.startswith("dolamcp_"))
        self.assertEqual(created["key"]["status"], "active")

        # 2. List keys - full secret must NOT be in stored list
        keys = mcp_integration.list_keys()
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0]["id"], key_id)
        self.assertNotIn("apiKey", keys[0])
        self.assertTrue(keys[0]["prefix"].startswith("dolamcp_"))

        # 3. Authenticate with valid key
        headers = {"x-api-key": api_key}
        key_info, err = mcp_integration.authenticate_key(headers)
        self.assertIsNone(err)
        self.assertIsNotNone(key_info)
        self.assertEqual(key_info["id"], key_id)

        # 4. Authenticate with Bearer token
        headers_bearer = {"Authorization": f"Bearer {api_key}"}
        key_info_b, err_b = mcp_integration.authenticate_key(headers_bearer)
        self.assertIsNone(err_b)
        self.assertEqual(key_info_b["id"], key_id)

        # 5. Authenticate with invalid key
        _, err_invalid = mcp_integration.authenticate_key({"x-api-key": "invalid_key"})
        self.assertIsNotNone(err_invalid)

        # 6. Revoke key
        revoked = mcp_integration.revoke_key(key_id)
        self.assertTrue(revoked)

        # 7. Authenticate with revoked key fails
        _, err_revoked = mcp_integration.authenticate_key(headers)
        self.assertIsNotNone(err_revoked)

    async def test_json_rpc_initialize_and_notifications(self):
        # initialize doesn't require API key
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26"},
        }
        res = await mcp_integration.handle_mcp_request(payload, {}, server.store, server.pool)
        self.assertEqual(res["jsonrpc"], "2.0")
        self.assertEqual(res["id"], 1)
        self.assertEqual(res["result"]["protocolVersion"], "2025-03-26")
        self.assertEqual(res["result"]["serverInfo"]["name"], "dola-render-gateway")

        # notification ack
        ack_res = await mcp_integration.handle_mcp_request({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }, {}, server.store, server.pool)
        self.assertEqual(ack_res["jsonrpc"], "2.0")
        self.assertIsNone(ack_res["result"])

    async def test_tools_list_and_call(self):
        created = mcp_integration.create_key("Claude Bot")
        api_key = created["apiKey"]
        headers = {"x-api-key": api_key}

        # 1. tools/list
        list_res = await mcp_integration.handle_mcp_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
        }, headers, server.store, server.pool)
        self.assertEqual(list_res["jsonrpc"], "2.0")
        tools = list_res["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        self.assertIn("dola_create_video", tool_names)
        self.assertIn("dola_get_task_status", tool_names)
        self.assertIn("dola_list_tasks", tool_names)
        self.assertIn("dola_list_accounts", tool_names)

        # 2. tools/call dola_list_accounts
        call_acc = await mcp_integration.handle_mcp_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "dola_list_accounts",
                "arguments": {},
            },
        }, headers, server.store, server.pool)
        self.assertIn("result", call_acc)
        content = call_acc["result"]["content"][0]["text"]
        acc_data = json.loads(content)
        self.assertIn("accounts", acc_data)

        # 3. tools/call dola_create_video
        call_create = await mcp_integration.handle_mcp_request({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "dola_create_video",
                "arguments": {
                    "prompt": "Cyberpunk robot walking in neon rain",
                    "ratio": "16:9",
                    "duration": 10,
                },
            },
        }, headers, server.store, server.pool)
        self.assertIn("result", call_create)
        create_data = json.loads(call_create["result"]["content"][0]["text"])
        self.assertTrue(create_data["ok"])
        task_id = create_data["task_id"]

        # 4. tools/call dola_get_task_status
        call_status = await mcp_integration.handle_mcp_request({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "dola_get_task_status",
                "arguments": {"task_id": task_id},
            },
        }, headers, server.store, server.pool)
        self.assertIn("result", call_status)
        status_data = json.loads(call_status["result"]["content"][0]["text"])
        self.assertEqual(status_data["id"], task_id)
        self.assertEqual(status_data["status"], "queued")

    async def test_fastapi_admin_endpoints(self):
        saved_key = config.ADMIN_KEY
        config.ADMIN_KEY = "test_admin_secret"
        try:
            # 1. Config endpoint
            conf = await server.mcp_config_endpoint()
            self.assertTrue(conf["ok"])

            # 2. Key creation endpoint
            body = server.McpKeyCreateBody(name="Cursor Agent")
            create_res = await server.mcp_key_create(body, x_admin_key="test_admin_secret")
            self.assertTrue(create_res["ok"])
            key_id = create_res["key"]["id"]

            # 3. Keys list endpoint
            keys_res = await server.mcp_keys_list(x_admin_key="test_admin_secret")
            self.assertTrue(keys_res["ok"])
            self.assertEqual(len(keys_res["keys"]), 1)

            # 4. Usage endpoint
            usage_res = await server.mcp_usage_endpoint(period="today", x_admin_key="test_admin_secret")
            self.assertTrue(usage_res["ok"])
            self.assertIn("metrics", usage_res)

            # 5. Revoke endpoint
            del_res = await server.mcp_key_revoke(key_id, x_admin_key="test_admin_secret")
            self.assertTrue(del_res["ok"])

            # 6. Gateway info endpoint
            info = await server.mcp_info()
            self.assertTrue(info["ok"])
            self.assertEqual(info["transport"], "streamable-http")
        finally:
            config.ADMIN_KEY = saved_key

    async def test_usage_metrics_and_quota_dashboard(self):
        created = mcp_integration.create_key("Metrics Bot")
        api_key = created["apiKey"]
        headers = {"x-api-key": api_key}

        # 1. Create a video
        create_res = await mcp_integration.handle_mcp_request({
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "dola_create_video",
                "arguments": {"prompt": "Sunset over mountain lake"},
            },
        }, headers, server.store, server.pool)
        self.assertIn("result", create_res)
        task_id = json.loads(create_res["result"]["content"][0]["text"])["task_id"]

        # 2. Call download tool
        server.store.update(task_id, status="completed", video_url="http://127.0.0.1:8000/videos/sunset.mp4")
        dl_res = await mcp_integration.handle_mcp_request({
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "dola_download_video",
                "arguments": {"task_id": task_id},
            },
        }, headers, server.store, server.pool)
        self.assertIn("result", dl_res)

        # 3. Simulate a failure
        fail_res = await mcp_integration.handle_mcp_request({
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "dola_create_video",
                "arguments": {"prompt": ""},  # empty prompt -> error
            },
        }, headers, server.store, server.pool)
        self.assertIn("error", fail_res)

        # 4. Check usage metrics
        usage = mcp_integration.get_usage(period="today")
        self.assertTrue(usage["ok"])
        metrics = usage["metrics"]

        # User-specified metrics:
        self.assertEqual(metrics["video_create_requested"], 2)  # 1 success + 1 failed attempt
        self.assertEqual(metrics["video_create_success"], 1)
        self.assertEqual(metrics["video_create_failed"], 1)
        self.assertEqual(metrics["video_download_success"], 1)
        self.assertEqual(metrics["daily_limit"], 100)
        self.assertEqual(metrics["daily_used"], 1)
        self.assertEqual(metrics["daily_remaining"], 99)

        # Check key breakdown
        self.assertIn("keyUsage", usage)
        self.assertEqual(len(usage["keyUsage"]), 1)
        k_stat = usage["keyUsage"][0]
        self.assertEqual(k_stat["create_requested"], 2)
        self.assertEqual(k_stat["create_success"], 1)
        self.assertEqual(k_stat["create_failed"], 1)
        self.assertEqual(k_stat["download_success"], 1)


if __name__ == "__main__":
    unittest.main()
