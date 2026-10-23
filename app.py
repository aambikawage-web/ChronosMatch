
import sqlite3
import uuid
import random
import time
from datetime import datetime

import pandas as pd
import streamlit as st

# ============================================================
# CHRONOSMATCH INSTITUTIONAL SIMULATION TERMINAL
# Simulated data only. No broker connection or live trading.
# Uses a NEW database so older schemas cannot cause errors.
# ============================================================

DB_FILE = "chronosmatch_institutional.db"

SYMBOLS = ["AAPL", "MSFT", "NVDA", "TSLA"]

START_PRICES = {
    "AAPL": 225.00,
    "MSFT": 510.00,
    "NVDA": 180.00,
    "TSLA": 350.00,
}

st.set_page_config(
    page_title="ChronosMatch Institutional",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------- DATABASE ----------------

def connect_db():
    return sqlite3.connect(DB_FILE, timeout=15)


def init_db():
    with connect_db() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                filled_quantity INTEGER NOT NULL DEFAULT 0,
                remaining INTEGER NOT NULL,
                status TEXT NOT NULL,
                latency_us INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                buy_order_id TEXT NOT NULL,
                sell_order_id TEXT NOT NULL,
                latency_us INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                volume INTEGER NOT NULL,
                latency_us INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_orders_symbol
            ON orders(symbol, side, status);

            CREATE INDEX IF NOT EXISTS idx_trades_symbol
            ON trades(symbol, created_at);

            CREATE INDEX IF NOT EXISTS idx_prices_symbol
            ON price_history(symbol, created_at);
        """)


def timestamp():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def query_df(sql, params=()):
    con = connect_db()
    try:
        return pd.read_sql_query(sql, con, params=params)
    finally:
        con.close()


# ---------------- SESSION STATE ----------------

def init_state():
    if "prices" not in st.session_state:
        st.session_state.prices = dict(START_PRICES)

    if "auto_run" not in st.session_state:
        st.session_state.auto_run = True

    if "symbol" not in st.session_state:
        st.session_state.symbol = "AAPL"

    if "orders_per_cycle" not in st.session_state:
        st.session_state.orders_per_cycle = 3


# ---------------- ORDER MATCHING ----------------

def submit_order(symbol, side, quantity, price):
    start = time.perf_counter()

    order_id = uuid.uuid4().hex[:12].upper()
    quantity = int(quantity)
    remaining = quantity
    filled = 0
    created_at = timestamp()

    con = connect_db()

    try:
        con.execute("BEGIN")

        if side == "BUY":
            resting_orders = con.execute("""
                SELECT id, price, quantity, filled_quantity, remaining
                FROM orders
                WHERE symbol = ?
                  AND side = 'SELL'
                  AND status IN ('OPEN', 'PARTIAL')
                  AND remaining > 0
                  AND price <= ?
                ORDER BY price ASC, created_at ASC
            """, (symbol, float(price))).fetchall()

        else:
            resting_orders = con.execute("""
                SELECT id, price, quantity, filled_quantity, remaining
                FROM orders
                WHERE symbol = ?
                  AND side = 'BUY'
                  AND status IN ('OPEN', 'PARTIAL')
                  AND remaining > 0
                  AND price >= ?
                ORDER BY price DESC, created_at ASC
            """, (symbol, float(price))).fetchall()

        for resting in resting_orders:
            if remaining <= 0:
                break

            resting_id, resting_price, _, resting_filled, resting_remaining = resting

            resting_remaining = int(resting_remaining)
            resting_filled = int(resting_filled)

            fill_qty = min(remaining, resting_remaining)

            if fill_qty <= 0:
                continue

            # The resting order's price determines execution price.
            trade_price = float(resting_price)

            if side == "BUY":
                buy_id = order_id
                sell_id = resting_id
            else:
                buy_id = resting_id
                sell_id = order_id

            con.execute("""
                INSERT INTO trades (
                    id, created_at, symbol, price, quantity,
                    buy_order_id, sell_order_id, latency_us
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uuid.uuid4().hex[:12].upper(),
                timestamp(),
                symbol,
                trade_price,
                fill_qty,
                buy_id,
                sell_id,
                0,
            ))

            new_resting_remaining = resting_remaining - fill_qty
            new_resting_filled = resting_filled + fill_qty

            resting_status = (
                "FILLED"
                if new_resting_remaining == 0
                else "PARTIAL"
            )

            con.execute("""
                UPDATE orders
                SET remaining = ?,
                    filled_quantity = ?,
                    status = ?
                WHERE id = ?
            """, (
                new_resting_remaining,
                new_resting_filled,
                resting_status,
                resting_id,
            ))

            remaining -= fill_qty
            filled += fill_qty

        latency_us = max(
            1,
            int((time.perf_counter() - start) * 1_000_000),
        )

        # Update latency for trades created by this incoming order.
        con.execute("""
            UPDATE trades
            SET latency_us = ?
            WHERE buy_order_id = ? OR sell_order_id = ?
        """, (latency_us, order_id, order_id))

        status = (
            "FILLED" if remaining == 0
            else "PARTIAL" if filled > 0
            else "OPEN"
        )

        con.execute("""
            INSERT INTO orders (
                id, created_at, symbol, side, price,
                quantity, filled_quantity, remaining,
                status, latency_us
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_id,
            created_at,
            symbol,
            side,
            float(price),
            quantity,
            filled,
            remaining,
            status,
            latency_us,
        ))

        con.commit()

        return order_id, status, remaining, latency_us

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()


# ---------------- MARKET SIMULATION ----------------

def generate_activity(symbol, count):
    for _ in range(count):
        previous = st.session_state.prices.get(
            symbol, START_PRICES[symbol]
        )

        new_price = max(
            0.01,
            round(previous * (1 + random.uniform(-0.0015, 0.0015)), 2),
        )

        st.session_state.prices[symbol] = new_price

        side = random.choice(["BUY", "SELL"])
        quantity = random.choice([10, 20, 25, 50, 75, 100])

        offset = random.choice([0.00, 0.01, 0.02, 0.03])

        if side == "BUY":
            limit_price = round(new_price + offset, 2)
        else:
            limit_price = round(max(0.01, new_price - offset), 2)

        _, _, _, latency_us = submit_order(
            symbol, side, quantity, limit_price
        )

        con = connect_db()
        try:
            con.execute("""
                INSERT INTO price_history (
                    created_at, symbol, price, volume, latency_us
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                timestamp(),
                symbol,
                new_price,
                quantity,
                latency_us,
            ))
            con.commit()
        finally:
            con.close()


