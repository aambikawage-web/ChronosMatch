import unittest

from upstox_adapter import OrderRequest, PaperTrader, UpstoxAdapter


class TestPaperTrader(unittest.TestCase):

    def setUp(self):
        self.trader = PaperTrader()

    def test_valid_buy_order(self):
        order = self.trader.place_order("DEMO", "BUY", 2, 100.0)
        self.assertEqual(order["status"], "PAPER_FILLED")
        self.assertEqual(order["simulated_value"], 200.0)

    def test_valid_sell_order(self):
        order = self.trader.place_order("DEMO", "SELL", 1, 50.0)
        self.assertEqual(order["side"], "SELL")

    def test_invalid_side_rejected(self):
        with self.assertRaises(ValueError):
            self.trader.place_order("DEMO", "HOLD", 1, 100.0)

    def test_zero_quantity_rejected(self):
        with self.assertRaises(ValueError):
            self.trader.place_order("DEMO", "BUY", 0, 100.0)

    def test_invalid_price_rejected(self):
        with self.assertRaises(ValueError):
            self.trader.place_order("DEMO", "BUY", 1, -10.0)

    def test_real_broker_orders_disabled(self):
        adapter = UpstoxAdapter()
        self.assertFalse(adapter.enabled)

        with self.assertRaises(RuntimeError):
            adapter.place_order(OrderRequest("DEMO", "BUY", 1))

    def test_live_quotes_disabled(self):
        adapter = UpstoxAdapter()

        with self.assertRaises(RuntimeError):
            adapter.get_market_quote("DEMO")


if __name__ == "__main__":
    unittest.main()