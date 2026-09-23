import unittest
from unittest.mock import patch

from flow_element_locator import FlowElementLocator
from flow_live_runner import FlowLiveSession


class FakeMouse:
    def __init__(self):
        self.clicks = []

    async def click(self, x, y):
        self.clicks.append((x, y))


class FakePage:
    def __init__(self):
        self.mouse = FakeMouse()

    async def evaluate(self, _script):
        return {
            "categories": {
                "model_selector": [
                    {"label": "Model: Nano Banana 2", "center": {"x": 10, "y": 20}},
                    {"label": "Banana Pro", "center": {"x": 30, "y": 40}},
                ],
                "quantity_selector": [
                    {"label": "x1", "center": {"x": 50, "y": 60}},
                    {"label": "x4", "center": {"x": 70, "y": 80}},
                ],
            }
        }


class FlowSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_locator_clicks_matching_category_option(self):
        page = FakePage()
        clicked = await FlowElementLocator.select_category_option(
            page, "model_selector", "Banana Pro"
        )
        self.assertTrue(clicked)
        self.assertEqual(page.mouse.clicks, [(30, 40)])

    async def test_flow_session_applies_configured_model_and_quantity(self):
        session = FlowLiveSession()
        session.model = "Banana Pro"
        session.quantity = "x4"
        calls = []

        async def fake_select(_page, category, value):
            calls.append((category, value))
            return True

        with patch.object(FlowElementLocator, "select_category_option", fake_select):
            await session._apply_model_and_quantity(FakePage())

        self.assertEqual(
            calls,
            [("model_selector", "Banana Pro"), ("quantity_selector", "x4")],
        )


if __name__ == "__main__":
    unittest.main()

