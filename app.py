from pathlib import Path
from datetime import datetime
import time

import pandas as pd
import streamlit as st
import plotly.express as px

import database
from chronosmatch import ChronosMatch
from upstox_adapter import PaperTrader
from upstox_local_simulator import UpstoxLocalSimulator


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DB_PATH = BASE_DIR / "chronosmatch_simulation.db"
ENGINE_DB_PATH = BASE_DIR / "chronosmatch_aapl.db"

DEFAULT_SYMBOL = "AAPL"
DEFAULT_PRICE = 100.00
MAX_ORDER_QUANTITY = 1000
MAX_ORDER_VALUE = 100000.00

database.DB_NAME = ENGINE_DB_PATH
database.create_tables()

st.set_page_config(
    page_title="ChronosMatch | HFT Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 2. SESSION STATE
# ============================================================

DEFAULTS = {
    "engine": None,
    "last_order_message": "",
    "last_order_status": "success",
    "latency_samples": [],
    "submitted_count": 0,
    "paper_trader": None,
    "upstox_simulator": None,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def get_engine():
    if st.session_state.engine is None:
        st.session_state.engine = ChronosMatch()
    return st.session_state.engine


def get_paper_trader():
    if st.session_state.paper_trader is None:
        st.session_state.paper_trader = PaperTrader()
    return st.session_state.paper_trader


def get_upstox_simulator():
    if st.session_state.upstox_simulator is None:
        st.session_state.upstox_simulator = UpstoxLocalSimulator()
    return st.session_state.upstox_simulator


# ============================================================
# 3. DATABASE DATA FUNCTIONS
# ============================================================

def orders_dataframe():
    rows = database.get_all_orders()
    records = []

    for order in rows:
        quantity = int(order["quantity"])
        remaining = int(order["remaining_quantity"])

        records.append({
            "Order ID": order["id"],
            "Symbol": DEFAULT_SYMBOL,
            "Side": order["side"].upper(),
            "Price": float(order["price"]),
            "Quantity": quantity,
            "Filled": quantity - remaining,
            "Remaining": remaining,
            "Status": order["status"],
        })

    return pd.DataFrame(
        records,
        columns=[
            "Order ID", "Symbol", "Side", "Price",
            "Quantity", "Filled", "Remaining", "Status",
        ],
    )


def trades_dataframe():
    rows = database.get_all_trades()
    records = []

    for trade in rows:
        price = float(trade["price"])
        quantity = int(trade["quantity"])

        records.append({
            "Trade ID": trade["id"],
            "Symbol": DEFAULT_SYMBOL,
            "Price": price,
            "Quantity": quantity,
            "Notional": price * quantity,
        })

    return pd.DataFrame(
        records,
        columns=[
            "Trade ID", "Symbol", "Price",
            "Quantity", "Notional",
        ],
    )


# FIXED: get_active_orders() returns quantity, not remaining_quantity.
def open_orders_dataframe():
    rows = database.get_active_orders()
    records = []

    for order in rows:
        records.append({
            "Order ID": order["id"],
            "Symbol": DEFAULT_SYMBOL,
            "Side": order["side"].upper(),
            "Price": float(order["price"]),
            "Remaining": int(order["quantity"]),
        })

    return pd.DataFrame(
        records,
        columns=[
            "Order ID", "Symbol", "Side", "Price", "Remaining",
        ],
    )


def format_money(value):
    return f"${float(value):,.2f}"


def set_message(message, status="success"):
    st.session_state.last_order_message = message
    st.session_state.last_order_status = status


def display_message():
    message = st.session_state.last_order_message

    if not message:
        return

    if st.session_state.last_order_status == "error":
        st.error(message)
    else:
        st.success(message)


# ============================================================
# 4. ORDER VALIDATION AND SUBMISSION
# ============================================================

def submit_simulation_order(side, price, quantity):
    side = str(side).upper()
    price = float(price)
    quantity = int(quantity)

    if side not in ("BUY", "SELL"):
        set_message("Invalid order side.", "error")
        return

    if price <= 0:
        set_message("Price must be greater than zero.", "error")
        return

    if quantity <= 0:
        set_message("Quantity must be greater than zero.", "error")
        return

    if quantity > MAX_ORDER_QUANTITY:
        set_message(
            f"Maximum order quantity is {MAX_ORDER_QUANTITY}.",
            "error",
        )
        return

    if price * quantity > MAX_ORDER_VALUE:
        set_message(
            f"Order value cannot exceed {format_money(MAX_ORDER_VALUE)}.",
            "error",
        )
        return

    engine = get_engine()
    start = time.perf_counter()

    try:
        order = engine.submit_order(
            side.lower(),
            price,
            quantity,
        )

        elapsed = (time.perf_counter() - start) * 1000

        st.session_state.latency_samples.append(elapsed)
        st.session_state.submitted_count += 1

        set_message(
            f"{side} order submitted successfully. Order ID: {order}",
            "success",
        )

    except Exception as exc:
        set_message(
            f"Order submission failed: {exc}",
            "error",
        )



# ============================================================
# 5. CYBERPUNK NEON DASHBOARD STYLING
# ============================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        --bg: #050807;
        --panel: #0b1210;
        --panel2: #101b17;
        --neon: #39ff14;
        --cyan: #00f5ff;
        --purple: #b026ff;
        --red: #ff3155;
        --text: #e7fff0;
        --muted: #83a394;
        --border: rgba(57,255,20,0.22);
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background:
            linear-gradient(rgba(57,255,20,0.025) 1px, transparent 1px),
            linear-gradient(90deg, rgba(57,255,20,0.025) 1px, transparent 1px),
            radial-gradient(ellipse at 10% 0%, #10251a 0%, transparent 35%),
            radial-gradient(ellipse at 90% 10%, #101a2d 0%, transparent 35%),
            #050807;
        background-size: 35px 35px, 35px 35px, auto, auto, auto;
        color: var(--text);
    }

    [data-testid="stHeader"] {
        background: rgba(5,8,7,0.95);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a1510, #050807);
        border-right: 1px solid var(--border);
    }

    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.5rem;
    }

    [data-testid="stSidebar"] .stRadio label {
        color: #b9d8c5;
        font-weight: 600;
        padding: 5px 0;
        transition: 0.2s;
    }

    [data-testid="stSidebar"] .stRadio label:hover {
        color: var(--neon);
    }

    .main .block-container {
        max-width: 1550px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    h1, h2, h3 {
        color: var(--neon) !important;
        font-family: 'Orbitron', sans-serif !important;
        letter-spacing: 0.5px;
    }

    p, label, span {
        color: #c3ddce;
    }

    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #101c16, #09100d);
        border: 1px solid rgba(57,255,20,0.28);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 0 12px rgba(57,255,20,0.06);
        transition: all 0.25s ease;
    }

    [data-testid="stMetric"]:hover {
        border-color: var(--neon);
        box-shadow: 0 0 18px rgba(57,255,20,0.22);
        transform: translateY(-3px);
    }

    [data-testid="stMetricLabel"] {
        color: #8eae9b !important;
        font-size: 0.8rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    [data-testid="stMetricValue"] {
        color: var(--neon) !important;
        font-weight: 800 !important;
        text-shadow: 0 0 10px rgba(57,255,20,0.2);
    }

    div.stButton > button,
    div.stFormSubmitButton > button {
        background: linear-gradient(100deg, #123c20, #087d46);
        color: #ffffff;
        border: 1px solid var(--neon);
        border-radius: 7px;
        font-weight: 700;
        transition: all 0.2s ease;
    }

    div.stButton > button:hover,
    div.stFormSubmitButton > button:hover {
        background: #39ff14;
        color: #050807;
        box-shadow: 0 0 18px rgba(57,255,20,0.5);
        transform: translateY(-2px);
        border-color: var(--neon);
    }

    div[data-testid="stForm"] {
        background: rgba(11,18,16,0.95);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 0 18px rgba(0,0,0,0.3);
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 10px;
        overflow: hidden;
    }

    div[data-testid="stPlotlyChart"] {
        background: #0b1210;
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 8px;
    }

    div[data-testid="stAlert"] {
        border-radius: 9px;
        border: 1px solid var(--border);
    }

    input, textarea {
        background-color: #0b1510 !important;
        color: #e7fff0 !important;
        border-color: rgba(57,255,20,0.3) !important;
    }

    [data-baseweb="select"] > div {
        background-color: #0b1510;
        border-color: rgba(57,255,20,0.3);
    }

    hr {
        border-color: rgba(57,255,20,0.2);
    }

    .terminal-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 2.2rem;
        font-weight: 800;
        color: var(--neon);
        letter-spacing: 1px;
        text-shadow: 0 0 12px rgba(57,255,20,0.45);
    }

    .terminal-subtitle {
        color: #8eae9b;
        font-size: 0.9rem;
        letter-spacing: 1px;
        margin-top: -5px;
    }

    .status-pill {
        display: inline-block;
        background: rgba(57,255,20,0.09);
        color: var(--neon);
        border: 1px solid rgba(57,255,20,0.5);
        padding: 6px 13px;
        border-radius: 5px;
        font-size: 0.75rem;
        font-weight: 800;
        letter-spacing: 1px;
        box-shadow: 0 0 10px rgba(57,255,20,0.12);
    }

    .cyber-label {
        color: var(--cyan);
        font-family: 'Orbitron', sans-serif;
        letter-spacing: 2px;
        font-size: 0.75rem;
    }

    @keyframes cyberGlow {
        0%, 100% { text-shadow: 0 0 5px #39ff14; }
        50% { text-shadow: 0 0 16px #39ff14; }
    }

    .terminal-title {
        animation: cyberGlow 3s infinite;
    }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation: none !important;
            transition: none !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)



# ============================================================
# 6. CYBERPUNK SIDEBAR NAVIGATION
# ============================================================

with st.sidebar:

    st.markdown(
        """
        <div style="padding: 8px 4px 22px 4px;">
            <div style="
                font-family: Orbitron, sans-serif;
                font-size: 1.45rem;
                font-weight: 800;
                color: #39ff14;
                text-shadow: 0 0 12px rgba(57,255,20,0.6);
            ">
                ⚡ CHRONOS
            </div>

            <div style="
                font-family: Orbitron, sans-serif;
                color: #00f5ff;
                font-size: 0.72rem;
                margin-top: 7px;
                letter-spacing: 2px;
            ">
                MATCH ENGINE
            </div>

            <div style="
                color: #83a394;
                font-size: 0.68rem;
                margin-top: 5px;
            ">
                HIGH FREQUENCY TRADING SYSTEM
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<span class="status-pill">● SYSTEM ONLINE</span>',
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown(
        '<div class="cyber-label">◈ CONTROL CENTER</div>',
        unsafe_allow_html=True,
    )

    page = st.radio(
        "NAVIGATION",
        [
            "Terminal Overview",
            "Order Entry",
            "Market Depth",
            "Trade History",
            "Performance Lab",
            "Risk Monitor",
            "Backtesting",
            "Paper Trading",
            "Upstox Simulator",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    st.markdown(
        """
        <div style="
            color: #83a394;
            font-size: 0.72rem;
            line-height: 1.8;
        ">
            <span style="color:#39ff14;">●</span> LOCAL ENGINE ACTIVE
            <br>
            <span style="color:#00f5ff;">◈</span> SIMULATION MODE
            <br>
            <span style="color:#b026ff;">◆</span> CHRONOSMATCH v1.0
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.caption(
        f"LAST UPDATE: {datetime.now().strftime('%d %b %Y, %H:%M:%S')}"
    )



# ============================================================
# 7. LOAD DATA
# ============================================================

orders_df = orders_dataframe()
trades_df = trades_dataframe()
open_orders_df = open_orders_dataframe()

total_orders = len(orders_df)
total_trades = len(trades_df)
open_orders_count = len(open_orders_df)

total_volume = (
    int(trades_df["Quantity"].sum())
    if not trades_df.empty
    else 0
)

total_notional = (
    float(trades_df["Notional"].sum())
    if not trades_df.empty
    else 0.0
)

average_latency = (
    sum(st.session_state.latency_samples)
    / len(st.session_state.latency_samples)
    if st.session_state.latency_samples
    else 0.0
)


# ============================================================
# 8. COMMON HEADER
# ============================================================

st.markdown(
    '<div class="terminal-title">ChronosMatch Terminal</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="terminal-subtitle">'
    'Real-time order matching • Execution analytics • Simulation environment'
    '</div>',
    unsafe_allow_html=True,
)

st.write("")


# ============================================================
# 9. TERMINAL OVERVIEW — LIVE REFRESH
# ============================================================

if page == "Terminal Overview":

    @st.fragment(run_every=2)
    def live_terminal_overview():

        orders_df = orders_dataframe()
        trades_df = trades_dataframe()
        open_orders_df = open_orders_dataframe()

        total_orders = len(orders_df)
        total_trades = len(trades_df)
        open_orders_count = len(open_orders_df)

        total_volume = (
            int(trades_df["Quantity"].sum())
            if not trades_df.empty
            else 0
        )

        total_notional = (
            float(trades_df["Notional"].sum())
            if not trades_df.empty
            else 0.0
        )

        average_latency = (
            sum(st.session_state.latency_samples)
            / len(st.session_state.latency_samples)
            if st.session_state.latency_samples
            else 0.0
        )

        buy_orders_count = (
            int((orders_df["Side"] == "BUY").sum())
            if not orders_df.empty
            else 0
        )

        sell_orders_count = (
            int((orders_df["Side"] == "SELL").sum())
            if not orders_df.empty
            else 0
        )

        average_execution_price = (
            total_notional / total_volume
            if total_volume > 0
            else 0.0
        )

        st.caption(
            f"LIVE · Refreshes every 2 seconds · "
            f"Last updated: {datetime.now().strftime('%H:%M:%S')}"
        )

        st.subheader("Market Overview")

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Total Orders Processed", f"{total_orders:,}")
        col2.metric("Total Trades", f"{total_trades:,}")
        col3.metric("Open Orders", f"{open_orders_count:,}")
        col4.metric("Traded Volume", f"{total_volume:,}")

        st.write("")

        col5, col6, col7, col8 = st.columns(4)

        col5.metric("Total Notional", format_money(total_notional))
        col6.metric(
            "Average Execution Price",
            format_money(average_execution_price),
        )
        col7.metric("Average Latency", f"{average_latency:.4f} ms")
        col8.metric(
            "Submitted This Session",
            st.session_state.submitted_count,
        )

        st.write("")

        col9, col10 = st.columns(2)

        col9.metric("Total Buy Orders", f"{buy_orders_count:,}")
        col10.metric("Total Sell Orders", f"{sell_orders_count:,}")

        st.divider()

        left, right = st.columns([1.4, 1])

        with left:
            st.subheader("Recent Trades")

            if trades_df.empty:
                st.info(
                    "No trades available yet. "
                    "Submit simulation orders to begin."
                )
            else:
                st.dataframe(
                    trades_df.tail(10).iloc[::-1],
                    width="stretch",
                    hide_index=True,
                )

        with right:
            st.subheader("Order Status")

            if orders_df.empty:
                st.info("No orders available.")
            else:
                status_counts = (
                    orders_df["Status"]
                    .astype(str)
                    .value_counts()
                    .reset_index()
                )

                status_counts.columns = ["Status", "Count"]

                fig = px.pie(
                    status_counts,
                    names="Status",
                    values="Count",
                    hole=0.65,
                    title="Order Distribution",
                )

                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#e8eef9",
                    margin=dict(t=50, b=10, l=10, r=10),
                )

                st.plotly_chart(fig, width="stretch")

        st.divider()

        st.subheader("Open Orders")

        if open_orders_df.empty:
            st.info("There are no active orders.")
        else:
            st.dataframe(
                open_orders_df,
                width="stretch",
                hide_index=True,
            )

    live_terminal_overview()


# ============================================================
# 10. ORDER ENTRY
# ============================================================

elif page == "Order Entry":

    st.subheader("Place Simulation Order")

    st.info(
        "This order entry page uses the local ChronosMatch matching engine. "
        "It does not place real broker orders."
    )

    left, right = st.columns([1, 1])

    with left:
        with st.form("order_entry_form"):

            side = st.selectbox("Order Side", ["BUY", "SELL"])

            symbol = st.text_input(
                "Symbol",
                value=DEFAULT_SYMBOL,
            )

            price = st.number_input(
                "Limit Price",
                min_value=0.01,
                value=DEFAULT_PRICE,
                step=0.50,
            )

            quantity = st.number_input(
                "Quantity",
                min_value=1,
                max_value=MAX_ORDER_QUANTITY,
                value=10,
                step=1,
            )

            order_value = price * quantity

            st.metric(
                "Estimated Order Value",
                format_money(order_value),
            )

            submitted = st.form_submit_button(
                "Submit Simulation Order",
                width="stretch",
            )

            if submitted:
                if symbol.strip().upper() != DEFAULT_SYMBOL:
                    set_message(
                        f"This engine is configured for {DEFAULT_SYMBOL}.",
                        "error",
                    )
                else:
                    submit_simulation_order(
                        side,
                        price,
                        quantity,
                    )

    with right:
        st.subheader("Order Guidelines")

        st.markdown(
            f"""
            - Supported symbol: **{DEFAULT_SYMBOL}**
            - Maximum quantity: **{MAX_ORDER_QUANTITY}**
            - Maximum order value: **{format_money(MAX_ORDER_VALUE)}**
            - Order type: **Limit order**
            - Execution: **Local simulation**
            """
        )

        display_message()

    st.divider()

    st.subheader("Recent Orders")

    if orders_df.empty:
        st.info("No orders submitted yet.")
    else:
        st.dataframe(
            orders_df.tail(15).iloc[::-1],
            width="stretch",
            hide_index=True,
        )


# ============================================================
# 11. MARKET DEPTH
# ============================================================

elif page == "Market Depth":

    st.subheader("Market Depth")

    st.caption(
        "Current resting orders in the local matching engine."
    )

    buy_orders = open_orders_df[
        open_orders_df["Side"] == "BUY"
    ].copy()

    sell_orders = open_orders_df[
        open_orders_df["Side"] == "SELL"
    ].copy()

    buy_orders = buy_orders.sort_values(
        "Price",
        ascending=False,
    )

    sell_orders = sell_orders.sort_values(
        "Price",
        ascending=True,
    )

    buy_col, sell_col = st.columns(2)

    with buy_col:
        st.markdown("### 🟢 Buy Side")

        if buy_orders.empty:
            st.info("No open buy orders.")
        else:
            st.dataframe(
                buy_orders,
                width="stretch",
                hide_index=True,
            )

    with sell_col:
        st.markdown("### 🔴 Sell Side")

        if sell_orders.empty:
            st.info("No open sell orders.")
        else:
            st.dataframe(
                sell_orders,
                width="stretch",
                hide_index=True,
            )

    st.divider()

    st.subheader("Order Book Summary")

    best_bid = (
        buy_orders["Price"].max()
        if not buy_orders.empty
        else None
    )

    best_ask = (
        sell_orders["Price"].min()
        if not sell_orders.empty
        else None
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Best Bid",
        format_money(best_bid) if best_bid is not None else "—",
    )

    c2.metric(
        "Best Ask",
        format_money(best_ask) if best_ask is not None else "—",
    )

    spread = (
        best_ask - best_bid
        if best_bid is not None and best_ask is not None
        else None
    )

    c3.metric(
        "Spread",
        format_money(spread) if spread is not None else "—",
    )


# ============================================================
# 12. TRADE HISTORY
# ============================================================

elif page == "Trade History":

    st.subheader("Trade History")

    if trades_df.empty:
        st.info("No completed trades available.")
    else:
        search_col, count_col = st.columns([2, 1])

        with search_col:
            search_text = st.text_input(
                "Search trade ID",
                placeholder="Enter trade ID",
            )

        with count_col:
            rows_to_show = st.selectbox(
                "Rows to display",
                [10, 25, 50, 100, "All"],
                index=1,
            )

        filtered_trades = trades_df.copy()

        if search_text.strip():
            filtered_trades = filtered_trades[
                filtered_trades["Trade ID"]
                .astype(str)
                .str.contains(search_text.strip(), case=False)
            ]

        if rows_to_show != "All":
            filtered_trades = filtered_trades.tail(
                int(rows_to_show)
            )

        st.dataframe(
            filtered_trades.iloc[::-1],
            width="stretch",
            hide_index=True,
        )

        st.download_button(
            "Download Trade History CSV",
            data=trades_df.to_csv(index=False),
            file_name="chronosmatch_trade_history.csv",
            mime="text/csv",
        )

    st.divider()

    st.subheader("Trade Statistics")

    if not trades_df.empty:
        a, b, c = st.columns(3)

        a.metric("Number of Trades", len(trades_df))

        b.metric(
            "Average Trade Price",
            format_money(trades_df["Price"].mean()),
        )

        c.metric(
            "Total Traded Value",
            format_money(trades_df["Notional"].sum()),
        )


# ============================================================
# 13. PERFORMANCE LAB
# ============================================================

elif page == "Performance Lab":

    st.subheader("Execution Performance")

    latency_values = st.session_state.latency_samples

    col1, col2, col3 = st.columns(3)

    col1.metric("Samples", len(latency_values))

    col2.metric(
        "Average Latency",
        f"{average_latency:.4f} ms",
    )

    col3.metric(
        "Fastest Execution",
        f"{min(latency_values):.4f} ms"
        if latency_values
        else "—",
    )

    st.divider()

    if latency_values:
        latency_df = pd.DataFrame({
            "Execution": range(1, len(latency_values) + 1),
            "Latency (ms)": latency_values,
        })

        fig = px.line(
            latency_df,
            x="Execution",
            y="Latency (ms)",
            markers=True,
            title="Execution Latency",
        )

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        st.plotly_chart(fig, width="stretch")

    else:
        st.info(
            "No latency samples yet. Submit simulation orders to collect data."
        )

    st.caption(
        "Latency values are measured locally and are not exchange latency."
    )


# ============================================================
# 14. RISK MONITOR
# ============================================================

elif page == "Risk Monitor":

    st.subheader("Risk Monitor")

    st.caption(
        "Basic pre-trade limits for local simulation orders."
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Maximum Quantity", MAX_ORDER_QUANTITY)

    col2.metric(
        "Maximum Order Value",
        format_money(MAX_ORDER_VALUE),
    )

    col3.metric("Current Open Orders", open_orders_count)

    st.divider()

    if not orders_df.empty:
        st.subheader("Order Value Exposure")

        exposure_df = orders_df.copy()

        exposure_df["Order Value"] = (
            exposure_df["Price"] * exposure_df["Quantity"]
        )

        st.dataframe(
            exposure_df[
                [
                    "Order ID",
                    "Side",
                    "Price",
                    "Quantity",
                    "Order Value",
                    "Status",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

        total_exposure = exposure_df["Order Value"].sum()

        st.metric(
            "Total Submitted Order Value",
            format_money(total_exposure),
        )

    else:
        st.info("No order exposure to display.")

    st.warning(
        "This is a basic simulation risk monitor, not a production-grade "
        "financial risk management system."
    )


# ============================================================
# 15. BACKTESTING
# ============================================================

elif page == "Backtesting":

    st.subheader("Backtesting Lab")

    st.info(
        "This page provides a basic historical trade-data analysis. "
        "It does not fetch external market data."
    )

    if trades_df.empty:
        st.info(
            "Complete some simulated trades before running the analysis."
        )
    else:
        backtest_df = trades_df.copy()

        backtest_df["Cumulative Volume"] = (
            backtest_df["Quantity"].cumsum()
        )

        backtest_df["Cumulative Notional"] = (
            backtest_df["Notional"].cumsum()
        )

        fig = px.line(
            backtest_df,
            x="Trade ID",
            y="Cumulative Notional",
            markers=True,
            title="Cumulative Traded Notional",
        )

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        st.plotly_chart(fig, width="stretch")

        st.dataframe(
            backtest_df,
            width="stretch",
            hide_index=True,
        )


# ============================================================
# 16. PAPER TRADING
# ============================================================

elif page == "Paper Trading":

    st.subheader("Paper Trading")

    st.info(
        "Paper trading is simulated trading. No real money or broker orders "
        "are involved."
    )

    trader = get_paper_trader()

    st.markdown("### Account Summary")

    try:
        balance = trader.get_balance()
        positions = trader.get_positions()
        paper_orders = trader.get_orders()

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Available Balance",
            format_money(balance),
        )

        c2.metric("Open Positions", len(positions))

        c3.metric("Paper Orders", len(paper_orders))

        st.divider()

        st.markdown("### Place Paper Order")

        with st.form("paper_order_form"):

            paper_side = st.selectbox(
                "Side",
                ["BUY", "SELL"],
                key="paper_side",
            )

            paper_symbol = st.text_input(
                "Symbol",
                value=DEFAULT_SYMBOL,
                key="paper_symbol",
            )

            paper_price = st.number_input(
                "Price",
                min_value=0.01,
                value=DEFAULT_PRICE,
                key="paper_price",
            )

            paper_quantity = st.number_input(
                "Quantity",
                min_value=1,
                max_value=MAX_ORDER_QUANTITY,
                value=1,
                key="paper_quantity",
            )

            paper_submit = st.form_submit_button(
                "Place Paper Order",
                width="stretch",
            )

            if paper_submit:
                result = trader.place_order(
                    paper_symbol.strip().upper(),
                    paper_side.lower(),
                    float(paper_price),
                    int(paper_quantity),
                )

                st.success(
                    f"Paper order submitted: {result}"
                )

                st.rerun()

        st.divider()

        st.markdown("### Positions")

        if positions:
            st.dataframe(
                pd.DataFrame(positions),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("No paper positions available.")

        st.markdown("### Paper Orders")

        if paper_orders:
            st.dataframe(
                pd.DataFrame(paper_orders),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("No paper orders available.")

    except Exception as exc:
        st.error(f"Paper trading module error: {exc}")


# ============================================================
# 17. UPSTOX LOCAL SIMULATOR
# ============================================================

elif page == "Upstox Simulator":

    st.subheader("Upstox-Style Local Order Simulator")

    st.warning(
        "This is a local simulator only. It is not connected to the official "
        "Upstox API or sandbox. No real orders are sent."
    )

    simulator = get_upstox_simulator()

    st.markdown("### Place Local Simulated Order")

    with st.form("upstox_local_order_form"):

        local_symbol = st.text_input(
            "Trading Symbol",
            value=DEFAULT_SYMBOL,
        )

        local_side = st.selectbox(
            "Transaction Type",
            ["BUY", "SELL"],
        )

        local_quantity = st.number_input(
            "Quantity",
            min_value=1,
            max_value=MAX_ORDER_QUANTITY,
            value=1,
        )

        local_price = st.number_input(
            "Price",
            min_value=0.01,
            value=DEFAULT_PRICE,
        )

        local_submit = st.form_submit_button(
            "Submit Local Order",
            width="stretch",
        )

        if local_submit:
            try:
                result = simulator.place_order(
                    symbol=local_symbol.strip().upper(),
                    side=local_side.lower(),
                    quantity=int(local_quantity),
                    price=float(local_price),
                )

                st.success(
                    f"Local order created successfully: {result}"
                )

            except Exception as exc:
                st.error(f"Local order failed: {exc}")

    st.divider()

    st.markdown("### Local Order Management")

    local_orders = simulator.get_orders()

    open_local_orders = [
        order for order in local_orders
        if order.get("status") == "OPEN"
    ]

    st.metric("Open Local Orders", len(open_local_orders))

    if local_orders:
        st.dataframe(
            pd.DataFrame(local_orders),
            width="stretch",
            hide_index=True,
        )

        st.markdown("### Modify or Cancel Order")

        order_ids = [
            order.get("order_id")
            for order in open_local_orders
        ]

        if order_ids:
            selected_order = st.selectbox(
                "Select Order ID",
                order_ids,
            )

            modify_col, cancel_col = st.columns(2)

            with modify_col:
                with st.form("modify_local_order_form"):

                    new_quantity = st.number_input(
                        "New Quantity",
                        min_value=1,
                        value=1,
                    )

                    new_price = st.number_input(
                        "New Price",
                        min_value=0.01,
                        value=DEFAULT_PRICE,
                    )

                    modify_submit = st.form_submit_button(
                        "Modify Order",
                        width="stretch",
                    )

                    if modify_submit:
                        try:
                            result = simulator.modify_order(
                                selected_order,
                                quantity=int(new_quantity),
                                price=float(new_price),
                            )

                            st.success(f"Order modified: {result}")

                            st.rerun()

                        except Exception as exc:
                            st.error(f"Modification failed: {exc}")

            with cancel_col:
                st.write("")

                if st.button(
                    "Cancel Selected Order",
                    width="stretch",
                ):
                    try:
                        result = simulator.cancel_order(
                            selected_order
                        )

                        st.success(f"Order cancelled: {result}")

                        st.rerun()

                    except Exception as exc:
                        st.error(f"Cancellation failed: {exc}")

        else:
            st.info("There are no open local orders.")

    else:
        st.info("No local simulator orders yet.")


# ============================================================
# 18. FOOTER
# ============================================================

st.divider()

st.markdown(
    """
    <div style="
        text-align: center;
        padding: 14px 0;
        color: #64748b;
        font-size: 0.78rem;
    ">
        ⚡ <strong>ChronosMatch</strong> |
        Local HFT Matching Engine Simulation |
        Built with Python and Streamlit
        <br>
        For educational and testing purposes only.
        No real broker orders are placed.
    </div>
    """,
    unsafe_allow_html=True,
)