import unittest
from datetime import datetime, timezone

from quota_time import day_bounds, day_key, next_reset_ts


class QuotaTimeTests(unittest.TestCase):
    def test_day_key_uses_configured_reset_timezone(self):
        at = datetime(2026, 9, 23, 16, 0, tzinfo=timezone.utc)
        self.assertEqual(day_key(at, "Asia/Tokyo"), "2026-09-24")

    def test_day_bounds_match_midnight_in_reset_timezone(self):
        start, end = day_bounds("2026-09-24", "Asia/Tokyo")
        self.assertEqual(
            datetime.fromtimestamp(start, timezone.utc),
            datetime(2026, 9, 23, 15, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            datetime.fromtimestamp(end, timezone.utc),
            datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc),
        )

    def test_next_reset_is_midnight_in_reset_timezone(self):
        at = datetime(2026, 9, 23, 10, 0, tzinfo=timezone.utc)
        reset = next_reset_ts(at, "Asia/Tokyo")
        self.assertEqual(
            datetime.fromtimestamp(reset, timezone.utc),
            datetime(2026, 9, 23, 15, 0, tzinfo=timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()

