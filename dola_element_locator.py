"""Dola.com Element Locator & Indexed DOM Snapshot Engine.

Adapted from Browser Use / Jev Ultrafast DOM snapshotting architecture.
Extracts real-time physical coordinates, roles, labels, categories and bounding boxes
of all interactive elements on Dola.com for ultra-reliable automation.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

# JavaScript code executed in page context to snapshot and locate elements
DOLA_SNAPSHOT_JS = r"""
() => {
  if (!document.body) return { elements: [], categories: {} };

  const isVisible = (el) => {
    if (!el || el.closest('[aria-hidden="true"],[inert]')) return false;
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    if (r.bottom <= 0 || r.top >= window.innerHeight || r.right <= 0 || r.left >= window.innerWidth) return false;
    const style = window.getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none' && style.opacity !== '0';
  };

  const getCleanText = (el) => {
    if (!el) return '';
    return (
      el.getAttribute('aria-label') ||
      el.getAttribute('placeholder') ||
      el.getAttribute('title') ||
      el.getAttribute('alt') ||
      (el.tagName === 'INPUT' ? el.value : el.innerText) ||
      ''
    ).replace(/\s+/g, ' ').trim();
  };

  const interactiveSelectors = [
    'button',
    'a[href]',
    'input',
    'textarea',
    'select',
    '[contenteditable="true"]',
    '[role="button"]',
    '[role="tab"]',
    '[role="combobox"]',
    '[role="menuitem"]',
    '[role="option"]',
    '[role="checkbox"]',
    '[role="radio"]',
    '.semi-button',
    '.semi-select',
    '.semi-switch'
  ];

  const rawElements = Array.from(document.querySelectorAll(interactiveSelectors.join(',')));
  const results = [];
  const categories = {
    video_button: null,
    prompt_input: null,
    send_button: null,
    model_selector: [],
    ratio_selector: [],
    duration_selector: [],
    upload_input: null,
    login_button: null,
    captcha: null
  };

  // 1. File upload input detection
  const fileInput = document.querySelector('input[type="file"]');
  if (fileInput) {
    const r = fileInput.getBoundingClientRect();
    categories.upload_input = {
      tag: 'input',
      type: 'file',
      rect: { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height) },
      center: { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) }
    };
  }

  // 2. Captcha iframe detection
  const captchaIframe = document.querySelector('iframe[src*="bdcaptcha"]') || document.querySelector('iframe[src*="verify"]');
  if (captchaIframe) {
    const r = captchaIframe.getBoundingClientRect();
    categories.captcha = {
      rect: { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height) },
      center: { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) },
      src: captchaIframe.src
    };
  }

  let index = 1;
  for (const el of rawElements) {
    if (!isVisible(el)) continue;
    const r = el.getBoundingClientRect();
    const label = getCleanText(el);
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role') || (tag === 'button' ? 'button' : (tag === 'textarea' || el.isContentEditable ? 'textbox' : 'element'));

    const item = {
      index: index++,
      id: 'e' + (index - 1),
      tag,
      role,
      label,
      value: el.value || '',
      rect: {
        x: Math.round(r.x),
        y: Math.round(r.y),
        width: Math.round(r.width),
        height: Math.round(r.height)
      },
      center: {
        x: Math.round(r.x + r.width / 2),
        y: Math.round(r.y + r.height / 2)
      },
      category: null
    };

    const lLower = label.toLowerCase();

    // Identify Video Create button ("動画を作成", "Create video", "Generate video")
    if (lLower.includes('動画を作成') || lLower.includes('create video') || lLower.includes('generate video') || lLower.includes('動画')) {
      if (item.rect.height < 120 && (tag === 'button' || role === 'button' || el.closest('button'))) {
        item.category = 'video_button';
        if (!categories.video_button) categories.video_button = item;
      }
    }

    // Identify Prompt input box
    if (tag === 'textarea' || el.isContentEditable || (tag === 'input' && (item.rect.width > 220 || lLower.includes('prompt') || lLower.includes('メッセージ')))) {
      item.category = 'prompt_input';
      if (!categories.prompt_input || item.rect.width * item.rect.height > categories.prompt_input.rect.width * categories.prompt_input.rect.height) {
        categories.prompt_input = item;
      }
    }

    // Identify Send button
    if (lLower === '送信' || lLower === 'send' || lLower.includes('generate') || (el.querySelector('svg') && item.rect.width < 60 && item.rect.height < 60)) {
      if (categories.prompt_input && Math.abs(item.center.y - categories.prompt_input.center.y) < 80 && item.center.x > categories.prompt_input.center.x) {
        item.category = 'send_button';
        categories.send_button = item;
      }
    }

    // Identify Model selector
    if (lLower.includes('モデル') || lLower.includes('model') || lLower.includes('seedance') || lLower.includes('2.0') || lLower.includes('2.5')) {
      item.category = 'model_selector';
      categories.model_selector.push(item);
    }

    // Identify Aspect ratio buttons
    if (['16:9', '9:16', '1:1', '4:3', '3:4', '21:9'].some(ratio => lLower.includes(ratio)) || lLower.includes('比率') || lLower.includes('ratio')) {
      item.category = 'ratio_selector';
      categories.ratio_selector.push(item);
    }

    // Identify Duration buttons
    if (['10s', '15s', '30s', '5s'].some(d => lLower.includes(d)) || lLower.includes('秒') || lLower.includes('duration')) {
      item.category = 'duration_selector';
      categories.duration_selector.push(item);
    }

    // Identify Login button
    if (lLower.includes('ログイン') || lLower.includes('login') || lLower.includes('sign in')) {
      item.category = 'login_button';
      if (!categories.login_button) categories.login_button = item;
    }

    results.push(item);
  }

  return {
    url: window.location.href,
    title: document.title,
    viewport: { width: window.innerWidth, height: window.innerHeight },
    total_elements: results.length,
    elements: results,
    categories
  };
}
"""

# JavaScript to render visual bounding box overlays with numbered badges (like Jev Inspector)
HIGHLIGHT_OVERLAY_JS = r"""
(elements) => {
  const existing = document.getElementById('__dola_locator_overlay__');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.id = '__dola_locator_overlay__';
  overlay.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:999999;';

  const categoryColors = {
    video_button: '#10b981',
    prompt_input: '#3b82f6',
    send_button: '#8b5cf6',
    model_selector: '#f59e0b',
    ratio_selector: '#ec4899',
    duration_selector: '#06b6d4',
    login_button: '#ef4444',
    default: 'rgba(66, 133, 244, 0.7)'
  };

  elements.forEach(item => {
    const r = item.rect;
    if (!r || r.width <= 0 || r.height <= 0) return;

    const color = categoryColors[item.category] || categoryColors.default;

    const box = document.createElement('div');
    box.style.cssText = `
      position: absolute;
      left: ${r.x}px;
      top: ${r.y}px;
      width: ${r.width}px;
      height: ${r.height}px;
      border: 2px solid ${color};
      border-radius: 4px;
      box-sizing: border-box;
      background: ${color}15;
    `;

    const badge = document.createElement('div');
    badge.style.cssText = `
      position: absolute;
      left: 0;
      top: -18px;
      background: ${color};
      color: #fff;
      font-size: 10px;
      font-family: monospace;
      font-weight: bold;
      padding: 1px 4px;
      border-radius: 3px;
      white-space: nowrap;
      pointer-events: none;
      box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    `;
    const catLabel = item.category ? ` [${item.category}]` : '';
    badge.textContent = `[${item.index}] ${item.label ? item.label.slice(0, 18) : item.role}${catLabel}`;

    box.appendChild(badge);
    overlay.appendChild(box);
  });

  document.body.appendChild(overlay);
  return true;
}
"""

REMOVE_OVERLAY_JS = r"""
() => {
  const existing = document.getElementById('__dola_locator_overlay__');
  if (existing) existing.remove();
  return true;
}
"""


class DolaElementLocator:
    """High-precision element finder and position resolver for Dola.com pages."""

    @staticmethod
    async def snapshot(page) -> dict[str, Any]:
        """Captures full indexed DOM table of all interactive elements on Dola with pixel coordinates."""
        return await page.evaluate(DOLA_SNAPSHOT_JS)

    @staticmethod
    async def find_element(page, query: str = "", role: str = "", category: str = "") -> dict[str, Any] | None:
        """Finds a specific element on the Dola page by query, role, or category."""
        data = await DolaElementLocator.snapshot(page)
        elements = data.get("elements", [])
        q = query.lower().strip() if query else ""

        # Check category first
        if category and category in data.get("categories", {}):
            cat_match = data["categories"][category]
            if isinstance(cat_match, dict):
                return cat_match
            if isinstance(cat_match, list) and cat_match:
                if not q:
                    return cat_match[0]
                for item in cat_match:
                    if q in item["label"].lower():
                        return item

        for item in elements:
            label = item["label"].lower()
            if role and item["role"] != role:
                continue
            if category and item.get("category") != category:
                continue
            if q and q not in label:
                continue
            return item
        return None

    @staticmethod
    async def click_element(page, element_info: dict[str, Any], click_delay_ms: int = 100) -> bool:
        """Clicks directly at the exact center coordinates of the resolved element."""
        center = element_info.get("center")
        if not center:
            rect = element_info.get("rect", {})
            if "x" in rect and "width" in rect:
                center = {
                    "x": rect["x"] + rect["width"] / 2,
                    "y": rect["y"] + rect["height"] / 2,
                }
        if not center:
            return False

        x, y = center["x"], center["y"]
        await page.mouse.move(x, y)
        await asyncio.sleep(click_delay_ms / 1000)
        await page.mouse.click(x, y)
        return True

    @staticmethod
    async def find_and_click(page, query: str = "", role: str = "", category: str = "", timeout: int = 5000) -> bool:
        """Finds and clicks an element within a timeout period."""
        end_time = asyncio.get_event_loop().time() + (timeout / 1000)
        while asyncio.get_event_loop().time() < end_time:
            el = await DolaElementLocator.find_element(page, query=query, role=role, category=category)
            if el:
                return await DolaElementLocator.click_element(page, el)
            await asyncio.sleep(0.3)
        return False

    @staticmethod
    async def find_video_button(page) -> dict[str, Any] | None:
        """Locates the '動画を作成' / Create Video entry button."""
        el = await DolaElementLocator.find_element(page, category="video_button")
        if not el:
            el = await DolaElementLocator.find_element(page, query="動画を作成")
        if not el:
            el = await DolaElementLocator.find_element(page, query="create video")
        return el

    @staticmethod
    async def find_prompt_input(page) -> dict[str, Any] | None:
        """Locates the main prompt / text input area."""
        el = await DolaElementLocator.find_element(page, category="prompt_input")
        if not el:
            el = await DolaElementLocator.find_element(page, role="textbox")
        return el

    @staticmethod
    async def find_submit_button(page) -> dict[str, Any] | None:
        """Locates the submit / send / generate button on Dola."""
        el = await DolaElementLocator.find_element(page, category="send_button")
        if not el:
            el = await DolaElementLocator.find_element(page, query="送信")
        if not el:
            el = await DolaElementLocator.find_element(page, query="send")
        if not el:
            el = await DolaElementLocator.find_element(page, query="generate")
        if not el:
            # Fallback directly to DOM query
            selectors = [
                'button[type="submit"]',
                'button[aria-label*="送信"]',
                'button[aria-label*="send" i]',
                'button:has(svg path)',
                'button:has(svg)',
                '[role="button"]:has(svg)',
            ]
            for sel in selectors:
                try:
                    btns = await page.query_selector_all(sel)
                    for btn in btns:
                        if await btn.is_visible():
                            r = await btn.bounding_box()
                            if r and r.get("width", 0) > 0 and r.get("height", 0) > 0:
                                return {
                                    "center": {"x": r["x"] + r["width"] / 2, "y": r["y"] + r["height"] / 2},
                                    "rect": r,
                                    "label": "submit",
                                    "category": "send_button",
                                }
                except Exception:
                    continue
        return el

    @staticmethod
    async def find_send_button(page) -> dict[str, Any] | None:
        """Alias for find_submit_button."""
        return await DolaElementLocator.find_submit_button(page)

    @staticmethod
    async def find_model_option(page, model_name: str) -> dict[str, Any] | None:
        """Locates the model selection dropdown / option (e.g. '2.0', '2.5')."""
        return await DolaElementLocator.find_element(page, query=model_name, category="model_selector")

    @staticmethod
    async def find_ratio_option(page, ratio: str) -> dict[str, Any] | None:
        """Locates the aspect ratio option (e.g. '16:9', '9:16', '1:1')."""
        return await DolaElementLocator.find_element(page, query=ratio, category="ratio_selector")

    @staticmethod
    async def find_duration_option(page, duration: int) -> dict[str, Any] | None:
        """Locates the duration option (e.g. '10s', '15s', '30s')."""
        return await DolaElementLocator.find_element(page, query=f"{duration}s", category="duration_selector")

    @staticmethod
    async def highlight_elements(page, filter_category: str | None = None) -> int:
        """Renders visual bounding box overlays with index badges onto the Dola page."""
        data = await DolaElementLocator.snapshot(page)
        elements = data.get("elements", [])
        if filter_category:
            elements = [e for e in elements if e.get("category") == filter_category]
        await page.evaluate(HIGHLIGHT_OVERLAY_JS, elements)
        return len(elements)

    @staticmethod
    async def remove_highlights(page) -> None:
        """Removes visual bounding box overlays."""
        await page.evaluate(REMOVE_OVERLAY_JS)
