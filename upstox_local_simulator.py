"""
ChronosMatch - Local Upstox API Simulator

LOCAL SIMULATION ONLY.
No network requests.
No Upstox authentication.
No real broker orders.
"""

from datetime import datetime, timezone
from copy import deepcopy


class UpstoxLocalSimulator:

    def __init__(self):
        self.orders = {}
        self.next_order_id = 1

    def place_order(
        self,
        symbol,
        side,
        quantity,
        price,
        order_type="LIMIT",
    ):
        symbol = str(symbol).strip().upper()
        side = str(side).strip().upper()
        order_type = str(order_type).strip().upper()

        if not symbol:
            raise ValueError("Symbol is required.")

        if side not in {"BUY", "SELL"}:
            raise ValueError("Side must be BUY or SELL.")

        if order_type not in {"LIMIT", "MARKET"}:
            raise ValueError("Order type must be LIMIT or MARKET.")

        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise ValueError("Quantity must be a positive integer.")

        if quantity <= 0:
            raise ValueError("Quantity must be positive.")

        if isinstance(price, bool) or not isinstance(price, (int, float)):
            raise ValueError("Price must be a valid number.")

        if order_type == "LIMIT" and price <= 0:
            raise ValueError("Limit price must be positive.")

        order_id = f"LOCAL-{self.next_order_id}"
        self.next_order_id += 1

        order = {
            "order_id": order_id,
            "symbol": symbol,
            "transaction_type": side,
            "quantity": quantity,
            "price": float(price),
            "order_type": order_type,
            "status": "OPEN",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "environment": "LOCAL_SIMULATION",
        }

        self.orders[order_id] = order

        return deepcopy(order)

    def modify_order(
        self,
        order_id,
        quantity=None,
        price=None,
    ):
        order = self._get_order(order_id)

        if order["status"] != "OPEN":
            raise ValueError("Only open orders can be modified.")

        if quantity is not None:
            if (
                isinstance(quantity, bool)
                or not isinstance(quantity, int)
                or quantity <= 0
            ):
                raise ValueError("Quantity must be positive.")

            order["quantity"] = quantity

        if price is not None:
            if (
                isinstance(price, bool)
                or not isinstance(price, (int, float))
                or price <= 0
            ):
                raise ValueError("Price must be positive.")

            order["price"] = float(price)

        return deepcopy(order)

    def cancel_order(self, order_id):
        order = self._get_order(order_id)

        if order["status"] != "OPEN":
            raise ValueError("Only open orders can be cancelled.")

        order["status"] = "CANCELLED"

        return deepcopy(order)

    def get_order(self, order_id):
        return deepcopy(self._get_order(order_id))

    def get_orders(self):
        return deepcopy(list(self.orders.values()))

    def _get_order(self, order_id):
        if order_id not in self.orders:
            raise ValueError("Order not found.")

        return self.orders[order_id]


if __name__ == "__main__":

    simulator = UpstoxLocalSimulator()

    print("ChronosMatch Local Upstox Simulator")
    print("-----------------------------------")

    order = simulator.place_order(
        symbol="DEMO",
        side="BUY",
        quantity=5,
        price=100.0,
    )

    print("\n1. Order placed:")
    print(order)

    modified = simulator.modify_order(
        order["order_id"],
        quantity=8,
        price=105.0,
    )

    print("\n2. Order modified:")
    print(modified)

    cancelled = simulator.cancel_order(order["order_id"])

    print("\n3. Order cancelled:")
    print(cancelled)

    print("\nNetwork requests: NONE")
    print("Real broker orders: NONE")