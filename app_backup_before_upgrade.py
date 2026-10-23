
import random
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# =========================================================
# CHRONOSMATCH — PROFESSIONAL HFT SIMULATION TERMINAL
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "chronosmatch_simulation.db"

REFRESH_MS = 2000
MAX_ROWS = 500
SYMBOLS = ["AAPL", "MSFT", "NVDA", "TSLA"]

st.set_page_config(
    page_title="ChronosMatch | HFT Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st_autorefresh(interval=REFRESH_MS, key="hft_auto_refresh")


# =========================================================
# STYLE
# =========================================================

st.markdown(
    """
    <style>
    .stApp {
        background: #080c12;
        color: #d9e2ef;
    }

    [data-testid="stSidebar"] {
        background: #0c131d;
        border-right: 1px solid #263445;
    }

    .terminal-header {
        background: linear-gradient(120deg, #101d2b, #0a111a);
        border: 1px solid #263b4e;
        border-radius: 12px;
        padding: 22px 25px;
        margin-bottom: 18px;
    }

    .brand {
        color: #61f5c6;
        font-size: 28px;
        font-weight: 850;
        letter-spacing: 2px;
    }

    .brand span {
        color: #e1eaf5;
    }

    .subtitle {
        color: #8398ae;
        font-size: 11px;
        letter-spacing: 1.8px;
        margin-top: 7px;
    }

    .engine-status {
        color: #61f5c6;
        font-size: 13px;
        font-weight: bold;
    }

    .section-label {
        color: #8fa5bd;
        font-size: 11px;
        letter-spacing: 1.7px;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .panel {
        background: #0e1722;
        border: 1px solid #243447;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }

    .small-note {
        color: #8296aa;
        font-size: 12px;
    }

    div[data-testid="stMetric"] {
        background: #0e1722;
        border: 1px solid #243447;
        padding: 14px;
        border-radius: 10px;
    }

    div[data-testid="stMetricLabel"] {
        color: #91a6bb;
    }

    div[data-testid="stMetricValue"] {
        color: #61f5c6;
    }

    h1, h2, h3 {
        color: #e1eaf5;
    }

    .stTabs [data-baseweb="tab"] {
        color: #a8b9cc;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid #243447;
        border-radius: 8px;
    }

    .footer {
        border-top: 1px solid #243447;
        margin-top: 25px;
        padding-top: 15px;
        text-align: center;
        color: #71869b;
        font-size: 11px;
        letter-spacing: 1px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# DATABASE — SEPARATE SIMULATION TABLES
# Existing chronosmatch.db is left untouched.
# =========================================================

def connect_db():
    return sqlite3.connect(DB_PATH, timeout=10)


def init_db():
    with connect_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS sim_orders (
                order_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                filled_quantity INTEGER NOT NULL,
                status TEXT NOT NULL,
                latency_us REAL NOT NULL
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS sim_trades (
                trade_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                buy_order_id TEXT NOT NULL,
                sell_order_id TEXT NOT NULL,
                latency_us REAL NOT NULL
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS sim_state (
                symbol TEXT PRIMARY KEY,
                last_price REAL NOT NULL
            )
        """)

        for symbol, price in {
            "AAPL": 225.00,
            "MSFT": 510.00,
            "NVDA": 180.00,
            "TSLA": 340.00,
        }.items():
            con.execute(
                "INSERT OR IGNORE INTO sim_state VALUES (?, ?)",
                (symbol, price),
            )


def load_table(table_name):
    # Only call with the fixed internal table names below.
    allowed = {"sim_orders", "sim_trades", "sim_state"}
    if table_name not in allowed:
        raise ValueError("Unknown table")

    with connect_db() as con:
        return pd.read_sql_query(
            f"SELECT * FROM {table_name}",
            con,
        )


def get_last_price(symbol):
    with connect_db() as con:
        row = con.execute(
            "SELECT last_price FROM sim_state WHERE symbol = ?",
            (symbol,),
        ).fetchone()

    return float(row[0]) if row else 100.0


def save_last_price(symbol, price):
    with connect_db() as con:
        con.execute(
            """
            INSERT INTO sim_state(symbol, last_price)
            VALUES (?, ?)
            ON CONFLICT(symbol) DO UPDATE SET last_price = excluded.last_price
            """,
            (symbol, price),
        )


# =========================================================
# SIMULATED MATCHING ENGINE
# =========================================================

def simulate_market_event(symbol):
    """
    Generate one synthetic order. A crossing order is matched
    against a resting opposite-side order for the same symbol.
    No broker or exchange is contacted.
    """
    start_ns = time.perf_counter_ns()
    now = datetime.now().astimezone().isoformat(timespec="milliseconds")

    reference_price = get_last_price(symbol)

    # Synthetic price movement, intentionally small.
    reference_price = max(
        1.0,
        reference_price + random.choice([-1, -0.5, 0, 0.5, 1])
    )

    side = random.choice(["BUY", "SELL"])
    quantity = random.randint(1, 25)

    # Random limit price around the reference.
    offset = random.choice([-1.0, -0.5, 0.0, 0.5, 1.0])
    price = round(reference_price + offset, 2)

    order_id = "ORD-" + uuid.uuid4().hex[:10].upper()
    status = "OPEN"
    filled_quantity = 0
    trades_created = []

    with connect_db() as con:
        # Look for an opposite-side resting order that can match.
        opposite_side = "SELL" if side == "BUY" else "BUY"

        if side == "BUY":
            crossing_condition = "price <= ?"
            price_order = "price ASC, timestamp ASC"
        else:
            crossing_condition = "price >= ?"
            price_order = "price DESC, timestamp ASC"

        candidates = con.execute(
            f"""
            SELECT order_id, price, quantity, filled_quantity
            FROM sim_orders
            WHERE symbol = ?
              AND side = ?
              AND status IN ('OPEN', 'PARTIAL')
              AND {crossing_condition}
            ORDER BY {price_order}
            LIMIT 10
            """,
            (symbol, opposite_side, price),
        ).fetchall()

        remaining = quantity

        for resting_id, resting_price, resting_qty, resting_filled in candidates:
            available = int(resting_qty) - int(resting_filled)
            if available <= 0:
                continue

            matched_qty = min(remaining, available)
            remaining -= matched_qty
            filled_quantity += matched_qty

            # Trade occurs at the resting order's price.
            trade_price = round(float(resting_price), 2)
            trade_id = "TRD-" + uuid.uuid4().hex[:10].upper()

            trades_created.append((
                trade_id,
                now,
                symbol,
                trade_price,
                matched_qty,
                order_id,
                resting_id,
                0.0,
            ))

            new_resting_filled = int(resting_filled) + matched_qty
            resting_status = (
                "FILLED"
                if new_resting_filled >= int(resting_qty)
                else "PARTIAL"
            )

            con.execute(
                """
                UPDATE sim_orders
                SET filled_quantity = ?, status = ?
                WHERE order_id = ?
                """,
                (new_resting_filled, resting_status, resting_id),
            )

            if remaining == 0:
                break

        status = (
            "FILLED" if filled_quantity == quantity
            else "PARTIAL" if filled_quantity > 0
            else "OPEN"
        )

        latency_us = (time.perf_counter_ns() - start_ns) / 1000.0

        con.execute(
            """
            INSERT INTO sim_orders (
                order_id, timestamp, symbol, side, price,
                quantity, filled_quantity, status, latency_us
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id, now, symbol, side, price,
                quantity, filled_quantity, status, latency_us,
            ),
        )

        for trade in trades_created:
            con.execute(
                """
                INSERT INTO sim_trades (
                    trade_id, timestamp, symbol, price, quantity,
                    buy_order_id, sell_order_id, latency_us
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                trade,
            )

        # Update synthetic reference price after this event.
        latest_price = round(
            max(1.0, reference_price + random.choice([-0.5, 0, 0.5])),
            2,
        )

        con.execute(
            """
            UPDATE sim_state SET last_price = ? WHERE symbol = ?
            """,
            (latest_price, symbol),
        )

        # Bound database growth for a lightweight demo.
        con.execute("""
            DELETE FROM sim_orders
            WHERE order_id NOT IN (
                SELECT order_id FROM sim_orders
                ORDER BY timestamp DESC LIMIT ?
            )
        """, (MAX_ROWS,))

        con.execute("""
            DELETE FROM sim_trades
            WHERE trade_id NOT IN (
                SELECT trade_id FROM sim_trades
                ORDER BY timestamp DESC LIMIT ?
            )
        """, (MAX_ROWS,))


# =========================================================
# START SIMULATOR / SETTINGS
# =========================================================

init_db()

with st.sidebar:
    st.markdown("## ⚡ CHRONOSMATCH")
    st.caption("Order Matching & Execution Analytics")
    st.divider()

    selected_symbol = st.selectbox(
        "SIMULATION SYMBOL",
        SYMBOLS,
        index=0,
    )

    simulation_enabled = st.toggle(
        "Run simulation",
        value=True,
        help="Generate synthetic orders locally.",
    )

    event_rate = st.slider(
        "Events per refresh",
        min_value=1,
        max_value=10,
        value=3,
    )

    st.divider()
    st.markdown("### ENGINE STATUS")

    if simulation_enabled:
        st.success("SIMULATOR RUNNING")
    else:
        st.warning("SIMULATOR PAUSED")

    st.caption("Data: synthetic / local only")
    st.caption(f"Refresh: {REFRESH_MS // 1000} seconds")

if simulation_enabled:
    for _ in range(event_rate):
        simulate_market_event(selected_symbol)

# Reload the persisted state after generating events.
orders_df = load_table("sim_orders")
trades_df = load_table("sim_trades")
state_df = load_table("sim_state")

symbol_orders = orders_df[
    orders_df["symbol"] == selected_symbol
].copy() if not orders_df.empty else pd.DataFrame()

symbol_trades = trades_df[
    trades_df["symbol"] == selected_symbol
].copy() if not trades_df.empty else pd.DataFrame()

last_price = get_last_price(selected_symbol)


# =========================================================
# TERMINAL HEADER
# =========================================================

st.markdown(
    f"""
    <div class="terminal-header">
        <div style="display:flex;justify-content:space-between;gap:20px;align-items:center;">
            <div>
                <div class="brand">CHRONOSMATCH <span>TERMINAL</span></div>
                <div class="subtitle">
                    ORDER MATCHING · MARKET DEPTH · EXECUTION ANALYTICS
                </div>
            </div>
            <div style="text-align:right;">
                <div class="engine-status">
                    ● {"ENGINE ACTIVE" if simulation_enabled else "ENGINE PAUSED"}
                </div>
                <div class="subtitle">LOCAL SIMULATION · {selected_symbol}</div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(
    "Simulation dashboard — all generated prices, orders and fills are synthetic."
)


# =========================================================
# TOP METRICS
# =========================================================

total_orders = len(symbol_orders)
total_trades = len(symbol_trades)

filled_count = 0
if not symbol_orders.empty:
    filled_count = int(
        symbol_orders["status"].isin(["FILLED", "PARTIAL"]).sum()
    )

fill_rate = (
    100 * filled_count / total_orders
    if total_orders else 0.0
)

traded_volume = (
    int(symbol_trades["quantity"].sum())
    if not symbol_trades.empty else 0
)

avg_latency = (
    float(symbol_orders["latency_us"].mean())
    if not symbol_orders.empty else 0.0
)

m1, m2, m3, m4, m5 = st.columns(5)

m1.metric("LAST SIM PRICE", f"${last_price:,.2f}")
m2.metric("ORDERS", f"{total_orders:,}")
m3.metric("TRADES", f"{total_trades:,}")
m4.metric("FILL RATE", f"{fill_rate:.1f}%")
m5.metric("AVG ORDER LATENCY", f"{avg_latency:,.1f} µs")


# =========================================================
# MAIN TERMINAL PANELS
# =========================================================

depth_tab, tape_tab, analytics_tab, history_tab = st.tabs(
    ["MARKET DEPTH", "LIVE TRADE TAPE", "ANALYTICS", "ORDER HISTORY"]
)


# ---------------------------------------------------------
# MARKET DEPTH
# ---------------------------------------------------------

with depth_tab:
    left, right = st.columns(2)

    if not symbol_orders.empty:
        open_orders = symbol_orders[
            symbol_orders["status"].isin(["OPEN", "PARTIAL"])
        ].copy()
    else:
        open_orders = pd.DataFrame()

    if not open_orders.empty:
        bids = (
            open_orders[open_orders["side"] == "BUY"]
            .groupby("price", as_index=False)["quantity"]
            .sum()
            .sort_values("price", ascending=False)
            .head(10)
        )

        asks = (
            open_orders[open_orders["side"] == "SELL"]
            .groupby("price", as_index=False)["quantity"]
            .sum()
            .sort_values("price", ascending=True)
            .head(10)
        )
    else:
        bids = pd.DataFrame(columns=["price", "quantity"])
        asks = pd.DataFrame(columns=["price", "quantity"])

    with left:
        st.markdown("### 🟢 BUY SIDE / BIDS")
        if bids.empty:
            st.info("No resting buy orders yet.")
        else:
            bids["notional"] = bids["price"] * bids["quantity"]
            bids.columns = ["Price ($)", "Quantity", "Notional ($)"]
            st.dataframe(
                bids,
                width="stretch",
                hide_index=True,
            )

    with right:
        st.markdown("### 🔴 SELL SIDE / ASKS")
        if asks.empty:
            st.info("No resting sell orders yet.")
        else:
            asks["notional"] = asks["price"] * asks["quantity"]
            asks.columns = ["Price ($)", "Quantity", "Notional ($)"]
            st.dataframe(
                asks,
                width="stretch",
                hide_index=True,
            )

    st.markdown("### OPEN ORDER BOOK")

    if open_orders.empty:
        st.info("No open orders. New orders appear as the simulator runs.")
    else:
        display_book = open_orders[
            [
                "timestamp", "order_id", "symbol", "side",
                "price", "quantity", "filled_quantity", "status",
            ]
        ].sort_values("timestamp", ascending=False).head(30)

        st.dataframe(
            display_book,
            width="stretch",
            hide_index=True,
        )


# ---------------------------------------------------------
# LIVE TRADE TAPE
# ---------------------------------------------------------

with tape_tab:
    st.markdown("### ⚡ EXECUTION TAPE")

    if symbol_trades.empty:
        st.info("Waiting for the first simulated execution.")
    else:
        tape = symbol_trades.sort_values(
            "timestamp", ascending=False
        ).head(50).copy()

        tape["notional"] = tape["price"] * tape["quantity"]

        tape = tape[
            [
                "timestamp", "trade_id", "symbol", "price",
                "quantity", "notional", "latency_us",
            ]
        ]

        tape.columns = [
            "Timestamp", "Trade ID", "Symbol", "Price ($)",
            "Quantity", "Notional ($)", "Latency (µs)",
        ]

        st.dataframe(
            tape,
            width="stretch",
            hide_index=True,
        )


# ---------------------------------------------------------
# ANALYTICS
# ---------------------------------------------------------

with analytics_tab:
    st.markdown("### EXECUTION ANALYTICS")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### Trade Price History")

        if not symbol_trades.empty:
            chart_data = symbol_trades.copy()
            chart_data["timestamp"] = pd.to_datetime(
                chart_data["timestamp"], errors="coerce"
            )
            chart_data = chart_data.dropna(subset=["timestamp"])
            chart_data = chart_data.sort_values("timestamp")

            if not chart_data.empty:
                st.line_chart(
                    chart_data.set_index("timestamp")[["price"]],
                    width="stretch",
                )
            else:
                st.info("Price history will appear after executions.")
        else:
            st.info("Price history will appear after executions.")

    with c2:
        st.markdown("#### Orders by Side")

        if not symbol_orders.empty:
            side_counts = (
                symbol_orders.groupby("side")
                .size()
                .rename("orders")
            )

            st.bar_chart(side_counts, width="stretch")
        else:
            st.info("Waiting for orders.")

    st.markdown("#### Engine Counters")

    e1, e2, e3 = st.columns(3)
    e1.metric("TRADED QUANTITY", f"{traded_volume:,}")
    e2.metric("OPEN ORDERS", f"{len(open_orders):,}")
    e3.metric("SYMBOLS CONFIGURED", len(SYMBOLS))

    st.caption(
        "Latency is the local Python time spent processing a simulated order. "
        "It is not exchange or network latency."
    )


# ---------------------------------------------------------
# ORDER HISTORY
# ---------------------------------------------------------

with history_tab:
    st.markdown("### RECENT ORDERS")

    if symbol_orders.empty:
        st.info("No orders generated for this symbol yet.")
    else:
        st.dataframe(
            symbol_orders.sort_values(
                "timestamp", ascending=False
            ).head(100),
            width="stretch",
            hide_index=True,
        )

    st.markdown("### RECENT EXECUTIONS")

    if symbol_trades.empty:
        st.info("No executions recorded yet.")
    else:
        st.dataframe(
            symbol_trades.sort_values(
                "timestamp", ascending=False
            ).head(100),
            width="stretch",
            hide_index=True,
        )


# =========================================================
# FOOTER
# =========================================================

st.markdown(
    f"""
    <div class="footer">
        CHRONOSMATCH · LOCAL MATCHING SIMULATOR · AUTO REFRESH ENABLED
        <br><br>
        Last dashboard render: {datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")}
    </div>
    """,
    unsafe_allow_html=True,
)
