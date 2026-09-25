"""Model Context Protocol (MCP) Integration Module for Dola Render Gateway.

Follows the standards defined in refer/MCP_INTEGRATION_TEMPLATE.md:
- Managed API key provisioning (CSPRNG 256-bit, SHA-256 hash storage, one-time secret display)
- Streamable HTTP JSON-RPC 2.0 gateway (/mcp)
- Interactive client setup snippets (Claude, Cursor, ChatGPT, VS Code, Codex)
- Quota enforcement, rate limiting, and telemetry logging
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import config


DATA_DIR = Path(getattr(config, "DOWNLOAD_DIR", "downloads")).parent / "data"
KEYS_FILE = DATA_DIR / "mcp_keys.json"
USAGE_FILE = DATA_DIR / "mcp_usage.json"
LOCK = threading.RLock()
RATE_WINDOWS: dict[str, list[float]] = {}


def _ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today_str() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def _public_base_url() -> str:
    if getattr(config, "PUBLIC_BASE", None):
        return str(config.PUBLIC_BASE).rstrip("/")
    host = getattr(config, "HOST", "127.0.0.1")
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    port = getattr(config, "PORT", 8000)
    return f"http://{host}:{port}"


def get_manifest() -> dict:
    base = _public_base_url()
    return {
        "schema_version": 1,
        "product": {
            "name": "Dola Render Gateway",
            "slug": "dola-render-gateway",
            "description": "High-performance video generation pipeline and MCP AI Assistant Gateway.",
        },
        "endpoints": {
            "app_base_url": base,
            "auth_base_url": base,
            "api_base_url": base,
            "mcp_base_url": base,
            "mcp_path": "/mcp",
            "media_base_url": base,
            "docs_base_url": f"{base}/docs",
            "health_url": f"{base}/api/admin/settings",
        },
        "mcp": {
            "transport": "streamable-http",
            "protocol_version": "2025-03-26",
            "server_id": "dola-render-gateway",
            "auth": {
                "type": "header",
                "header": "x-api-key",
                "bearer_supported": True,
                "key_prefix": "dolamcp_",
            },
            "rate_limit_per_minute": 60,
        },
        "permissions": {
            "manage_key": "mcp-key:manage",
            "view_usage": "mcp-usage:read",
            "call_tools": "mcp-tools:call",
        },
        "features": [
            {
                "id": "video_generation",
                "label": "Video Generation",
                "description": "Generate videos using Dola pool accounts with customizable prompt, ratio, and duration.",
                "result_delivery": "signed_url",
                "tools": [
                    {
                        "name": "dola_create_video",
                        "operation": "create",
                        "description": "Tạo tác vụ render video AI mới vào hàng đợi Dola.",
                        "input_schema_ref": "#/schemas/dola_create_video_input",
                    },
                    {
                        "name": "dola_get_task_status",
                        "operation": "read",
                        "description": "Tra cứu trạng thái tiến độ và URL video MP4 theo task_id.",
                        "input_schema_ref": "#/schemas/dola_get_task_status_input",
                    },
                    {
                        "name": "dola_list_tasks",
                        "operation": "read",
                        "description": "Lấy danh sách các tác vụ render video gần đây.",
                        "input_schema_ref": "#/schemas/dola_list_tasks_input",
                    },
                    {
                        "name": "dola_list_accounts",
                        "operation": "read",
                        "description": "Xem danh sách tài khoản Google/Dola trong pool và trạng thái hoạt động.",
                        "input_schema_ref": "#/schemas/dola_list_accounts_input",
                    },
                    {
                        "name": "dola_download_video",
                        "operation": "download",
                        "description": "Lấy thông tin và liên kết tải video MP4 đã render hoàn tất.",
                        "input_schema_ref": "#/schemas/dola_download_video_input",
                    },
                ],
                "usage_events": {
                    "requested": "video_create_requested",
                    "success": "video_create_success",
                    "failed": "video_create_failed",
                    "downloaded": "video_download_success",
                },
                "quota_metric": "video_create_success",
            }
        ],
        "usage": {
            "enabled": True,
            "timezone": "Asia/Ho_Chi_Minh",
            "retention_days": 90,
            "dashboard_metrics": [
                {"metric": "tool_call_total", "label": "Tổng lượt gọi Tool"},
                {"metric": "video_create_requested", "label": "Số lần tạo"},
                {"metric": "video_download_success", "label": "Số lần tải về"},
                {"metric": "video_create_success", "label": "Tạo thành công"},
                {"metric": "video_create_failed", "label": "Tạo thất bại"},
                {"metric": "daily_limit", "label": "Giới hạn tối đa / 1 ngày"},
            ],
        },
        "quota": {
            "policies": [
                {
                    "id": "daily_video_generations",
                    "metric": "video_create_success",
                    "scope": "workspace",
                    "period": "day",
                    "limit": 100,
                    "consume_on": "success",
                    "timezone": "Asia/Ho_Chi_Minh",
                }
            ]
        },
        "schemas": {
            "dola_create_video_input": {
                "type": "object",
                "required": ["prompt"],
                "properties": {
                    "prompt": {"type": "string", "description": "Nội dung prompt tạo video."},
                    "ratio": {
                        "type": "string",
                        "enum": ["16:9", "9:16", "1:1", "4:3", "3:4"],
                        "default": "16:9",
                        "description": "Tỉ lệ khung hình (mặc định: 16:9).",
                    },
                    "duration": {
                        "type": "integer",
                        "enum": [10, 15, 30],
                        "default": 10,
                        "description": "Độ dài video tính bằng giây (10, 15, hoặc 30).",
                    },
                    "model": {
                        "type": "string",
                        "default": "seedance-2.0",
                        "description": "Tên model tạo video (mặc định: seedance-2.0).",
                    },
                    "reference_images": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Danh sách URL ảnh mẫu hỗ trợ tạo video.",
                    },
                },
                "additionalProperties": False,
            },
            "dola_get_task_status_input": {
                "type": "object",
                "required": ["task_id"],
                "properties": {
                    "task_id": {"type": "string", "description": "Mã định danh tác vụ video."},
                },
                "additionalProperties": False,
            },
            "dola_list_tasks_input": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10, "description": "Số tác vụ tối đa trả về."},
                },
                "additionalProperties": False,
            },
            "dola_list_accounts_input": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "dola_download_video_input": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Mã định danh tác vụ cần tải video."},
                    "filename": {"type": "string", "description": "Tên file video cần tải (nếu có)."},
                },
                "additionalProperties": False,
            },
        },
    }


def public_config() -> dict:
    mani = get_manifest()
    endpoint = f"{mani['endpoints']['mcp_base_url']}{mani['endpoints']['mcp_path']}"
    slug = mani["product"]["slug"]
    header = mani["mcp"]["auth"]["header"]
    return {
        "ok": True,
        "product": mani["product"],
        "endpoint": endpoint,
        "transport": mani["mcp"]["transport"],
        "protocolVersion": mani["mcp"]["protocol_version"],
        "auth": mani["mcp"]["auth"],
        "features": mani["features"],
        "usage": mani["usage"],
        "quota": mani["quota"],
        "schemas": mani["schemas"],
        "setupSnippets": {
            "claude": {
                "mcpServers": {
                    slug: {
                        "url": endpoint,
                        "headers": {header: "YOUR_MCP_API_KEY"},
                    }
                }
            },
            "cursor": {
                "mcpServers": {
                    slug: {
                        "url": endpoint,
                        "headers": {header: "YOUR_MCP_API_KEY"},
                    }
                }
            },
            "vscode": {
                "servers": {
                    slug: {
                        "type": "http",
                        "url": endpoint,
                        "headers": {header: "YOUR_MCP_API_KEY"},
                    }
                }
            },
            "chatgpt": f"Server URL: {endpoint}\nTransport: Streamable HTTP\nAuthentication: Custom header\n{header}: YOUR_MCP_API_KEY",
            "codex": f"export DOLA_MCP_API_KEY=\"YOUR_MCP_API_KEY\"\ncodex mcp add {slug} --url {endpoint} --bearer-token-env-var DOLA_MCP_API_KEY",
        },
    }


def _read_json(path: Path, default):
    _ensure_dirs()
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload):
    _ensure_dirs()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _key_hash(key_str: str) -> str:
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()


def _key_preview(key_str: str) -> str:
    val = str(key_str)
    if len(val) > 22:
        return f"{val[:12]}…{val[-6:]}"
    return val


def list_keys() -> list[dict]:
    with LOCK:
        data = _read_json(KEYS_FILE, [])
        keys = data if isinstance(data, list) else []
        safe = []
        for k in keys:
            safe.append({
                "id": k.get("id"),
                "name": k.get("name"),
                "prefix": k.get("prefix"),
                "status": k.get("status", "active"),
                "createdAt": k.get("createdAt"),
                "lastUsedAt": k.get("lastUsedAt", ""),
                "revokedAt": k.get("revokedAt", ""),
            })
        return safe


def create_key(name: str) -> dict:
    clean_name = (name or "").strip()[:64] or "MCP Assistant"
    prefix = get_manifest()["mcp"]["auth"]["key_prefix"]
    # CSPRNG 256-bit token
    raw_secret = secrets.token_urlsafe(32)
    api_key = f"{prefix}{raw_secret}"
    key_id = str(uuid.uuid4())
    now = _now_iso()

    record = {
        "id": key_id,
        "name": clean_name,
        "prefix": _key_preview(api_key),
        "key_hash": _key_hash(api_key),
        "status": "active",
        "createdAt": now,
        "lastUsedAt": "",
        "revokedAt": "",
    }

    with LOCK:
        keys = _read_json(KEYS_FILE, [])
        if not isinstance(keys, list):
            keys = []
        keys.insert(0, record)
        _write_json(KEYS_FILE, keys)

    # Secret is returned only once
    return {
        "ok": True,
        "apiKey": api_key,
        "key": {
            "id": record["id"],
            "name": record["name"],
            "prefix": record["prefix"],
            "status": record["status"],
            "createdAt": record["createdAt"],
        },
    }


def revoke_key(key_id: str) -> bool:
    with LOCK:
        keys = _read_json(KEYS_FILE, [])
        if not isinstance(keys, list):
            return False
        found = False
        for k in keys:
            if k.get("id") == key_id:
                k["status"] = "revoked"
                k["revokedAt"] = _now_iso()
                found = True
                break
        if found:
            _write_json(KEYS_FILE, keys)
        return found


def authenticate_key(headers: dict) -> tuple[dict | None, str | None]:
    """Authenticates against x-api-key or Authorization Bearer."""
    auth_header_name = get_manifest()["mcp"]["auth"]["header"].lower()
    provided_key = ""

    for h_name, h_val in headers.items():
        if h_name.lower() == auth_header_name:
            provided_key = str(h_val).strip()
            break

    if not provided_key:
        auth_val = headers.get("authorization") or headers.get("Authorization") or ""
        if auth_val.lower().startswith("bearer "):
            provided_key = auth_val.split(" ", 1)[1].strip()

    if not provided_key:
        return None, "Missing x-api-key or Authorization Bearer header."

    khash = _key_hash(provided_key)
    with LOCK:
        keys = _read_json(KEYS_FILE, [])
        if isinstance(keys, list):
            for k in keys:
                if k.get("status") == "active" and hmac.compare_digest(k.get("key_hash", ""), khash):
                    k["lastUsedAt"] = _now_iso()
                    _write_json(KEYS_FILE, keys)
                    return k, None

    return None, "Invalid or revoked MCP API key."


def check_rate_limit(key_id: str) -> bool:
    limit = get_manifest()["mcp"]["rate_limit_per_minute"]
    now = time.time()
    with LOCK:
        window = [t for t in RATE_WINDOWS.get(key_id, []) if now - t < 60]
        if len(window) >= limit:
            RATE_WINDOWS[key_id] = window
            return False
        window.append(now)
        RATE_WINDOWS[key_id] = window
        return True


def record_activity(
    key_info: dict | None,
    *,
    tool: str,
    status: str,
    latency_ms: int = 0,
    error_code: str = "",
    metric: str = "tool_call_total",
):
    event = {
        "id": uuid.uuid4().hex[:12],
        "time": _now_iso(),
        "day": _today_str(),
        "tool": tool,
        "keyId": key_info.get("id") if key_info else "",
        "keyPreview": key_info.get("prefix") if key_info else "System",
        "status": status,
        "latencyMs": int(latency_ms),
        "errorCode": error_code,
        "metric": metric,
    }
    with LOCK:
        data = _read_json(USAGE_FILE, {"events": []})
        if not isinstance(data, dict):
            data = {"events": []}
        events = data.get("events", [])
        events.append(event)
        data["events"] = events[-500:]  # Keep last 500 events
        _write_json(USAGE_FILE, data)
    return event


def get_usage(period: str = "today") -> dict:
    mani = get_manifest()
    with LOCK:
        data = _read_json(USAGE_FILE, {"events": []})
        all_events = data.get("events", []) if isinstance(data, dict) else []

    today = _today_str()
    now_ts = time.time()

    if period == "today":
        events = [e for e in all_events if e.get("day") == today]
    elif period == "7d":
        cutoff = time.strftime("%Y-%m-%d", time.localtime(now_ts - 7 * 86400))
        events = [e for e in all_events if e.get("day", "") >= cutoff]
    elif period == "30d":
        cutoff = time.strftime("%Y-%m-%d", time.localtime(now_ts - 30 * 86400))
        events = [e for e in all_events if e.get("day", "") >= cutoff]
    else:
        events = all_events

    tool_call_total = len(events)
    video_create_requested = sum(
        1 for e in events
        if e.get("metric") in ("video_create_requested", "video_create_success", "video_create_failed")
        or e.get("tool") == "dola_create_video"
    )
    video_download_success = sum(
        1 for e in events
        if e.get("metric") == "video_download_success" or e.get("tool") in ("dola_download_video", "download_video")
    )
    video_create_success = sum(
        1 for e in events
        if e.get("metric") == "video_create_success" and e.get("status") == "success"
    )
    video_create_failed = sum(
        1 for e in events
        if (e.get("metric") == "video_create_failed" or e.get("status") == "failed")
        and e.get("tool") == "dola_create_video"
    )

    daily_limit = 100
    for policy in mani["quota"]["policies"]:
        if policy.get("id") == "daily_video_generations":
            daily_limit = int(policy.get("limit", 100))

    # Daily quota is strictly enforced for today's successful creations
    today_events = [e for e in all_events if e.get("day") == today]
    daily_used = sum(
        1 for e in today_events
        if e.get("metric") == "video_create_success" and e.get("status") == "success"
    )
    daily_remaining = max(0, daily_limit - daily_used)

    metrics_count = {
        "tool_call_total": tool_call_total,
        "video_create_requested": video_create_requested,
        "video_download_success": video_download_success,
        "video_create_success": video_create_success,
        "video_create_failed": video_create_failed,
        "daily_limit": daily_limit,
        "daily_used": daily_used,
        "daily_remaining": daily_remaining,
    }

    # Per-key breakdown
    keys_map = {k.get("id"): k for k in list_keys()}
    key_usage_map = {}
    for e in events:
        kid = e.get("keyId") or "system"
        if kid not in key_usage_map:
            k_info = keys_map.get(kid, {})
            key_usage_map[kid] = {
                "keyId": kid,
                "name": k_info.get("name") or (e.get("keyPreview") if kid != "system" else "Direct / Admin"),
                "prefix": k_info.get("prefix") or e.get("keyPreview", "System"),
                "status": k_info.get("status", "active"),
                "tool_calls": 0,
                "create_requested": 0,
                "create_success": 0,
                "create_failed": 0,
                "download_success": 0,
            }
        key_usage_map[kid]["tool_calls"] += 1
        if e.get("tool") == "dola_create_video":
            key_usage_map[kid]["create_requested"] += 1
            if e.get("status") == "success":
                key_usage_map[kid]["create_success"] += 1
            else:
                key_usage_map[kid]["create_failed"] += 1
        if e.get("metric") == "video_download_success" or e.get("tool") in ("dola_download_video", "download_video"):
            key_usage_map[kid]["download_success"] += 1

    policies = [
        {
            "id": "daily_video_generations",
            "metric": "video_create_success",
            "limit": daily_limit,
            "used": daily_used,
            "remaining": daily_remaining,
            "period": "day",
            "timezone": mani["quota"]["policies"][0].get("timezone", "Asia/Ho_Chi_Minh"),
            "resetAt": f"{today} 23:59:59 {mani['quota']['policies'][0].get('timezone', 'Asia/Ho_Chi_Minh')}",
        }
    ]

    return {
        "ok": True,
        "period": period,
        "metrics": metrics_count,
        "quota": policies,
        "keyUsage": list(key_usage_map.values()),
        "recentActivity": list(reversed(events[-50:])),
    }


def get_tool_catalog() -> list[dict]:
    mani = get_manifest()
    schemas = mani.get("schemas", {})
    tools = []
    for feature in mani.get("features", []):
        for t in feature.get("tools", []):
            s_ref = t.get("input_schema_ref", "").split("/")[-1]
            tools.append({
                "name": t["name"],
                "description": t.get("description", ""),
                "inputSchema": schemas.get(s_ref, {"type": "object"}),
            })
    return tools


async def handle_mcp_request(payload: dict, headers: dict, store, pool) -> dict:
    """Processes incoming JSON-RPC 2.0 requests over Streamable HTTP."""
    req_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}

    # 1. Initialize does not require API key (handshake discovery)
    if method == "initialize":
        client_version = params.get("protocolVersion") or "2025-03-26"
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": client_version,
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": "dola-render-gateway",
                    "version": "0.4.0",
                },
            },
        }

    # 2. Notification ack
    if method == "notifications/initialized":
        return {"jsonrpc": "2.0", "result": None}

    # 3. All other operations require valid MCP API key
    key_info, auth_err = authenticate_key(headers)
    if auth_err:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32001,
                "message": f"MCP Authentication Failed: {auth_err}",
            },
        }

    # 4. Check rate limit
    if not check_rate_limit(key_info["id"]):
        record_activity(key_info, tool=method or "unknown", status="failed", error_code="rate_limit")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32002,
                "message": "Rate limit exceeded (60 calls/minute). Please slow down.",
            },
        }

    start_time = time.time()

    # 5. Handle tools/list
    if method == "tools/list":
        tools = get_tool_catalog()
        record_activity(key_info, tool="tools/list", status="success", latency_ms=int((time.time() - start_time) * 1000))
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tools},
        }

    # 6. Handle tools/call
    if method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments") or {}

        try:
            if tool_name == "dola_create_video":
                # Check daily creation quota
                cur_usage = get_usage(period="today")
                daily_rem = cur_usage.get("metrics", {}).get("daily_remaining", 100)
                daily_max = cur_usage.get("metrics", {}).get("daily_limit", 100)
                if daily_rem <= 0:
                    record_activity(
                        key_info,
                        tool=tool_name,
                        status="failed",
                        error_code="mcp_quota_exceeded",
                        metric="video_create_failed",
                    )
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32003,
                            "message": f"mcp_quota_exceeded: Đã đạt giới hạn tối đa {daily_max} lần tạo video / ngày. Hạn mức sẽ tự động reset lúc 00:00 (Asia/Ho_Chi_Minh).",
                        },
                    }

                prompt = str(args.get("prompt", "")).strip()
                if not prompt:
                    raise ValueError("Prompt is required and cannot be empty.")
                ratio = args.get("ratio", "16:9")
                duration = int(args.get("duration", 10))
                model = args.get("model", "seedance-2.0")
                ref_images = args.get("reference_images") or []

                # Create task in store
                task_id = "video_" + uuid.uuid4().hex
                store.create(
                    task_id,
                    model,
                    prompt,
                    ratio or "16:9",
                    duration,
                    reference_images=json.dumps(ref_images, ensure_ascii=False) if ref_images else None,
                    api_key_hash=key_info.get("key_hash"),
                    api_key_name=key_info.get("name"),
                    daily_limit=0,
                    concurrency_limit=0,
                    max_pending=getattr(config, "MAX_PENDING_TASKS", 100),
                )

                latency = int((time.time() - start_time) * 1000)
                record_activity(
                    key_info,
                    tool=tool_name,
                    status="success",
                    latency_ms=latency,
                    metric="video_create_success",
                )

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps({
                                    "ok": True,
                                    "task_id": task_id,
                                    "status": "queued",
                                    "prompt": prompt,
                                    "ratio": ratio,
                                    "duration": duration,
                                    "message": f"Tác vụ video {task_id} đã được tạo thành công và đang chờ xử lý trong Dola pool.",
                                }, ensure_ascii=False),
                            }
                        ]
                    },
                }

            elif tool_name == "dola_get_task_status":
                task_id = str(args.get("task_id", "")).strip()
                if not task_id:
                    raise ValueError("task_id is required.")
                task = store.get(task_id)
                if not task:
                    raise ValueError(f"Task '{task_id}' not found.")

                latency = int((time.time() - start_time) * 1000)
                record_activity(key_info, tool=tool_name, status="success", latency_ms=latency)

                # Format task output
                task_info = {
                    "id": task["id"],
                    "status": task["status"],
                    "prompt": task.get("prompt", ""),
                    "ratio": task.get("ratio", ""),
                    "duration": task.get("duration", 10),
                    "video_url": task.get("video_url"),
                    "account": task.get("account"),
                    "error": task.get("error"),
                    "created_at": task.get("created_at"),
                    "completed_at": task.get("completed_at"),
                }

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(task_info, ensure_ascii=False),
                            }
                        ]
                    },
                }

            elif tool_name == "dola_list_tasks":
                limit = max(1, min(50, int(args.get("limit", 10))))
                tasks = store.recent_tasks(limit=limit)
                summary_tasks = [
                    {
                        "id": t["id"],
                        "status": t["status"],
                        "prompt": t.get("prompt", "")[:80],
                        "created_at": t.get("created_at"),
                        "video_url": t.get("video_url"),
                    }
                    for t in tasks
                ]
                latency = int((time.time() - start_time) * 1000)
                record_activity(key_info, tool=tool_name, status="success", latency_ms=latency)

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps({"tasks": summary_tasks, "count": len(summary_tasks)}, ensure_ascii=False),
                            }
                        ]
                    },
                }

            elif tool_name == "dola_list_accounts":
                accounts = pool.accounts if pool else []
                accounts_data = []
                for acc in accounts:
                    stats = pool.get_account_stats(acc) if hasattr(pool, "get_account_stats") else {}
                    accounts_data.append({
                        "name": acc,
                        "today_tasks": stats.get("today_tasks", 0),
                        "quota_blocked": stats.get("quota_blocked", False),
                    })
                latency = int((time.time() - start_time) * 1000)
                record_activity(key_info, tool=tool_name, status="success", latency_ms=latency)

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps({
                                    "accounts": accounts_data,
                                    "total_accounts": len(accounts_data),
                                }, ensure_ascii=False),
                            }
                        ]
                    },
                }

            elif tool_name == "dola_download_video":
                task_id = str(args.get("task_id", "")).strip()
                filename = str(args.get("filename", "")).strip()
                target_filename = ""
                video_url = ""

                if task_id:
                    task = store.get(task_id)
                    if not task:
                        raise ValueError(f"Task '{task_id}' not found.")
                    video_url = task.get("video_url") or ""
                    if not video_url:
                        raise ValueError(f"Task '{task_id}' has not produced a video yet (status: {task.get('status')}).")
                    target_filename = video_url.rsplit("/", 1)[-1].split("?")[0]
                elif filename:
                    target_filename = filename
                    video_url = f"{_public_base_url()}/videos/{filename}"
                else:
                    raise ValueError("Vui lòng cung cấp 'task_id' hoặc 'filename'.")

                latency = int((time.time() - start_time) * 1000)
                record_activity(
                    key_info,
                    tool=tool_name,
                    status="success",
                    latency_ms=latency,
                    metric="video_download_success",
                )

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps({
                                    "ok": True,
                                    "filename": target_filename,
                                    "download_url": video_url,
                                    "status": "ready",
                                    "message": f"Video sẵn sàng để tải xuống: {video_url}",
                                }, ensure_ascii=False),
                            }
                        ]
                    },
                }

            else:
                raise ValueError(f"Unknown tool: '{tool_name}'")

        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            record_activity(
                key_info,
                tool=tool_name or "tools/call",
                status="failed",
                latency_ms=latency,
                error_code=str(e),
                metric="video_create_failed" if tool_name == "dola_create_video" else "tool_call_failed",
            )
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32603,
                    "message": f"Tool execution failed: {str(e)}",
                },
            }

    # 7. Unrecognized method
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32601,
            "message": f"Method '{method}' not found.",
        },
    }
