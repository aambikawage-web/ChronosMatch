
from __future__ import annotations

import random
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ==========================================================
# CHRONOSMATCH - HIGH FREQUENCY TRADING SIMULATION TERMINAL
# Educational simulation only. No live trading.
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "chronosmatch_simulation.db"

SYMBOLS = ["AAPL", "MSFT", "NVDA", "TSLA"]

DEFAULT_PRICES = {
    "AAPL": 249.00,
    "MSFT": 512.00,
    "NVDA": 184.00,
    "TSLA": 341.00,
}

st.set_page_config(
    page_title="ChronosMatch | HFT Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================================
# STYLING
# ==========================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Inter:wght@400;500;600;700;800&display=swap');

    .stApp {
        background: #080d16;
        color: #e6edf7;
        font-family: Inter, sans-serif;
    }

    [data-testid="stHeader"] {
        background: #080d16;
    }

    [data-testid="stSidebar"] {
        background: #0b1220;
        border-right: 1px solid #20324a;
    }

    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #101b2c, #0c1421);
        border: 1px solid #20324a;
        border-radius: 12px;
        padding: 14px;
    }

    [data-testid="stMetricLabel"] {
        color: #93a8c3;
    }

    [data-testid="stMetricValue"] {
        color: #f4f8ff;
        font-family: 'DM Mono', monospace;
        font-size: 24px;
    }

    .terminal-title {
        font-size: 30px;
        font-weight: 800;
        color: #f3f7ff;
    }

    .terminal-sub {
        color: #8ea3bf;
        font-size: 13px;
    }

    .sim-badge {
        display: inline-block;
        background: #33260f;
        color: #fbbf24;
        border: 1px solid #76561b;
        border-radius: 20px;
        padding: 5px 10px;
        font-size: 11px;
        font-weight: 700;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid #20324a;
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==========================================================
# DATABASE CONNECTION
# ==========================================================

def connect_db():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=15,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def columns(conn, table):
    return {
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }


def ensure_column(conn, table, name, definition):
    if name not in columns(conn, table):
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN {name} {definition}"
        )


