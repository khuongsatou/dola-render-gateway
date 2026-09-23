"""Dola Pool: OpenAI-compatible Video API (FastAPI) and Admin Dashboard.

Endpoints (Asynchronous 2-stage):
POST /v1/videos/generations -> Create task (status=queued)
GET  /v1/videos/<id>         -> Query task status (queued/processing/completed/failed)
GET  /videos/<file>          -> Static video download server

Admin Dashboard: GET / -> web/index.html; Admin API /api/admin/*
"""
import asyncio
import hashlib
import json
import re
import shutil
import time
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from jev_live_runner import jev_live_session
from flow_live_runner import flow_live_session
from flow_element_locator import FlowElementLocator

import config
from add_account import add_account_flow
from browser_pool import AllAccountsLimitedError, AllAccountsQuotaBlockedError, BrowserPool
import chrome_profile_scanner
from media import download_reference_images, validate_reference_urls
from store import PendingTaskLimitExceeded, TaskQuotaExceeded, TaskStore

Path(config.DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path("web").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="dola-pool", version="0.4.0")

store = TaskStore(config.DB_PATH)
pool = BrowserPool(max_concurrency=config.MAX_CONCURRENCY)

app.mount("/videos", StaticFiles(directory=config.DOWNLOAD_DIR), name="videos")

# Background jobs (add/verify), in-memory
JOBS: dict[str, dict] = {}

SIZE_TO_RATIO = {
    "1280x720": "16:9", "1920x1080": "16:9",
    "720x1280": "9:16", "1080x1920": "9:16",
    "1024x1024": "1:1", "1440x1080": "4:3", "1080x1440": "3:4",
}
SUPPORTED_DURATIONS = (10, 15, 30)
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


class KeyConcurrencyLimiter:
    """Concurrency limits per API Key; 0 = unlimited."""

    def __init__(self):
        self._condition = asyncio.Condition()
        self._active: defaultdict[str, int] = defaultdict(int)

    async def acquire(self, api_key_hash: str | None, limit: int):
        if not api_key_hash or limit <= 0:
            return
        async with self._condition:
            while self._active[api_key_hash] >= limit:
                await self._condition.wait()
            self._active[api_key_hash] += 1

    async def release(self, api_key_hash: str | None):
        if not api_key_hash:
            return
        async with self._condition:
            if self._active[api_key_hash] > 0:
                self._active[api_key_hash] -= 1
            if self._active[api_key_hash] == 0:
                self._active.pop(api_key_hash, None)
            self._condition.notify_all()



key_limiter = KeyConcurrencyLimiter()


# ===== Authentication =====


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _anonymous_client() -> dict:
    return {
        "api_key_hash": None,
        "api_key_name": "Anonymous",
        "daily_limit": 0,
        "concurrency_limit": 0,
        "allowed_durations": list(SUPPORTED_DURATIONS),
    }


def _env_client(key: str) -> dict:
    return {
        "api_key_hash": _hash_key(key),
        "api_key_name": f"Env Key ({key[:8]}…)",
        "daily_limit": 0,
        "concurrency_limit": 0,
        "allowed_durations": list(SUPPORTED_DURATIONS),
    }


def _admin_client() -> dict:
    return {
        "api_key_hash": None,
        "api_key_name": "Admin Dashboard",
        "daily_limit": 0,
        "concurrency_limit": 0,
        "allowed_durations": list(SUPPORTED_DURATIONS),
    }


def _auth(authorization):
    """Returns client policy for caller; empty key enables dev mode."""
    if not config.API_KEYS and not store.has_enabled_keys():
        return _anonymous_client()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    key = authorization[7:].strip()
    if not key:
        raise HTTPException(401, "missing bearer token")
    if key in config.API_KEYS:
        return _env_client(key)
    record = store.get_key(key)
    if not record or not store.is_key_valid(key):
        raise HTTPException(401, "invalid api key")
    store.touch_key(key)
    return {
        "api_key_hash": _hash_key(key),
        "api_key_name": record["name"] or "Unnamed Client",
        "daily_limit": record["daily_limit"],
        "concurrency_limit": record["concurrency_limit"],
        "allowed_durations": record["allowed_durations"],
    }


def _admin_auth(x_admin_key: str | None):
    if not config.ADMIN_KEY:
        return
    if x_admin_key != config.ADMIN_KEY:
        raise HTTPException(401, "invalid admin key")


