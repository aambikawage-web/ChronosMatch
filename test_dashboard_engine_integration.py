import os
import tempfile
import unittest

import database
from chronosmatch import ChronosMatch


class TestDashboardEngineIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_name = database.DB_NAME
        database.DB_NAME = os.path.join(self.temp_dir.name, "integration_test.db")
        database.create_tables()
        self.engine = ChronosMatch()

    def tearDown(self):
        database.DB_NAME = self.original_db_name
        self.temp_dir.cleanup()

    def test_order_entry_reaches_matching_engine(self):
        self.engine.submit_order("sell", 100, 5)
        result = self.engine.submit_order("buy", 100, 3)

        self.assertEqual(result["remaining_quantity"], 0)
        self.assertEqual(len(self.engine.trades), 1)
        self.assertEqual(self.engine.trades[0]["price"], 100.0)
        self.assertEqual(self.engine.trades[0]["quantity"], 3)


if __name__ == "__main__":
    unittest.main()
