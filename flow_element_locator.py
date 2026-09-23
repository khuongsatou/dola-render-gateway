"""Google Flow (flow.google.com) Element Locator & Indexed DOM Snapshot Engine.

Extracts real-time physical coordinates, roles, labels, categories and bounding boxes
of interactive elements on Google Flow for visual automation and streaming inspection.
"""

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger("flow_locator")

FLOW_SNAPSHOT_JS = r"""
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
    '[role="radio"]'
  ];

  const rawElements = Array.from(document.querySelectorAll(interactiveSelectors.join(',')));
  const results = [];
  const categories = {
    composer_input: null,
    submit_button: null,
    mode_selector: [],
    ratio_selector: [],
    model_selector: [],
    quantity_selector: [],
    add_media_button: null,
    login_button: null
  };

  let index = 1;
  for (const el of rawElements) {
    if (!isVisible(el)) continue;
    const r = el.getBoundingClientRect();
    const label = getCleanText(el);
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role') || (tag === 'button' ? 'button' : (tag === 'textarea' || el.isContentEditable ? 'textbox' : 'element'));

    const item = {
      index: index++,
      id: 'flow_e' + (index - 1),
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

    // 1. Google Flow Composer: "What do you want to create?"
    const isComposerPlaceholder = lLower.includes('what do you want to create') ||
                                  lLower.includes('describe what you want') ||
                                  lLower.includes('create with flow') ||
                                  lLower.includes('prompt');
    const isComposerTag = tag === 'textarea' || el.isContentEditable || (tag === 'input' && item.rect.width > 280);
    if (isComposerTag || isComposerPlaceholder) {
      if (!categories.composer_input || item.rect.y > categories.composer_input.rect.y) {
        item.category = 'composer_input';
        categories.composer_input = item;
      }
    }

    // 2. Submit / Arrow Button (near composer)
    const isArrowSubmit = (
      lLower === 'create' ||
      lLower === 'generate' ||
      lLower === 'submit' ||
      lLower.includes('arrow') ||
      el.getAttribute('aria-label')?.toLowerCase().includes('send') ||
      el.getAttribute('aria-label')?.toLowerCase().includes('generate') ||
      el.querySelector('svg') && item.rect.width <= 64 && item.rect.height <= 64
    );
    if (isArrowSubmit && (tag === 'button' || role === 'button' || el.closest('button'))) {
      if (item.rect.y > window.innerHeight * 0.5) {
        item.category = 'submit_button';
        categories.submit_button = item;
      }
    }

    // 3. Mode selector: "Image" vs "Video"
    if (lLower === 'image' || lLower === 'video' || lLower.includes('image mode') || lLower.includes('video mode')) {
      item.category = 'mode_selector';
      categories.mode_selector.push(item);
    }

    // 4. Aspect ratio options: 16:9, 4:3, 1:1, 3:4, 9:16
    if (['16:9', '9:16', '1:1', '4:3', '3:4'].some(ratio => lLower.includes(ratio))) {
      item.category = 'ratio_selector';
      categories.ratio_selector.push(item);
    }

    // 5. Model selector: Nano Banana 2, dynamic model dropdown
    if (lLower.includes('banana') || lLower.includes('model') || lLower.includes('nano banana')) {
      item.category = 'model_selector';
      categories.model_selector.push(item);
    }

    // 6. Quantity: x1, x2, x3, x4
    if (['x1', 'x2', 'x3', 'x4'].some(q => lLower === q || lLower.includes(q))) {
      item.category = 'quantity_selector';
      categories.quantity_selector.push(item);
    }

    // 7. Add media reference: "+"
    if ((label === '+' || el.getAttribute('aria-label')?.includes('add') || el.getAttribute('aria-label')?.includes('media')) && item.rect.width < 50) {
      item.category = 'add_media_button';
      categories.add_media_button = item;
    }

    // 8. Google Sign-in detection
    if (lLower.includes('sign in') || lLower.includes('đăng nhập') || lLower.includes('google account')) {
      item.category = 'login_button';
      if (!categories.login_button) categories.login_button = item;
    }

    results.push(item);
  }

  // Fallback: If composer_input wasn't found by text, pick largest editable element in bottom half
  if (!categories.composer_input) {
    const editables = results.filter(
      r => (r.tag === 'textarea' || r.role === 'textbox' || r.tag === 'input') && r.rect.y > window.innerHeight * 0.4
    );
    if (editables.length > 0) {
      editables.sort((a, b) => (b.rect.width * b.rect.height) - (a.rect.width * a.rect.height));
      categories.composer_input = editables[0];
      editables[0].category = 'composer_input';
    }
  }

  return {
    url: window.location.href,
    title: document.title,
    viewport: { width: window.innerWidth, height: window.innerHeight },
    total_elements: results.length,
    categories,
    elements: results
  };
}
"""

