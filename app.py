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
# PROFESSIONAL TRADING TERMINAL THEME
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
            radial-gradient(ellipse at top left, #10263f 0%, transparent 38%),
            linear-gradient(135deg, #070d16 0%, #0b1422 55%, #0d1b2a 100%);
        color: #edf2ff;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #101d2b 0%, #09131f 100%);
        border-right: 1px solid #24374b;
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
        background: linear-gradient(145deg, #152538, #0f1c2b);
        border: 1px solid #26394d;
        padding: 20px 18px;
        border-radius: 16px;
        min-height: 120px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    }

    [data-testid="stMetricLabel"] {
        color: #9eb2c8 !important;
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
        border: 1px solid #26394d;
        border-radius: 15px;
        padding: 12px;
    }

    .stButton > button,
    .stDownloadButton > button,
    [data-testid="stFormSubmitButton"] > button {
        border-radius: 10px;
        border: 1px solid #167d9a;
        background: linear-gradient(135deg, #087e8b, #155e75);
        color: white;
        font-weight: 650;
        transition: all 0.2s ease;
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover,
    [data-testid="stFormSubmitButton"] > button:hover {
        border-color: #67e8f9;
        background: linear-gradient(135deg, #0891b2, #0e7490);
        color: white;
        transform: translateY(-1px);
    }

    [data-testid="stDataFrame"] {
        border: 1px solid #26394d;
        border-radius: 12px;
        overflow: hidden;
    }

    input, textarea, [data-baseweb="select"] > div {
        border-radius: 9px !important;
    }

    .terminal-header {
        padding: 12px 0 22px 0;
        border-bottom: 1px solid #26394d;
        margin-bottom: 24px;
    }

    .terminal-eyebrow {
        color: #67e8f9;
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
        border-bottom: 1px solid #26394d;
    }

    [data-testid="stTabs"] [data-baseweb="tab"] {
        background: #101d2b;
        border-radius: 9px 9px 0 0;
        padding: 12px 16px;
        color: #aab5ce;
    }

    [data-testid="stTabs"] [aria-selected="true"] {
        background: #163247 !important;
        color: #a5f3fc !important;
        border-bottom: 2px solid #22d3ee;
    }

    hr {
        border-color: #26394d;
    }

    [data-testid="stAlert"] {
        background: #13182a;
        border: 1px solid #2c4358;
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
            font-size: 1.2rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DATABASE UTILITIES
# ============================================================

def get_connection():
    return sqlite3.connect(DB_PATH, timeout=10)


def get_tables():
    if not DB_PATH.exists():
        return []

    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        return [row[0] for row in rows]
    except sqlite3.Error:
        return []


def quote_identifier(identifier):
    return '"' + str(identifier).replace('"', '""') + '"'


def read_table(table_name):
    if table_name not in get_tables():
        return pd.DataFrame()

    try:
        with get_connection() as conn:
            return pd.read_sql_query(
                f"SELECT * FROM {quote_identifier(table_name)}",
                conn,
            )
    except (sqlite3.Error, pd.errors.DatabaseError):
        return pd.DataFrame()


def find_table(possible_names):
    existing = get_tables()
    lower_names = {name.lower(): name for name in existing}

    for possible in possible_names:
        if possible.lower() in lower_names:
            return lower_names[possible.lower()]

    for name in existing:
        if any(term in name.lower() for term in possible_names):
            return name

    return None


def find_column(df, possible_names):
    if df.empty:
        return None

    lower_columns = {str(col).lower(): col for col in df.columns}

    for possible in possible_names:
        if possible.lower() in lower_columns:
            return lower_columns[possible.lower()]

    for col in df.columns:
        if any(term in str(col).lower() for term in possible_names):
            return col

    return None


def load_trade_data():
    table_name = find_table(["trades", "trade_history", "executions", "fills"])

    if not table_name:
        return pd.DataFrame()

    df = read_table(table_name)
    if df.empty:
        return df

    df = df.copy()

    price_col = find_column(df, ["price", "execution_price", "trade_price"])
    qty_col = find_column(df, ["quantity", "qty", "volume", "size"])
    time_col = find_column(
        df, ["timestamp", "created_at", "datetime", "trade_time", "time"]
    )
    symbol_col = find_column(df, ["symbol", "ticker", "instrument"])

    if price_col:
        df["_price"] = pd.to_numeric(df[price_col], errors="coerce")

    if qty_col:
        df["_quantity"] = pd.to_numeric(df[qty_col], errors="coerce")

    if time_col:
        df["_time"] = pd.to_datetime(df[time_col], errors="coerce")

    if symbol_col:
        df["_symbol"] = df[symbol_col].astype(str)

    return df


def load_order_data():
    table_name = find_table(["orders", "order_book", "order_history"])

    if not table_name:
        return pd.DataFrame()

    df = read_table(table_name)
    if df.empty:
        return df

    df = df.copy()

    price_col = find_column(df, ["price", "limit_price", "order_price"])
    qty_col = find_column(df, ["quantity", "qty", "volume", "size"])
    side_col = find_column(df, ["side", "direction", "order_type"])
    status_col = find_column(df, ["status", "state"])
    time_col = find_column(
        df, ["timestamp", "created_at", "datetime", "order_time", "time"]
    )
    symbol_col = find_column(df, ["symbol", "ticker", "instrument"])

    if price_col:
        df["_price"] = pd.to_numeric(df[price_col], errors="coerce")

    if qty_col:
        df["_quantity"] = pd.to_numeric(df[qty_col], errors="coerce")

    if side_col:
        df["_side"] = df[side_col].astype(str).str.upper()

    if status_col:
        df["_status"] = df[status_col].astype(str).str.upper()

    if time_col:
        df["_time"] = pd.to_datetime(df[time_col], errors="coerce")

    if symbol_col:
        df["_symbol"] = df[symbol_col].astype(str)

    return df


# ============================================================
# SESSION STATE
# ============================================================

def initialize_state():
    defaults = {
        "selected_symbol": DEFAULT_SYMBOL,
        "refresh_enabled": False,
        "refresh_seconds": 5,
        "last_order_message": "",
        "simulated_orders": [],
        "simulated_trades": [],
        "latency_samples": [],
        "throughput_samples": [],
        "price_history": [],
        "backtest_results": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_state()

trades = load_trade_data()
orders = load_order_data()


# ============================================================
# GENERIC CHART HELPERS
# ============================================================

def style_chart(fig, height=340):
    fig.update_layout(
        template="plotly_dark",
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(9,18,30,0.8)",
        font=dict(
            family="Inter, sans-serif",
            color="#dce7f7",
            size=11,
        ),
        margin=dict(l=18, r=18, t=48, b=18),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
        xaxis=dict(
            gridcolor="rgba(114,140,170,0.13)",
            zerolinecolor="rgba(114,140,170,0.15)",
        ),
        yaxis=dict(
            gridcolor="rgba(114,140,170,0.13)",
            zerolinecolor="rgba(114,140,170,0.15)",
        ),
    )
    return fig


def empty_chart(message):
    st.info(message)


def money(value):
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def number(value):
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def get_total_quantity(df):
    if "_quantity" not in df.columns:
        return 0.0
    return float(df["_quantity"].fillna(0).sum())


def get_total_notional(df):
    if not {"_price", "_quantity"}.issubset(df.columns):
        return 0.0
    return float(
        (df["_price"].fillna(0) * df["_quantity"].fillna(0)).sum()
    )


def get_vwap(df):
    if not {"_price", "_quantity"}.issubset(df.columns):
        return 0.0

    valid = df.dropna(subset=["_price", "_quantity"])
    valid = valid[valid["_quantity"] > 0]

    total_qty = valid["_quantity"].sum()
    if total_qty <= 0:
        return 0.0

    return float((valid["_price"] * valid["_quantity"]).sum() / total_qty)


def show_header():
    left, right = st.columns([4, 1])

    with left:
        st.markdown(
            """
            <div class="terminal-header">
                <div class="terminal-eyebrow">Execution Intelligence Platform</div>
                <div class="terminal-title">CHRONOSMATCH</div>
                <div class="terminal-subtitle">
                    Professional order matching • Market microstructure • Analytics
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            '<div style="text-align:right;padding-top:18px">'
            '<span class="status-pill">● SIMULATION MODE</span></div>',
            unsafe_allow_html=True,
        )
        st.caption(datetime.now().strftime("%d %b %Y • %H:%M:%S"))


# ============================================================
# ORDER SUBMISSION
# ============================================================

def validate_order(side, quantity, price):
    if side not in {"BUY", "SELL"}:
        return False, "Side must be BUY or SELL."

    if quantity <= 0:
        return False, "Quantity must be greater than zero."

    if price <= 0:
        return False, "Price must be greater than zero."

    if quantity > 1_000_000:
        return False, "Quantity exceeds the simulation safety limit."

    if price > 1_000_000_000:
        return False, "Price exceeds the simulation safety limit."

    return True, ""


def insert_order_if_compatible(side, quantity, price, symbol):
    """
    Insert into the existing orders table only when its required columns
    can be identified. This does not replace or modify the matching engine.
    """
    table_name = find_table(["orders", "order_book", "order_history"])
    if not table_name:
        return False, "No compatible orders table was found."

    df = read_table(table_name)
    columns = list(df.columns)

    side_col = find_column(df, ["side", "direction", "order_type"])
    qty_col = find_column(df, ["quantity", "qty", "volume", "size"])
    price_col = find_column(df, ["price", "limit_price", "order_price"])

    if not all([side_col, qty_col, price_col]):
        return False, (
            "The existing order table does not expose recognizable side, "
            "quantity, and price columns. No database changes were made."
        )

    values = {
        side_col: side,
        qty_col: quantity,
        price_col: price,
    }

    symbol_col = find_column(df, ["symbol", "ticker", "instrument"])
    status_col = find_column(df, ["status", "state"])
    id_col = find_column(df, ["id", "order_id"])
    time_col = find_column(
        df, ["timestamp", "created_at", "datetime", "order_time", "time"]
    )

    if symbol_col:
        values[symbol_col] = symbol

    if status_col:
        values[status_col] = "PENDING"

    if time_col:
        values[time_col] = datetime.now().isoformat(timespec="seconds")

    if id_col and id_col.lower() not in {"id", "order_id"}:
        values[id_col] = str(uuid.uuid4())

    insert_columns = [col for col in columns if col in values]
    insert_values = [values[col] for col in insert_columns]

    if not insert_columns:
        return False, "No compatible columns found. No order was inserted."

    sql = (
        f"INSERT INTO {quote_identifier(table_name)} "
        f"({', '.join(quote_identifier(col) for col in insert_columns)}) "
        f"VALUES ({', '.join('?' for _ in insert_columns)})"
    )

    try:
        with get_connection() as conn:
            conn.execute(sql, insert_values)
        return True, "Order recorded in the existing database table."
    except sqlite3.Error as exc:
        return False, f"Database rejected the order: {exc}"


def submit_simulation_order(side, quantity, price, symbol):
    valid, reason = validate_order(side, quantity, price)

    if not valid:
        st.session_state.last_order_message = reason
        return

    start = time.perf_counter_ns()

    order = {
        "order_id": str(uuid.uuid4())[:8].upper(),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "symbol": symbol,
        "side": side,
        "quantity": int(quantity),
        "price": float(price),
        "status": "SIMULATED",
    }

    st.session_state.simulated_orders.append(order)

    elapsed_us = (time.perf_counter_ns() - start) / 1000.0
    st.session_state.latency_samples.append(
        {
            "timestamp": datetime.now(),
            "latency_us": elapsed_us,
        }
    )

    st.session_state.throughput_samples.append(
        {
            "timestamp": datetime.now(),
            "orders": 1,
        }
    )

    st.session_state.last_order_message = (
        f"Simulated {side} order for {quantity} {symbol} at {money(price)}. "
        "This action does not invoke your matching engine."
    )


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

with st.sidebar:
    st.markdown("## ⚡ CHRONOSMATCH")
    st.caption("HFT TERMINAL v2.0")
    st.divider()

    page = st.radio(
        "WORKSPACE",
        [
            "Terminal Overview",
            "Order Entry",
            "Market Depth",
            "Trade History",
            "Performance Lab",
            "Risk Monitor",
            "Backtesting",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    symbol_options = [DEFAULT_SYMBOL, "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL"]
    selected_symbol = st.selectbox(
        "Instrument",
        symbol_options,
        index=symbol_options.index(st.session_state.selected_symbol)
        if st.session_state.selected_symbol in symbol_options
        else 0,
    )
    st.session_state.selected_symbol = selected_symbol

    st.session_state.refresh_enabled = st.toggle(
        "Auto refresh",
        value=st.session_state.refresh_enabled,
    )

    if st.session_state.refresh_enabled:
        st.session_state.refresh_seconds = st.select_slider(
            "Refresh interval",
            options=[2, 5, 10, 15, 30],
            value=st.session_state.refresh_seconds,
        )

    st.divider()
    st.caption("Local simulation database")
    st.code(DB_PATH.name, language=None)

    if not DB_PATH.exists():
        st.warning("Database file not found.")


if st.session_state.refresh_enabled and st_autorefresh is not None:
    st_autorefresh(
        interval=st.session_state.refresh_seconds * 1000,
        key="chronosmatch_autorefresh",
    )


# ============================================================
# PAGE HEADER
# ============================================================

show_header()


# ============================================================
# TERMINAL OVERVIEW
# ============================================================

if page == "Terminal Overview":
    st.subheader("Market & Execution Overview")
    st.caption(
        "This screen visualizes records found in the local database and "
        "orders submitted through the simulation panel."
    )

    simulated_orders = pd.DataFrame(st.session_state.simulated_orders)
    simulated_trades = pd.DataFrame(st.session_state.simulated_trades)

    total_trades = len(trades) if not trades.empty else len(simulated_trades)
    total_qty = get_total_quantity(trades)
    total_notional = get_total_notional(trades)
    vwap = get_vwap(trades)

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Recorded Trades", f"{total_trades:,}")
    c2.metric("Executed Quantity", number(total_qty))
    c3.metric("Traded Notional", money(total_notional))
    c4.metric("VWAP", money(vwap))

    st.divider()

    left, right = st.columns([1.6, 1])

    with left:
        st.markdown("### Execution Activity")

        if (
            not trades.empty
            and "_time" in trades.columns
            and "_quantity" in trades.columns
        ):
            chart_df = trades.dropna(subset=["_time", "_quantity"]).copy()
            chart_df = chart_df.sort_values("_time")

            if not chart_df.empty:
                chart_df["_cumulative_qty"] = chart_df["_quantity"].cumsum()

                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=chart_df["_time"],
                        y=chart_df["_cumulative_qty"],
                        mode="lines",
                        name="Cumulative volume",
                        line=dict(color="#22d3ee", width=2.5),
                        fill="tozeroy",
                        fillcolor="rgba(34,211,238,0.08)",
                    )
                )
                fig.update_layout(
                    title="Cumulative Executed Quantity",
                    xaxis_title="Time",
                    yaxis_title="Quantity",
                )
                st.plotly_chart(style_chart(fig), width="stretch")
            else:
                empty_chart("No timestamped trade data available.")
        else:
            empty_chart("Trade timestamps and quantities are needed here.")

    with right:
        st.markdown("### Order Status")

        if not orders.empty and "_status" in orders.columns:
            status_counts = (
                orders["_status"]
                .value_counts()
                .rename_axis("Status")
                .reset_index(name="Orders")
            )

            fig = go.Figure(
                data=[
                    go.Pie(
                        labels=status_counts["Status"],
                        values=status_counts["Orders"],
                        hole=0.65,
                        textinfo="label+percent",
                    )
                ]
            )
            st.plotly_chart(
                style_chart(fig, height=320),
                width="stretch",
            )
        else:
            empty_chart("No compatible order status data found.")

    st.markdown("### Recent Recorded Trades")

    if not trades.empty:
        st.dataframe(
            trades.tail(15),
            width="stretch",
            hide_index=True,
        )
    else:
        empty_chart("No trades are currently recorded in the database.")

    if st.session_state.last_order_message:
        st.info(st.session_state.last_order_message)


# ============================================================
# ORDER ENTRY
# ============================================================

elif page == "Order Entry":
    st.subheader("Order Entry")
    st.caption(
        "Simulation-only order entry. This panel does not connect to a broker "
        "and does not automatically invoke the matching engine."
    )

    buy_col, sell_col = st.columns(2)

    with buy_col:
        st.markdown("### 🟢 BUY ORDER")

        with st.form("buy_order_form"):
            buy_symbol = st.selectbox(
                "Symbol",
                symbol_options,
                key="buy_symbol",
            )
            buy_qty = st.number_input(
                "Quantity",
                min_value=1,
                max_value=1_000_000,
                value=10,
                step=1,
                key="buy_qty",
            )
            buy_price = st.number_input(
                "Limit Price",
                min_value=0.01,
                max_value=1_000_000_000.0,
                value=DEFAULT_PRICE,
                step=0.01,
                format="%.2f",
                key="buy_price",
            )
            st.metric("Estimated Order Value", money(buy_qty * buy_price))
            buy_submit = st.form_submit_button(
                "Submit Simulated Buy",
                use_container_width=True,
            )

            if buy_submit:
                submit_simulation_order(
                    "BUY", buy_qty, buy_price, buy_symbol
                )

    with sell_col:
        st.markdown("### 🔴 SELL ORDER")

        with st.form("sell_order_form"):
            sell_symbol = st.selectbox(
                "Symbol",
                symbol_options,
                key="sell_symbol",
            )
            sell_qty = st.number_input(
                "Quantity",
                min_value=1,
                max_value=1_000_000,
                value=10,
                step=1,
                key="sell_qty",
            )
            sell_price = st.number_input(
                "Limit Price",
                min_value=0.01,
                max_value=1_000_000_000.0,
                value=DEFAULT_PRICE,
                step=0.01,
                format="%.2f",
                key="sell_price",
            )
            st.metric("Estimated Order Value", money(sell_qty * sell_price))
            sell_submit = st.form_submit_button(
                "Submit Simulated Sell",
                use_container_width=True,
            )

            if sell_submit:
                submit_simulation_order(
                    "SELL", sell_qty, sell_price, sell_symbol
                )

    if st.session_state.last_order_message:
        st.info(st.session_state.last_order_message)

    st.divider()
    st.markdown("### Session Orders")

    session_orders = pd.DataFrame(st.session_state.simulated_orders)

    if not session_orders.empty:
        st.dataframe(
            session_orders.iloc[::-1],
            width="stretch",
            hide_index=True,
        )

        st.download_button(
            "Export Session Orders",
            data=session_orders.to_csv(index=False).encode("utf-8"),
            file_name="chronosmatch_session_orders.csv",
            mime="text/csv",
        )
    else:
        empty_chart("No session orders have been submitted.")


# ============================================================
# MARKET DEPTH
# ============================================================

elif page == "Market Depth":
    st.subheader("Market Depth")
    st.caption(
        "Depth is aggregated from recognized order records in the local "
        "database. It is not a live market feed."
    )

    if orders.empty or not {
        "_side", "_price", "_quantity"
    }.issubset(orders.columns):
        empty_chart(
            "A compatible orders table with side, price, and quantity "
            "columns is required to display market depth."
        )
    else:
        depth = orders.dropna(subset=["_side", "_price", "_quantity"]).copy()

        if "_symbol" in depth.columns:
            depth = depth[depth["_symbol"] == selected_symbol]

        active_statuses = {
            "OPEN", "PENDING", "NEW", "PARTIALLY_FILLED", "PARTIAL",
            "ACTIVE", "ACCEPTED",
        }

        if "_status" in depth.columns:
            depth = depth[
                depth["_status"].str.upper().isin(active_statuses)
            ]

        bids = depth[
            depth["_side"].str.contains("BUY|BID", regex=True)
        ].groupby("_price", as_index=False)["_quantity"].sum()

        asks = depth[
            depth["_side"].str.contains("SELL|ASK", regex=True)
        ].groupby("_price", as_index=False)["_quantity"].sum()

        bids = bids.sort_values("_price", ascending=False).head(20)
        asks = asks.sort_values("_price", ascending=True).head(20)

        bid_qty = float(bids["_quantity"].sum()) if not bids.empty else 0
        ask_qty = float(asks["_quantity"].sum()) if not asks.empty else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Bid Quantity", number(bid_qty))
        c2.metric("Ask Quantity", number(ask_qty))
        c3.metric(
            "Bid / Ask Imbalance",
            number(
                (bid_qty - ask_qty) / (bid_qty + ask_qty)
                if bid_qty + ask_qty > 0 else 0
            ),
        )

        left, right = st.columns(2)

        with left:
            st.markdown("### Bid Book")
            if not bids.empty:
                fig = go.Figure()
                fig.add_trace(
                    go.Bar(
                        x=bids["_quantity"],
                        y=bids["_price"],
                        orientation="h",
                        marker_color="#22c55e",
                        name="Bids",
                    )
                )
                fig.update_layout(
                    title="Buy-Side Depth",
                    xaxis_title="Quantity",
                    yaxis_title="Price",
                )
                st.plotly_chart(style_chart(fig), width="stretch")
                st.dataframe(
                    bids.sort_values("_price", ascending=False),
                    width="stretch",
                    hide_index=True,
                )
            else:
                empty_chart("No active bid orders found.")

        with right:
            st.markdown("### Ask Book")
            if not asks.empty:
                fig = go.Figure()
                fig.add_trace(
                    go.Bar(
                        x=asks["_quantity"],
                        y=asks["_price"],
                        orientation="h",
                        marker_color="#f87171",
                        name="Asks",
                    )
                )
                fig.update_layout(
                    title="Sell-Side Depth",
                    xaxis_title="Quantity",
                    yaxis_title="Price",
                )
                st.plotly_chart(style_chart(fig), width="stretch")
                st.dataframe(
                    asks.sort_values("_price"),
                    width="stretch",
                    hide_index=True,
                )
            else:
                empty_chart("No active ask orders found.")

        if not bids.empty or not asks.empty:
            st.markdown("### Combined Market Depth")

            fig = go.Figure()

            if not bids.empty:
                bids_plot = bids.sort_values("_price")
                bids_plot = bids_plot.copy()
                bids_plot["cumulative"] = bids_plot["_quantity"].cumsum()

                fig.add_trace(
                    go.Scatter(
                        x=bids_plot["_price"],
                        y=bids_plot["cumulative"],
                        mode="lines",
                        fill="tozeroy",
                        name="Bid depth",
                        line=dict(color="#22c55e", width=2),
                    )
                )

            if not asks.empty:
                asks_plot = asks.sort_values("_price")
                asks_plot = asks_plot.copy()
                asks_plot["cumulative"] = asks_plot["_quantity"].cumsum()

                fig.add_trace(
                    go.Scatter(
                        x=asks_plot["_price"],
                        y=asks_plot["cumulative"],
                        mode="lines",
                        fill="tozeroy",
                        name="Ask depth",
                        line=dict(color="#f87171", width=2),
                    )
                )

            fig.update_layout(
                title=f"{selected_symbol} Cumulative Market Depth",
                xaxis_title="Price",
                yaxis_title="Cumulative Quantity",
            )
            st.plotly_chart(style_chart(fig, height=420), width="stretch")


# ============================================================
# TRADE HISTORY
# ============================================================

elif page == "Trade History":
    st.subheader("Trade History")

    if trades.empty:
        empty_chart("No recorded trade history was found.")
    else:
        filtered = trades.copy()

        if "_symbol" in filtered.columns:
            filtered = filtered[filtered["_symbol"] == selected_symbol]

        c1, c2, c3 = st.columns(3)
        c1.metric("Trades", f"{len(filtered):,}")
        c2.metric("Quantity", number(get_total_quantity(filtered)))
        c3.metric("VWAP", money(get_vwap(filtered)))

        st.dataframe(
            filtered.iloc[::-1],
            width="stretch",
            hide_index=True,
        )

        st.download_button(
            "Export Trade History CSV",
            data=filtered.to_csv(index=False).encode("utf-8"),
            file_name=f"{selected_symbol.lower()}_trade_history.csv",
            mime="text/csv",
        )

        if {"_price", "_quantity"}.issubset(filtered.columns):
            valid = filtered.dropna(subset=["_price", "_quantity"]).copy()

            if not valid.empty:
                valid["_notional"] = valid["_price"] * valid["_quantity"]

                left, right = st.columns(2)

                with left:
                    fig = go.Figure()
                    fig.add_trace(
                        go.Histogram(
                            x=valid["_price"],
                            nbinsx=30,
                            marker_color="#38bdf8",
                            name="Execution prices",
                        )
                    )
                    fig.update_layout(
                        title="Execution Price Distribution",
                        xaxis_title="Price",
                        yaxis_title="Number of trades",
                    )
                    st.plotly_chart(style_chart(fig), width="stretch")

                with right:
                    fig = go.Figure()
                    fig.add_trace(
                        go.Scatter(
                            x=valid["_quantity"],
                            y=valid["_price"],
                            mode="markers",
                            marker=dict(
                                color=valid["_notional"],
                                colorscale="Viridis",
                                size=8,
                                showscale=True,
                                colorbar=dict(title="Notional"),
                            ),
                            name="Trade",
                        )
                    )
                    fig.update_layout(
                        title="Execution Price vs Quantity",
                        xaxis_title="Quantity",
                        yaxis_title="Price",
                    )
                    st.plotly_chart(style_chart(fig), width="stretch")


# ============================================================
# PERFORMANCE LAB
# ============================================================

elif page == "Performance Lab":
    st.subheader("Performance Lab")
    st.caption(
        "Latency figures below are measurements of this dashboard's local "
        "simulation submission code, not exchange or matching-engine latency."
    )

    latency_df = pd.DataFrame(st.session_state.latency_samples)
    throughput_df = pd.DataFrame(st.session_state.throughput_samples)

    if not latency_df.empty:
        latency_values = latency_df["latency_us"].dropna()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Samples", f"{len(latency_values):,}")
        c2.metric("Mean Latency", f"{latency_values.mean():,.2f} µs")
        c3.metric("P95 Latency", f"{latency_values.quantile(0.95):,.2f} µs")
        c4.metric("P99 Latency", f"{latency_values.quantile(0.99):,.2f} µs")

        left, right = st.columns(2)

        with left:
            fig = go.Figure()
            fig.add_trace(
                go.Histogram(
                    x=latency_values,
                    nbinsx=30,
                    marker_color="#38bdf8",
                    name="Latency",
                )
            )
            fig.update_layout(
                title="Local Submission Latency Distribution",
                xaxis_title="Microseconds",
                yaxis_title="Count",
            )
            st.plotly_chart(style_chart(fig), width="stretch")

        with right:
            latency_df = latency_df.copy()
            latency_df["sample"] = range(1, len(latency_df) + 1)

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=latency_df["sample"],
                    y=latency_df["latency_us"],
                    mode="lines+markers",
                    line=dict(color="#a78bfa", width=2),
                    name="Latency",
                )
            )
            fig.update_layout(
                title="Latency per Local Submission",
                xaxis_title="Sample",
                yaxis_title="Microseconds",
            )
            st.plotly_chart(style_chart(fig), width="stretch")
    else:
        empty_chart(
            "No latency samples yet. Submit simulated orders in Order Entry "
            "to collect local timing samples."
        )

    st.divider()
    st.markdown("### Throughput Samples")

    if not throughput_df.empty:
        throughput_df = throughput_df.copy()
        throughput_df["timestamp"] = pd.to_datetime(
            throughput_df["timestamp"], errors="coerce"
        )

        grouped = (
            throughput_df.dropna(subset=["timestamp"])
            .set_index("timestamp")
            .resample("1min")["orders"]
            .sum()
            .reset_index()
        )

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=grouped["timestamp"],
                y=grouped["orders"],
                marker_color="#2dd4bf",
                name="Submitted orders",
            )
        )
        fig.update_layout(
            title="Local Order Submissions per Minute",
            xaxis_title="Time",
            yaxis_title="Orders",
        )
        st.plotly_chart(style_chart(fig), width="stretch")
    else:
        empty_chart("No throughput samples have been collected in this session.")

    benchmark_table = find_table(["benchmark", "performance", "latency"])
    if benchmark_table:
        st.divider()
        st.markdown("### Recorded Benchmark Data")
        st.dataframe(
            read_table(benchmark_table),
            width="stretch",
            hide_index=True,
        )


# ============================================================
# RISK MONITOR
# ============================================================

elif page == "Risk Monitor":
    st.subheader("Risk Monitor")
    st.caption(
        "Descriptive simulation risk indicators. This is not a complete "
        "portfolio, margin, or regulatory risk system."
    )

    if trades.empty or not {
        "_price", "_quantity"
    }.issubset(trades.columns):
        empty_chart("Trade price and quantity data is required for risk metrics.")
    else:
        valid = trades.dropna(subset=["_price", "_quantity"]).copy()
        valid = valid[valid["_quantity"] > 0]

        if valid.empty:
            empty_chart("No valid trades are available.")
        else:
            valid["_notional"] = valid["_price"] * valid["_quantity"]

            max_trade = float(valid["_notional"].max())
            total_notional = float(valid["_notional"].sum())
            average_trade = float(valid["_notional"].mean())
            total_qty = float(valid["_quantity"].sum())

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Traded Notional", money(total_notional))
            c2.metric("Largest Trade", money(max_trade))
            c3.metric("Average Trade", money(average_trade))
            c4.metric("Total Quantity", number(total_qty))

            left, right = st.columns(2)

            with left:
                fig = go.Figure()
                fig.add_trace(
                    go.Box(
                        y=valid["_notional"],
                        boxpoints="outliers",
                        marker_color="#f59e0b",
                        name="Trade notional",
                    )
                )
                fig.update_layout(
                    title="Trade Notional Outlier Analysis",
                    yaxis_title="Notional",
                )
                st.plotly_chart(style_chart(fig), width="stretch")

            with right:
                fig = go.Figure()
                fig.add_trace(
                    go.Histogram(
                        x=valid["_quantity"],
                        nbinsx=25,
                        marker_color="#a78bfa",
                        name="Quantity",
                    )
                )
                fig.update_layout(
                    title="Trade Quantity Distribution",
                    xaxis_title="Quantity",
                    yaxis_title="Frequency",
                )
                st.plotly_chart(style_chart(fig), width="stretch")

            st.markdown("### Largest Trades")

            st.dataframe(
                valid.sort_values("_notional", ascending=False).head(20),
                width="stretch",
                hide_index=True,
            )

            st.warning(
                "Risk figures only describe the available trade records. "
                "They do not calculate live exposure, margin requirements, "
                "or guaranteed loss limits."
            )

    st.divider()
    st.markdown("### Session Order Limits")

    with st.form("risk_limits_form"):
        max_order_qty = st.number_input(
            "Maximum simulated order quantity",
            min_value=1,
            max_value=1_000_000,
            value=1000,
            step=100,
        )
        max_order_value = st.number_input(
            "Maximum simulated order value ($)",
            min_value=1.0,
            max_value=1_000_000_000.0,
            value=100_000.0,
            step=1000.0,
        )
        save_limits = st.form_submit_button("Apply Session Limits")

        if save_limits:
            st.session_state["max_order_qty"] = int(max_order_qty)
            st.session_state["max_order_value"] = float(max_order_value)
            st.success("Session limits saved for display and future validation.")


# ============================================================
# BACKTESTING
# ============================================================

elif page == "Backtesting":
    st.subheader("Backtesting Lab")
    st.caption(
        "This is a simple historical-price strategy illustration. "
        "It does not model transaction costs, slippage, queue priority, "
        "or guaranteed executable fills."
    )

    if trades.empty or "_price" not in trades.columns:
        empty_chart(
            "Historical trade prices are required to run this illustrative "
            "backtest. Record trades in the database first."
        )
    else:
        backtest_data = trades.dropna(subset=["_price"]).copy()

        if "_time" in backtest_data.columns:
            backtest_data = backtest_data.dropna(subset=["_time"])
            backtest_data = backtest_data.sort_values("_time")

        if "_symbol" in backtest_data.columns:
            backtest_data = backtest_data[
                backtest_data["_symbol"] == selected_symbol
            ]

        backtest_data = backtest_data.tail(MAX_CHART_POINTS).reset_index(
            drop=True
        )

        if len(backtest_data) < 3:
            empty_chart(
                "At least three historical price observations are needed "
                "for the illustrative moving-average strategy."
            )
        else:
            with st.form("backtest_form"):
                fast_window = st.slider(
                    "Fast moving-average window",
                    min_value=2,
                    max_value=min(20, len(backtest_data) - 1),
                    value=3,
                )
                slow_window = st.slider(
                    "Slow moving-average window",
                    min_value=3,
                    max_value=min(50, len(backtest_data)),
                    value=min(8, len(backtest_data)),
                )
                starting_capital = st.number_input(
                    "Starting capital ($)",
                    min_value=100.0,
                    max_value=10_000_000.0,
                    value=10_000.0,
                    step=100.0,
                )
                run_backtest = st.form_submit_button("Run Illustrative Backtest")

            if run_backtest:
                if fast_window >= slow_window:
                    st.error(
                        "The fast moving-average window must be smaller "
                        "than the slow moving-average window."
                    )
                else:
                    result = backtest_data.copy()
                    result["fast_ma"] = result["_price"].rolling(
                        fast_window
                    ).mean()
                    result["slow_ma"] = result["_price"].rolling(
                        slow_window
                    ).mean()

                    result["signal"] = (
                        result["fast_ma"] > result["slow_ma"]
                    ).astype(int)

                    result["market_return"] = result["_price"].pct_change().fillna(0)
                    result["strategy_return"] = (
                        result["signal"].shift(1).fillna(0)
                        * result["market_return"]
                    )

                    result["equity"] = (
                        starting_capital
                        * (1 + result["strategy_return"]).cumprod()
                    )

                    total_return = (
                        result["equity"].iloc[-1] / starting_capital - 1
                    ) * 100

                    result["running_peak"] = result["equity"].cummax()
                    result["drawdown"] = (
                        result["equity"] / result["running_peak"] - 1
                    ) * 100

                    max_drawdown = float(result["drawdown"].min())

                    st.session_state.backtest_results = {
                        "data": result,
                        "total_return": total_return,
                        "max_drawdown": max_drawdown,
                        "starting_capital": starting_capital,
                    }

            result_bundle = st.session_state.backtest_results

            if result_bundle:
                result = result_bundle["data"]

                c1, c2, c3 = st.columns(3)
                c1.metric(
                    "Illustrative Return",
                    f"{result_bundle['total_return']:.2f}%",
                )
                c2.metric(
                    "Ending Equity",
                    money(result["equity"].iloc[-1]),
                )
                c3.metric(
                    "Maximum Drawdown",
                    f"{result_bundle['max_drawdown']:.2f}%",
                )

                fig = go.Figure()

                x_values = (
                    result["_time"]
                    if "_time" in result.columns
                    else list(range(len(result)))
                )

                fig.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=result["_price"],
                        mode="lines",
                        name="Historical price",
                        line=dict(color="#38bdf8", width=2),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=result["fast_ma"],
                        mode="lines",
                        name="Fast MA",
                        line=dict(color="#f59e0b", width=1.5),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=result["slow_ma"],
                        mode="lines",
                        name="Slow MA",
                        line=dict(color="#a78bfa", width=1.5),
                    )
                )
                fig.update_layout(
                    title="Historical Price and Moving Averages",
                    xaxis_title="Observation",
                    yaxis_title="Price",
                )
                st.plotly_chart(style_chart(fig, height=400), width="stretch")

                equity_fig = go.Figure()
                equity_fig.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=result["equity"],
                        mode="lines",
                        fill="tozeroy",
                        name="Illustrative equity",
                        line=dict(color="#34d399", width=2),
                        fillcolor="rgba(52,211,153,0.08)",
                    )
                )
                equity_fig.update_layout(
                    title="Illustrative Strategy Equity Curve",
                    xaxis_title="Observation",
                    yaxis_title="Equity ($)",
                )
                st.plotly_chart(
                    style_chart(equity_fig, height=350),
                    width="stretch",
                )

                st.markdown("### Backtest Observations")
                st.dataframe(result, width="stretch", hide_index=True)

                st.download_button(
                    "Export Backtest Results",
                    data=result.to_csv(index=False).encode("utf-8"),
                    file_name="chronosmatch_backtest_results.csv",
                    mime="text/csv",
                )


# ============================================================
# FOOTER
# ============================================================

st.divider()

footer_left, footer_right = st.columns([3, 1])

with footer_left:
    st.caption(
        "CHRONOSMATCH • Professional Trading Terminal • "
        "Local simulation and historical analysis"
    )

with footer_right:
    st.caption(
        f"Last rendered: {datetime.now().strftime('%H:%M:%S')}"
    )