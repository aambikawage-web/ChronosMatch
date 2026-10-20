
import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_NAME = Path(__file__).with_name("chronosmatch.db")


@contextmanager
def connect():
    """Open a database connection and always close it."""
    conn = sqlite3.connect(DB_NAME, timeout=10)

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_tables():
    """Create database tables if they do not exist."""
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL
            )
        """)

        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(orders)")
        }

        if "remaining_quantity" not in columns:
            conn.execute("""
                ALTER TABLE orders
                ADD COLUMN remaining_quantity INTEGER NOT NULL DEFAULT 0
            """)

        if "status" not in columns:
            conn.execute("""
                ALTER TABLE orders
                ADD COLUMN status TEXT NOT NULL DEFAULT 'HISTORICAL'
            """)


def get_next_order_id():
    """Return the next available order ID."""
    with connect() as conn:
        row = conn.execute("""
            SELECT COALESCE(MAX(id), 0) + 1
            FROM orders
        """).fetchone()

        return row[0]


def save_order(order):
    """Save a new order."""
    with connect() as conn:
        conn.execute("""
            INSERT INTO orders (
                id,
                side,
                price,
                quantity,
                remaining_quantity,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            order["id"],
            order["side"],
            order["price"],
            order["quantity"],
            order["quantity"],
            "OPEN",
        ))


def update_order_remaining(order_id, remaining_quantity):
    """Update remaining quantity and order status."""
    with connect() as conn:
        row = conn.execute("""
            SELECT quantity
            FROM orders
            WHERE id = ?
        """, (order_id,)).fetchone()

        if row is None:
            return

        original_quantity = row[0]

        if remaining_quantity == 0:
            status = "FILLED"
        elif remaining_quantity < original_quantity:
            status = "PARTIAL"
        else:
            status = "OPEN"

        conn.execute("""
            UPDATE orders
            SET remaining_quantity = ?, status = ?
            WHERE id = ?
        """, (
            remaining_quantity,
            status,
            order_id,
        ))


def cancel_order_in_db(order_id):
    """Cancel an open or partially filled order."""
    with connect() as conn:
        cursor = conn.execute("""
            UPDATE orders
            SET status = 'CANCELLED'
            WHERE id = ?
              AND status IN ('OPEN', 'PARTIAL')
              AND remaining_quantity > 0
        """, (order_id,))

        return cursor.rowcount > 0


def save_trade(trade):
    """Save an executed trade."""
    with connect() as conn:
        conn.execute("""
            INSERT INTO trades (price, quantity)
            VALUES (?, ?)
        """, (
            trade["price"],
            trade["quantity"],
        ))


def get_active_orders():
    """Get orders that are still open or partially filled."""
    with connect() as conn:
        rows = conn.execute("""
            SELECT
                id,
                side,
                price,
                remaining_quantity AS quantity
            FROM orders
            WHERE status IN ('OPEN', 'PARTIAL')
              AND remaining_quantity > 0
            ORDER BY id
        """).fetchall()

    return [
        {
            "id": row[0],
            "side": row[1],
            "price": row[2],
            "quantity": row[3],
        }
        for row in rows
    ]


def get_all_orders():
    """Get all orders, newest first."""
    with connect() as conn:
        rows = conn.execute("""
            SELECT
                id,
                side,
                price,
                quantity,
                remaining_quantity,
                status
            FROM orders
            ORDER BY id DESC
        """).fetchall()

    columns = [
        "id",
        "side",
        "price",
        "quantity",
        "remaining_quantity",
        "status",
    ]

    return [
        dict(zip(columns, row))
        for row in rows
    ]


def get_all_trades():
    """Get all trades, newest first."""
    with connect() as conn:
        rows = conn.execute("""
            SELECT id, price, quantity
            FROM trades
            ORDER BY id DESC
        """).fetchall()

    return [
        {
            "id": row[0],
            "price": row[1],
            "quantity": row[2],
        }
        for row in rows
    ]


def show_saved_data():
    """Display saved orders and trades."""
    print("\nORDERS:", get_all_orders())
    print("\nTRADES:", get_all_trades())


if __name__ == "__main__":
    create_tables()
    print("Database and tables ready!")
    show_saved_data()