FLOW_HIGHLIGHT_JS = r"""
(data) => {
  document.querySelectorAll('.flow-jev-badge, .flow-jev-box').forEach(e => e.remove());

  const categoryColors = {
    composer_input: '#7C3AED',
    submit_button: '#34C759',
    mode_selector: '#0A84FF',
    ratio_selector: '#FF9500',
    model_selector: '#AF52DE',
    quantity_selector: '#FF2D55',
    add_media_button: '#5856D6',
    login_button: '#FF3B30'
  };

  const container = document.createElement('div');
  container.id = 'flow-jev-overlay-root';
  container.style.position = 'fixed';
  container.style.top = '0';
  container.style.left = '0';
  container.style.width = '100vw';
  container.style.height = '100vh';
  container.style.pointerEvents = 'none';
  container.style.zIndex = '9999999';

  let count = 0;
  for (const item of (data.elements || [])) {
    if (!item.category && item.index > 30) continue;
    const color = categoryColors[item.category] || 'rgba(124, 58, 237, 0.6)';

    const box = document.createElement('div');
    box.className = 'flow-jev-box';
    box.style.position = 'absolute';
    box.style.left = item.rect.x + 'px';
    box.style.top = item.rect.y + 'px';
    box.style.width = item.rect.width + 'px';
    box.style.height = item.rect.height + 'px';
    box.style.border = '2px solid ' + color;
    box.style.borderRadius = '6px';
    box.style.boxSizing = 'border-box';
    box.style.pointerEvents = 'none';

    const badge = document.createElement('div');
    badge.className = 'flow-jev-badge';
    badge.style.position = 'absolute';
    badge.style.left = item.rect.x + 'px';
    badge.style.top = Math.max(0, item.rect.y - 18) + 'px';
    badge.style.background = color;
    badge.style.color = '#fff';
    badge.style.fontSize = '10px';
    badge.style.fontFamily = 'monospace';
    badge.style.fontWeight = 'bold';
    badge.style.padding = '1px 5px';
    badge.style.borderRadius = '3px';
    badge.style.whiteSpace = 'nowrap';
    badge.style.boxShadow = '0 2px 4px rgba(0,0,0,0.4)';
    badge.style.pointerEvents = 'none';

    const labelSnippet = (item.label || item.role).slice(0, 20);
    badge.textContent = `[${item.index}] ${labelSnippet}` + (item.category ? ` • ${item.category}` : '');

    container.appendChild(box);
    container.appendChild(badge);
    count++;
  }

  document.body.appendChild(container);
  return count;
}
"""

FLOW_REMOVE_HIGHLIGHT_JS = r"""
() => {
  const root = document.getElementById('flow-jev-overlay-root');
  if (root) root.remove();
  document.querySelectorAll('.flow-jev-badge, .flow-jev-box').forEach(e => e.remove());
}
"""


class FlowElementLocator:
    """Provides DOM scanning, indexing and highlighting for Google Flow."""

    @staticmethod
    async def snapshot(page) -> dict[str, Any]:
        try:
            return await page.evaluate(FLOW_SNAPSHOT_JS)
        except Exception as e:
            logger.error("Failed to snapshot Google Flow DOM: %s", e)
            return {"elements": [], "categories": {}, "total_elements": 0}

    @staticmethod
    async def highlight_elements(page) -> int:
        try:
            snap = await FlowElementLocator.snapshot(page)
            return await page.evaluate(FLOW_HIGHLIGHT_JS, snap)
        except Exception as e:
            logger.error("Failed to highlight Google Flow elements: %s", e)
            return 0

    @staticmethod
    async def remove_highlights(page):
        try:
            await page.evaluate(FLOW_REMOVE_HIGHLIGHT_JS)
        except Exception:
            pass

    @staticmethod
    async def find_composer(page) -> dict[str, Any] | None:
        snap = await FlowElementLocator.snapshot(page)
        return snap.get("categories", {}).get("composer_input")

    @staticmethod
    async def find_submit_button(page) -> dict[str, Any] | None:
        snap = await FlowElementLocator.snapshot(page)
        return snap.get("categories", {}).get("submit_button")
