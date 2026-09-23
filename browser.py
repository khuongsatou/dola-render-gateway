"""Patchright persistent context launcher: Explicit proxy and anti-detection parameters."""
from pathlib import Path

import config

LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
]


async def launch_account_context(p, account: str, headless: bool = None, use_extension: bool = False, incognito: bool = None):
    """Launches accounts/<account> profile, returns BrowserContext. Caller must close.

    p: async_playwright() instance
    headless: None = uses config.HEADLESS
    incognito: None = uses config.INCOGNITO
    """
    profile_dir = Path("accounts") / account
    if not profile_dir.exists():
        raise FileNotFoundError(
            f"Account profile does not exist: {profile_dir} (run python add_account.py {account} first)"
        )
    launch_headless = config.HEADLESS if headless is None else headless
    if incognito is not None:
        launch_incognito = incognito
    else:
        acc_incognito = False
        try:
            import sqlite3
            conn = sqlite3.connect(config.POOL_DB_PATH)
            row = conn.execute("SELECT incognito FROM accounts_meta WHERE name=?", (account,)).fetchone()
            if row and row[0]:
                acc_incognito = True
            conn.close()
        except Exception:
            pass
        launch_incognito = acc_incognito or config.INCOGNITO

    args = list(LAUNCH_ARGS)
    if launch_incognito:
        args.append("--incognito")

    if use_extension:
        if not config.EXTENSION_ENABLED:
            raise RuntimeError("Dola extension is disabled (DOLA_EXTENSION_ENABLED=0)")
        extension_dir = Path(config.EXTENSION_DIR).resolve()
        if not extension_dir.exists():
            raise FileNotFoundError(f"Dola extension directory does not exist: {extension_dir}")
        # Chromium debugger extension requires headed window to intercept skill/action-bar responses
        launch_headless = False
        args.extend([
            f"--disable-extensions-except={extension_dir}",
            f"--load-extension={extension_dir}",
        ])
        if launch_incognito:
            args.append("--enable-incognito-extensions")
    kwargs = {
        "headless": launch_headless,
        "args": args,
        "locale": "ja-JP",
        "timezone_id": "Asia/Tokyo",
    }
    if config.PROXY:
        kwargs["proxy"] = {"server": config.PROXY}
    context = await p.chromium.launch_persistent_context(str(profile_dir), **kwargs)
    cookies_file = profile_dir / "cookies.json"
    if cookies_file.exists():
        try:
            import json
            raw_cookies = json.loads(cookies_file.read_text(encoding="utf-8"))
            if isinstance(raw_cookies, list) and raw_cookies:
                await context.add_cookies(raw_cookies)
        except Exception:
            pass
    return context


def cookie_value(cookies: list, name: str) -> str:
    """Extracts cookie value from context.cookies() result."""
    return next((c["value"] for c in cookies if c["name"] == name and c["value"]), "")


async def check_login_state(account: str) -> bool:
    """Opens Dola in headless mode and checks whether session is active."""
    from patchright.async_api import async_playwright
    async with async_playwright() as p:
        context = await launch_account_context(p, account)
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto("https://www.dola.com/chat", timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)
            cookies = await context.cookies("https://www.dola.com")
            if not cookie_value(cookies, "sessionid"):
                return False
            return bool(await page.evaluate(
                """() => !!(document.querySelector('textarea')
                        || document.querySelector('[contenteditable="true"]')
                        || document.querySelector('input[type="text"]'))"""
            ))
        finally:
            await context.close()
