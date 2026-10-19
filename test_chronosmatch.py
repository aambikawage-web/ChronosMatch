
import os
import tempfile
import unittest

import database
from chronosmatch import ChronosMatch


class TestChronosMatch(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_name = database.DB_NAME

        database.DB_NAME = os.path.join(
            self.temp_dir.name,
            "test.db",
        )

        database.create_tables()
        self.engine = ChronosMatch()

    def tearDown(self):
        database.DB_NAME = self.original_db_name
        self.temp_dir.cleanup()

    def test_matching_orders(self):
        self.engine.submit_order("sell", 100, 5)
        self.engine.submit_order("buy", 100, 5)

        trades = database.get_all_trades()

        self.assertEqual(len(trades), 1)
        self.assertEqual(float(trades[0]["price"]), 100)
        self.assertEqual(int(trades[0]["quantity"]), 5)

    def test_partial_fill(self):
        self.engine.submit_order("sell", 100, 10)
        self.engine.submit_order("buy", 100, 4)

        trades = database.get_all_trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(int(trades[0]["quantity"]), 4)

        remaining_sells = [
            order for order in self.engine.sell_orders
            if order["remaining_quantity"] > 0
        ]

        self.assertEqual(len(remaining_sells), 1)
        self.assertEqual(
            remaining_sells[0]["remaining_quantity"],
            6,
        )

    def test_unmatched_orders(self):
        self.engine.submit_order("buy", 90, 5)
        self.engine.submit_order("sell", 100, 5)

        self.assertEqual(len(database.get_all_trades()), 0)
        self.assertEqual(len(self.engine.buy_orders), 1)
        self.assertEqual(len(self.engine.sell_orders), 1)

    def test_cancel_open_buy_order(self):
        order = self.engine.submit_order("buy", 90, 5)

        self.assertTrue(self.engine.cancel_order(order["id"]))
        self.assertEqual(len(self.engine.buy_orders), 0)

    def test_cancel_open_sell_order(self):
        order = self.engine.submit_order("sell", 110, 5)

        self.assertTrue(self.engine.cancel_order(order["id"]))
        self.assertEqual(len(self.engine.sell_orders), 0)

    def test_cancel_nonexistent_order(self):
        self.assertFalse(self.engine.cancel_order(99999))

    def test_cancel_same_order_twice(self):
        order = self.engine.submit_order("buy", 90, 5)

        self.assertTrue(self.engine.cancel_order(order["id"]))
        self.assertFalse(self.engine.cancel_order(order["id"]))

    def test_invalid_side(self):
        with self.assertRaises(ValueError):
            self.engine.submit_order("invalid", 100, 1)

    def test_invalid_prices(self):
        for price in (0, -1, float("nan"), float("inf"), float("-inf")):
            with self.subTest(price=price):
                with self.assertRaises(ValueError):
                    self.engine.submit_order("buy", price, 1)

    def test_invalid_quantities(self):
        for quantity in (0, -1):
            with self.subTest(quantity=quantity):
                with self.assertRaises(ValueError):
                    self.engine.submit_order("buy", 100, quantity)

    def test_fractional_quantity(self):
        with self.assertRaises(ValueError):
            self.engine.submit_order("buy", 100, 1.5)

    def test_boolean_values_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.submit_order("buy", True, 1)

        with self.assertRaises(ValueError):
            self.engine.submit_order("buy", 100, True)

    def test_database_persists_orders_and_trades(self):
        self.engine.submit_order("sell", 100, 3)
        self.engine.submit_order("buy", 100, 3)

        self.assertEqual(len(database.get_all_orders()), 2)
        self.assertEqual(len(database.get_all_trades()), 1)

    def test_price_time_priority(self):
        first = self.engine.submit_order("sell", 100, 2)
        second = self.engine.submit_order("sell", 100, 3)

        self.assertLess(first["id"], second["id"])
        self.assertEqual(self.engine.sell_orders[0]["id"], first["id"])

    def test_trade_uses_resting_order_price(self):
        self.engine.submit_order("sell", 100, 2)
        self.engine.submit_order("buy", 105, 2)

        trades = database.get_all_trades()

        self.assertEqual(len(trades), 1)
        self.assertEqual(float(trades[0]["price"]), 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
