"""
ChronosMatch broker adapter scaffold.

Safe defaults:
- No network requests
- No real broker orders
- Paper trading only
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class OrderRequest:
    symbol: str
    side: str
    quantity: int


class UpstoxAdapter:
    """Placeholder for a future, authenticated Upstox connection."""

    def __init__(self):
        self.enabled = False

    def get_connection_status(self) -> str:
        return "DISABLED — broker connection not verified"

    def get_market_quote(self, symbol: str) -> Optional[dict]:
        raise RuntimeError(
            "Live market data is unavailable until authorized API "
            "access is configured and verified."
        )

    def place_order(self, order: OrderRequest) -> dict:
        raise RuntimeError(
            "Real broker orders are disabled. Use paper trading."
        )


class PaperTrader:
    """Simulates orders using a supplied price; never contacts a broker."""

    def __init__(self):
        self.orders = []
        self.next_order_id = 1

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
    ) -> dict:
        symbol = symbol.strip().upper()
        side = side.strip().upper()

        if not symbol:
            raise ValueError("Symbol is required.")

        if side not in {"BUY", "SELL"}:
            raise ValueError("Side must be BUY or SELL.")

        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise ValueError("Quantity must be a positive integer.")

        if quantity <= 0:
            raise ValueError("Quantity must be a positive integer.")

        if isinstance(price, bool) or not isinstance(price, (int, float)):
            raise ValueError("Price must be a positive finite number.")

        import math

        if not math.isfinite(price) or price <= 0:
            raise ValueError("Price must be a positive finite number.")

        order = {
            "order_id": self.next_order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": float(price),
            "status": "PAPER_FILLED",
            "simulated_value": quantity * float(price),
        }

        self.orders.append(order)
        self.next_order_id += 1
        return order

    def get_orders(self) -> list[dict]:
        return list(self.orders)


if __name__ == "__main__":
    trader = PaperTrader()

    example = trader.place_order(
        symbol="DEMO",
        side="BUY",
        quantity=1,
        price=100.0,
    )

    print("Paper-trading demonstration")
    print(example)
    print("Broker requests: NONE")
    print("Real orders: NONE")