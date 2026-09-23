"""Jev Live Runner: Real-time visual automation & streaming engine for Dola.com.

Provides step-by-step human-like operations (smooth bezier mouse movement,
indexed DOM element overlays, keystroke typing) and real-time screen frame
broadcasting via Server-Sent Events (SSE) to the Web Dashboard.
"""

import asyncio
import base64
import json
import logging
import random
import time
from pathlib import Path
from typing import Any, AsyncGenerator

from patchright.async_api import async_playwright

from account_locks import acquire_account_execution, release_account_execution
import config
from browser import cookie_value, launch_account_context
from dola_element_locator import DolaElementLocator
from store import TaskStore
from video_worker import POLL_JS, _download, extract_unwatermarked_url
from video_worker_ui import find_captcha_frame, solve_slider

logger = logging.getLogger("jev_live")


async def smooth_mouse_move(page, start_pos: tuple[float, float], end_pos: tuple[float, float], duration_ms: int = 450):
    """Interpolates mouse movement along an ease-out Bezier curve mimicking human hand physics."""
    steps = max(10, int(duration_ms / 20))
    sx, sy = start_pos
    ex, ey = end_pos

    # Slight natural curved trajectory
    mid_x = (sx + ex) / 2 + random.uniform(-25, 25)
    mid_y = (sy + ey) / 2 + random.uniform(-20, 20)

    for i in range(1, steps + 1):
        t = i / steps
        bx = (1 - t) ** 2 * sx + 2 * (1 - t) * t * mid_x + t ** 2 * ex
        by = (1 - t) ** 2 * sy + 2 * (1 - t) * t * mid_y + t ** 2 * ey
        await page.mouse.move(bx, by)
        await asyncio.sleep(0.015)

    return (ex, ey)


async def human_type(page, text: str):
    """Types text with natural human variance, burst cadence, and micro pauses."""
    for ch in text:
        await page.keyboard.type(ch)
        delay = random.uniform(0.03, 0.09)
        if ch in (" ", ",", ".", "!"):
            delay += 0.08
        await asyncio.sleep(delay)


