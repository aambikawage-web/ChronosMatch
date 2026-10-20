
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

        database.DB_NAME = os.path.join(
            self.temp_dir.name,
            "test.db",
        )

        database.create_tables()
        self.engine = ChronosMatch()

    def tearDown(self):
        """Restore the database path and remove temporary files."""
        try:
            # Close the engine if it provides a close method.
            if hasattr(self, "engine") and hasattr(
                self.engine, "close"
            ):
                self.engine.close()
        finally:
            database.DB_NAME = self.original_db_name
            self.temp_dir.cleanup()

    def test_matching_orders(self):
        """Matching buy and sell orders should execute a trade."""
        self.engine.submit_order("sell", 100, 5)
        self.engine.submit_order("buy", 100, 5)

        trades = database.get_all_trades()

        self.assertEqual(len(trades), 1)
        self.assertEqual(float(trades[0]["price"]), 100)
        self.assertEqual(int(trades[0]["quantity"]), 5)

    def test_partial_fill(self):
        """A smaller incoming order should partially fill a resting order."""
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
        self.assertEqual(
            remaining_sells[0]["remaining_quantity"],
            6,
        )

    def test_unmatched_orders(self):
        """Orders with incompatible prices should remain unmatched."""
        self.engine.submit_order("buy", 90, 5)
        self.engine.submit_order("sell", 100, 5)

        self.assertEqual(len(database.get_all_trades()), 0)

        active_orders = database.get_active_orders()
        self.assertEqual(len(active_orders), 2)

    def test_cancel_open_buy_order(self):
        """An open buy order should be cancellable."""
        order = self.engine.submit_order("buy", 90, 5)

        self.assertTrue(
            self.engine.cancel_order(order["id"])
        )

        active_orders = database.get_active_orders()
        self.assertFalse(
            any(item["id"] == order["id"] for item in active_orders)
        )

    def test_cancel_open_sell_order(self):
        """An open sell order should be cancellable."""
        order = self.engine.submit_order("sell", 110, 5)

        self.assertTrue(
            self.engine.cancel_order(order["id"])
        )

        active_orders = database.get_active_orders()
        self.assertFalse(
            any(item["id"] == order["id"] for item in active_orders)
        )

    def test_cancel_nonexistent_order(self):
        """Cancelling an unknown order should return False."""
        self.assertFalse(
            self.engine.cancel_order(99999)
        )

    def test_cancel_same_order_twice(self):
        """An order should not be cancellable twice."""
        order = self.engine.submit_order("buy", 90, 5)

        self.assertTrue(
            self.engine.cancel_order(order["id"])
        )
        self.assertFalse(
            self.engine.cancel_order(order["id"])
        )

    def test_invalid_side(self):
        """An unsupported order side should be rejected."""
        with self.assertRaises((ValueError, TypeError)):
            self.engine.submit_order("invalid", 100, 5)

    def test_invalid_prices(self):
        """Zero, negative, infinite, and NaN prices should be rejected."""
        invalid_prices = (
            0,
            -1,
            float("inf"),
            float("-inf"),
            float("nan"),
        )

        for price in invalid_prices:
            with self.subTest(price=price):
                with self.assertRaises((ValueError, TypeError)):
                    self.engine.submit_order("buy", price, 5)

    def test_invalid_quantities(self):
        """Zero and negative quantities should be rejected."""
        for quantity in (0, -1):
            with self.subTest(quantity=quantity):
                with self.assertRaises((ValueError, TypeError)):
                    self.engine.submit_order("buy", 100, quantity)

    def test_fractional_quantity(self):
        """Fractional quantities should be rejected."""
        with self.assertRaises((ValueError, TypeError)):
            self.engine.submit_order("buy", 100, 1.5)

    def test_boolean_values_rejected(self):
        """Boolean values should not be accepted as price or quantity."""
        with self.assertRaises((ValueError, TypeError)):
            self.engine.submit_order("buy", True, 5)

        with self.assertRaises((ValueError, TypeError)):
            self.engine.submit_order("buy", 100, True)

    def test_price_time_priority(self):
        """Earlier orders at the same price should fill first."""
        first = self.engine.submit_order("sell", 100, 2)
        second = self.engine.submit_order("sell", 100, 3)

        self.engine.submit_order("buy", 100, 3)

        orders = {
            order["id"]: order
            for order in database.get_all_orders()
        }

        self.assertEqual(
            orders[first["id"]]["remaining_quantity"],
            0,
        )
        self.assertEqual(
            orders[second["id"]]["remaining_quantity"],
            2,
        )

    def test_trade_uses_resting_order_price(self):
        """The trade should execute at the resting order's price."""
        self.engine.submit_order("sell", 100, 5)
        self.engine.submit_order("buy", 105, 5)

        trades = database.get_all_trades()

        self.assertEqual(len(trades), 1)
        self.assertEqual(float(trades[0]["price"]), 100)

    def test_database_persists_orders_and_trades(self):
        """Submitted orders and executed trades should be persisted."""
        self.engine.submit_order("sell", 100, 5)
        self.engine.submit_order("buy", 100, 5)

        orders = database.get_all_orders()
        trades = database.get_all_trades()

        self.assertEqual(len(orders), 2)
        self.assertEqual(len(trades), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
