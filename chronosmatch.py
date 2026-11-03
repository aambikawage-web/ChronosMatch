
import copy
import heapq
import math

from database import (
    create_tables,
    save_order_and_match,
    get_next_order_id,
    get_active_orders,
    cancel_order_in_db,
)


class ChronosMatch:
    """
    Price-time-priority matching engine.

    Buy orders:
        Highest price first, earliest order ID first.

    Sell orders:
        Lowest price first, earliest order ID first.

    Uses heaps and an order lookup dictionary.
    Database writes are batched per incoming order.
    """

    def __init__(self):
        create_tables()

        self._buy_heap = []
        self._sell_heap = []

        self._active_orders = {}
        self.trades = []

        self.order_id = get_next_order_id()

        # Restore active orders from SQLite.
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

            if order["remaining_quantity"] <= 0:
                continue

            self._active_orders[order["id"]] = order
            self._add_to_heap(order)

    def _add_to_heap(self, order):
        """Add an active order to its appropriate priority heap."""

        if order["side"] == "buy":
            heapq.heappush(
                self._buy_heap,
                (-order["price"], order["id"]),
            )
        else:
            heapq.heappush(
                self._sell_heap,
                (order["price"], order["id"]),
            )

    def _get_order(self, side, order_id):
        """Find an order only if it is still active."""

        order = self._active_orders.get(order_id)

        if order is None or order["side"] != side:
            return None

        return order

    def _clean_heap(self, side):
        """Remove stale or completed entries from the heap."""

        heap = (
            self._buy_heap
            if side == "buy"
            else self._sell_heap
        )

        while heap:
            _, order_id = heap[0]
            order = self._get_order(side, order_id)

            if (
                order is not None
                and order["remaining_quantity"] > 0
            ):
                break

            heapq.heappop(heap)

    @property
    def buy_orders(self):
        """Return active buy orders in price-time priority."""

        orders = [
            order
            for order in self._active_orders.values()
            if order["side"] == "buy"
            and order["remaining_quantity"] > 0
        ]

        return sorted(
            orders,
            key=lambda order: (-order["price"], order["id"]),
        )

    @property
    def sell_orders(self):
        """Return active sell orders in price-time priority."""

        orders = [
            order
            for order in self._active_orders.values()
            if order["side"] == "sell"
            and order["remaining_quantity"] > 0
        ]

        return sorted(
            orders,
            key=lambda order: (order["price"], order["id"]),
        )

    def submit_order(self, side, price, quantity):
        """Validate, match and save a new order."""

        # Validate side.
        if not isinstance(side, str) or side not in (
            "buy",
            "sell",
        ):
            raise ValueError("Side must be 'buy' or 'sell'")

        # Validate price.
        if (
            isinstance(price, bool)
            or not isinstance(price, (int, float))
        ):
            raise ValueError("Price must be a number")

        if not math.isfinite(price):
            raise ValueError("Price must be finite")

        if price <= 0:
            raise ValueError("Price must be greater than zero")

        # Validate quantity.
        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, (int, float))
        ):
            raise ValueError("Quantity must be a number")

        if not math.isfinite(quantity):
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

        # Save the original in-memory state.
        previous_buy_heap = copy.deepcopy(self._buy_heap)
        previous_sell_heap = copy.deepcopy(self._sell_heap)
        previous_active_orders = copy.deepcopy(
            self._active_orders
        )
        previous_trades = copy.deepcopy(self.trades)

        order_updates = []

        try:
            # Match the incoming order.
            if side == "buy":
                self._match_buy_order(order, order_updates)
            else:
                self._match_sell_order(order, order_updates)

            # Identify trades created by this order.
            new_trades = self.trades[len(previous_trades):]

            # Include the incoming order's final quantity.
            order_updates.append(
                (
                    order["id"],
                    order["remaining_quantity"],
                )
            )

            # Save order, trades and updates in one transaction.
            save_order_and_match(
                order,
                new_trades,
                order_updates,
            )

        except Exception:
            # Restore the original state if database saving fails.
            self._buy_heap = previous_buy_heap
            self._sell_heap = previous_sell_heap
            self._active_orders = previous_active_orders
            self.trades = previous_trades

            raise

        # Update order ID only after successful database saving.
        self.order_id += 1

        # Add any remaining quantity to the order book.
        if order["remaining_quantity"] > 0:
            self._active_orders[order["id"]] = order
            self._add_to_heap(order)

        return order

    def _execute_trade(
        self,
        incoming_order,
        resting_order,
        quantity,
        order_updates,
    ):
        """Execute a trade at the resting order's price."""

        trade = {
            "price": float(resting_order["price"]),
            "quantity": int(quantity),
        }

        self.trades.append(trade)

        incoming_order["remaining_quantity"] -= quantity
        resting_order["remaining_quantity"] -= quantity

        order_updates.append(
            (
                resting_order["id"],
                resting_order["remaining_quantity"],
            )
        )

        # Remove fully filled resting orders.
        if resting_order["remaining_quantity"] == 0:
            self._active_orders.pop(
                resting_order["id"],
                None,
            )

    def _match_buy_order(self, order, order_updates):
        """Match incoming buy orders against best sell orders."""

        while order["remaining_quantity"] > 0:
            self._clean_heap("sell")

            if not self._sell_heap:
                break

            best_price, best_id = self._sell_heap[0]

            if order["price"] < best_price:
                break

            resting_order = self._active_orders[best_id]

            trade_quantity = min(
                order["remaining_quantity"],
                resting_order["remaining_quantity"],
            )

            self._execute_trade(
                order,
                resting_order,
                trade_quantity,
                order_updates,
            )

            if resting_order["remaining_quantity"] == 0:
                heapq.heappop(self._sell_heap)

    def _match_sell_order(self, order, order_updates):
        """Match incoming sell orders against best buy orders."""

        while order["remaining_quantity"] > 0:
            self._clean_heap("buy")

            if not self._buy_heap:
                break

            negative_price, best_id = self._buy_heap[0]
            best_price = -negative_price

            if order["price"] > best_price:
                break

            resting_order = self._active_orders[best_id]

            trade_quantity = min(
                order["remaining_quantity"],
                resting_order["remaining_quantity"],
            )

            self._execute_trade(
                order,
                resting_order,
                trade_quantity,
                order_updates,
            )

            if resting_order["remaining_quantity"] == 0:
                heapq.heappop(self._buy_heap)

    def cancel_order(self, order_id):
        """Cancel an active order using its ID."""

        if (
            isinstance(order_id, bool)
            or not isinstance(order_id, int)
        ):
            raise ValueError("Order ID must be an integer")

        order = self._active_orders.get(order_id)

        if order is None:
            return False

        if order["remaining_quantity"] <= 0:
            return False

        result = cancel_order_in_db(order_id)

        if result is False:
            return False

        # Lazy deletion: stale heap entries are removed later.
        self._active_orders.pop(order_id, None)

        return True

    def get_order_book(self):
        """Return independent copies of active orders."""

        return {
            "buy_orders": [
                dict(order)
                for order in self.buy_orders
            ],
            "sell_orders": [
                dict(order)
                for order in self.sell_orders
            ],
        }