def _normalize_allowed_durations(values) -> list[int]:
    if values is None:
        return list(SUPPORTED_DURATIONS)
    try:
        normalized = sorted({int(value) for value in values})
    except (TypeError, ValueError):
        raise HTTPException(422, "allowed_durations must be an array of 10, 15, or 30")
    if not normalized or any(value not in SUPPORTED_DURATIONS for value in normalized):
        raise HTTPException(422, "allowed_durations must contain at least one of 10, 15, 30")
    return normalized


# ===== Client API =====


class VideoGenRequest(BaseModel):
    model: str = "seedance-2.0"
    prompt: str = Field(..., min_length=1)
    size: str | None = None
    ratio: str | None = None
    duration: int | None = Field(None, ge=10, le=30)
    # Accepts durations: 10, 15, 30 seconds.
    reference_images: list[str] = Field(default_factory=list)
    account: str | None = None


class TaskResponse(BaseModel):
    id: str
    status: str
    model: str | None = None
    prompt: str | None = None
    video_url: str | None = None
    error: str | None = None


def _resolve_ratio(size, ratio):
    if size and size in SIZE_TO_RATIO:
        return SIZE_TO_RATIO[size]
    return ratio


async def _run_task(task_id, model, prompt, ratio, duration, reference_images, client, preferred_account: str | None = None):
    api_key_hash = client.get("api_key_hash")
    acquired = False
    reference_root = None
    try:
        await key_limiter.acquire(api_key_hash, client.get("concurrency_limit", 0))
        acquired = True
        store.update(task_id, status="processing", started_at=time.time())

        def on_conversation_id(account, conversation_id, deadline_at):
            store.update(task_id, status="processing", account=account,
                         conversation_id=conversation_id, deadline_at=deadline_at,
                         last_poll_at=time.time())

        def on_poll(now):
            store.update(task_id, last_poll_at=now)

        reference_root, reference_paths = await download_reference_images(
            reference_images or [], task_id)
        result = await pool.generate_video(
            prompt, ratio, duration, model,
            on_conversation_id=on_conversation_id, on_poll=on_poll,
            reference_image_paths=reference_paths,
            preferred_account=preferred_account)
        public_url = f"{config.PUBLIC_BASE}/videos/{Path(result['local_path']).name}"
        store.update(task_id, status="completed", video_url=public_url,
                     account=result.get("account"), last_poll_at=time.time(),
                     finished_at=time.time())
    except (AllAccountsLimitedError, AllAccountsQuotaBlockedError) as e:
        store.update(task_id, status="failed", error=str(e)[:500],
                     failure_code="429", finished_at=time.time())
    except Exception as e:
        store.update(task_id, status="failed", error=str(e)[:500],
                     finished_at=time.time())
    finally:
        if reference_root:
            shutil.rmtree(reference_root, ignore_errors=True)
        if acquired:
            await key_limiter.release(api_key_hash)


async def _resume_task(row: dict):
    task_id = row["id"]
    deadline = row.get("deadline_at") or (
        time.time() + (1800 if row.get("duration") == 30 else config.VIDEO_TIMEOUT)
    )
    remaining = max(1, int(deadline - time.time()))
    api_key_hash = row.get("api_key_hash")
    acquired = False
    try:
        await key_limiter.acquire(
            api_key_hash, int(row.get("client_concurrency_limit") or 0)
        )
        acquired = True
        store.update(task_id, status="processing", last_poll_at=time.time(),
                     started_at=row.get("started_at") or time.time())

        def on_poll(now):
            store.update(task_id, last_poll_at=now)

        result = await pool.resume_video(
            row["account"], row["conversation_id"], remaining, on_poll=on_poll)
        public_url = f"{config.PUBLIC_BASE}/videos/{Path(result['local_path']).name}"
        store.update(task_id, status="completed", video_url=public_url,
                     account=result.get("account"), last_poll_at=time.time(),
                     finished_at=time.time())
    except Exception as e:
        store.update(task_id, status="failed", error=str(e)[:500],
                     finished_at=time.time())
    finally:
        if acquired:
            await key_limiter.release(api_key_hash)


def _task_client(row: dict) -> dict:
    """Restores client context from task snapshot."""
    return {
        "api_key_hash": row.get("api_key_hash"),
        "api_key_name": row.get("api_key_name") or "Historical Task",
        "daily_limit": 0,
        "concurrency_limit": int(row.get("client_concurrency_limit") or 0),
        "allowed_durations": list(SUPPORTED_DURATIONS),
    }


def _task_reference_images(raw) -> list[str]:
    try:
        values = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return values if isinstance(values, list) else []


