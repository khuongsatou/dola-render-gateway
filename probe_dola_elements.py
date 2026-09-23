#!/usr/bin/env python3
"""Probe & Inspect Elements on Dola.com using Indexed DOM Snapshot Engine.

Usage:
  python probe_dola_elements.py [account_name] [--headless] [--highlight] [--output elements.png]
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Auto-switch to project virtual environment if available
_venv_py = Path(__file__).resolve().parent / ".venv" / "bin" / "python"
if _venv_py.exists() and sys.executable != str(_venv_py):
    os.execv(str(_venv_py), [str(_venv_py)] + sys.argv)

from patchright.async_api import async_playwright

import config
from browser import launch_account_context
from dola_element_locator import DolaElementLocator


async def inspect_dola_elements(
    account: str,
    headless: bool = False,
    highlight: bool = True,
    output_image: str = "dola_elements_annotated.png",
    json_output: str = "dola_elements.json",
):
    print(f"[*] Launching browser context for account '{account}'...")
    async with async_playwright() as p:
        try:
            context = await launch_account_context(p, account, headless=headless)
        except Exception as e:
            print(f"[!] Failed to launch account '{account}': {e}", file=sys.stderr)
            return

        try:
            page = context.pages[0] if context.pages else await context.new_page()
            url = "https://www.dola.com/chat"
            print(f"[*] Navigating to {url}...")
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            print("[*] Waiting for UI elements to render...")
            await page.wait_for_timeout(5000)

            # Snapshot elements
            snapshot = await DolaElementLocator.snapshot(page)
            elements = snapshot.get("elements", [])
            categories = snapshot.get("categories", {})

            print(f"\n[+] Total interactive elements discovered: {len(elements)}")
            print(f"{'#':<4} {'Role':<12} {'Category':<18} {'Coordinates (X, Y, W, H)':<26} {'Label':<35}")
            print("-" * 100)

            for el in elements:
                r = el["rect"]
                coord_str = f"({r['x']}, {r['y']}, {r['width']}x{r['height']})"
                cat_str = el["category"] or "-"
                label_str = (el["label"][:32] + "...") if len(el["label"]) > 35 else el["label"]
                print(f"{el['index']:<4} {el['role']:<12} {cat_str:<18} {coord_str:<26} {label_str:<35}")

            print("-" * 100)
            print("\n[+] Key Identified Dola Controls:")
            for cat_name, val in categories.items():
                if val:
                    if isinstance(val, dict):
                        c = val.get("center", {})
                        print(f"  • {cat_name:<18}: ({c.get('x')}, {c.get('y')}) | {val.get('label') or val.get('tag')}")
                    elif isinstance(val, list) and val:
                        print(f"  • {cat_name:<18}: {len(val)} item(s) found:")
                        for sub in val:
                            c = sub.get("center", {})
                            print(f"      - ({c.get('x')}, {c.get('y')}): {sub.get('label')}")

            # Save JSON
            Path(json_output).write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"\n[+] Saved full element metadata to: {json_output}")

            # Visual overlay & screenshot
            if highlight:
                count = await DolaElementLocator.highlight_elements(page)
                await page.wait_for_timeout(1000)
                await page.screenshot(path=output_image)
                print(f"[+] Highlighted {count} elements and saved visual snapshot to: {output_image}")

        finally:
            await context.close()


def main():
    parser = argparse.ArgumentParser(description="Locate and inspect interactive elements on Dola.com")
    parser.add_argument("account", nargs="?", default="", help="Account profile to use (default: first found in accounts/)")
    parser.add_argument("--headless", action="store_true", help="Run in headless browser mode")
    parser.add_argument("--no-highlight", action="store_true", help="Disable visual bounding box highlights")
    parser.add_argument("--output", default="dola_elements_annotated.png", help="Output path for annotated screenshot")
    parser.add_argument("--json", default="dola_elements.json", help="Output path for elements JSON")
    args = parser.parse_args()

    acc = args.account
    if not acc:
        accounts_dir = Path("accounts")
        dirs = [d.name for d in accounts_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if not dirs:
            print("[!] No accounts found in accounts/ directory. Please import or add an account first.", file=sys.stderr)
            sys.exit(1)
        acc = dirs[0]
        print(f"[*] No account specified, using default: '{acc}'")

    asyncio.run(inspect_dola_elements(
        account=acc,
        headless=args.headless,
        highlight=not args.no_highlight,
        output_image=args.output,
        json_output=args.json,
    ))


if __name__ == "__main__":
    main()
