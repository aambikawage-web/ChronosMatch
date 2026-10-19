
import math

import database
from database import (
    create_tables,
    save_order,
    save_trade,
    get_next_order_id,
    get_active_orders,
    update_order_remaining,
    cancel_order_in_db,
)


class ChronosMatch:
    """A simple price-time-priority order matching engine."""

    def __init__(self):
        create_tables()

        self.buy_orders = []
        self.sell_orders = []
        self.trades = []

        self.order_id = get_next_order_id()

        for saved_order in get_active_orders():
            order = dict(saved_order)

            order["id"] = int(order["id"])
            order["price"] = float(order["price"])
            order["remaining_quantity"] = int(
                order.get(
                    "remaining_quantity",
                    order.get("quantity", 0),
                )
            )

            if order["side"] == "buy":
                self.buy_orders.append(order)
            elif order["side"] == "sell":
                self.sell_orders.append(order)

        self._sort_orders()

    def _sort_orders(self):
        """Sort buys by highest price first and sells by lowest price first."""
        self.buy_orders.sort(
            key=lambda order: (-order["price"], order["id"])
        )
        self.sell_orders.sort(
            key=lambda order: (order["price"], order["id"])
        )

    def submit_order(self, side, price, quantity):
        """Validate, store and match a new order."""

        if not isinstance(side, str) or side not in ("buy", "sell"):
            raise ValueError("Side must be 'buy' or 'sell'")

        if (
            isinstance(price, bool)
            or not isinstance(price, (int, float))
        ):
            raise ValueError("Price must be a number")

        if (
            isinstance(price, float)
            and not math.isfinite(price)
        ):
            raise ValueError("Price must be finite")

        if price <= 0:
            raise ValueError("Price must be greater than zero")

        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, (int, float))
        ):
            raise ValueError("Quantity must be a number")

        if (
            isinstance(quantity, float)
            and not math.isfinite(quantity)
        ):
            raise ValueError("Quantity must be finite")

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero")

        if int(quantity) != quantity:
            raise ValueError("Quantity must be a whole number")

        order = {
            "id": self.order_id,
            "side": side,
            "price": float(price),
            "quantity": int(quantity),
            "remaining_quantity": int(quantity),
        }

        # Persist the order using the existing database interface.
        save_order(order)

        self.order_id += 1

        if side == "buy":
            self._match_buy_order(order)
        else:
            self._match_sell_order(order)

        # Persist remaining quantity and status.
        update_order_remaining(
            order["id"],
            order["remaining_quantity"],
        )

        self._sort_orders()
        return order

    def _execute_trade(self, incoming_order, resting_order, quantity):
        """Execute a trade at the resting order's price."""

        trade = {
            "price": float(resting_order["price"]),
            "quantity": int(quantity),
        }

        save_trade(trade)
        self.trades.append(trade)

        incoming_order["remaining_quantity"] -= quantity
        resting_order["remaining_quantity"] -= quantity

        update_order_remaining(
            resting_order["id"],
            resting_order["remaining_quantity"],
        )

    def _match_buy_order(self, order):
        """Match an incoming buy order against the best sell orders."""

        while (
            order["remaining_quantity"] > 0
            and self.sell_orders
            and order["price"] >= self.sell_orders[0]["price"]
        ):
            resting_order = self.sell_orders[0]

            trade_quantity = min(
                order["remaining_quantity"],
                resting_order["remaining_quantity"],
            )

            self._execute_trade(
                order,
                resting_order,
                trade_quantity,
            )

            if resting_order["remaining_quantity"] == 0:
                self.sell_orders.pop(0)

        if order["remaining_quantity"] > 0:
            self.buy_orders.append(order)

    def _match_sell_order(self, order):
        """Match an incoming sell order against the best buy orders."""

        while (
            order["remaining_quantity"] > 0
            and self.buy_orders
            and order["price"] <= self.buy_orders[0]["price"]
        ):
            resting_order = self.buy_orders[0]

            trade_quantity = min(
                order["remaining_quantity"],
                resting_order["remaining_quantity"],
            )

            self._execute_trade(
                order,
                resting_order,
                trade_quantity,
            )

            if resting_order["remaining_quantity"] == 0:
                self.buy_orders.pop(0)

        if order["remaining_quantity"] > 0:
            self.sell_orders.append(order)

    def cancel_order(self, order_id):
        """Cancel an active order by its ID."""

        if isinstance(order_id, bool) or not isinstance(order_id, int):
            raise ValueError("Order ID must be an integer")

        for order_book in (self.buy_orders, self.sell_orders):
            for order in order_book:
                if order["id"] == order_id:
                    if order["remaining_quantity"] <= 0:
                        return False

                    result = cancel_order_in_db(order_id)

                    if result is False:
                        return False

                    order_book.remove(order)
                    return True

        return False

    def get_order_book(self):
        """Return copies of the current buy and sell order books."""
        return {
            "buy_orders": [dict(order) for order in self.buy_orders],
            "sell_orders": [dict(order) for order in self.sell_orders],
        }
