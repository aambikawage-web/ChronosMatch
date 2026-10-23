from __future__ import annotations

import random
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="ChronosMatch | HFT Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "chronosmatch_simulation.db"

DEFAULT_SYMBOL = "AAPL"
DEFAULT_PRICE = 100.00
MAX_CHART_POINTS = 300


# ============================================================
# MODERN DARK UI THEME
# ============================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background:
            radial-gradient(ellipse at top left, #1c1640 0%, transparent 38%),
            linear-gradient(135deg, #070a13 0%, #0b1020 55%, #101525 100%);
        color: #edf2ff;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111426 0%, #0a0d19 100%);
        border-right: 1px solid #28233f;
    }

    [data-testid="stHeader"] {
        background: rgba(7, 10, 19, 0.9);
    }

    .block-container {
        max-width: 1600px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    h1, h2, h3 {
        color: #f5f6ff !important;
        letter-spacing: -0.5px;
    }

    p, label, [data-testid="stCaptionContainer"] {
        color: #aab5ce;
    }

    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #171a2d, #101423);
        border: 1px solid #2a2d48;
        padding: 20px 18px;
        border-radius: 16px;
        min-height: 120px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    }

    [data-testid="stMetricLabel"] {
        color: #9ca8c5 !important;
        font-size: 0.83rem;
    }

    [data-testid="stMetricValue"] {
        color: #f8f9ff !important;
        font-weight: 750;
    }

    [data-testid="stMetricDelta"] {
        font-size: 0.8rem;
    }

    div[data-testid="stForm"],
    div[data-testid="stExpander"] {
        background: rgba(18, 21, 38, 0.85);
        border: 1px solid #2a2d48;
        border-radius: 15px;
        padding: 12px;
    }

    .stButton > button,
    .stDownloadButton > button,
    [data-testid="stFormSubmitButton"] > button {
        border-radius: 10px;
        border: 1px solid #6e58c9;
        background: linear-gradient(135deg, #7557f6, #5238c9);
        color: white;
        font-weight: 650;
        transition: all 0.2s ease;
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover,
    [data-testid="stFormSubmitButton"] > button:hover {
        border-color: #b5a5ff;
        background: linear-gradient(135deg, #8a70ff, #6549e7);
        color: white;
        transform: translateY(-1px);
    }

    [data-testid="stDataFrame"] {
        border: 1px solid #292d47;
        border-radius: 12px;
        overflow: hidden;
    }

    input, textarea, [data-baseweb="select"] > div {
        border-radius: 9px !important;
    }

    .terminal-header {
        padding: 12px 0 22px 0;
        border-bottom: 1px solid #292d47;
        margin-bottom: 24px;
    }

    .terminal-eyebrow {
        color: #a494ff;
        text-transform: uppercase;
        font-size: 0.74rem;
        font-weight: 800;
        letter-spacing: 2px;
    }

    .terminal-title {
        color: #ffffff;
        font-size: clamp(1.8rem, 3vw, 2.6rem);
        font-weight: 800;
        margin: 5px 0;
    }

    .terminal-subtitle {
        color: #a8b3cc;
        font-size: 0.92rem;
    }

    .status-pill {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 30px;
        background: #12382f;
        border: 1px solid #1e725b;
        color: #6ee7b7;
        font-weight: 700;
        font-size: 0.76rem;
    }

    .status-pill.off {
        background: #38212b;
        border-color: #754052;
        color: #fda4af;
    }

    .section-note {
        color: #91a0bd;
        font-size: 0.82rem;
        margin-top: -8px;
        margin-bottom: 12px;
    }

    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid #292d47;
    }

    [data-testid="stTabs"] [data-baseweb="tab"] {
        background: #111426;
        border-radius: 9px 9px 0 0;
        padding: 12px 16px;
        color: #aab5ce;
    }

    [data-testid="stTabs"] [aria-selected="true"] {
        background: #292044 !important;
        color: #c4b5fd !important;
        border-bottom: 2px solid #8b5cf6;
    }

    hr {
        border-color: #292d47;
    }

    [data-testid="stAlert"] {
        background: #13182a;
        border: 1px solid #303652;
        border-radius: 12px;
    }

    footer {
        visibility: hidden;
    }

    #MainMenu {
        visibility: hidden;
    }

    @media (max-width: 768px) {
        .block-container {
            padding: 1rem;
        }

        [data-testid="stMetric"] {
            padding: 14px;
            min-height: 100px;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.4rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DATABASE
# ============================================================

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }


def ensure_column(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    declaration: str,
) -> None:
    if column not in table_columns(conn, table):
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {declaration}"
        )


def init_db() -> None:
    with connect_db() as conn:
        conn.execute(
            """
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
            """
        )

        conn.execute(
            """
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
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sim_price_ticks (
                tick_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price REAL NOT NULL
            )
            """
        )

        ensure_column(conn, "sim_orders", "created_at", "TEXT")
        ensure_column(conn, "sim_orders", "updated_at", "TEXT")
        ensure_column(conn, "sim_trades", "latency_ms", "REAL DEFAULT 0")

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sim_orders_symbol_status "
            "ON sim_orders(symbol, status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sim_orders_timestamp "
            "ON sim_orders(timestamp)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sim_trades_symbol_timestamp "
            "ON sim_trades(symbol, timestamp)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sim_ticks_symbol_timestamp "
            "ON sim_price_ticks(symbol, timestamp)"
        )


init_db()


# ============================================================
# DATA HELPERS
# ============================================================

def read_df(query: str, params: tuple = ()) -> pd.DataFrame:
    with connect_db() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_orders(symbol: str | None = None) -> pd.DataFrame:
    query = "SELECT * FROM sim_orders"
    params: tuple = ()

    if symbol:
        query += " WHERE symbol = ?"
        params = (symbol,)

    query += " ORDER BY timestamp DESC LIMIT 1000"
    return read_df(query, params)


def get_trades(
    symbol: str | None = None,
    limit: int = 500,
) -> pd.DataFrame:
    query = "SELECT * FROM sim_trades"
    params: tuple = ()

    if symbol:
        query += " WHERE symbol = ?"
        params = (symbol,)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params = (*params, int(limit))
    return read_df(query, params)


def get_ticks(
    symbol: str,
    limit: int = MAX_CHART_POINTS,
) -> pd.DataFrame:
    return read_df(
        """
        SELECT timestamp, symbol, price
        FROM (
            SELECT timestamp, symbol, price
            FROM sim_price_ticks
            WHERE symbol = ?
            ORDER BY tick_id DESC
            LIMIT ?
        )
        ORDER BY timestamp ASC
        """,
        (symbol, int(limit)),
    )


def current_reference_price(symbol: str) -> float:
    tick = read_df(
        """
        SELECT price
        FROM sim_price_ticks
        WHERE symbol = ?
        ORDER BY tick_id DESC
        LIMIT 1
        """,
        (symbol,),
    )

    if not tick.empty:
        return float(tick.iloc[0]["price"])

    trade = read_df(
        """
        SELECT price
        FROM sim_trades
        WHERE symbol = ?
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (symbol,),
    )

    if not trade.empty:
        return float(trade.iloc[0]["price"])

    return DEFAULT_PRICE


def save_tick(symbol: str, price: float) -> None:
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO sim_price_ticks(timestamp, symbol, price)
            VALUES (?, ?, ?)
            """,
            (now_iso(), symbol, round(float(price), 4)),
        )


# ============================================================
# ORDER MATCHING ENGINE
# ============================================================

def submit_order(
    symbol: str,
    side: str,
    price: float,
    quantity: int,
) -> dict:
    """
    Submit a simulated limit order and match against eligible
    opposite-side resting orders using price-time priority.

    Trade price is the resting order's price.
    This function does not send orders to a real exchange.
    """
    side = side.upper().strip()
    symbol = symbol.upper().strip()
    price = round(float(price), 4)
    quantity = int(quantity)

    if side not in {"BUY", "SELL"}:
        raise ValueError("Side must be BUY or SELL.")
    if not symbol:
        raise ValueError("Enter a symbol.")
    if price <= 0:
        raise ValueError("Price must be greater than zero.")
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    order_id = str(uuid.uuid4())
    created = now_iso()
    start = time.perf_counter_ns()
    remaining = quantity
    fills = 0

    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO sim_orders (
                order_id, timestamp, symbol, side, price,
                quantity, filled_quantity, status, latency_us,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 0, 'OPEN', 0, ?, ?)
            """,
            (
                order_id,
                created,
                symbol,
                side,
                price,
                quantity,
                created,
                created,
            ),
        )

        if side == "BUY":
            candidates = conn.execute(
                """
                SELECT *
                FROM sim_orders
                WHERE symbol = ?
                  AND side = 'SELL'
                  AND status IN ('OPEN', 'PARTIAL')
                  AND price <= ?
                  AND order_id != ?
                ORDER BY price ASC, timestamp ASC
                """,
                (symbol, price, order_id),
            ).fetchall()
        else:
            candidates = conn.execute(
                """
                SELECT *
                FROM sim_orders
                WHERE symbol = ?
                  AND side = 'BUY'
                  AND status IN ('OPEN', 'PARTIAL')
                  AND price >= ?
                  AND order_id != ?
                ORDER BY price DESC, timestamp ASC
                """,
                (symbol, price, order_id),
            ).fetchall()

        for resting in candidates:
            if remaining <= 0:
                break

            resting_remaining = (
                int(resting["quantity"])
                - int(resting["filled_quantity"])
            )

            if resting_remaining <= 0:
                continue

            fill_qty = min(remaining, resting_remaining)
            trade_price = float(resting["price"])
            trade_time = now_iso()

            if side == "BUY":
                buy_id = order_id
                sell_id = resting["order_id"]
            else:
                buy_id = resting["order_id"]
                sell_id = order_id

            conn.execute(
                """
                INSERT INTO sim_trades (
                    trade_id, timestamp, symbol, price, quantity,
                    buy_order_id, sell_order_id, latency_us, latency_ms
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
                """,
                (
                    str(uuid.uuid4()),
                    trade_time,
                    symbol,
                    trade_price,
                    fill_qty,
                    buy_id,
                    sell_id,
                ),
            )

            new_resting_filled = (
                int(resting["filled_quantity"]) + fill_qty
            )

            resting_status = (
                "FILLED"
                if new_resting_filled >= int(resting["quantity"])
                else "PARTIAL"
            )

            conn.execute(
                """
                UPDATE sim_orders
                SET filled_quantity = ?, status = ?, updated_at = ?
                WHERE order_id = ?
                """,
                (
                    new_resting_filled,
                    resting_status,
                    trade_time,
                    resting["order_id"],
                ),
            )

            remaining -= fill_qty
            fills += fill_qty

        elapsed_us = (time.perf_counter_ns() - start) / 1000.0

        final_status = (
            "FILLED"
            if remaining == 0
            else "PARTIAL"
            if fills > 0
            else "OPEN"
        )

        conn.execute(
            """
            UPDATE sim_orders
            SET filled_quantity = ?, status = ?,
                latency_us = ?, updated_at = ?
            WHERE order_id = ?
            """,
            (fills, final_status, elapsed_us, now_iso(), order_id),
        )

        conn.execute(
            """
            UPDATE sim_trades
            SET latency_us = ?, latency_ms = ?
            WHERE buy_order_id = ? OR sell_order_id = ?
            """,
            (
                elapsed_us,
                elapsed_us / 1000.0,
                order_id,
                order_id,
            ),
        )

    return {
        "order_id": order_id,
        "status": final_status,
        "filled_quantity": fills,
        "remaining_quantity": remaining,
        "latency_us": elapsed_us,
    }


def generate_simulated_order(symbol: str) -> dict:
    """Generate a random order for simulation and match it."""
    reference = current_reference_price(symbol)

    proposed_price = max(
        0.01,
        round(reference * (1 + random.uniform(-0.003, 0.003)), 2),
    )

    side = random.choice(["BUY", "SELL"])
    quantity = random.choice([1, 2, 5, 10, 20, 25, 50])

    result = submit_order(symbol, side, proposed_price, quantity)

    next_price = max(
        0.01,
        round(reference * (1 + random.uniform(-0.0015, 0.0015)), 4),
    )

    save_tick(symbol, next_price)
    return result


# ============================================================
# SESSION STATE AND SIDEBAR
# ============================================================

if "auto_run" not in st.session_state:
    st.session_state.auto_run = False

if "simulation_speed" not in st.session_state:
    st.session_state.simulation_speed = 2000

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = DEFAULT_SYMBOL

with st.sidebar:
    st.markdown("## 📈 ChronosMatch")
    st.caption("HIGH-FREQUENCY TRADING SIMULATOR")
    st.divider()

    symbol_input = st.text_input(
        "Trading symbol",
        value=st.session_state.selected_symbol,
        max_chars=15,
    ).strip().upper()

    symbol = symbol_input or DEFAULT_SYMBOL
    st.session_state.selected_symbol = symbol

    st.markdown("### Simulation controls")

    st.session_state.simulation_speed = st.select_slider(
        "Refresh interval",
        options=[500, 1000, 2000, 3000, 5000],
        value=st.session_state.simulation_speed,
        format_func=lambda value: f"{value / 1000:.1f} sec",
    )

    if st.session_state.auto_run:
        if st.button("⏹ Stop simulation", width="stretch"):
            st.session_state.auto_run = False
            st.rerun()
    else:
        if st.button("▶ Start simulation", width="stretch"):
            st.session_state.auto_run = True
            st.rerun()

    st.markdown(
        f"""
        <span class="status-pill{' off' if not st.session_state.auto_run else ''}">
        {'● SIMULATION RUNNING' if st.session_state.auto_run else '● SIMULATION PAUSED'}
        </span>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    st.caption("Data storage")
    st.code(DB_PATH.name, language=None)
    st.caption("Simulation only • No live exchange connection")


if st.session_state.auto_run and st_autorefresh is not None:
    st_autorefresh(
        interval=st.session_state.simulation_speed,
        limit=None,
        key="chronosmatch_auto_refresh",
    )

if st.session_state.auto_run:
    try:
        generate_simulated_order(symbol)
    except Exception as exc:
        st.error(f"Simulation error: {exc}")


# ============================================================
# HEADER
# ============================================================

st.markdown(
    f"""
    <div class="terminal-header">
        <div class="terminal-eyebrow">
            Trading infrastructure / Simulation environment
        </div>
        <div class="terminal-title">ChronosMatch Terminal</div>
        <div class="terminal-subtitle">
            Order matching • Market depth • Execution analytics
            &nbsp; | &nbsp; Symbol: <b>{symbol}</b>
        </div>
        <div style="margin-top: 12px;">
            <span class="status-pill off">
                SIMULATION ONLY — NO LIVE TRADING
            </span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# LOAD DASHBOARD DATA
# ============================================================

try:
    orders = get_orders(symbol)
    trades = get_trades(symbol, 500)
    ticks = get_ticks(symbol)
except Exception as exc:
    st.error(f"Could not read the simulation database: {exc}")
    st.stop()

all_symbol_orders = orders.copy()
all_symbol_trades = trades.copy()

if not all_symbol_orders.empty:
    all_symbol_orders["remaining_quantity"] = (
        all_symbol_orders["quantity"].astype(int)
        - all_symbol_orders["filled_quantity"].astype(int)
    )

open_orders = (
    all_symbol_orders[
        all_symbol_orders["status"].isin(["OPEN", "PARTIAL"])
    ].copy()
    if not all_symbol_orders.empty
    else pd.DataFrame()
)

total_orders = len(all_symbol_orders)
total_trades = len(all_symbol_trades)

total_volume = (
    int(all_symbol_trades["quantity"].sum())
    if not all_symbol_trades.empty
    else 0
)

avg_latency = (
    float(all_symbol_orders["latency_us"].mean())
    if not all_symbol_orders.empty
    else 0.0
)

reference_price = current_reference_price(symbol)

previous_price = (
    float(ticks.iloc[-2]["price"])
    if len(ticks) >= 2
    else reference_price
)

price_change_pct = (
    ((reference_price - previous_price) / previous_price) * 100
    if previous_price
    else 0.0
)


# ============================================================
# KPI CARDS
# ============================================================

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric(
    "Last simulated price",
    f"${reference_price:,.4f}",
    f"{price_change_pct:+.3f}%",
)

k2.metric("Orders", f"{total_orders:,}")
k3.metric("Executed trades", f"{total_trades:,}")
k4.metric("Traded volume", f"{total_volume:,}")
k5.metric("Avg. order latency", f"{avg_latency:,.2f} µs")

st.write("")


# ============================================================
# MAIN TABS
# ============================================================

tab_market, tab_orders, tab_trades, tab_analytics, tab_export = st.tabs(
    [
        "📊 Market overview",
        "📋 Orders",
        "⚡ Trade tape",
        "🧠 Analytics",
        "📥 Export data",
    ]
)


# ============================================================
# MARKET OVERVIEW
# ============================================================

with tab_market:
    left, right = st.columns([1.8, 1])

    with left:
        st.subheader("Price movement")
        st.markdown(
            '<div class="section-note">Simulated price history • Hover to inspect points</div>',
            unsafe_allow_html=True,
        )

        if not ticks.empty:
            chart = go.Figure()

            chart.add_trace(
                go.Scatter(
                    x=ticks["timestamp"],
                    y=ticks["price"],
                    mode="lines",
                    name="Simulated price",
                    line=dict(color="#9b87ff", width=2.5),
                    fill="tozeroy",
                    fillcolor="rgba(139, 92, 246, 0.12)",
                    hovertemplate=(
                        "Time: %{x}<br>"
                        "Price: $%{y:.4f}<extra></extra>"
                    ),
                )
            )

            chart.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(13,17,34,0.75)",
                margin=dict(l=10, r=10, t=20, b=10),
                height=360,
                xaxis_title=None,
                yaxis_title="Price ($)",
                hovermode="x unified",
                showlegend=False,
                xaxis=dict(
                    showgrid=False,
                    rangeslider=dict(visible=True),
                ),
                yaxis=dict(
                    gridcolor="rgba(150,160,210,0.12)",
                    fixedrange=False,
                    autorange=True,
                ),
            )

            st.plotly_chart(chart, use_container_width=True)
        else:
            st.info(
                "No chart history yet. Start the simulation or submit an "
                "order to begin generating chart points."
            )

    with right:
        st.subheader("Market depth")
        st.markdown(
            '<div class="section-note">Open simulated orders by price level</div>',
            unsafe_allow_html=True,
        )

        if not open_orders.empty:
            sells = open_orders[open_orders["side"] == "SELL"].copy()
            buys = open_orders[open_orders["side"] == "BUY"].copy()

            sells["remaining_quantity"] = (
                sells["quantity"].astype(int)
                - sells["filled_quantity"].astype(int)
            )

            buys["remaining_quantity"] = (
                buys["quantity"].astype(int)
                - buys["filled_quantity"].astype(int)
            )

            asks = (
                sells.groupby("price", as_index=False)["remaining_quantity"]
                .sum()
                .sort_values("price", ascending=True)
                .head(8)
            )

            bids = (
                buys.groupby("price", as_index=False)["remaining_quantity"]
                .sum()
                .sort_values("price", ascending=False)
                .head(8)
            )

            if not asks.empty:
                asks = asks.sort_values("price", ascending=False)

            depth_rows = []

            for _, row in asks.iterrows():
                depth_rows.append(
                    {
                        "Side": "ASK",
                        "Price": float(row["price"]),
                        "Quantity": int(row["remaining_quantity"]),
                    }
                )

            for _, row in bids.iterrows():
                depth_rows.append(
                    {
                        "Side": "BID",
                        "Price": float(row["price"]),
                        "Quantity": int(row["remaining_quantity"]),
                    }
                )

            depth_df = pd.DataFrame(
                depth_rows,
                columns=["Side", "Price", "Quantity"],
            )

            if not depth_df.empty:
                st.dataframe(
                    depth_df.style.format(
                        {
                            "Price": "${:,.4f}",
                            "Quantity": "{:,}",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=360,
                )
            else:
                st.info("No open bid or ask orders.")
        else:
            st.info("The order book is empty. Submit an order to populate it.")

    st.divider()

    spread_col, imbalance_col, buy_col, sell_col = st.columns(4)

    best_bid = (
        float(
            open_orders.loc[
                open_orders["side"] == "BUY",
                "price",
            ].max()
        )
        if not open_orders.empty
        and (open_orders["side"] == "BUY").any()
        else None
    )

    best_ask = (
        float(
            open_orders.loc[
                open_orders["side"] == "SELL",
                "price",
            ].min()
        )
        if not open_orders.empty
        and (open_orders["side"] == "SELL").any()
        else None
    )

    if best_bid is not None and best_ask is not None:
        spread = best_ask - best_bid
        spread_text = f"${spread:,.4f}"
    else:
        spread_text = "—"

    if not open_orders.empty:
        buy_depth = int(
            open_orders.loc[
                open_orders["side"] == "BUY",
                "remaining_quantity",
            ].sum()
        )

        sell_depth = int(
            open_orders.loc[
                open_orders["side"] == "SELL",
                "remaining_quantity",
            ].sum()
        )
    else:
        buy_depth = sell_depth = 0

    total_depth = buy_depth + sell_depth

    imbalance = (
        (buy_depth - sell_depth) / total_depth * 100
        if total_depth
        else 0
    )

    spread_col.metric("Bid–ask spread", spread_text)
    imbalance_col.metric("Book imbalance", f"{imbalance:+.1f}%")
    buy_col.metric("Open bid quantity", f"{buy_depth:,}")
    sell_col.metric("Open ask quantity", f"{sell_depth:,}")


# ============================================================
# ORDERS TAB AND MANUAL ORDER FORM
# ============================================================

with tab_orders:
    st.subheader("Submit a simulated limit order")

    st.caption(
        "Orders are written to SQLite and matched against eligible resting "
        "orders using price-time priority."
    )

    with st.form("manual_order_form", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns(4)

        order_symbol = c1.text_input(
            "Symbol",
            value=symbol,
            max_chars=15,
        ).strip().upper()

        order_side = c2.selectbox("Side", ["BUY", "SELL"])

        order_price = c3.number_input(
            "Limit price ($)",
            min_value=0.01,
            value=float(round(reference_price, 2)),
            step=0.01,
            format="%.4f",
        )

        order_quantity = c4.number_input(
            "Quantity",
            min_value=1,
            max_value=1_000_000,
            value=10,
            step=1,
        )

        submitted = st.form_submit_button(
            "Submit simulated order",
            use_container_width=True,
        )

        if submitted:
            try:
                result = submit_order(
                    order_symbol,
                    order_side,
                    order_price,
                    order_quantity,
                )

                save_tick(
                    order_symbol,
                    current_reference_price(order_symbol),
                )

                st.success(
                    f"Order {result['order_id'][:8]}… submitted. "
                    f"Status: {result['status']}. "
                    f"Filled: {result['filled_quantity']}/"
                    f"{order_quantity}. "
                    f"Latency: {result['latency_us']:.2f} µs."
                )

                st.rerun()

            except Exception as exc:
                st.error(f"Could not submit order: {exc}")

    st.divider()
    st.subheader("Order history")

    if not orders.empty:
        order_view = orders.copy()

        order_view = order_view.rename(
            columns={
                "order_id": "Order ID",
                "timestamp": "Timestamp",
                "symbol": "Symbol",
                "side": "Side",
                "price": "Limit Price",
                "quantity": "Quantity",
                "filled_quantity": "Filled",
                "status": "Status",
                "latency_us": "Latency (µs)",
            }
        )

        order_view["Order ID"] = order_view["Order ID"].astype(str).str[:8]

        st.dataframe(
            order_view[
                [
                    "Order ID",
                    "Timestamp",
                    "Symbol",
                    "Side",
                    "Limit Price",
                    "Quantity",
                    "Filled",
                    "Status",
                    "Latency (µs)",
                ]
            ].style.format(
                {
                    "Limit Price": "${:,.4f}",
                    "Quantity": "{:,}",
                    "Filled": "{:,}",
                    "Latency (µs)": "{:,.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No orders yet. Submit a simulated order to get started.")


# ============================================================
# TRADE TAPE TAB
# ============================================================

with tab_trades:
    st.subheader("Executed trades")
    st.caption("Trade records produced by the local matching engine.")

    if not trades.empty:
        trade_view = trades.copy()

        trade_view = trade_view.rename(
            columns={
                "trade_id": "Trade ID",
                "timestamp": "Timestamp",
                "symbol": "Symbol",
                "price": "Price",
                "quantity": "Quantity",
                "buy_order_id": "Buy Order",
                "sell_order_id": "Sell Order",
                "latency_us": "Latency (µs)",
                "latency_ms": "Latency (ms)",
            }
        )

        trade_view["Trade ID"] = (
            trade_view["Trade ID"].astype(str).str[:8]
        )
        trade_view["Buy Order"] = (
            trade_view["Buy Order"].astype(str).str[:8]
        )
        trade_view["Sell Order"] = (
            trade_view["Sell Order"].astype(str).str[:8]
        )

        st.dataframe(
            trade_view[
                [
                    "Trade ID",
                    "Timestamp",
                    "Symbol",
                    "Price",
                    "Quantity",
                    "Buy Order",
                    "Sell Order",
                    "Latency (µs)",
                ]
            ].style.format(
                {
                    "Price": "${:,.4f}",
                    "Quantity": "{:,}",
                    "Latency (µs)": "{:,.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "No trades yet. A trade occurs when a simulated buy and sell "
            "order have compatible limit prices."
        )


# ============================================================
# ANALYTICS TAB
# ============================================================

with tab_analytics:
    st.subheader("Execution analytics")
    st.caption(
        "Metrics describe this local simulation and are not exchange "
        "performance measurements."
    )

    if not all_symbol_orders.empty:
        latency_values = all_symbol_orders["latency_us"].dropna()

        if not latency_values.empty:
            p50 = float(latency_values.quantile(0.50))
            p95 = float(latency_values.quantile(0.95))
            p99 = float(latency_values.quantile(0.99))
            mean_latency = float(latency_values.mean())
        else:
            p50 = p95 = p99 = mean_latency = 0.0

        a1, a2, a3, a4 = st.columns(4)

        a1.metric("Mean latency", f"{mean_latency:,.2f} µs")
        a2.metric("P50 latency", f"{p50:,.2f} µs")
        a3.metric("P95 latency", f"{p95:,.2f} µs")
        a4.metric("P99 latency", f"{p99:,.2f} µs")

        st.divider()

        lat_left, lat_right = st.columns(2)

        with lat_left:
            st.subheader("Order latency distribution")

            if not latency_values.empty:
                latency_fig = go.Figure(
                    data=[
                        go.Histogram(
                            x=latency_values,
                            nbinsx=25,
                            marker_color="#8b5cf6",
                            name="Order latency",
                        )
                    ]
                )

                latency_fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(13,17,34,0.75)",
                    xaxis_title="Processing latency (µs)",
                    yaxis_title="Order count",
                    height=300,
                    margin=dict(l=10, r=10, t=20, b=10),
                )

                st.plotly_chart(
                    latency_fig,
                    use_container_width=True,
                )

        with lat_right:
            st.subheader("Recent order latency")

            if not all_symbol_orders.empty:
                latency_chart = all_symbol_orders.head(100).copy()
                latency_chart["Sequence"] = range(
                    len(latency_chart),
                    0,
                    -1,
                )
                latency_chart = latency_chart.sort_values("Sequence")
                latency_chart = latency_chart.set_index("Sequence")[
                    ["latency_us"]
                ]

                st.line_chart(
                    latency_chart,
                    height=300,
                    use_container_width=True,
                )

            st.caption(
                "Local application processing time only; not network or "
                "exchange latency."
            )

        if not all_symbol_trades.empty:
            st.subheader("Executed volume by price")

            volume_by_price = (
                all_symbol_trades.groupby("price", as_index=False)["quantity"]
                .sum()
                .sort_values("price")
            )

            volume_fig = go.Figure(
                go.Bar(
                    x=volume_by_price["price"],
                    y=volume_by_price["quantity"],
                    marker_color="#34d399",
                    name="Volume",
                )
            )

            volume_fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(13,17,34,0.75)",
                xaxis_title="Trade price ($)",
                yaxis_title="Executed quantity",
                height=300,
                margin=dict(l=10, r=10, t=20, b=10),
            )

            st.plotly_chart(volume_fig, use_container_width=True)

    else:
        st.info("Submit orders to begin collecting latency analytics.")


# ============================================================
# EXPORT TAB
# ============================================================

with tab_export:
    st.subheader("Export simulation data")
    st.caption(
        "Download the currently selected symbol's records as CSV files."
    )

    export_orders = get_orders(symbol)
    export_trades = get_trades(symbol, 100000)
    export_ticks = get_ticks(symbol, 100000)

    e1, e2, e3 = st.columns(3)

    with e1:
        st.markdown("#### Orders")
        st.write(f"{len(export_orders):,} rows")

        st.download_button(
            "⬇ Download orders CSV",
            data=export_orders.to_csv(index=False).encode("utf-8"),
            file_name=f"{symbol.lower()}_orders.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with e2:
        st.markdown("#### Trades")
        st.write(f"{len(export_trades):,} rows")

        st.download_button(
            "⬇ Download trades CSV",
            data=export_trades.to_csv(index=False).encode("utf-8"),
            file_name=f"{symbol.lower()}_trades.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with e3:
        st.markdown("#### Price history")
        st.write(f"{len(export_ticks):,} rows")

        st.download_button(
            "⬇ Download prices CSV",
            data=export_ticks.to_csv(index=False).encode("utf-8"),
            file_name=f"{symbol.lower()}_price_history.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.divider()

    st.warning(
        "CSV export does not delete or modify database records. "
        "Keep a backup of your SQLite database before making schema changes."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "ChronosMatch • Educational HFT simulation • "
    "SQLite persistence • No live broker or exchange connectivity"
)