@app.on_event("startup")
async def resume_incomplete_tasks():
    """Recovers accepted sessions on startup and requeues pending tasks."""
    for row in store.recoverable_tasks():
        asyncio.create_task(_resume_task(row))
    for row in store.recoverable_queued_tasks():
        ratio = row.get("ratio")
        if ratio == "default":
            ratio = None
        asyncio.create_task(_run_task(
            row["id"], row["model"], row["prompt"], ratio, row["duration"],
            _task_reference_images(row.get("reference_images")), _task_client(row),
        ))


@app.post("/v1/videos/generations", response_model=TaskResponse)
async def create_video(
    req: VideoGenRequest,
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    if x_admin_key:
        _admin_auth(x_admin_key)
        client = _admin_client()
    else:
        client = _auth(authorization)
    duration = req.duration or 10
    if duration not in SUPPORTED_DURATIONS:
        raise HTTPException(422, "Currently supports durations of 10s, 15s, and 30s")
    if duration not in client["allowed_durations"]:
        raise HTTPException(422, f"Current API Key is not allowed to generate {duration}s videos")
    model_key = req.model.lower().replace("-", "_")
    if model_key not in (
        "seedance_2.0", "seedance_2.5", "seedance_v2.0", "seedance_v2.5",
        "seedance_20", "seedance_25", "seedance_v20", "seedance_v25",
    ):
        raise HTTPException(422, "Supported models are seedance-2.0 and seedance-2.5")
    try:
        reference_images = await validate_reference_urls(req.reference_images)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    # Queue task when accounts are busy; reject only when pool is fully exhausted.
    if not pool.available and pool.all_accounts_limited:
        raise HTTPException(429, "Rate limited: All accounts reached Dola daily video limit, please try again tomorrow")
    if not pool.available and pool.all_accounts_quota_blocked:
        raise HTTPException(429, "Insufficient credits: All accounts lack points, waiting for refresh")
    if not pool.accounts:
        raise HTTPException(503, "no account in pool")
    task_id = "video_" + uuid.uuid4().hex
    ratio = _resolve_ratio(req.size, req.ratio)
    try:
        store.create(
            task_id,
            req.model,
            req.prompt,
            ratio or "default",
            duration,
            reference_images=json.dumps(reference_images, ensure_ascii=False),
            api_key_hash=client["api_key_hash"],
            api_key_name=client["api_key_name"],
            daily_limit=client["daily_limit"],
            concurrency_limit=client["concurrency_limit"],
            max_pending=config.MAX_PENDING_TASKS,
        )
    except TaskQuotaExceeded as exc:
        raise HTTPException(429, str(exc)) from exc
    except PendingTaskLimitExceeded as exc:
        raise HTTPException(429, str(exc)) from exc
    asyncio.create_task(_run_task(
        task_id, req.model, req.prompt, ratio, duration, reference_images, client,
        preferred_account=req.account,
    ))
    return TaskResponse(id=task_id, status="queued", model=req.model, prompt=req.prompt)


@app.get("/v1/videos/{task_id}", response_model=TaskResponse)
async def get_video(
    task_id: str,
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    if x_admin_key:
        _admin_auth(x_admin_key)
        row = store.get(task_id)
    else:
        client = _auth(authorization)
        row = store.get_for_client(task_id, client["api_key_hash"])
    if not row:
        raise HTTPException(404, "task not found")
    return TaskResponse(
        id=row["id"],
        status=row["status"],
        model=row["model"],
        prompt=row["prompt"],
        video_url=row["video_url"],
        error=row["error"],
    )


@app.get("/health")
async def health():
    return {
        "ok": True,
        "accounts": pool.account_status(),
        "available": pool.available,
        "pending_tasks": store.pending_task_count(),
        "max_pending_tasks": config.MAX_PENDING_TASKS,
    }


# ===== Admin Dashboard API =====


class AdminLogin(BaseModel):
    key: str


class AccountPatch(BaseModel):
    scheduling: bool | None = None
    incognito: bool | None = None
    note: str | None = None
    email: str | None = None


class AccountAdd(BaseModel):
    name: str
    email: str
    password: str
    totp: str
    incognito: bool | None = None


class ChromeProfileImport(BaseModel):
    directory: str
    name: str | None = None


class ChromeProfileBulkImport(BaseModel):
    directories: list[str]
    prefix: str = "p_"


class SettingsPatch(BaseModel):
    incognito: bool | None = None
    headless: bool | None = None


class KeyCreate(BaseModel):
    name: str = ""
    daily_limit: int = Field(0, ge=0, le=1_000_000)
    concurrency_limit: int = Field(0, ge=0, le=1_000)
    allowed_durations: list[int] = Field(default_factory=lambda: list(SUPPORTED_DURATIONS))
    expires_at: float | None = Field(None, ge=0)


class KeyPatch(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    daily_limit: int | None = Field(None, ge=0, le=1_000_000)
    concurrency_limit: int | None = Field(None, ge=0, le=1_000)
    allowed_durations: list[int] | None = None
    expires_at: float | None = Field(None, ge=0)


@app.post("/api/admin/login")
async def admin_login(body: AdminLogin):
    if not config.ADMIN_KEY:
        return {"ok": True, "auth_required": False}
    if body.key == config.ADMIN_KEY:
        return {"ok": True, "auth_required": True}
    raise HTTPException(401, "wrong admin key")


@app.get("/api/admin/settings")
async def admin_get_settings(x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    return {
        "incognito": config.INCOGNITO,
        "headless": config.HEADLESS,
    }


@app.patch("/api/admin/settings")
async def admin_patch_settings(body: SettingsPatch, x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    if body.incognito is not None:
        config.INCOGNITO = body.incognito
    if body.headless is not None:
        config.HEADLESS = body.headless
    return {
        "ok": True,
        "incognito": config.INCOGNITO,
        "headless": config.HEADLESS,
    }


@app.get("/api/admin/accounts")
async def admin_accounts(x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    return {"accounts": pool.list_accounts()}


@app.patch("/api/admin/accounts/{name}")
async def admin_account_patch(name: str, body: AccountPatch,
                              x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    if name not in pool.accounts:
        raise HTTPException(404, "account not found")
    if body.scheduling is not None:
        pool.set_scheduling(name, body.scheduling)
    if body.incognito is not None:
        pool.set_incognito(name, body.incognito)
    if body.note is not None:
        pool.set_note(name, body.note)
    if body.email is not None:
        pool.set_email(name, body.email)
    return {"ok": True}


@app.delete("/api/admin/accounts/{name}")
async def admin_account_delete(name: str, x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    if name not in pool.accounts:
        raise HTTPException(404, "account not found")
    try:
        pool.delete_account(name)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.post("/api/admin/accounts/{name}/verify")
async def admin_account_verify(name: str, x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    try:
        ok = await pool.verify_account(name)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return {"ok": ok}


async def _run_add_job(name: str, email: str, password: str, totp: str, incognito: bool | None = None):
    JOBS[name] = {"kind": "add", "status": "running", "error": "", "started_at": time.time()}
    try:
        await add_account_flow(name, email, password, totp, incognito=incognito)
        pool.set_email(name, email)
        pool.set_login_status(name, True)
        JOBS[name] = {**JOBS[name], "status": "success"}
    except Exception as e:
        JOBS[name] = {**JOBS[name], "status": "failed", "error": str(e)[:300]}


@app.post("/api/admin/accounts", status_code=202)
async def admin_account_add(body: AccountAdd, x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    if not NAME_RE.match(body.name):
        raise HTTPException(400, "invalid account name")
    if body.name in pool.accounts:
        raise HTTPException(409, "account exists")
    if JOBS.get(body.name, {}).get("status") == "running":
        raise HTTPException(409, "add job running")
    asyncio.create_task(_run_add_job(body.name, body.email, body.password, body.totp, incognito=body.incognito))
    return {"ok": True, "job": "running"}


@app.get("/api/admin/chrome-profiles")
async def admin_chrome_profiles(x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    profiles = chrome_profile_scanner.scan_chrome_profiles(
        accounts_dir=pool.accounts_dir,
        db_path=config.DB_PATH.replace("tasks.db", "pool_usage.db") if "tasks.db" in config.DB_PATH else "pool_usage.db",
    )
    return {
        "ok": True,
        "total": len(profiles),
        "imported": sum(1 for p in profiles if p["is_imported"]),
        "profiles": profiles,
    }


@app.post("/api/admin/chrome-profiles/import")
async def admin_chrome_profile_import(body: ChromeProfileImport, x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    try:
        res = chrome_profile_scanner.import_chrome_profile(
            directory=body.directory,
            target_name=body.name,
            accounts_dir=pool.accounts_dir,
            db_path="pool_usage.db",
        )
        # Ensure pool recognizes the newly imported account
        pool._ensure_meta(res["name"])
        return {"ok": True, "account": res}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/admin/chrome-profiles/bulk-import")
async def admin_chrome_profiles_bulk_import(body: ChromeProfileBulkImport, x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    try:
        summary = chrome_profile_scanner.bulk_import_chrome_profiles(
            directories=body.directories,
            prefix=body.prefix or "p_",
            accounts_dir=pool.accounts_dir,
            db_path="pool_usage.db",
        )
        for r in summary.get("results", []):
            if r.get("name"):
                pool._ensure_meta(r["name"])
        return summary
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/admin/dola/elements")
async def admin_dola_elements(account: str | None = None, x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    acc = account or (pool.accounts[0] if pool.accounts else None)
    if not acc:
        raise HTTPException(400, "no accounts available in pool")
    from patchright.async_api import async_playwright
    from browser import launch_account_context
    from dola_element_locator import DolaElementLocator
    async with async_playwright() as p:
        try:
            context = await launch_account_context(p, acc, headless=True)
            try:
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto("https://www.dola.com/chat", timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(4000)
                snapshot = await DolaElementLocator.snapshot(page)
                return {"ok": True, "account": acc, "data": snapshot}
            finally:
                await context.close()
        except Exception as e:
            raise HTTPException(500, f"Element inspection failed: {str(e)[:200]}")


class JevLiveStartRequest(BaseModel):
    account: str | None = None
    prompt: str | None = None
    mode: str | None = "human_flow"
    model: str | None = "seedance-2.0"
    ratio: str | None = "16:9"
    duration: int | None = 10


@app.post("/api/admin/jev/live-start")
async def admin_jev_live_start(req: JevLiveStartRequest, x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    acc = (req.account or "").strip()
    if acc and acc not in pool.accounts:
        if not (Path("accounts") / acc).exists():
            raise HTTPException(404, f"Profile tài khoản '{acc}' không tồn tại trong thư mục accounts/")
    if not acc:
        # Ưu tiên tài khoản đã đăng nhập thành công (login_ok == 1)
        for a in pool.list_accounts():
            if a.get("login_ok") == 1:
                acc = a["name"]
                break
        if not acc and pool.accounts:
            acc = pool.accounts[0]
    if not acc:
        raise HTTPException(400, "Không có tài khoản khả dụng trong pool")
    res = await jev_live_session.start(
        account=acc,
        prompt=req.prompt or "",
        mode=req.mode or "human_flow",
        model=req.model or "seedance-2.0",
        ratio=req.ratio or "16:9",
        duration=req.duration or 10,
    )
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "Không thể khởi chạy phiên Live Jev"))
    return res


@app.get("/api/admin/jev/live-status")
async def admin_jev_live_status(x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    return jev_live_session.get_status()


@app.post("/api/admin/jev/live-stop")
async def admin_jev_live_stop(x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    await jev_live_session.stop()
    return {"ok": True}


@app.get("/api/admin/jev/live-stream")
async def admin_jev_live_stream():
    q = jev_live_session.subscribe()

    async def event_generator():
        try:
            st = jev_live_session.get_status()
            yield f"event: status\ndata: {json.dumps(st, ensure_ascii=False)}\n\n"
            if jev_live_session.last_frame:
                yield f"event: frame\ndata: {json.dumps({'image': jev_live_session.last_frame, 'caption': 'Khung hình hiện tại'}, ensure_ascii=False)}\n\n"

            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=20.0)
                    evt = msg.get("type", "message")
                    yield f"event: {evt}\ndata: {json.dumps(msg, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            jev_live_session.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class FlowLiveStartRequest(BaseModel):
    account: str | None = None
    prompt: str | None = None
    mode: str | None = "image"
    model: str | None = "Nano Banana 2"
    ratio: str | None = "16:9"
    quantity: str | None = "x1"


@app.post("/api/admin/flow/live-start")
async def admin_flow_live_start(req: FlowLiveStartRequest, x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    acc = (req.account or "").strip()
    if not acc:
        # Ưu tiên tài khoản đã đăng nhập
        for a in pool.list_accounts():
            if a.get("login_ok") == 1:
                acc = a["name"]
                break
        if not acc and pool.accounts:
            acc = pool.accounts[0]
    if not acc:
        acc = "vankhuong240_p185"

    res = await flow_live_session.start(
        account=acc,
        prompt=req.prompt or "",
        mode=req.mode or "image",
        model=req.model or "Nano Banana 2",
        ratio=req.ratio or "16:9",
        quantity=req.quantity or "x1",
    )
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "Không thể khởi chạy phiên Live Flow"))
    return res


@app.get("/api/admin/flow/live-status")
async def admin_flow_live_status(x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    return flow_live_session.get_status()


@app.post("/api/admin/flow/live-stop")
async def admin_flow_live_stop(x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    await flow_live_session.stop()
    return {"ok": True}


@app.get("/api/admin/flow/live-stream")
async def admin_flow_live_stream():
    q = flow_live_session.subscribe()

    async def event_generator():
        try:
            st = flow_live_session.get_status()
            yield f"event: status\ndata: {json.dumps(st, ensure_ascii=False)}\n\n"
            if flow_live_session.last_frame:
                yield f"event: frame\ndata: {json.dumps({'image': flow_live_session.last_frame, 'caption': 'Khung hình hiện tại'}, ensure_ascii=False)}\n\n"

            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=20.0)
                    evt = msg.get("type", "message")
                    yield f"event: {evt}\ndata: {json.dumps(msg, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            flow_live_session.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/admin/flow/elements")
async def admin_flow_elements(account: str | None = None, x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    acc = account or (pool.accounts[0] if pool.accounts else "vankhuong240_p185")
    from patchright.async_api import async_playwright
    async with async_playwright() as p:
        try:
            context = await flow_live_session._resolve_browser_context(p, acc)
            try:
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto("https://flow.google.com/", timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(4000)
                snapshot = await FlowElementLocator.snapshot(page)
                return {"ok": True, "account": acc, "data": snapshot}
            finally:
                await context.close()
        except Exception as e:
            raise HTTPException(500, f"Flow element inspection failed: {str(e)[:200]}")


@app.get("/api/admin/jobs")
async def admin_jobs(x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    return {"jobs": JOBS}


@app.get("/api/admin/tasks")
async def admin_tasks(limit: int = 50, x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    return {"tasks": store.recent_tasks(min(max(limit, 1), 200))}


@app.get("/api/admin/stats")
async def admin_stats(x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    st = store.stats()
    accs = pool.list_accounts()
    sched = [a for a in accs if a["scheduling"] and not a["cooling"]]
    st["total_accounts"] = len(accs)
    st["available_accounts"] = sum(1 for a in sched if a["remaining"] > 0)
    st["total_remaining"] = sum(a["remaining"] for a in sched)
    totals = st.pop("per_account_total", {})
    st["per_account"] = [{**a, "completed_total": totals.get(a["name"], 0)} for a in accs]
    return st


@app.get("/api/admin/keys")
async def admin_keys(x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    keys = []
    for key in store.list_keys():
        usage = store.key_usage(store.hash_api_key(key["key"]))
        keys.append({**key, **{
            "today_total": usage["total"],
            "today_completed": usage["completed"],
            "today_failed": usage["failed"],
            "today_active": usage["active"],
            "today_queued": usage["queued"],
        }})
    return {"keys": keys, "env_keys": len(config.API_KEYS)}


@app.post("/api/admin/keys")
async def admin_key_create(body: KeyCreate, x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    allowed = _normalize_allowed_durations(body.allowed_durations)
    return {"created": store.create_key(
        body.name,
        daily_limit=body.daily_limit,
        concurrency_limit=body.concurrency_limit,
        allowed_durations=allowed,
        expires_at=body.expires_at,
    )}


@app.patch("/api/admin/keys/{key}")
async def admin_key_patch(key: str, body: KeyPatch,
                          x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    if not store.get_key(key):
        raise HTTPException(404, "api key not found")
    fields = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.enabled is not None:
        fields["enabled"] = 1 if body.enabled else 0
    if body.daily_limit is not None:
        fields["daily_limit"] = body.daily_limit
    if body.concurrency_limit is not None:
        fields["concurrency_limit"] = body.concurrency_limit
    if body.allowed_durations is not None:
        fields["allowed_durations"] = _normalize_allowed_durations(body.allowed_durations)
    if body.expires_at is not None:
        fields["expires_at"] = body.expires_at
    store.update_key(key, **fields)
    return {"ok": True}


@app.delete("/api/admin/keys/{key}")
async def admin_key_delete(key: str, x_admin_key: str | None = Header(default=None)):
    _admin_auth(x_admin_key)
    if not store.get_key(key):
        raise HTTPException(404, "api key not found")
    store.delete_key(key)
    return {"ok": True}


@app.get("/web")
@app.get("/web/")
async def redirect_web():
    return RedirectResponse(url="/")


# Dashboard single-file frontend
app.mount("/", StaticFiles(directory="web", html=True), name="web")

