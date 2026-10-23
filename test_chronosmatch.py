
import os
import tempfile
import unittest

import database
from chronosmatch import ChronosMatch


class TestChronosMatch(unittest.TestCase):

    def setUp(self):
        """Create an isolated temporary database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_name = database.DB_NAME
        database.DB_NAME = os.path.join(self.temp_dir.name, "test.db")

        database.create_tables()
        self.engine = ChronosMatch()

    def tearDown(self):
        """Restore database settings and clean up temporary files."""
        try:
            if hasattr(self, "engine") and hasattr(self.engine, "close"):
                self.engine.close()
        finally:
            database.DB_NAME = self.original_db_name
            self.temp_dir.cleanup()

    # ---------------- ORIGINAL TESTS ----------------

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

        orders = database.get_all_orders()
        remaining_sells = [
            order for order in orders
            if order["side"] == "sell"
            and order["remaining_quantity"] > 0
        ]

        self.assertEqual(len(remaining_sells), 1)
        self.assertEqual(remaining_sells[0]["remaining_quantity"], 6)

    def test_unmatched_orders(self):
        self.engine.submit_order("buy", 90, 5)
        self.engine.submit_order("sell", 100, 5)

        self.assertEqual(len(database.get_all_trades()), 0)
        self.assertEqual(len(database.get_active_orders()), 2)

    def test_cancel_open_buy_order(self):
        order = self.engine.submit_order("buy", 90, 5)
        self.assertTrue(self.engine.cancel_order(order["id"]))

        active_orders = database.get_active_orders()
        self.assertFalse(
            any(item["id"] == order["id"] for item in active_orders)
        )

    def test_cancel_open_sell_order(self):
        order = self.engine.submit_order("sell", 110, 5)
        self.assertTrue(self.engine.cancel_order(order["id"]))

        active_orders = database.get_active_orders()
        self.assertFalse(
            any(item["id"] == order["id"] for item in active_orders)
        )

    def test_cancel_nonexistent_order(self):
        self.assertFalse(self.engine.cancel_order(99999))

    def test_cancel_same_order_twice(self):
        order = self.engine.submit_order("buy", 90, 5)
        self.assertTrue(self.engine.cancel_order(order["id"]))
        self.assertFalse(self.engine.cancel_order(order["id"]))

    def test_invalid_side(self):
        with self.assertRaises((ValueError, TypeError)):
            self.engine.submit_order("invalid", 100, 5)

    def test_invalid_prices(self):
        invalid_prices = (0, -1, float("inf"), float("-inf"), float("nan"))

        for price in invalid_prices:
            with self.subTest(price=price):
                with self.assertRaises((ValueError, TypeError)):
                    self.engine.submit_order("buy", price, 5)

    def test_invalid_quantities(self):
        for quantity in (0, -1):
            with self.subTest(quantity=quantity):
                with self.assertRaises((ValueError, TypeError)):
                    self.engine.submit_order("buy", 100, quantity)

    def test_fractional_quantity(self):
        with self.assertRaises((ValueError, TypeError)):
            self.engine.submit_order("buy", 100, 1.5)

    def test_boolean_values_rejected(self):
        with self.assertRaises((ValueError, TypeError)):
            self.engine.submit_order("buy", True, 5)

        with self.assertRaises((ValueError, TypeError)):
            self.engine.submit_order("buy", 100, True)

    def test_price_time_priority(self):
        first = self.engine.submit_order("sell", 100, 2)
        second = self.engine.submit_order("sell", 100, 3)

        self.engine.submit_order("buy", 100, 3)

        orders = {
            order["id"]: order
            for order in database.get_all_orders()
        }

        self.assertEqual(orders[first["id"]]["remaining_quantity"], 0)
        self.assertEqual(orders[second["id"]]["remaining_quantity"], 2)

    def test_trade_uses_resting_order_price(self):
        self.engine.submit_order("sell", 100, 5)
        self.engine.submit_order("buy", 105, 5)

        trades = database.get_all_trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(float(trades[0]["price"]), 100)

    def test_database_persists_orders_and_trades(self):
        self.engine.submit_order("sell", 100, 5)
        self.engine.submit_order("buy", 100, 5)

        self.assertEqual(len(database.get_all_orders()), 2)
        self.assertEqual(len(database.get_all_trades()), 1)

    # ---------------- 20 ADDITIONAL TESTS ----------------

    def test_15_valid_buy_order_remains_open(self):
        order = self.engine.submit_order("buy", 100, 5)
        book = self.engine.get_order_book()

        self.assertEqual(order["remaining_quantity"], 5)
        self.assertEqual(len(book["buy_orders"]), 1)

    def test_16_valid_sell_order_remains_open(self):
        order = self.engine.submit_order("sell", 110, 5)
        book = self.engine.get_order_book()

        self.assertEqual(order["remaining_quantity"], 5)
        self.assertEqual(len(book["sell_orders"]), 1)

    def test_17_non_string_side_is_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.submit_order(None, 100, 5)

    def test_18_non_numeric_price_is_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.submit_order("buy", "100", 5)

    def test_19_non_numeric_quantity_is_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.submit_order("buy", 100, "5")

    def test_20_infinite_quantity_is_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.submit_order("buy", 100, float("inf"))

    def test_21_nan_quantity_is_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.submit_order("buy", 100, float("nan"))

    def test_22_fractional_price_is_supported(self):
        order = self.engine.submit_order("buy", 100.5, 2)

        self.assertEqual(order["price"], 100.5)
        self.assertEqual(order["remaining_quantity"], 2)

    def test_23_buy_above_ask_executes_trade(self):
        self.engine.submit_order("sell", 100, 3)
        self.engine.submit_order("buy", 105, 3)

        trades = database.get_all_trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(float(trades[0]["price"]), 100)
        self.assertEqual(int(trades[0]["quantity"]), 3)

    def test_24_sell_below_bid_executes_trade(self):
        self.engine.submit_order("buy", 105, 3)
        self.engine.submit_order("sell", 100, 3)

        trades = database.get_all_trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(float(trades[0]["price"]), 105)
        self.assertEqual(int(trades[0]["quantity"]), 3)

    def test_25_buy_below_ask_does_not_trade(self):
        self.engine.submit_order("sell", 101, 2)
        self.engine.submit_order("buy", 100, 2)

        self.assertEqual(len(database.get_all_trades()), 0)

    def test_26_sell_above_bid_does_not_trade(self):
        self.engine.submit_order("buy", 99, 2)
        self.engine.submit_order("sell", 100, 2)

        self.assertEqual(len(database.get_all_trades()), 0)

    def test_27_best_priced_sell_is_matched_first(self):
        self.engine.submit_order("sell", 102, 2)
        self.engine.submit_order("sell", 101, 2)
        self.engine.submit_order("buy", 101, 2)

        trades = database.get_all_trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(float(trades[0]["price"]), 101)

    def test_28_best_priced_buy_is_matched_first(self):
        self.engine.submit_order("buy", 99, 2)
        self.engine.submit_order("buy", 100, 2)
        self.engine.submit_order("sell", 100, 2)

        trades = database.get_all_trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(float(trades[0]["price"]), 100)

    def test_29_same_price_buy_orders_follow_fifo(self):
        first = self.engine.submit_order("buy", 100, 2)
        second = self.engine.submit_order("buy", 100, 3)
        self.engine.submit_order("sell", 100, 3)

        orders = {
            order["id"]: order
            for order in database.get_all_orders()
        }

        self.assertEqual(orders[first["id"]]["remaining_quantity"], 0)
        self.assertEqual(orders[second["id"]]["remaining_quantity"], 2)

    def test_30_one_buy_matches_multiple_sell_orders(self):
        self.engine.submit_order("sell", 100, 2)
        self.engine.submit_order("sell", 101, 3)
        incoming = self.engine.submit_order("buy", 101, 5)

        trades = database.get_all_trades()
        self.assertEqual(len(trades), 2)
        self.assertEqual(
            [int(trade["quantity"]) for trade in trades],
            [3, 2],
        )
        self.assertEqual(incoming["remaining_quantity"], 0)

    def test_31_one_sell_matches_multiple_buy_orders(self):
        self.engine.submit_order("buy", 102, 2)
        self.engine.submit_order("buy", 101, 3)
        incoming = self.engine.submit_order("sell", 101, 5)

        trades = database.get_all_trades()
        self.assertEqual(len(trades), 2)
        self.assertEqual(
            [int(trade["quantity"]) for trade in trades],
            [3, 2],
        )
        self.assertEqual(incoming["remaining_quantity"], 0)

    def test_32_order_book_returns_independent_copies(self):
        self.engine.submit_order("buy", 100, 5)
        book = self.engine.get_order_book()

        book["buy_orders"][0]["remaining_quantity"] = 999

        fresh_book = self.engine.get_order_book()
        self.assertEqual(
            fresh_book["buy_orders"][0]["remaining_quantity"],
            5,
        )

    def test_33_cancel_order_rejects_invalid_id_type(self):
        for order_id in (True, "1", 1.5, None):
            with self.subTest(order_id=order_id):
                with self.assertRaises(ValueError):
                    self.engine.cancel_order(order_id)

    def test_34_cancel_partially_filled_order(self):
        sell = self.engine.submit_order("sell", 100, 5)
        self.engine.submit_order("buy", 100, 2)

        self.assertEqual(sell["remaining_quantity"], 3)
        self.assertTrue(self.engine.cancel_order(sell["id"]))

        book = self.engine.get_order_book()
        self.assertFalse(
            any(
                order["id"] == sell["id"]
                for order in book["sell_orders"]
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