def initialize_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sim_orders (
                order_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                filled_quantity INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'OPEN',
                latency_us REAL NOT NULL DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sim_trades (
                trade_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                buy_order_id TEXT NOT NULL,
                sell_order_id TEXT NOT NULL,
                latency_us REAL NOT NULL DEFAULT 0,
                latency_ms REAL DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sim_state (
                symbol TEXT PRIMARY KEY,
                last_price REAL NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sim_ticks (
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        # Add optional fields if an older table is missing them.
        order_fields = {
            "timestamp": "TEXT",
            "symbol": "TEXT",
            "side": "TEXT",
            "price": "REAL DEFAULT 0",
            "quantity": "INTEGER DEFAULT 0",
            "filled_quantity": "INTEGER DEFAULT 0",
            "status": "TEXT DEFAULT 'OPEN'",
            "latency_us": "REAL DEFAULT 0",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }

        for name, definition in order_fields.items():
            ensure_column(conn, "sim_orders", name, definition)

        trade_fields = {
            "timestamp": "TEXT",
            "symbol": "TEXT",
            "price": "REAL DEFAULT 0",
            "quantity": "INTEGER DEFAULT 0",
            "buy_order_id": "TEXT",
            "sell_order_id": "TEXT",
            "latency_us": "REAL DEFAULT 0",
            "latency_ms": "REAL DEFAULT 0",
        }

        for name, definition in trade_fields.items():
            ensure_column(conn, "sim_trades", name, definition)

        now = datetime.now().isoformat(timespec="milliseconds")

        for symbol, price in DEFAULT_PRICES.items():
            conn.execute("""
                INSERT OR IGNORE INTO sim_state
                (symbol, last_price, updated_at)
                VALUES (?, ?, ?)
            """, (symbol, price, now))

            conn.execute("""
                INSERT INTO sim_ticks(symbol, price, timestamp)
                SELECT ?, ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM sim_ticks WHERE symbol = ?
                )
            """, (symbol, price, now, symbol))

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sim_orders_symbol
            ON sim_orders(symbol, status)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sim_trades_symbol
            ON sim_trades(symbol, timestamp)
        """)


def read_df(sql, params=()):
    with connect_db() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def current_price(symbol):
    with connect_db() as conn:
        row = conn.execute(
            "SELECT last_price FROM sim_state WHERE symbol=?",
            (symbol,),
        ).fetchone()

    if row:
        return float(row["last_price"])

    return DEFAULT_PRICES[symbol]


def update_price(symbol, price):
    now = datetime.now().isoformat(timespec="milliseconds")

    with connect_db() as conn:
        conn.execute("""
            INSERT INTO sim_state(symbol, last_price, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                last_price=excluded.last_price,
                updated_at=excluded.updated_at
        """, (symbol, price, now))

        conn.execute("""
            INSERT INTO sim_ticks(symbol, price, timestamp)
            VALUES (?, ?, ?)
        """, (symbol, price, now))

        conn.execute("""
            DELETE FROM sim_ticks
            WHERE rowid IN (
                SELECT rowid FROM sim_ticks
                WHERE symbol=?
                ORDER BY rowid DESC
                LIMIT -1 OFFSET 500
            )
        """, (symbol,))


# ==========================================================
# ORDER MATCHING ENGINE
# ==========================================================

def place_order(symbol, side, quantity, price):
    side = side.upper()
    quantity = int(quantity)
    price = round(float(price), 2)

    if symbol not in SYMBOLS:
        raise ValueError("Unsupported market symbol.")

    if side not in ("BUY", "SELL"):
        raise ValueError("Side must be BUY or SELL.")

    if quantity < 1:
        raise ValueError("Quantity must be at least 1.")

    if price <= 0:
        raise ValueError("Price must be greater than zero.")

    started = time.perf_counter()
    order_id = uuid.uuid4().hex[:12].upper()
    now = datetime.now().isoformat(timespec="milliseconds")

    remaining = quantity
    filled = 0

    with connect_db() as conn:
        conn.execute("BEGIN IMMEDIATE")

        conn.execute("""
            INSERT INTO sim_orders (
                order_id, timestamp, symbol, side, price,
                quantity, filled_quantity, status,
                latency_us, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 0, 'OPEN', 0, ?, ?)
        """, (
            order_id, now, symbol, side, price,
            quantity, now, now,
        ))

        opposite = "SELL" if side == "BUY" else "BUY"
        comparator = "<=" if side == "BUY" else ">="
        price_sort = "ASC" if side == "BUY" else "DESC"

        resting = conn.execute(f"""
            SELECT * FROM sim_orders
            WHERE symbol=?
              AND side=?
              AND status IN ('OPEN', 'PARTIAL')
              AND quantity > filled_quantity
              AND price {comparator} ?
            ORDER BY price {price_sort}, timestamp ASC, rowid ASC
        """, (symbol, opposite, price)).fetchall()

        for old in resting:
            if remaining <= 0:
                break

            old_remaining = (
                int(old["quantity"]) - int(old["filled_quantity"])
            )

            fill_qty = min(remaining, old_remaining)

            if fill_qty <= 0:
                continue

            execution_price = float(old["price"])

            if side == "BUY":
                buy_id, sell_id = order_id, old["order_id"]
            else:
                buy_id, sell_id = old["order_id"], order_id

            latency_ms = (time.perf_counter() - started) * 1000
            trade_time = datetime.now().isoformat(
                timespec="milliseconds"
            )

            conn.execute("""
                INSERT INTO sim_trades (
                    trade_id, timestamp, symbol, price, quantity,
                    buy_order_id, sell_order_id, latency_us, latency_ms
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uuid.uuid4().hex[:12].upper(),
                trade_time,
                symbol,
                execution_price,
                fill_qty,
                buy_id,
                sell_id,
                latency_ms * 1000,
                latency_ms,
            ))

            old_filled = int(old["filled_quantity"]) + fill_qty
            old_status = (
                "FILLED"
                if old_filled >= int(old["quantity"])
                else "PARTIAL"
            )

            conn.execute("""
                UPDATE sim_orders
                SET filled_quantity=?, status=?, updated_at=?
                WHERE order_id=?
            """, (
                old_filled,
                old_status,
                trade_time,
                old["order_id"],
            ))

            remaining -= fill_qty
            filled += fill_qty

        status = (
            "FILLED" if remaining == 0
            else "PARTIAL" if filled > 0
            else "OPEN"
        )

        total_latency_us = (time.perf_counter() - started) * 1_000_000

        conn.execute("""
            UPDATE sim_orders
            SET filled_quantity=?, status=?, updated_at=?, latency_us=?
            WHERE order_id=?
        """, (
            filled,
            status,
            datetime.now().isoformat(timespec="milliseconds"),
            total_latency_us,
            order_id,
        ))

    return {
        "order_id": order_id,
        "status": status,
        "filled": filled,
        "remaining": remaining,
    }


def generate_event(symbol):
    old_price = current_price(symbol)

    new_price = max(
        1.0,
        old_price * (1 + random.uniform(-0.001, 0.001)),
    )

    new_price = round(new_price, 2)
    update_price(symbol, new_price)

    side = random.choice(["BUY", "SELL"])
    limit_price = round(
        new_price * (1 + random.uniform(-0.0015, 0.0015)),
        2,
    )

    quantity = random.choice([1, 2, 3, 5, 8, 10, 12, 20, 25])

    return place_order(symbol, side, quantity, limit_price)


# ==========================================================
# DATA LOADERS
# ==========================================================

def get_orders(symbol, limit=300):
    return read_df("""
        SELECT order_id, timestamp, symbol, side, price, quantity,
               filled_quantity,
               MAX(quantity-filled_quantity, 0) AS remaining,
               status, latency_us
        FROM sim_orders
        WHERE symbol=?
        ORDER BY rowid DESC
        LIMIT ?
    """, (symbol, limit))


def get_trades(symbol, limit=300):
    return read_df("""
        SELECT trade_id, timestamp, symbol, price, quantity,
               buy_order_id, sell_order_id, latency_us, latency_ms
        FROM sim_trades
        WHERE symbol=?
        ORDER BY rowid DESC
        LIMIT ?
    """, (symbol, limit))


def get_ticks(symbol, limit=250):
    frame = read_df("""
        SELECT price, timestamp FROM sim_ticks
        WHERE symbol=?
        ORDER BY rowid DESC
        LIMIT ?
    """, (symbol, limit))

    if not frame.empty:
        frame = frame.iloc[::-1].reset_index(drop=True)
        frame["timestamp"] = pd.to_datetime(
            frame["timestamp"], errors="coerce"
        )

    return frame


def csv_data(frame):
    return frame.to_csv(index=False).encode("utf-8-sig")


def money(value):
    return f"${float(value):,.2f}"


# ==========================================================
# STARTUP
# ==========================================================

initialize_db()
st_autorefresh(interval=2000, key="terminal_refresh")

# ==========================================================
# SIDEBAR
# ==========================================================

with st.sidebar:
    st.markdown("## ◈ CHRONOSMATCH")
    st.caption("ZERO-COPY HFT ENGINE")
    st.markdown("---")

    symbol = st.selectbox("Market symbol", SYMBOLS)

    automatic = st.toggle("Automatic simulation", value=True)
    events = st.slider("Events per refresh", 1, 10, 3)

    st.markdown("---")
    st.markdown("### Manual order")

    with st.form("manual_order"):
        manual_symbol = st.selectbox(
            "Symbol", SYMBOLS, key="manual_symbol"
        )
        manual_side = st.radio(
            "Side", ["BUY", "SELL"], horizontal=True
        )
        manual_quantity = st.number_input(
            "Quantity", min_value=1, max_value=100000, value=10
        )
        manual_price = st.number_input(
            "Limit price ($)",
            min_value=0.01,
            value=float(round(current_price(manual_symbol), 2)),
            step=0.05,
            format="%.2f",
        )
        submit = st.form_submit_button(
            "Submit simulated order",
            use_container_width=True,
        )

    st.markdown("---")
    st.markdown(
        '<span class="sim-badge">SIMULATION ONLY</span>',
        unsafe_allow_html=True,
    )
    st.caption("No broker or live exchange connection.")

if automatic:
    for _ in range(events):
        try:
            generate_event(symbol)
        except Exception as exc:
            st.sidebar.error(f"Simulation error: {exc}")
            break

if submit:
    try:
        result = place_order(
            manual_symbol,
            manual_side,
            manual_quantity,
            manual_price,
        )
        st.sidebar.success(
            f"{result['order_id']} · {result['status']} · "
            f"filled {result['filled']}/{manual_quantity}"
        )
    except Exception as exc:
        st.sidebar.error(f"Order failed: {exc}")

# ==========================================================
# LOAD DATA
# ==========================================================

price = current_price(symbol)
orders = get_orders(symbol)
trades = get_trades(symbol)
ticks = get_ticks(symbol)

order_count = len(orders)
trade_count = len(trades)

filled_orders = (
    int((orders["status"] == "FILLED").sum())
    if not orders.empty else 0
)

fill_rate = (
    filled_orders / order_count * 100
    if order_count else 0
)

trade_volume = (
    int(trades["quantity"].sum())
    if not trades.empty else 0
)

avg_latency = (
    float(trades["latency_ms"].mean())
    if not trades.empty else 0.0
)

# ==========================================================
# HEADER
# ==========================================================

st.markdown(
    """
    <div class="terminal-title">
        ChronosMatch <span style="color:#28d9a2">/</span>
        Market Terminal
    </div>
    <div class="terminal-sub">
        Order matching · Market depth · Execution analytics
    </div>
    <br>
    <span class="sim-badge">● SYNTHETIC DATA · SIMULATION ONLY</span>
    <hr style="border-color:#20324a">
    """,
    unsafe_allow_html=True,
)

# ==========================================================
# TOP METRICS
# ==========================================================

m1, m2, m3, m4, m5 = st.columns(5)

m1.metric(f"{symbol} price", money(price))
m2.metric("Total orders", f"{order_count:,}")
m3.metric("Executed trades", f"{trade_count:,}")
m4.metric("Filled-order rate", f"{fill_rate:.1f}%")
m5.metric("Avg match latency", f"{avg_latency:.2f} ms")

# ==========================================================
# PRICE CHART
# ==========================================================

left, right = st.columns([1.6, 1])

with left:
    st.subheader("Price movement")

    if not ticks.empty:
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=ticks["timestamp"],
            y=ticks["price"],
            mode="lines",
            line=dict(color="#28d9a2", width=2),
            fill="tozeroy",
            fillcolor="rgba(40,217,162,0.07)",
            name="Synthetic price",
        ))

        low = float(ticks["price"].min())
        high = float(ticks["price"].max())
        padding = max((high - low) * 0.20, 0.10)

        fig.update_layout(
            template="plotly_dark",
            height=330,
            margin=dict(l=10, r=10, t=20, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0b1422",
            xaxis_title=None,
            yaxis_title="Price ($)",
            showlegend=False,
        )

        # Zoom in around the actual price range.
        fig.update_yaxes(
            gridcolor="#20324a",
            range=[low - padding, high + padding],
            tickprefix="$",
        )
        fig.update_xaxes(showgrid=False)

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Waiting for simulated price ticks.")

# ==========================================================
# MARKET SNAPSHOT
# ==========================================================

with right:
    st.subheader("Market snapshot")

    book = read_df("""
        SELECT side, price, quantity, filled_quantity
        FROM sim_orders
        WHERE symbol=?
          AND status IN ('OPEN', 'PARTIAL')
    """, (symbol,))

    best_bid = None
    best_ask = None

    if not book.empty:
        book["remaining"] = (
            book["quantity"] - book["filled_quantity"]
        ).clip(lower=0)

        book = book[book["remaining"] > 0]
        bids = book[book["side"] == "BUY"]
        asks = book[book["side"] == "SELL"]

        if not bids.empty:
            best_bid = float(bids["price"].max())

        if not asks.empty:
            best_ask = float(asks["price"].min())

    spread = (
        best_ask - best_bid
        if best_bid is not None and best_ask is not None
        else None
    )

    a, b = st.columns(2)
    a.metric("Best bid", money(best_bid) if best_bid is not None else "—")
    b.metric("Best ask", money(best_ask) if best_ask is not None else "—")

    st.metric("Bid/ask spread", money(spread) if spread is not None else "—")
    st.metric("Executed quantity", f"{trade_volume:,}")

# ==========================================================
# TABS
# ==========================================================

tab_book, tab_tape, tab_analytics, tab_orders, tab_export = st.tabs([
    "Order book",
    "Trade tape",
    "Analytics",
    "Order history",
    "CSV export",
])

# ==========================================================
# ORDER BOOK
# ==========================================================

with tab_book:
    st.subheader("Market depth")

    if not book.empty:
        bids = (
            book[book["side"] == "BUY"]
            .groupby("price", as_index=False)["remaining"]
            .sum()
            .sort_values("price", ascending=False)
            .head(12)
            .rename(columns={
                "price": "Bid price ($)",
                "remaining": "Remaining quantity",
            })
        )

        asks = (
            book[book["side"] == "SELL"]
            .groupby("price", as_index=False)["remaining"]
            .sum()
            .sort_values("price")
            .head(12)
            .rename(columns={
                "price": "Ask price ($)",
                "remaining": "Remaining quantity",
            })
        )
    else:
        bids = pd.DataFrame(columns=["Bid price ($)", "Remaining quantity"])
        asks = pd.DataFrame(columns=["Ask price ($)", "Remaining quantity"])

    bid_col, ask_col = st.columns(2)

    with bid_col:
        st.markdown("### 🟢 BUY ORDERS")
        if bids.empty:
            st.info("No resting buy orders.")
        else:
            st.dataframe(bids, hide_index=True, use_container_width=True)

    with ask_col:
        st.markdown("### 🔴 SELL ORDERS")
        if asks.empty:
            st.info("No resting sell orders.")
        else:
            st.dataframe(asks, hide_index=True, use_container_width=True)

# ==========================================================
# TRADE TAPE
# ==========================================================

with tab_tape:
    st.subheader("Recent simulated executions")

    if trades.empty:
        st.info("Waiting for simulated trades.")
    else:
        tape = trades.head(100).copy()
        tape["timestamp"] = pd.to_datetime(
            tape["timestamp"], errors="coerce"
        ).dt.strftime("%H:%M:%S.%f").str[:-3]

        tape = tape.rename(columns={
            "trade_id": "Trade ID",
            "timestamp": "Time",
            "symbol": "Symbol",
            "price": "Price ($)",
            "quantity": "Quantity",
            "buy_order_id": "Buy order ID",
            "sell_order_id": "Sell order ID",
            "latency_ms": "Latency (ms)",
        })

        st.dataframe(
            tape,
            hide_index=True,
            use_container_width=True,
            height=400,
        )

        st.download_button(
            "Download trade tape CSV",
            csv_data(tape),
            "chronosmatch_trade_tape.csv",
            "text/csv",
        )

# ==========================================================
# ANALYTICS
# ==========================================================

with tab_analytics:
    st.subheader("Execution analytics")

    a, b, c, d = st.columns(4)

    a.metric("Executed volume", f"{trade_volume:,}")
    b.metric(
        "Average trade price",
        money(trades["price"].mean()) if not trades.empty else "—",
    )
    c.metric("Average latency", f"{avg_latency:.2f} ms")
    d.metric("Fully filled orders", f"{filled_orders:,}")

    if not trades.empty:
        chart = trades.copy()
        chart["timestamp"] = pd.to_datetime(
            chart["timestamp"], errors="coerce"
        )
        chart = chart.dropna(subset=["timestamp"]).sort_values("timestamp")

        if not chart.empty:
            volume_fig = px.bar(
                chart.tail(80),
                x="timestamp",
                y="quantity",
                title="Recent executed quantity",
                labels={
                    "timestamp": "Time",
                    "quantity": "Quantity",
                },
            )
            volume_fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#0b1422",
            )
            st.plotly_chart(volume_fig, use_container_width=True)

        latency_fig = px.histogram(
            trades,
            x="latency_ms",
            nbins=20,
            title="Simulated matching latency distribution",
            labels={"latency_ms": "Latency (ms)"},
        )
        latency_fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0b1422",
        )
        st.plotly_chart(latency_fig, use_container_width=True)
    else:
        st.info("Analytics will appear as simulated trades are created.")

# ==========================================================
# ORDER HISTORY
# ==========================================================

with tab_orders:
    st.subheader("Recent order history")

    if orders.empty:
        st.info("No orders recorded.")
    else:
        order_view = orders.copy().rename(columns={
            "order_id": "Order ID",
            "timestamp": "Timestamp",
            "symbol": "Symbol",
            "side": "Side",
            "price": "Limit price ($)",
            "quantity": "Quantity",
            "filled_quantity": "Filled",
            "remaining": "Remaining",
            "status": "Status",
            "latency_us": "Latency (µs)",
        })

        st.dataframe(
            order_view,
            hide_index=True,
            use_container_width=True,
            height=400,
        )

        st.download_button(
            "Download order history CSV",
            csv_data(order_view),
            "chronosmatch_orders.csv",
            "text/csv",
        )

# ==========================================================
# CSV EXPORT
# ==========================================================

with tab_export:
    st.subheader("Export simulation records")

    all_orders = read_df("""
        SELECT order_id, timestamp, symbol, side, price,
               quantity, filled_quantity, status, latency_us
        FROM sim_orders
        ORDER BY rowid DESC
        LIMIT 1500
    """)

    all_trades = read_df("""
        SELECT trade_id, timestamp, symbol, price, quantity,
               buy_order_id, sell_order_id, latency_us, latency_ms
        FROM sim_trades
        ORDER BY rowid DESC
        LIMIT 1500
    """)

    x, y = st.columns(2)

    with x:
        st.markdown("### Orders")
        st.write(f"{len(all_orders)} records")
        st.download_button(
            "Export all orders",
            csv_data(all_orders),
            "chronosmatch_all_orders.csv",
            "text/csv",
            use_container_width=True,
        )

    with y:
        st.markdown("### Trades")
        st.write(f"{len(all_trades)} records")
        st.download_button(
            "Export all trades",
            csv_data(all_trades),
            "chronosmatch_all_trades.csv",
            "text/csv",
            use_container_width=True,
        )

    st.caption("CSV exports contain simulation records only.")

# ==========================================================
# FOOTER
# ==========================================================

st.markdown(
    """
    <hr style="border-color:#20324a">
    <div style="color:#7f93ae;font-size:12px">
        CHRONOSMATCH · EDUCATIONAL HFT SIMULATION
        · Synthetic prices and orders
        · No live exchange or broker connection
    </div>
    """,
    unsafe_allow_html=True,
)
