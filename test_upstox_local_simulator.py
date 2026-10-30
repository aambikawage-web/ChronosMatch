import unittest

from upstox_local_simulator import UpstoxLocalSimulator


class TestUpstoxLocalSimulator(unittest.TestCase):

    def setUp(self):
        self.simulator = UpstoxLocalSimulator()

    def test_place_order(self):
        order = self.simulator.place_order(
            "DEMO", "BUY", 5, 100.0
        )
        self.assertEqual(order["status"], "OPEN")

    def test_modify_order(self):
        order = self.simulator.place_order(
            "DEMO", "BUY", 5, 100.0
        )

        modified = self.simulator.modify_order(
            order["order_id"], quantity=8, price=105.0
        )

        self.assertEqual(modified["quantity"], 8)
        self.assertEqual(modified["price"], 105.0)

    def test_cancel_order(self):
        order = self.simulator.place_order(
            "DEMO", "SELL", 2, 110.0
        )

        cancelled = self.simulator.cancel_order(
            order["order_id"]
        )

        self.assertEqual(cancelled["status"], "CANCELLED")

    def test_invalid_side(self):
        with self.assertRaises(ValueError):
            self.simulator.place_order(
                "DEMO", "HOLD", 1, 100.0
            )

    def test_invalid_quantity(self):
        with self.assertRaises(ValueError):
            self.simulator.place_order(
                "DEMO", "BUY", 0, 100.0
            )

    def test_invalid_price(self):
        with self.assertRaises(ValueError):
            self.simulator.place_order(
                "DEMO", "BUY", 1, -10.0
            )

    def test_cancelled_order_cannot_be_modified(self):
        order = self.simulator.place_order(
            "DEMO", "BUY", 1, 100.0
        )

        self.simulator.cancel_order(order["order_id"])

        with self.assertRaises(ValueError):
            self.simulator.modify_order(
                order["order_id"], price=110.0
            )


if __name__ == "__main__":
    unittest.main()