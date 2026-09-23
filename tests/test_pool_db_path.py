import tempfile
import unittest
from pathlib import Path

import config
from browser_pool import BrowserPool


class PoolDatabasePathTests(unittest.TestCase):
    def test_browser_pool_defaults_to_config_pool_db_path(self):
        with tempfile.TemporaryDirectory(prefix="dola-pool-db-") as tmp:
            path = Path(tmp) / "custom-pool.db"
            old_path = config.POOL_DB_PATH
            config.POOL_DB_PATH = str(path)
            try:
                pool = BrowserPool()
                self.assertTrue(path.exists())
                actual = Path(pool._conn.execute("PRAGMA database_list").fetchone()[2]).resolve()
                self.assertEqual(actual, path.resolve())
            finally:
                config.POOL_DB_PATH = old_path


if __name__ == "__main__":
    unittest.main()
