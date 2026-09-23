import unittest
from pathlib import Path

from patchright.async_api import async_playwright


class DashboardMobileTests(unittest.IsolatedAsyncioTestCase):
    async def test_dashboard_does_not_overflow_horizontally_on_mobile(self):
        page_url = Path("web/index.html").resolve().as_uri()
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 390, "height": 844})
            try:
                await page.goto(page_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(500)
                metrics = await page.evaluate(
                    "() => ({scrollWidth: document.documentElement.scrollWidth, "
                    "clientWidth: document.documentElement.clientWidth})"
                )
            finally:
                await browser.close()

        self.assertLessEqual(metrics["scrollWidth"], metrics["clientWidth"])


if __name__ == "__main__":
    unittest.main()
