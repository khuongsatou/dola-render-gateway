import asyncio
import unittest

from account_locks import account_execution


class AccountLockTests(unittest.IsolatedAsyncioTestCase):
    async def test_account_execution_serializes_same_profile(self):
        events = []

        async def worker(name):
            async with account_execution("shared-test-account"):
                events.append(f"{name}:start")
                await asyncio.sleep(0.05)
                events.append(f"{name}:end")

        await asyncio.gather(worker("a"), worker("b"))

        self.assertEqual(
            events,
            ["a:start", "a:end", "b:start", "b:end"],
        )

    async def test_account_execution_allows_different_profiles(self):
        events = []

        async def worker(name):
            async with account_execution(name):
                events.append(f"{name}:start")
                await asyncio.sleep(0.05)
                events.append(f"{name}:end")

        await asyncio.gather(worker("lock-account-a"), worker("lock-account-b"))

        self.assertEqual(events.count("lock-account-a:start"), 1)
        self.assertEqual(events.count("lock-account-b:start"), 1)
        self.assertLess(events.index("lock-account-a:start"), events.index("lock-account-a:end"))
        self.assertLess(events.index("lock-account-b:start"), events.index("lock-account-b:end"))


if __name__ == "__main__":
    unittest.main()