class JevLiveSession:
    def __init__(self):
        self.is_running: bool = False
        self.account: str = ""
        self.mode: str = "human_flow"  # "inspect" | "human_flow" | "generate"
        self.prompt: str = ""
        self.model: str = "seedance-2.0"
        self.ratio: str = "16:9"
        self.duration: int = 10
        self.current_step: int = 0
        self.total_steps: int = 7
        self.status_text: str = "Idle"
        self.listeners: list[asyncio.Queue] = []
        self._task: asyncio.Task | None = None
        self._execution_acquired: bool = False
        self._stop_requested: bool = False
        self.history_logs: list[dict[str, Any]] = []
        self.last_frame: str | None = None

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=100)
        self.listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self.listeners:
            self.listeners.remove(q)

    async def broadcast(self, event_type: str, data: dict[str, Any]):
        msg = {
            "type": event_type,
            "timestamp": time.time(),
            **data,
        }
        if event_type == "log":
            self.history_logs.append(msg)
            if len(self.history_logs) > 200:
                self.history_logs.pop(0)
        elif event_type == "frame":
            self.last_frame = msg.get("image")

        stale = []
        for q in self.listeners:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                stale.append(q)
            except Exception:
                stale.append(q)
        for s in stale:
            self.unsubscribe(s)

    async def stop(self):
        self._stop_requested = True
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.is_running = False
        await self.broadcast("status", {"running": False, "status": "Stopped by user"})

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self.is_running,
            "account": self.account,
            "mode": self.mode,
            "prompt": self.prompt,
            "model": self.model,
            "ratio": self.ratio,
            "duration": self.duration,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "status_text": self.status_text,
            "has_last_frame": bool(self.last_frame),
            "recent_logs": self.history_logs[-20:],
        }

    async def start(
        self,
        account: str,
        prompt: str = "",
        mode: str = "human_flow",
        model: str = "seedance-2.0",
        ratio: str = "16:9",
        duration: int = 10,
    ) -> dict[str, Any]:
        if self.is_running:
            return {"ok": False, "error": "A Live Jev session is already running"}

        self.account = account
        self.prompt = prompt or "A majestic golden eagle soaring through mist in sunset"
        self.mode = mode
        self.model = model or "seedance-2.0"
        self.ratio = ratio or "16:9"
        self.duration = duration or 10
        self.current_step = 0
        self.total_steps = 3 if mode == "inspect" else 7
        self.is_running = True
        self._stop_requested = False
        self.history_logs = []
        self.last_frame = None

        await acquire_account_execution(self.account, config.MAX_CONCURRENCY)
        self._execution_acquired = True
        try:
            self._task = asyncio.create_task(self._run_workflow())
        except BaseException:
            release_account_execution(self.account, config.MAX_CONCURRENCY)
            self._execution_acquired = False
            raise
        return {
            "ok": True,
            "account": account,
            "mode": mode,
            "model": self.model,
            "ratio": self.ratio,
            "duration": self.duration,
        }

    async def _capture_frame_base64(self, page, quality: int = 80) -> str:
        """Takes a JPEG screenshot and converts to data URL."""
        raw = await page.screenshot(type="jpeg", quality=quality)
        b64 = base64.b64encode(raw).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"

    async def _run_workflow(self):
        mouse_pos = (250.0, 180.0)
        try:
            await self.broadcast("status", {"running": True, "status": f"Khởi tạo trình duyệt cho {self.account}..."})

            # STEP 1: Launch Context
            self.current_step = 1
            self.status_text = f"Đang mở Chrome profile: {self.account}"
            await self.broadcast("step", {
                "step": 1, "total": self.total_steps,
                "title": "Mở Trình Duyệt",
                "detail": f"Khởi động persistent context cho tài khoản {self.account}",
            })

            async with async_playwright() as p:
                context = await launch_account_context(p, self.account, headless=True, incognito=False)
                try:
                    page = context.pages[0] if context.pages else await context.new_page()
                    await page.set_viewport_size({"width": 1280, "height": 800})

                    # STEP 2: Navigate to Dola Chat
                    self.current_step = 2
                    self.status_text = "Đang tải trang https://www.dola.com/chat..."
                    await self.broadcast("step", {
                        "step": 2, "total": self.total_steps,
                        "title": "Điều Hướng Dola.com",
                        "detail": f"Truy cập https://www.dola.com/chat với Profile [{self.account}]",
                    })

                    await page.goto("https://www.dola.com/chat", timeout=60000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(3500)

                    cookies = await context.cookies("https://www.dola.com")
                    has_session = any(c.get("name") == "sessionid" and c.get("value") for c in cookies)
                    if has_session:
                        await self.broadcast("log", {
                            "level": "success",
                            "message": f"🔐 Profile [{self.account}] đã xác thực phiên đăng nhập (sessionid active)",
                        })
                    else:
                        await self.broadcast("log", {
                            "level": "warn",
                            "message": f"⚠️ Profile [{self.account}] chưa có sessionid. Đang kiểm tra giao diện...",
                        })

                    frame_initial = await self._capture_frame_base64(page)
                    await self.broadcast("frame", {
                        "step": 2,
                        "caption": f"Trang Dola Chat đã tải thành công với Profile: {self.account}",
                        "image": frame_initial,
                    })

                    # STEP 3: Jev Indexed DOM Snapshot
                    self.current_step = 3
                    self.status_text = "Jev đang phân tích DOM và trích xuất tọa độ..."
                    await self.broadcast("step", {
                        "step": 3, "total": self.total_steps,
                        "title": "Jev DOM Scan & Indexing",
                        "detail": "Trích xuất toàn bộ tọa độ và loại nút tương tác trên màn hình",
                    })

                    snapshot = await DolaElementLocator.snapshot(page)
                    total_el = snapshot.get("total_elements", 0)
                    cats = list(snapshot.get("categories", {}).keys())

                    await self.broadcast("log", {
                        "level": "info",
                        "message": f"🎯 Jev phát hiện {total_el} phần tử tương tác (Categories: {', '.join(cats)})",
                    })

                    # Render bounding boxes overlay
                    count_badges = await DolaElementLocator.highlight_elements(page)
                    await page.wait_for_timeout(400)
                    frame_overlay = await self._capture_frame_base64(page)
                    await self.broadcast("frame", {
                        "step": 3,
                        "caption": f"Jev Visual Bounding Boxes ({count_badges} badges)",
                        "image": frame_overlay,
                        "elements_count": total_el,
                    })
                    await DolaElementLocator.remove_highlights(page)

                    if self.mode == "inspect":
                        self.status_text = "Hoàn tất quét & trực quan hóa phần tử Dola"
                        await self.broadcast("step", {
                            "step": self.total_steps, "total": self.total_steps,
                            "title": "Hoàn Tất",
                            "detail": f"Đã quét và lập chỉ mục thành công {total_el} phần tử",
                        })
                        return

                    # STEP 4: Locate '動画を作成' & Smooth Glide Mouse Click
                    self.current_step = 4
                    self.status_text = "Jev đang dò nút '動画を作成' (Tạo video)..."
                    await self.broadcast("step", {
                        "step": 4, "total": self.total_steps,
                        "title": "Định Vị & Click Nút Tạo Video",
                        "detail": "Lướt chuột cong tự nhiên và click vào nút '動画を作成'",
                    })

                    video_btn = await DolaElementLocator.find_video_button(page)
                    if video_btn:
                        vx = video_btn["center"]["x"]
                        vy = video_btn["center"]["y"]
                        await self.broadcast("log", {
                            "level": "info",
                            "message": f"📍 Nút Tạo Video tại x={vx:.1f}, y={vy:.1f}. Di chuyển chuột mượt mà...",
                        })
                        mouse_pos = await smooth_mouse_move(page, mouse_pos, (vx, vy), duration_ms=500)
                        await page.wait_for_timeout(250)
                        await page.mouse.down()
                        await page.wait_for_timeout(80)
                        await page.mouse.up()
                        await page.wait_for_timeout(2000)

                        frame_clicked = await self._capture_frame_base64(page)
                        await self.broadcast("frame", {
                            "step": 4,
                            "caption": "Đã bấm '動画を作成' và mở giao diện tạo video",
                            "image": frame_clicked,
                        })
                    else:
                        await self.broadcast("log", {
                            "level": "warning",
                            "message": "Không tìm thấy nút '動画を作成' (có thể đã ở giao diện tạo video)",
                        })

                    # --- OPTIONAL: Configure Model, Ratio, and Duration in UI ---
                    try:
                        # Model selection
                        is_v25 = "2.5" in self.model.lower()
                        opt_text = "Dreamina Seedance 2.5" if is_v25 else "Dreamina Seedance 2.0"
                        m_btn = None
                        for label in ("モデル 2.0高速", "モデル 2.5", "モデル 2.0"):
                            loc = page.get_by_text(label, exact=False).first
                            if await loc.count() and await loc.is_visible():
                                m_btn = loc
                                break
                        if m_btn:
                            await self.broadcast("log", {"level": "info", "message": f"⚙️ Đang cấu hình Model: {self.model}..."})
                            box = await m_btn.bounding_box()
                            if box:
                                mouse_pos = await smooth_mouse_move(page, mouse_pos, (box["x"] + box["width"]/2, box["y"] + box["height"]/2), duration_ms=250)
                            await m_btn.click(timeout=3000)
                            await page.wait_for_timeout(300)
                            opt_loc = page.get_by_text(opt_text, exact=False).first
                            if await opt_loc.count() and await opt_loc.is_visible():
                                await opt_loc.click(timeout=3000)
                                await page.wait_for_timeout(300)
                    except Exception as err:
                        logger.debug("Model setup skipped: %s", err)

                    try:
                        # Ratio selection
                        if self.ratio:
                            r_btn = page.get_by_text("比率", exact=False).first
                            if await r_btn.count() and await r_btn.is_visible():
                                await self.broadcast("log", {"level": "info", "message": f"📐 Đang cấu hình Tỉ lệ: {self.ratio}..."})
                                await r_btn.click(timeout=2500)
                                await page.wait_for_timeout(300)
                                opt_r = page.get_by_text(self.ratio, exact=True).first
                                if await opt_r.count() and await opt_r.is_visible():
                                    await opt_r.click(timeout=2500)
                                    await page.wait_for_timeout(300)
                    except Exception as err:
                        logger.debug("Ratio setup skipped: %s", err)

                    try:
                        # Duration selection
                        if self.duration:
                            d_str = f"{self.duration}s"
                            d_btn = page.get_by_text(d_str, exact=True).first
                            if await d_btn.count() and await d_btn.is_visible():
                                await self.broadcast("log", {"level": "info", "message": f"⏱️ Đang chọn Thời lượng: {d_str}..."})
                                await d_btn.click(timeout=2500)
                                await page.wait_for_timeout(300)
                    except Exception as err:
                        logger.debug("Duration setup skipped: %s", err)

                    # STEP 5: Locate Prompt Input & Human Type
                    self.current_step = 5
                    self.status_text = "Jev đang nhập prompt tạo video..."
                    await self.broadcast("step", {
                        "step": 5, "total": self.total_steps,
                        "title": "Nhập Prompt Tự Nhiên",
                        "detail": f"Gõ prompt: \"{self.prompt}\"",
                    })

                    prompt_box = await DolaElementLocator.find_prompt_input(page)
                    if not prompt_box:
                        box_el = await page.query_selector("textarea") or await page.query_selector("[contenteditable='true']")
                        if box_el:
                            r = await box_el.bounding_box()
                            if r:
                                prompt_box = {"center": {"x": r["x"] + r["width"] / 2, "y": r["y"] + r["height"] / 2}}

                    if prompt_box:
                        px = prompt_box["center"]["x"]
                        py = prompt_box["center"]["y"]
                        mouse_pos = await smooth_mouse_move(page, mouse_pos, (px, py), duration_ms=400)
                        await page.mouse.click(px, py)
                        await page.wait_for_timeout(200)

                        # Human typing
                        await human_type(page, self.prompt)
                        await page.wait_for_timeout(500)

                        frame_typed = await self._capture_frame_base64(page)
                        await self.broadcast("frame", {
                            "step": 5,
                            "caption": f"Đã nhập prompt vào ô soạn thảo ({len(self.prompt)} ký tự)",
                            "image": frame_typed,
                        })

                    # STEP 6: Submit Prompt & Solve Captcha
                    self.current_step = 6
                    self.status_text = "Đang gửi lệnh tạo video lên Dola..."
                    await self.broadcast("step", {
                        "step": 6, "total": self.total_steps,
                        "title": "Gửi Lệnh Sinh Video",
                        "detail": "Di chuột đến nút gửi và xác nhận tác vụ tạo video",
                    })

                    submit_btn = await DolaElementLocator.find_submit_button(page)
                    if submit_btn:
                        sx = submit_btn["center"]["x"]
                        sy = submit_btn["center"]["y"]
                        await self.broadcast("log", {
                            "level": "info",
                            "message": f"📍 Nút Submit tại x={sx:.1f}, y={sy:.1f}. Di chuyển chuột và bấm gửi...",
                        })
                        mouse_pos = await smooth_mouse_move(page, mouse_pos, (sx, sy), duration_ms=350)
                        await page.wait_for_timeout(200)
                        await page.mouse.click(sx, sy)
                    else:
                        await self.broadcast("log", {
                            "level": "info",
                            "message": "Không thấy nút gửi dạng pixel, thực hiện submit bằng phím Enter...",
                        })

                    # Also press Enter as reliable trigger
                    await page.wait_for_timeout(400)
                    await page.keyboard.press("Enter")
                    await self.broadcast("log", {
                        "level": "info",
                        "message": "📤 Đã kích hoạt lệnh gửi prompt (Click + Enter)!",
                    })
                    await page.wait_for_timeout(1500)

                    frame_submitted = await self._capture_frame_base64(page)
                    await self.broadcast("frame", {
                        "step": 6,
                        "caption": "Đã bấm gửi lệnh tạo video lên Dola",
                        "image": frame_submitted,
                    })

                    # Captcha Solver (up to 3 attempts)
                    for attempt in range(1, 4):
                        c_frame = None
                        for _ in range(10):
                            c_frame = find_captcha_frame(page)
                            if c_frame:
                                break
                            await asyncio.sleep(0.5)
                        if not c_frame:
                            break

                        await self.broadcast("log", {
                            "level": "warn",
                            "message": f"🧩 Phát hiện Captcha slider Dola (lần {attempt}/3). Jev đang tự động giải...",
                        })
                        c_img = await self._capture_frame_base64(page)
                        await self.broadcast("frame", {
                            "step": 6,
                            "caption": f"Đang giải Captcha Slider (Lần {attempt})",
                            "image": c_img,
                        })

                        if await solve_slider(page, c_frame, attempt):
                            await self.broadcast("log", {
                                "level": "success",
                                "message": "✅ Captcha đã được giải thành công!",
                            })
                            await page.wait_for_timeout(3000)
                            break
                        else:
                            await self.broadcast("log", {
                                "level": "warn",
                                "message": f"⚠️ Giải Captcha lần {attempt} chưa khớp, đang thử lại...",
                            })

                    # Acquire real conversation_id from URL
                    conv_id = ""
                    for _ in range(30):
                        await asyncio.sleep(1)
                        tail = page.url.rstrip("/").split("/")[-1]
                        if tail.isdigit():
                            conv_id = tail
                            break

                    if conv_id:
                        await self.broadcast("log", {
                            "level": "success",
                            "message": f"🎉 Tác vụ đã được Dola tiếp nhận! Conversation ID: {conv_id}",
                        })
                    else:
                        await self.broadcast("log", {
                            "level": "warn",
                            "message": "Chưa trích xuất được số ID trên URL, chuyển sang polling theo hội thoại hiện tại...",
                        })

                    # STEP 7: Video Polling on Dola
                    self.current_step = 7
                    self.status_text = "Đang theo dõi & polling video trên Dola..."
                    await self.broadcast("step", {
                        "step": 7, "total": self.total_steps,
                        "title": "Theo Dõi & Polling Video",
                        "detail": f"Đang chờ Dola render video hoàn tất (ID: {conv_id or 'active'})...",
                    })

                    cookies = await context.cookies("https://www.dola.com")
                    ms_token = cookie_value(cookies, "msToken")
                    fp = cookie_value(cookies, "s_v_web_id")

                    poll_start = time.time()
                    poll_timeout = 360  # 6 minutes max
                    video_result = None
                    last_frame_time = 0.0

                    while time.time() - poll_start < poll_timeout:
                        if self._stop_requested:
                            break
                        await asyncio.sleep(4)
                        elapsed = int(time.time() - poll_start)

                        # Capture live preview frame periodically
                        if time.time() - last_frame_time >= 8:
                            last_frame_time = time.time()
                            f_poll = await self._capture_frame_base64(page)
                            progress_pct = min(95, max(5, int(elapsed / 90 * 100)))
                            self.status_text = f"Đang render video trên Dola ({elapsed}s, ~{progress_pct}%)..."
                            await self.broadcast("frame", {
                                "step": 7,
                                "caption": f"Đang render video trên Dola ({elapsed}s)...",
                                "image": f_poll,
                            })
                            await self.broadcast("progress", {
                                "elapsed": elapsed,
                                "percent": progress_pct,
                                "status": self.status_text,
                            })
                            await self.broadcast("log", {
                                "level": "info",
                                "message": f"⏳ Đang render video trên Dola ({elapsed}s, ước tính ~{progress_pct}%)...",
                            })

                        # Poll Dola internal API
                        if conv_id:
                            try:
                                poll = await asyncio.wait_for(
                                    page.evaluate(POLL_JS, {"conversationId": conv_id, "msToken": ms_token, "fp": fp}),
                                    timeout=20,
                                )
                            except Exception as e:
                                logger.debug("Poll eval error: %s", e)
                                continue

                            # Check for account limit/quota errors in response text
                            has_fatal_error = False
                            for txt in poll.get("texts", []):
                                if any(k in txt for k in ("動画生成の1日あたりの上限", "上限", "daily limit", "quota")):
                                    has_fatal_error = True
                                    await self.broadcast("log", {
                                        "level": "error",
                                        "message": f"🚫 Tài khoản [{self.account}] đã chạm hạn mức tạo video hàng ngày của Dola!",
                                    })
                                    break
                                if any(k in txt for k in ("ポイント不足", "insufficient points", "insufficient credits")):
                                    has_fatal_error = True
                                    await self.broadcast("log", {
                                        "level": "error",
                                        "message": f"🚫 Tài khoản [{self.account}] không đủ điểm (credits) để tạo video!",
                                    })
                                    break
                            if has_fatal_error:
                                break

                            # Check for video models & completed videos
                            if poll.get("videos"):
                                v_models = poll.get("videoModels", [])
                                raw_url = poll["videos"][0]
                                unwatermarked = extract_unwatermarked_url(v_models[0] if v_models else "", raw_url)
                                await self.broadcast("log", {
                                    "level": "success",
                                    "message": "🎬 Video đã render xong trên Dola! Đang tải về máy chủ...",
                                })

                                # Download locally
                                local_p = await _download(unwatermarked, self.account)
                                video_web_url = f"/videos/{local_p.name}"

                                f_finish = await self._capture_frame_base64(page)
                                await self.broadcast("frame", {
                                    "step": 7,
                                    "caption": f"Hoàn tất tạo video trong {elapsed}s!",
                                    "image": f_finish,
                                })
                                await self.broadcast("progress", {
                                    "elapsed": elapsed,
                                    "percent": 100,
                                    "status": "Hoàn tất tạo video 100%",
                                })

                                video_result = {
                                    "video_url": video_web_url,
                                    "download_url": unwatermarked,
                                    "local_path": str(local_p),
                                    "conversation_id": conv_id,
                                    "account": self.account,
                                    "elapsed_seconds": elapsed,
                                    "model": self.model,
                                    "ratio": self.ratio,
                                    "duration": self.duration,
                                }
                                break

                    # Final completion broadcast
                    if video_result:
                        self.status_text = "Hoàn tất tạo & tải video thành công!"
                        await self.broadcast("done", {
                            "success": True,
                            "message": f"Video đã được tạo và tải về thành công trong {video_result['elapsed_seconds']}s!",
                            **video_result,
                        })
                        try:
                            t_store = TaskStore(config.DB_PATH)
                            tid = f"video_jev_{conv_id}_{int(time.time())}"
                            t_store.create(
                                task_id=tid,
                                model=self.model,
                                prompt=self.prompt,
                                ratio=self.ratio,
                                duration=self.duration,
                                account=self.account,
                            )
                            t_store.update(
                                task_id=tid,
                                status="completed",
                                video_url=video_result["video_url"],
                                conversation_id=conv_id,
                                finished_at=time.time(),
                            )
                        except Exception as err:
                            logger.warning("Failed to store Jev task: %s", err)
                    else:
                        if not self._stop_requested:
                            self.status_text = "Hết thời gian chờ tạo video (timeout)"
                            await self.broadcast("done", {
                                "success": False,
                                "message": f"Không nhận được video trong {poll_timeout}s. Conversation ID: {conv_id}",
                            })

                finally:
                    await context.close()

        except asyncio.CancelledError:
            self.status_text = "Phiên Live Jev đã bị người dùng hủy"
            await self.broadcast("done", {"success": False, "message": "Phiên Live bị hủy."})
        except Exception as e:
            logger.exception("Jev Live Runner error: %s", e)
            self.status_text = f"Lỗi: {str(e)}"
            await self.broadcast("error", {"message": str(e)})
            await self.broadcast("done", {"success": False, "message": str(e)})
        finally:
            self.is_running = False
            if self._execution_acquired:
                release_account_execution(self.account, config.MAX_CONCURRENCY)
                self._execution_acquired = False
            await self.broadcast("status", {"running": False, "status": self.status_text})


# Global singleton instance
jev_live_session = JevLiveSession()
