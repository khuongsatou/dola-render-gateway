import unittest
from pathlib import Path
from patchright.async_api import async_playwright


class WorkflowStudioUITests(unittest.IsolatedAsyncioTestCase):
    async def test_workflow_studio_is_profile_scoped_not_standalone_tab(self):
        page_url = Path("web/index.html").resolve().as_uri()
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            try:
                await page.goto(page_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(300)

                # 1. Ensure Workflow Studio is NOT a separate tab in <nav>
                nav_canvas_btn = await page.query_selector('nav button[data-tab="canvas"]')
                self.assertIsNone(nav_canvas_btn, "Workflow Studio should not be a separate tab in <nav>")

                # 2. Switch to Accounts Tab
                await page.click('nav button[data-tab="accounts"]')
                await page.wait_for_timeout(300)

                # 3. Ensure Workflow Studio button exists in Account Management header
                wf_hdr_btn = await page.query_selector('#tab-accounts button[onclick*="openWorkflowStudioModal"]')
                self.assertIsNotNone(wf_hdr_btn, "Workflow Studio button should exist in Account Management header")

                # 4. Check modal element exists
                modal_exists = await page.query_selector('#workflowStudioModal')
                self.assertIsNotNone(modal_exists, "#workflowStudioModal container must exist")

                # 5. Render an account row and click its profile-scoped Workflow Studio button
                await page.evaluate('''() => {
                    const btnHtml = '<button id="testAccWfBtn" class="btn btn-mini press" data-account="acc_profile_alpha" onclick="openWorkflowStudioModal(this.dataset.account)"><i class="bi bi-diagram-3-fill"></i> Workflow Studio</button>';
                    document.getElementById('accountsTable').innerHTML = btnHtml;
                }''')

                await page.click('#testAccWfBtn')
                await page.wait_for_timeout(300)

                modal_display = await page.evaluate("() => document.getElementById('workflowStudioModal').style.display")
                self.assertEqual(modal_display, "flex", "Workflow studio modal should open with display: flex")

                profile_text = await page.evaluate("() => document.getElementById('wfModalProfileBadge').textContent")
                self.assertIn("acc_profile_alpha", profile_text, "Profile badge should reflect target profile")

                account_worker = await page.evaluate("() => document.getElementById('node2Account').textContent")
                self.assertEqual(account_worker, "acc_profile_alpha", "Worker node 2 account should match target profile")

                # 6. Close modal using close button
                await page.click('#workflowStudioModal button[onclick*="closeWorkflowStudioModal"]')
                await page.wait_for_timeout(300)

                modal_display_closed = await page.evaluate("() => document.getElementById('workflowStudioModal').style.display")
                self.assertEqual(modal_display_closed, "none", "Workflow studio modal should hide on close")

            finally:
                await browser.close()


if __name__ == "__main__":
    unittest.main()
