"""Test manual human-like operations on Dola.com using Jev Ultrafast element locator.

Performs:
1. Initial page load & element snapshot.
2. Smooth human-like mouse glide & hover.
3. Clicking '動画を作成' (Create Video) using precise pixel coordinates.
4. Rendering Jev numbered element bounding boxes and badge overlays.
5. Smooth mouse move into prompt input & human keystroke typing.
6. Hovering the submit action element.
Captures sequential proof screenshots for each step.
"""

import asyncio
import math
import random
from pathlib import Path
from patchright.async_api import async_playwright

from browser import launch_account_context
from dola_element_locator import DolaElementLocator

STEP_DIR = Path("artifacts/jev_manual_steps")
STEP_DIR.mkdir(parents=True, exist_ok=True)


async def smooth_mouse_move(page, start_pos: tuple[float, float], end_pos: tuple[float, float], duration_ms: int = 400):
    """Interpolates mouse movement along an ease-out curve like a human hand."""
    steps = max(10, int(duration_ms / 20))
    sx, sy = start_pos
    ex, ey = end_pos

    # Add slight natural bezier curvature
    mid_x = (sx + ex) / 2 + random.uniform(-30, 30)
    mid_y = (sy + ey) / 2 + random.uniform(-20, 20)

    for i in range(1, steps + 1):
        t = i / steps
        # Quadratic bezier curve
        bx = (1 - t) ** 2 * sx + 2 * (1 - t) * t * mid_x + t ** 2 * ex
        by = (1 - t) ** 2 * sy + 2 * (1 - t) * t * mid_y + t ** 2 * ey
        await page.mouse.move(bx, by)
        await asyncio.sleep(0.015)

    return (ex, ey)


async def human_type(page, text: str):
    """Types text with natural human variance and keystroke delays."""
    for ch in text:
        await page.keyboard.type(ch)
        delay = random.uniform(0.04, 0.11)
        if ch in (" ", ",", "."):
            delay += 0.08  # Micro pause on punctuation/spaces
        await asyncio.sleep(delay)


async def run_manual_test():
    account = "vankhuong240_p185"
    print(f"[*] Starting Jev human-like manual operations test with account: {account}")

    mouse_pos = (200.0, 200.0)

    async with async_playwright() as p:
        # Launch persistent context
        context = await launch_account_context(p, account, headless=True)
        page = context.pages[0] if context.pages else await context.new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})

        # -------------------------------------------------------------
        # STEP 1: Load page & snapshot interactive elements
        # -------------------------------------------------------------
        print("\n[Step 1] Loading https://www.dola.com/chat...")
        await page.goto("https://www.dola.com/chat", timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        snapshot1 = await DolaElementLocator.snapshot(page)
        print(f"  -> Page Title: {await page.title()}")
        print(f"  -> Total interactive elements detected: {snapshot1['total_elements']}")
        print(f"  -> Categorized controls: {list(snapshot1['categories'].keys())}")

        step1_file = STEP_DIR / "01_initial_page.png"
        await page.screenshot(path=str(step1_file))
        print(f"  -> Saved Step 1 screenshot: {step1_file}")

        # -------------------------------------------------------------
        # STEP 2: Find '動画を作成' button & perform human mouse move + click
        # -------------------------------------------------------------
        print("\n[Step 2] Locating '動画を作成' (Create Video) button via Jev...")
        video_btn = await DolaElementLocator.find_video_button(page)
        if not video_btn:
            raise RuntimeError("Could not find '動画を作成' button via Jev locator!")

        vx = video_btn["center"]["x"]
        vy = video_btn["center"]["y"]
        print(f"  -> Found button at coordinates: x={vx}, y={vy} (size {video_btn['rect']['width']}x{video_btn['rect']['height']})")

        print("  -> Gliding mouse like human to button...")
        mouse_pos = await smooth_mouse_move(page, mouse_pos, (vx, vy), duration_ms=500)
        await page.wait_for_timeout(300)  # Human hover pause before clicking

        print("  -> Clicking '動画を作成' button...")
        await page.mouse.down()
        await page.wait_for_timeout(80)
        await page.mouse.up()
        await page.wait_for_timeout(2000)

        step2_file = STEP_DIR / "02_clicked_video_mode.png"
        await page.screenshot(path=str(step2_file))
        print(f"  -> Saved Step 2 screenshot: {step2_file}")

        # -------------------------------------------------------------
        # STEP 3: Render Jev Visual Bounding Box Overlay with Badges
        # -------------------------------------------------------------
        print("\n[Step 3] Rendering Jev Visual Bounding Box Overlays onto DOM...")
        count = await DolaElementLocator.highlight_elements(page)
        print(f"  -> Rendered {count} bounding box badges on screen!")

        step3_file = STEP_DIR / "03_jev_element_overlay.png"
        await page.screenshot(path=str(step3_file))
        print(f"  -> Saved Step 3 screenshot: {step3_file}")

        # Clean overlay so typing is unobstructed
        await DolaElementLocator.remove_highlights(page)
        await page.wait_for_timeout(500)

        # -------------------------------------------------------------
        # STEP 4: Locate Prompt Input & Type like a Human
        # -------------------------------------------------------------
        print("\n[Step 4] Locating Prompt Box via Jev...")
        prompt_box = await DolaElementLocator.find_prompt_input(page)
        if not prompt_box:
            # Fallback to selector
            box_el = await page.query_selector("textarea") or await page.query_selector("[contenteditable='true']")
            if box_el:
                r = await box_el.bounding_box()
                prompt_box = {"center": {"x": r["x"] + r["width"] / 2, "y": r["y"] + r["height"] / 2}}

        if prompt_box:
            px = prompt_box["center"]["x"]
            py = prompt_box["center"]["y"]
            print(f"  -> Gliding mouse to prompt box at x={px}, y={py}...")
            mouse_pos = await smooth_mouse_move(page, mouse_pos, (px, py), duration_ms=450)
            await page.mouse.click(px, py)
            await page.wait_for_timeout(300)

            test_prompt = "A magical cherry blossom garden with glowing lanterns in the rain"
            print(f"  -> Typing prompt with human keystroke rhythm: '{test_prompt}'...")
            await human_type(page, test_prompt)
            await page.wait_for_timeout(1000)

        step4_file = STEP_DIR / "04_prompt_typed.png"
        await page.screenshot(path=str(step4_file))
        print(f"  -> Saved Step 4 screenshot: {step4_file}")

        # -------------------------------------------------------------
        # STEP 5: Locate Send Button & Hover
        # -------------------------------------------------------------
        print("\n[Step 5] Locating Send / Submit button via Jev...")
        snapshot_after = await DolaElementLocator.snapshot(page)
        send_btn = snapshot_after["categories"].get("send_button")
        if not send_btn:
            send_btn = await DolaElementLocator.find_element(page, query="send") or await DolaElementLocator.find_element(page, role="button", query="送信")

        if send_btn:
            sx = send_btn["center"]["x"]
            sy = send_btn["center"]["y"]
            print(f"  -> Gliding mouse to Send button at x={sx}, y={sy}...")
            mouse_pos = await smooth_mouse_move(page, mouse_pos, (sx, sy), duration_ms=400)
            await page.wait_for_timeout(500)

        step5_file = STEP_DIR / "05_ready_to_send.png"
        await page.screenshot(path=str(step5_file))
        print(f"  -> Saved Step 5 screenshot: {step5_file}")

        print("\n=== ALL JEV MANUAL HUMAN-LIKE OPERATIONS COMPLETED SUCCESSFULLY! ===")
        await context.close()


if __name__ == "__main__":
    asyncio.run(run_manual_test())
