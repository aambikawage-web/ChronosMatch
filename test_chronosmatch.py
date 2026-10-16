import unittest
import tempfile
from pathlib import Path

import database
from chronosmatch import ChronosMatch


class TestChronosMatch(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DB_NAME = Path(self.temp_dir.name) / "test.db"
        database.create_tables()
        self.engine = ChronosMatch()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_matching_orders(self):
        self.engine.submit_order("sell", 100, 10)
        self.engine.submit_order("buy", 101, 6)

        trades = database.get_all_trades()
        active = database.get_active_orders()

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["price"], 100)
        self.assertEqual(trades[0]["quantity"], 6)

        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["side"], "sell")
        self.assertEqual(active[0]["quantity"], 4)

    def test_partial_fill(self):
        self.engine.submit_order("sell", 100, 10)
        self.engine.submit_order("buy", 100, 6)

        active = database.get_active_orders()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["quantity"], 4)

        orders = database.get_all_orders()
        buyer = next(o for o in orders if o["side"] == "buy")

        self.assertEqual(buyer["remaining_quantity"], 0)
        self.assertEqual(buyer["status"], "FILLED")

    def test_unmatched_orders(self):
        self.engine.submit_order("buy", 99, 5)

        active = database.get_active_orders()
        trades = database.get_all_trades()

        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["side"], "buy")
        self.assertEqual(active[0]["price"], 99)
        self.assertEqual(active[0]["quantity"], 5)
        self.assertEqual(len(trades), 0)

    def test_invalid_order(self):
        with self.assertRaises(ValueError):
            self.engine.submit_order("buy", -10, 5)

    def test_invalid_side(self):
        with self.assertRaises(ValueError):
            self.engine.submit_order("hold", 100, 5)

    def test_invalid_quantity(self):
        with self.assertRaises(ValueError):
            self.engine.submit_order("buy", 100, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)