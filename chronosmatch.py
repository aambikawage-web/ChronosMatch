from database import (
    create_tables,
    save_order,
    save_trade,
    get_next_order_id,
    get_active_orders,
    update_order_remaining,
)


class ChronosMatch:

    def __init__(self):
        create_tables()
        self.buy_orders = []
        self.sell_orders = []
        self.trades = []
        self.order_id = get_next_order_id()

        for order in get_active_orders():
            if order["side"] == "buy":
                self.buy_orders.append(order)
            else:
                self.sell_orders.append(order)

        self._sort_orders()

    def _sort_orders(self):
        self.buy_orders.sort(key=lambda o: (-o["price"], o["id"]))
        self.sell_orders.sort(key=lambda o: (o["price"], o["id"]))

    def submit_order(self, side, price, quantity):
        if not isinstance(side, str):
            raise ValueError("Side must be buy or sell")

        side = side.lower()

        if side not in ("buy", "sell"):
            raise ValueError("Invalid order side")

        if price <= 0 or quantity <= 0:
            raise ValueError("Price and quantity must be positive")

        if int(quantity) != quantity:
            raise ValueError("Quantity must be a whole number")

        order = {
            "id": self.order_id,
            "side": side,
            "price": float(price),
            "quantity": int(quantity),
        }

        save_order(order)
        self.order_id += 1

        if side == "buy":
            self._match_buy(order)
        else:
            self._match_sell(order)

        update_order_remaining(order["id"], order["quantity"])
        self._sort_orders()
        return order

    def _match_buy(self, order):
        while (
            order["quantity"] > 0
            and self.sell_orders
            and order["price"] >= self.sell_orders[0]["price"]
        ):
            seller = self.sell_orders[0]
            qty = min(order["quantity"], seller["quantity"])

            trade = {
                "price": seller["price"],
                "quantity": qty,
            }

            save_trade(trade)
            self.trades.append(trade)

            order["quantity"] -= qty
            seller["quantity"] -= qty

            update_order_remaining(seller["id"], seller["quantity"])

            if seller["quantity"] == 0:
                self.sell_orders.pop(0)

        if order["quantity"] > 0:
            self.buy_orders.append(order)

    def _match_sell(self, order):
        while (
            order["quantity"] > 0
            and self.buy_orders
            and order["price"] <= self.buy_orders[0]["price"]
        ):
            buyer = self.buy_orders[0]
            qty = min(order["quantity"], buyer["quantity"])

            trade = {
                "price": buyer["price"],
                "quantity": qty,
            }

            save_trade(trade)
            self.trades.append(trade)

            order["quantity"] -= qty
            buyer["quantity"] -= qty

            update_order_remaining(buyer["id"], buyer["quantity"])

            if buyer["quantity"] == 0:
                self.buy_orders.pop(0)

        if order["quantity"] > 0:
            self.sell_orders.append(order)

    def show_orders(self):
        print("BUY ORDERS:", self.buy_orders)
        print("SELL ORDERS:", self.sell_orders)


if __name__ == "__main__":
    engine = ChronosMatch()
    print("ChronosMatch engine ready.")
    engine.show_orders()