# ---------------- DASHBOARD STYLE ----------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');

.stApp {
    background: radial-gradient(ellipse at top, #0b2821 0%, #061310 65%);
    color: #e4fff5;
    font-family: Inter, sans-serif;
}

[data-testid="stSidebar"] {
    background: #071914;
    border-right: 1px solid #1d594b;
}

[data-testid="stHeader"] {
    background: rgba(6,19,16,.94);
}

.brand {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 23px;
    font-weight: 700;
    letter-spacing: 1px;
}

.brand span {
    color: #43e0b0;
}

.sub {
    color: #86b6a8;
    font-size: 10px;
    letter-spacing: 1.3px;
    margin-top: 6px;
}

.header {
    display: flex;
    justify-content: space-between;
    gap: 15px;
    padding: 20px;
    margin-bottom: 15px;
    background: linear-gradient(110deg, #102d25, #091b17);
    border: 1px solid #24735e;
    border-radius: 12px;
}

.status {
    font-family: monospace;
    color: #43e0b0;
    font-size: 12px;
    text-align: right;
}

.card {
    background: linear-gradient(140deg, #102b24, #0a1c18);
    border: 1px solid #1c5949;
    border-radius: 10px;
    padding: 14px;
    min-height: 100px;
}

.label {
    color: #86b6a8;
    font-size: 10px;
    letter-spacing: 1.2px;
}

.value {
    font-family: monospace;
    font-size: 23px;
    font-weight: 600;
    color: #eafff7;
    margin-top: 8px;
}

.note {
    font-size: 10px;
    color: #83b8a7;
    margin-top: 5px;
}

.section {
    font-size: 11px;
    color: #9dd7c4;
    font-weight: 700;
    letter-spacing: 1.5px;
    margin: 22px 0 10px;
}

.warning {
    border: 1px solid #65552b;
    background: #211e12;
    color: #e8d79d;
    border-radius: 7px;
    padding: 10px;
    margin-bottom: 14px;
    font-size: 11px;
}

div[data-testid="stDataFrame"] {
    border: 1px solid #1c5949;
    border-radius: 8px;
}

footer {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)


# ---------------- START APP ----------------

init_db()
init_state()

with st.sidebar:
    st.markdown(
        '<div class="brand">CHRONOS<span>MATCH</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub">INSTITUTIONAL SIMULATION TERMINAL</div>',
        unsafe_allow_html=True,
    )

    st.divider()
    st.markdown("**MARKET CONFIGURATION**")

    symbol = st.selectbox(
        "Instrument",
        SYMBOLS,
        index=SYMBOLS.index(st.session_state.symbol),
    )
    st.session_state.symbol = symbol

    st.session_state.orders_per_cycle = st.slider(
        "Orders per cycle",
        min_value=1,
        max_value=10,
        value=st.session_state.orders_per_cycle,
    )

    st.divider()
    st.markdown("**SIMULATION CONTROLS**")

    st.session_state.auto_run = st.toggle(
        "Automatic simulation",
        value=st.session_state.auto_run,
    )

    if st.button("Generate one cycle", width="stretch"):
        generate_activity(symbol, st.session_state.orders_per_cycle)
        st.rerun()

    if st.button("Reset simulation data", width="stretch"):
        # Only the NEW dashboard database is cleared.
        with connect_db() as con:
            con.execute("DELETE FROM orders")
            con.execute("DELETE FROM trades")
            con.execute("DELETE FROM price_history")
        st.session_state.prices = dict(START_PRICES)
        st.rerun()

    st.divider()
    st.markdown("**SYSTEM STATUS**")
    st.markdown("🟢 Local simulation ready")
    st.markdown("🟢 Dashboard database connected")
    st.markdown("⚪ Broker connection disabled")
    st.markdown("⚪ Live trading disabled")


if st.session_state.auto_run:
    generate_activity(symbol, st.session_state.orders_per_cycle)

    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(
            interval=2000,
            key="chronosmatch_refresh",
        )
    except ImportError:
        st.info(
            "For automatic refreshing, install "
            "streamlit-autorefresh."
        )


# ---------------- HEADER ----------------

st.markdown("""
<div class="header">
  <div>
    <div class="brand">CHRONOSMATCH <span>INSTITUTIONAL</span></div>
    <div class="sub">
      ORDER MANAGEMENT · MARKET DEPTH · EXECUTION ANALYTICS
    </div>
  </div>
  <div>
    <div class="status">● LOCAL SIMULATION ACTIVE</div>
    <div class="sub">SYNTHETIC DATA · NO LIVE ORDERS</div>
  </div>
</div>
<div class="warning">
  SIMULATION ONLY — all prices, orders, trades, and latency values
  are generated locally. No broker or exchange connection.
</div>
""", unsafe_allow_html=True)


# ---------------- LOAD DATA ----------------

last_price = st.session_state.prices[symbol]

orders = query_df("""
    SELECT *
    FROM orders
    WHERE symbol = ?
    ORDER BY rowid DESC
    LIMIT 500
""", (symbol,))

trades = query_df("""
    SELECT *
    FROM trades
    WHERE symbol = ?
    ORDER BY rowid DESC
    LIMIT 500
""", (symbol,))

prices = query_df("""
    SELECT *
    FROM price_history
    WHERE symbol = ?
    ORDER BY id DESC
    LIMIT 300
""", (symbol,))

latencies_ms = (
    orders["latency_us"].fillna(0) / 1000
    if not orders.empty else pd.Series(dtype=float)
)

trade_volume = (
    int(trades["quantity"].fillna(0).sum())
    if not trades.empty else 0
)

avg_latency = (
    float(latencies_ms.mean())
    if not latencies_ms.empty else 0.0
)


# ---------------- METRICS ----------------

st.markdown(
    '<div class="section">SYSTEM OVERVIEW</div>',
    unsafe_allow_html=True,
)

metrics = st.columns(4)

metric_values = [
    ("LAST SIM PRICE", f"${last_price:,.2f}", symbol),
    ("SIMULATED TRADES", f"{len(trades):,}", "Recorded fills"),
    ("EXECUTED VOLUME", f"{trade_volume:,}", "Units"),
    ("AVG PROCESSING", f"{avg_latency:.3f} ms", "Local measurement"),
]

for col, (label, value, note) in zip(metrics, metric_values):
    with col:
        st.markdown(
            f'<div class="card">'
            f'<div class="label">{label}</div>'
            f'<div class="value">{value}</div>'
            f'<div class="note">{note}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ---------------- ORDER ENTRY ----------------

st.markdown(
    '<div class="section">01 / ORDER ENTRY & MARKET DEPTH</div>',
    unsafe_allow_html=True,
)

entry_col, book_col = st.columns([0.8, 1.5], gap="large")

with entry_col:
    with st.container(border=True):
        side = st.radio("Order side", ["BUY", "SELL"], horizontal=True)

        quantity = st.number_input(
            "Quantity",
            min_value=1,
            max_value=1_000_000,
            value=100,
            step=10,
        )

        limit_price = st.number_input(
            "Limit price ($)",
            min_value=0.01,
            value=float(last_price),
            step=0.01,
            format="%.2f",
        )

        if st.button(
            "SUBMIT SIMULATED ORDER",
            type="primary",
            width="stretch",
        ):
            oid, status, remaining, latency_us = submit_order(
                symbol, side, int(quantity), float(limit_price)
            )

            st.success(
                f"{status} · Order {oid} · Remaining {remaining}"
            )
            st.caption(
                f"Local processing: {latency_us / 1000:.3f} ms"
            )
            st.rerun()


# ---------------- ORDER BOOK ----------------

with book_col:
    bids = query_df("""
        SELECT price,
               SUM(remaining) AS quantity,
               COUNT(*) AS orders
        FROM orders
        WHERE symbol = ?
          AND side = 'BUY'
          AND status IN ('OPEN', 'PARTIAL')
          AND remaining > 0
        GROUP BY price
        ORDER BY price DESC
        LIMIT 10
    """, (symbol,))

    asks = query_df("""
        SELECT price,
               SUM(remaining) AS quantity,
               COUNT(*) AS orders
        FROM orders
        WHERE symbol = ?
          AND side = 'SELL'
          AND status IN ('OPEN', 'PARTIAL')
          AND remaining > 0
        GROUP BY price
        ORDER BY price ASC
        LIMIT 10
    """, (symbol,))

    bid_col, ask_col = st.columns(2)

    with bid_col:
        st.markdown("**BIDS · BUY**")
        if bids.empty:
            st.info("No resting bids.")
        else:
            bids["price"] = bids["price"].map(lambda x: f"${x:,.2f}")
            bids.columns = ["Price", "Quantity", "Orders"]
            st.dataframe(
                bids, hide_index=True, width="stretch", height=280
            )

    with ask_col:
        st.markdown("**ASKS · SELL**")
        if asks.empty:
            st.info("No resting asks.")
        else:
            asks["price"] = asks["price"].map(lambda x: f"${x:,.2f}")
            asks.columns = ["Price", "Quantity", "Orders"]
            st.dataframe(
                asks, hide_index=True, width="stretch", height=280
            )


# ---------------- PERFORMANCE CHARTS ----------------

st.markdown(
    '<div class="section">02 / PERFORMANCE ANALYTICS</div>',
    unsafe_allow_html=True,
)

chart_left, chart_right = st.columns(2, gap="large")

with chart_left:
    st.markdown("**SIMULATED PRICE HISTORY**")
    if not prices.empty:
        plot = prices.copy()
        plot["Time"] = pd.to_datetime(
            plot["created_at"], errors="coerce"
        )
        plot = plot.dropna(subset=["Time"]).sort_values("Time")
        plot = plot.set_index("Time")[["price"]]
        st.line_chart(plot, height=260, width="stretch")
    else:
        st.info("Price history appears as simulation runs.")

with chart_right:
    st.markdown("**EXECUTION VOLUME**")
    if not trades.empty:
        plot = trades.copy()
        plot["Time"] = pd.to_datetime(
            plot["created_at"], errors="coerce"
        )
        plot = plot.dropna(subset=["Time"]).sort_values("Time")
        plot = plot.set_index("Time")[["quantity"]]
        st.bar_chart(plot, height=260, width="stretch")
    else:
        st.info("Volume chart appears after simulated fills.")


# ---------------- LATENCY MONITOR ----------------

st.markdown(
    '<div class="section">03 / LATENCY MONITOR</div>',
    unsafe_allow_html=True,
)

lat_left, lat_right = st.columns([1, 2], gap="large")

p50 = (
    float(latencies_ms.quantile(0.50))
    if not latencies_ms.empty else 0.0
)
p95 = (
    float(latencies_ms.quantile(0.95))
    if not latencies_ms.empty else 0.0
)
p99 = (
    float(latencies_ms.quantile(0.99))
    if not latencies_ms.empty else 0.0
)

with lat_left:
    st.markdown(
        f'<div class="card">'
        f'<div class="label">P50 PROCESSING</div>'
        f'<div class="value">{p50:.3f} ms</div>'
        f'<div class="label">P95 PROCESSING</div>'
        f'<div class="value">{p95:.3f} ms</div>'
        f'<div class="label">P99 PROCESSING</div>'
        f'<div class="value">{p99:.3f} ms</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with lat_right:
    if not orders.empty:
        latency_plot = orders.head(100).copy()
        latency_plot["Sequence"] = range(len(latency_plot), 0, -1)
        latency_plot = latency_plot.sort_values("Sequence")
        latency_plot["latency_ms"] = (
            latency_plot["latency_us"].fillna(0) / 1000
        )
        latency_plot = latency_plot.set_index("Sequence")[["latency_ms"]]
        st.line_chart(latency_plot, height=240, width="stretch")
    else:
        st.info("Latency values appear as orders are submitted.")

    st.caption(
        "Local Python/SQLite processing time, not exchange or network latency."
    )


# ---------------- TRADE FEED ----------------

st.markdown(
    '<div class="section">04 / SIMULATED TRADE FEED</div>',
    unsafe_allow_html=True,
)

if not trades.empty:
    tape = trades.head(30).copy()
    tape = tape.rename(columns={
        "created_at": "Time",
        "id": "Trade ID",
        "symbol": "Symbol",
        "price": "Price",
        "quantity": "Quantity",
        "buy_order_id": "Buy Order",
        "sell_order_id": "Sell Order",
        "latency_us": "Latency (us)",
    })

    columns = [
        c for c in [
            "Time", "Trade ID", "Symbol", "Price", "Quantity",
            "Buy Order", "Sell Order", "Latency (us)"
        ] if c in tape.columns
    ]

    st.dataframe(
        tape[columns],
        hide_index=True,
        width="stretch",
    )
else:
    st.info(
        "No trades yet. A trade is created when buy and sell prices cross."
    )


# ---------------- ORDER AUDIT ----------------

with st.expander("Order history and audit trail"):
    if not orders.empty:
        st.dataframe(
            orders.head(100),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No orders recorded yet.")

st.divider()

st.caption(
    "CHRONOSMATCH INSTITUTIONAL · SIMULATION ONLY · NO LIVE TRADING"
)
