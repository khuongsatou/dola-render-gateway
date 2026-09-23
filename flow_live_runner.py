"""Flow Live Runner: Real-time visual automation & streaming engine for Google Flow (flow.google.com).

Provides step-by-step human-like operations (smooth bezier mouse movement,
indexed DOM element overlays, keystroke typing on Flow Composer) and real-time screen frame
broadcasting via Server-Sent Events (SSE) to the Web Dashboard.
"""

import asyncio
import base64
import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Any, AsyncGenerator

from patchright.async_api import async_playwright

from account_locks import acquire_account_execution, release_account_execution
import config
from browser import launch_account_context
from flow_element_locator import FlowElementLocator

logger = logging.getLogger("flow_live")


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
        delay = random.uniform(0.03, 0.08)
        if ch in (" ", ",", ".", "!"):
            delay += 0.08
        await asyncio.sleep(delay)


class FlowLiveSession:
    def __init__(self):
        self.is_running: bool = False
        self.account: str = ""
        self.mode: str = "image"  # "image" | "video" | "inspect"
        self.prompt: str = ""
        self.model: str = "Nano Banana 2"
        self.ratio: str = "16:9"
        self.quantity: str = "x1"
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
        await self.broadcast("status", {"running": False, "status": "Phiên Live Flow đã dừng"})

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self.is_running,
            "account": self.account,
            "mode": self.mode,
            "prompt": self.prompt,
            "model": self.model,
            "ratio": self.ratio,
            "quantity": self.quantity,
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
        mode: str = "image",
        model: str = "Nano Banana 2",
        ratio: str = "16:9",
        quantity: str = "x1",
    ) -> dict[str, Any]:
        if self.is_running:
            return {"ok": False, "error": "Một phiên Live Flow đang chạy. Vui lòng dừng phiên trước."}

        self.account = account
        self.prompt = prompt or "A futuristic neon cyber city with flying vehicles in rainy night, cinematic lighting, 8k"
        self.mode = mode
        self.model = model or "Nano Banana 2"
        self.ratio = ratio or "16:9"
        self.quantity = quantity or "x1"
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
            "quantity": self.quantity,
        }

    async def _capture_frame_base64(self, page, quality: int = 80) -> str:
        """Takes a JPEG screenshot and converts to data URL."""
        raw = await page.screenshot(type="jpeg", quality=quality)
        b64 = base64.b64encode(raw).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"

    async def _resolve_browser_context(self, p, account: str):
        """Resolves existing profile from accounts/ or native Chrome user data directory."""
        # 1. Check local accounts directory
        acc_dir = Path("accounts") / account
        if acc_dir.exists():
            return await launch_account_context(p, account, headless=True, incognito=False)

        # 2. Check native Chrome profile
        chrome_root = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
        candidate_dir = chrome_root / account
        if candidate_dir.exists():
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(candidate_dir),
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
                viewport={"width": 1280, "height": 800},
            )
            return context

        # 3. Fallback to first available account in accounts/
        for pth in Path("accounts").iterdir():
            if pth.is_dir() and not pth.name.startswith("."):
                return await launch_account_context(p, pth.name, headless=True, incognito=False)

        raise FileNotFoundError(f"Không tìm thấy thư mục profile cho '{account}'")

    async def _run_workflow(self):
        mouse_pos = (300.0, 200.0)
        try:
            await self.broadcast("status", {"running": True, "status": f"Khởi tạo Chrome Profile cho {self.account}..."})

            # STEP 1: Launch Profile Context
            self.current_step = 1
            self.status_text = f"Mở Google Chrome Profile: {self.account}"
            await self.broadcast("step", {
                "step": 1, "total": self.total_steps,
                "title": "Mở Profile Chrome",
                "detail": f"Khởi động persistent context cho tài khoản {self.account}",
            })

            async with async_playwright() as p:
                context = await self._resolve_browser_context(p, self.account)
                try:
                    page = context.pages[0] if context.pages else await context.new_page()
                    await page.set_viewport_size({"width": 1280, "height": 800})

                    # STEP 2: Navigate to Google Flow
                    self.current_step = 2
                    self.status_text = "Đang tải Google Flow (https://flow.google.com/)..."
                    await self.broadcast("step", {
                        "step": 2, "total": self.total_steps,
                        "title": "Điều Hướng Google Flow",
                        "detail": f"Truy cập https://flow.google.com/ với Profile [{self.account}]",
                    })

                    try:
                        await page.goto("https://flow.google.com/", timeout=60000, wait_until="domcontentloaded")
                    except Exception as e:
                        logger.warning("Goto flow warning: %s", e)

                    await page.wait_for_timeout(3500)

                    # Check Google session
                    cookies = await context.cookies("https://google.com")
                    has_sid = any(c.get("name") in ("SID", "SSID", "__Secure-1PSID") for c in cookies)
                    if has_sid:
                        await self.broadcast("log", {
                            "level": "success",
                            "message": f"🔐 Profile [{self.account}] đã xác thực Google Account (SID active)",
                        })
                    else:
                        await self.broadcast("log", {
                            "level": "warn",
                            "message": f"⚠️ Profile [{self.account}] chưa phát hiện session Google SID. Đang kiểm tra giao diện...",
                        })

                    frame_initial = await self._capture_frame_base64(page)
                    await self.broadcast("frame", {
                        "step": 2,
                        "caption": f"Google Flow đã tải thành công với Profile: {self.account}",
                        "image": frame_initial,
                    })

                    # STEP 3: Jev Visual DOM Scan & Indexing
                    self.current_step = 3
                    self.status_text = "Jev đang quét DOM, phân tích Composer Google Flow..."
                    await self.broadcast("step", {
                        "step": 3, "total": self.total_steps,
                        "title": "Jev DOM Scan & Indexing",
                        "detail": "Trích xuất tọa độ Composer, Mode switch, Model, và Ratio",
                    })

                    snapshot = await FlowElementLocator.snapshot(page)
                    total_el = snapshot.get("total_elements", 0)
                    cats = list(snapshot.get("categories", {}).keys())

                    await self.broadcast("log", {
                        "level": "info",
                        "message": f"🎯 Jev phát hiện {total_el} phần tử tương tác trên Google Flow (Categories: {', '.join(cats)})",
                    })

                    # Render Visual Bounding Boxes overlay
                    count_badges = await FlowElementLocator.highlight_elements(page)
                    await page.wait_for_timeout(400)
                    frame_overlay = await self._capture_frame_base64(page)
                    await self.broadcast("frame", {
                        "step": 3,
                        "caption": f"Google Flow Visual Bounding Boxes ({count_badges} badges)",
                        "image": frame_overlay,
                        "elements_count": total_el,
                    })
                    await FlowElementLocator.remove_highlights(page)

                    if self.mode == "inspect":
                        self.status_text = "Hoàn tất quét & trực quan hóa phần tử Google Flow"
                        await self.broadcast("step", {
                            "step": self.total_steps, "total": self.total_steps,
                            "title": "Hoàn Tất Quét DOM",
                            "detail": f"Đã quét và lập chỉ mục thành công {total_el} phần tử trên Flow",
                        })
                        await self.broadcast("done", {
                            "success": True,
                            "message": f"Đã quét thành công {total_el} phần tử trên Google Flow!",
                        })
                        return

                    # STEP 4: Configure Output Mode & Ratio
                    self.current_step = 4
                    self.status_text = f"Cấu hình Output: {self.mode.upper()}, Tỉ lệ: {self.ratio}..."
                    await self.broadcast("step", {
                        "step": 4, "total": self.total_steps,
                        "title": "Cấu Hình Mode & Tỉ Lệ",
                        "detail": f"Chọn chế độ {self.mode.upper()} và tỉ lệ {self.ratio}",
                    })

                    # Try switching Image / Video mode if available in UI
                    try:
                        target_mode_label = "Image" if self.mode == "image" else "Video"
                        mode_btn = page.get_by_role("button", name=target_mode_label, exact=False).first
                        if not await mode_btn.count():
                            mode_btn = page.get_by_text(target_mode_label, exact=True).first

                        if await mode_btn.count() and await mode_btn.is_visible():
                            box = await mode_btn.bounding_box()
                            if box:
                                mouse_pos = await smooth_mouse_move(
                                    page, mouse_pos,
                                    (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2),
                                    duration_ms=300
                                )
                                await mode_btn.click()
                                await page.wait_for_timeout(300)
                                await self.broadcast("log", {
                                    "level": "info",
                                    "message": f"⚙️ Đã chọn Chế độ: {target_mode_label}",
                                })
                    except Exception as err:
                        logger.debug("Mode setup note: %s", err)

                    # Try configuring Aspect Ratio
                    try:
                        if self.ratio:
                            r_btn = page.get_by_text(self.ratio, exact=True).first
                            if await r_btn.count() and await r_btn.is_visible():
                                await r_btn.click()
                                await self.broadcast("log", {
                                    "level": "info",
                                    "message": f"📐 Đã cấu hình Tỉ lệ Flow: {self.ratio}",
                                })
                    except Exception as err:
                        logger.debug("Ratio setup note: %s", err)

                    await self._apply_model_and_quantity(page)

                    frame_configured = await self._capture_frame_base64(page)
                    await self.broadcast("frame", {
                        "step": 4,
                        "caption": f"Đã cấu hình Output: {self.mode.upper()} | {self.ratio}",
                        "image": frame_configured,
                    })

                    # STEP 5: Locate Flow Composer ("What do you want to create?") & Human Type
                    self.current_step = 5
                    self.status_text = "Di chuyển chuột và gõ prompt vào Flow Composer..."
                    await self.broadcast("step", {
                        "step": 5, "total": self.total_steps,
                        "title": "Nhập Prompt Vào Composer",
                        "detail": f"Gõ prompt: \"{self.prompt}\"",
                    })

                    composer_box = await FlowElementLocator.find_composer(page)
                    target_input = None

                    # If not found by bounding box, query directly
                    if not composer_box:
                        for sel in [
                            'textarea[placeholder*="What do you want to create"]',
                            'textarea',
                            '[contenteditable="true"]',
                            'input[placeholder*="What do you want to create"]'
                        ]:
                            loc = page.locator(sel).last
                            if await loc.count() and await loc.is_visible():
                                target_input = loc
                                r = await loc.bounding_box()
                                if r:
                                    composer_box = {"center": {"x": r["x"] + r["width"] / 2, "y": r["y"] + r["height"] / 2}}
                                break

                    if composer_box:
                        cx = composer_box["center"]["x"]
                        cy = composer_box["center"]["y"]
                        await self.broadcast("log", {
                            "level": "info",
                            "message": f"📍 Đã định vị Flow Composer tại x={cx:.1f}, y={cy:.1f}. Di chuột Bezier...",
                        })
                        mouse_pos = await smooth_mouse_move(page, mouse_pos, (cx, cy), duration_ms=450)
                        await page.mouse.click(cx, cy)
                        await page.wait_for_timeout(250)

                        # Type human prompt
                        await human_type(page, self.prompt)
                        await page.wait_for_timeout(400)

                        frame_typed = await self._capture_frame_base64(page)
                        await self.broadcast("frame", {
                            "step": 5,
                            "caption": f"Đã nhập prompt vào Flow Composer ({len(self.prompt)} ký tự)",
                            "image": frame_typed,
                        })
                    else:
                        await self.broadcast("log", {
                            "level": "warn",
                            "message": "Không tìm thấy ô Composer theo pixel, thực hiện gõ phím toàn trang...",
                        })
                        await human_type(page, self.prompt)

                    # STEP 6: Submit Arrow Click
                    self.current_step = 6
                    self.status_text = "Gửi lệnh tạo lên Google Flow..."
                    await self.broadcast("step", {
                        "step": 6, "total": self.total_steps,
                        "title": "Gửi Lệnh Tạo",
                        "detail": "Bấm nút mũi tên Submit trong Composer",
                    })

                    submit_btn = await FlowElementLocator.find_submit_button(page)
                    if submit_btn:
                        sx = submit_btn["center"]["x"]
                        sy = submit_btn["center"]["y"]
                        await self.broadcast("log", {
                            "level": "info",
                            "message": f"📍 Nút Submit Arrow tại x={sx:.1f}, y={sy:.1f}. Di chuột và nhấn gửi...",
                        })
                        mouse_pos = await smooth_mouse_move(page, mouse_pos, (sx, sy), duration_ms=300)
                        await page.wait_for_timeout(150)
                        await page.mouse.click(sx, sy)
                    else:
                        await self.broadcast("log", {
                            "level": "info",
                            "message": "Gửi lệnh qua phím Enter...",
                        })

                    # Reliable Enter trigger
                    await page.wait_for_timeout(300)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(1500)

                    frame_submitted = await self._capture_frame_base64(page)
                    await self.broadcast("frame", {
                        "step": 6,
                        "caption": "Đã bấm gửi lệnh tạo nội dung lên Google Flow",
                        "image": frame_submitted,
                    })

                    # STEP 7: Track Flow Generation & Preview
                    self.current_step = 7
                    self.status_text = "Theo dõi tiến trình sinh ảnh/video trên Google Flow..."
                    await self.broadcast("step", {
                        "step": 7, "total": self.total_steps,
                        "title": "Theo Dõi & Kết Quả",
                        "detail": "Đang theo dõi sản phẩm tạo trên Google Flow...",
                    })

                    start_poll = time.time()
                    poll_duration = 30  # Watch live for 30s
                    last_frame_time = 0.0

                    while time.time() - start_poll < poll_duration:
                        if self._stop_requested:
                            break
                        await asyncio.sleep(2)
                        elapsed = int(time.time() - start_poll)

                        if time.time() - last_frame_time >= 5:
                            last_frame_time = time.time()
                            f_poll = await self._capture_frame_base64(page)
                            pct = min(95, int(elapsed / poll_duration * 100))
                            self.status_text = f"Đang sinh trên Google Flow ({elapsed}s, ~{pct}%)..."
                            await self.broadcast("frame", {
                                "step": 7,
                                "caption": self.status_text,
                                "image": f_poll,
                            })
                            await self.broadcast("progress", {
                                "elapsed": elapsed,
                                "percent": pct,
                                "status": self.status_text,
                            })

                    # Final finish frame
                    frame_final = await self._capture_frame_base64(page)
                    await self.broadcast("frame", {
                        "step": 7,
                        "caption": "Hoàn tất phiên Live trên Google Flow!",
                        "image": frame_final,
                    })
                    await self.broadcast("progress", {
                        "elapsed": int(time.time() - start_poll),
                        "percent": 100,
                        "status": "Hoàn tất 100%",
                    })

                    self.status_text = "Hoàn tất phiên tương tác Google Flow thành công!"
                    await self.broadcast("done", {
                        "success": True,
                        "message": f"Đã gửi prompt và thao tác thành công trên Google Flow với profile [{self.account}]!",
                        "account": self.account,
                        "mode": self.mode,
                        "ratio": self.ratio,
                        "prompt": self.prompt,
                    })

                finally:
                    await context.close()

        except asyncio.CancelledError:
            self.status_text = "Phiên Live Flow đã bị người dùng hủy"
            await self.broadcast("done", {"success": False, "message": "Phiên Live bị hủy."})
        except Exception as e:
            logger.exception("Flow Live Runner error: %s", e)
            self.status_text = f"Lỗi: {str(e)}"
            await self.broadcast("error", {"message": str(e)})
            await self.broadcast("done", {"success": False, "message": str(e)})
        finally:
            self.is_running = False
            if self._execution_acquired:
                release_account_execution(self.account, config.MAX_CONCURRENCY)
                self._execution_acquired = False
            await self.broadcast("status", {"running": False, "status": self.status_text})

    async def _apply_model_and_quantity(self, page):
        """Applies the selected Flow model and quantity when their controls are visible."""
        for category, value, label in (
            ("model_selector", self.model, "Model"),
            ("quantity_selector", self.quantity, "Số lượng"),
        ):
            try:
                selected = await FlowElementLocator.select_category_option(page, category, value)
                if selected:
                    await self.broadcast("log", {
                        "level": "info",
                        "message": f"Đã chọn {label}: {value}",
                    })
                else:
                    await self.broadcast("log", {
                        "level": "warn",
                        "message": f"Không tìm thấy điều khiển {label}={value}; giữ cấu hình hiện tại.",
                    })
            except Exception as err:
                logger.debug("%s setup note: %s", label, err)


# Global singleton instance for Flow
flow_live_session = FlowLiveSession()
