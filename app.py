from pathlib import Path
from datetime import datetime
import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import database
from chronosmatch import ChronosMatch
from upstox_adapter import PaperTrader
from upstox_local_simulator import UpstoxLocalSimulator


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
ENGINE_DB_PATH = BASE_DIR / "chronosmatch_aapl.db"

DEFAULT_SYMBOL = "AAPL"
DEFAULT_PRICE = 100.00
MAX_ORDER_QUANTITY = 1000
MAX_ORDER_VALUE = 100000.00

database.DB_NAME = ENGINE_DB_PATH
database.create_tables()

st.set_page_config(
    page_title="ChronosMatch | Trading Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 2. SESSION STATE
# ============================================================

DEFAULTS = {
    "engine": None,
    "paper_trader": None,
    "upstox_simulator": None,
    "latency_samples": [],
    "submitted_count": 0,
    "last_order_message": "",
    "last_order_status": "success",
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
            "Side": str(order["side"]).upper(),
            "Price": float(order["price"]),
            "Quantity": quantity,
            "Filled": quantity - remaining,
            "Remaining": remaining,
            "Status": str(order["status"]).upper(),
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


def open_orders_dataframe():
    rows = database.get_active_orders()
    records = []

    for order in rows:
        records.append({
            "Order ID": order["id"],
            "Symbol": DEFAULT_SYMBOL,
            "Side": str(order["side"]).upper(),
            "Price": float(order["price"]),
            "Remaining": int(order["quantity"]),
        })

    return pd.DataFrame(
        records,
        columns=[
            "Order ID", "Symbol", "Side",
            "Price", "Remaining",
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


def calculate_metrics(orders, trades):
    total_orders = len(orders)
    total_trades = len(trades)

    volume = (
        int(trades["Quantity"].sum())
        if not trades.empty else 0
    )

    notional = (
        float(trades["Notional"].sum())
        if not trades.empty else 0.0
    )

    average_price = (
        notional / volume if volume > 0 else 0.0
    )

    buy_count = (
        int((orders["Side"] == "BUY").sum())
        if not orders.empty else 0
    )

    sell_count = (
        int((orders["Side"] == "SELL").sum())
        if not orders.empty else 0
    )

    submitted_quantity = (
        int(orders["Quantity"].sum())
        if not orders.empty else 0
    )

    filled_quantity = (
        int(orders["Filled"].sum())
        if not orders.empty else 0
    )

    fill_rate = (
        filled_quantity / submitted_quantity * 100
        if submitted_quantity > 0 else 0.0
    )

    return {
        "orders": total_orders,
        "trades": total_trades,
        "volume": volume,
        "notional": notional,
        "average_price": average_price,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "fill_rate": fill_rate,
    }


# ============================================================
# 4. ORDER SUBMISSION
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
            f"Maximum quantity is {MAX_ORDER_QUANTITY}.",
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
        order_id = engine.submit_order(
            side.lower(),
            price,
            quantity,
        )

        elapsed = (time.perf_counter() - start) * 1000

        st.session_state.latency_samples.append(elapsed)
        st.session_state.submitted_count += 1

        set_message(
            f"{side} order submitted successfully. Order ID: {order_id}",
            "success",
        )

    except Exception as exc:
        set_message(
            f"Order submission failed: {exc}",
            "error",
        )


# ============================================================
# 5. PROFESSIONAL TERMINAL DESIGN
# ============================================================

st.markdown(
    """
    <style>
    @import url(
        'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap'
    );

    :root {
        --background: #080e19;
        --panel: #111c2d;
        --border: #26364e;
        --text: #e5edf7;
        --muted: #91a1b7;
        --blue: #3b82f6;
        --green: #16c784;
        --red: #ea3943;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: var(--background);
        color: var(--text);
    }

    [data-testid="stHeader"] {
        background: var(--background);
    }

    [data-testid="stSidebar"] {
        background: #0d1726;
        border-right: 1px solid var(--border);
    }

    .main .block-container {
        max-width: 1600px;
        padding-top: 1.8rem;
        padding-bottom: 3rem;
    }

    h1, h2, h3 {
        color: #e5edf7 !important;
        font-weight: 700 !important;
    }

    p, label, span {
        color: #c4d0e0;
    }

    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #15243a, #101b2c);
        border: 1px solid #263a56;
        border-radius: 12px;
        padding: 17px;
    }

    [data-testid="stMetricLabel"] {
        color: #91a1b7 !important;
        font-size: 0.78rem !important;
        font-weight: 600;
    }

    [data-testid="stMetricValue"] {
        color: #e5edf7 !important;
        font-weight: 700 !important;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 9px;
        overflow: hidden;
    }

    div[data-testid="stPlotlyChart"] {
        background: #111c2d;
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 8px;
    }

    div[data-testid="stForm"] {
        background: #111c2d;
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 18px;
    }

    div.stButton > button,
    div.stFormSubmitButton > button {
        background: #2563eb;
        color: white;
        border: 1px solid #3b82f6;
        border-radius: 7px;
        font-weight: 600;
    }

    div.stButton > button:hover,
    div.stFormSubmitButton > button:hover {
        background: #1d4ed8;
        border-color: #60a5fa;
        color: white;
    }

    input, textarea {
        background: #111c2d !important;
        color: #e5edf7 !important;
    }

    [data-baseweb="select"] > div {
        background: #111c2d;
        border-color: #26364e;
    }

    hr {
        border-color: #26364e;
    }

    .terminal-brand {
        font-size: 1.45rem;
        font-weight: 800;
        letter-spacing: 1px;
        color: #e5edf7;
    }

    .terminal-brand span {
        color: #3b82f6;
    }

    .terminal-subtitle {
        color: #91a1b7;
        font-size: 0.82rem;
        margin-top: 5px;
    }

    .status-pill {
        display: inline-block;
        background: rgba(22,199,132,0.10);
        border: 1px solid rgba(22,199,132,0.35);
        color: #16c784;
        border-radius: 20px;
        padding: 5px 11px;
        font-size: 0.72rem;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 6. SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown(
        """
        <div class="terminal-brand">
            CHRONOS<span>MATCH</span>
        </div>
        <div class="terminal-subtitle">
            INSTITUTIONAL TRADING TERMINAL
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    st.markdown(
        '<span class="status-pill">● SIMULATION ENGINE READY</span>',
        unsafe_allow_html=True,
    )

    st.divider()

    page = st.radio(
        "NAVIGATION",
        [
            "Terminal Overview",
            "Order Entry",
            "Market Depth",
            "Trade Graphs",
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

    st.caption("SYSTEM")
    st.write("● Local matching engine")
    st.write("● Simulation mode")
    st.write("● SQLite database")

    st.divider()

    st.caption(
        f"Last update: {datetime.now().strftime('%d %b %Y %H:%M:%S')}"
    )


# ============================================================
# 7. LOAD DATA
# ============================================================

orders_df = orders_dataframe()
trades_df = trades_dataframe()
open_orders_df = open_orders_dataframe()

metrics = calculate_metrics(orders_df, trades_df)

average_latency = (
    sum(st.session_state.latency_samples)
    / len(st.session_state.latency_samples)
    if st.session_state.latency_samples else 0.0
)


# ============================================================
# 8. COMMON HEADER
# ============================================================

header_left, header_right = st.columns([3, 1])

with header_left:
    st.markdown("# ChronosMatch Trading Terminal")
    st.markdown(
        '<div class="terminal-subtitle">'
        'Order matching · Market depth · Execution analytics · Trade visualization'
        '</div>',
        unsafe_allow_html=True,
    )

with header_right:
    st.markdown(
        '<div style="text-align:right">'
        '<span class="status-pill">LOCAL SIMULATION</span>'
        '</div>',
        unsafe_allow_html=True,
    )

st.write("")


# ============================================================
# 9. TERMINAL OVERVIEW
# ============================================================

if page == "Terminal Overview":

    @st.fragment(run_every=2)
    def live_overview():

        current_orders = orders_dataframe()
        current_trades = trades_dataframe()
        current_open = open_orders_dataframe()

        current = calculate_metrics(
            current_orders,
            current_trades,
        )

        st.caption(
            f"Dashboard refreshes every 2 seconds · "
            f"Updated {datetime.now().strftime('%H:%M:%S')}"
        )

        st.subheader("Market Summary")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Total Orders", f"{current['orders']:,}")
        c2.metric("Completed Trades", f"{current['trades']:,}")
        c3.metric("Open Orders", f"{len(current_open):,}")
        c4.metric("Traded Volume", f"{current['volume']:,}")

        c5, c6, c7, c8 = st.columns(4)

        c5.metric(
            "Traded Notional",
            format_money(current["notional"]),
        )

        c6.metric(
            "Average Execution Price",
            format_money(current["average_price"]),
        )

        c7.metric(
            "Average Local Latency",
            f"{average_latency:.4f} ms",
        )

        c8.metric(
            "Fill Rate",
            f"{current['fill_rate']:.2f}%",
        )

        st.divider()

        left, right = st.columns([1.5, 1])

        with left:
            st.subheader("Recent Trades")

            if current_trades.empty:
                st.info("No completed trades yet.")
            else:
                st.dataframe(
                    current_trades.tail(10).iloc[::-1],
                    width="stretch",
                    hide_index=True,
                )

        with right:
            st.subheader("Order Side Distribution")

            if current_orders.empty:
                st.info("No orders available.")
            else:
                side_counts = (
                    current_orders["Side"]
                    .value_counts()
                    .rename_axis("Side")
                    .reset_index(name="Orders")
                )

                fig = px.pie(
                    side_counts,
                    names="Side",
                    values="Orders",
                    hole=0.62,
                    color="Side",
                    color_discrete_map={
                        "BUY": "#16c784",
                        "SELL": "#ea3943",
                    },
                )

                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(t=20, b=10, l=10, r=10),
                )

                st.plotly_chart(fig, width="stretch")

        st.divider()

        st.subheader("Current Open Orders")

        if current_open.empty:
            st.info("There are no active orders.")
        else:
            st.dataframe(
                current_open,
                width="stretch",
                hide_index=True,
            )

    live_overview()


# ============================================================
# 10. ORDER ENTRY
# ============================================================

elif page == "Order Entry":

    st.subheader("Order Entry")

    st.info(
        "Orders submitted here are processed by your local "
        "ChronosMatch matching engine. No real broker orders are placed."
    )

    left, right = st.columns([1.2, 1])

    with left:
        with st.form("order_entry_form"):

            side = st.selectbox(
                "Order Side",
                ["BUY", "SELL"],
            )

            symbol = st.text_input(
                "Trading Symbol",
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

            st.metric(
                "Estimated Order Value",
                format_money(price * quantity),
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
        st.subheader("Order Rules")

        st.metric("Maximum Quantity", MAX_ORDER_QUANTITY)

        st.metric(
            "Maximum Order Value",
            format_money(MAX_ORDER_VALUE),
        )

        st.write("Supported symbol:", DEFAULT_SYMBOL)
        st.write("Order type: Limit order")
        st.write("Execution: Local simulation")

        display_message()

    st.divider()

    st.subheader("Recent Orders")

    if orders_df.empty:
        st.info("No orders submitted yet.")
    else:
        st.dataframe(
            orders_df.tail(20).iloc[::-1],
            width="stretch",
            hide_index=True,
        )


# ============================================================
# 11. MARKET DEPTH
# ============================================================

elif page == "Market Depth":

    st.subheader("Market Depth")

    st.caption(
        "Aggregated resting orders from the local matching engine."
    )

    buy_orders = open_orders_df[
        open_orders_df["Side"] == "BUY"
    ].copy()

    sell_orders = open_orders_df[
        open_orders_df["Side"] == "SELL"
    ].copy()

    buy_depth = (
        buy_orders.groupby("Price", as_index=False)["Remaining"]
        .sum()
        .sort_values("Price", ascending=False)
    )

    sell_depth = (
        sell_orders.groupby("Price", as_index=False)["Remaining"]
        .sum()
        .sort_values("Price", ascending=True)
    )

    best_bid = (
        buy_depth["Price"].max()
        if not buy_depth.empty else None
    )

    best_ask = (
        sell_depth["Price"].min()
        if not sell_depth.empty else None
    )

    spread = (
        best_ask - best_bid
        if best_bid is not None and best_ask is not None
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

    c3.metric(
        "Bid-Ask Spread",
        format_money(spread) if spread is not None else "—",
    )

    st.divider()

    buy_col, sell_col = st.columns(2)

    with buy_col:
        st.markdown("### Buy Book")

        if buy_depth.empty:
            st.info("No open buy orders.")
        else:
            st.dataframe(
                buy_depth,
                width="stretch",
                hide_index=True,
            )

    with sell_col:
        st.markdown("### Sell Book")

        if sell_depth.empty:
            st.info("No open sell orders.")
        else:
            st.dataframe(
                sell_depth,
                width="stretch",
                hide_index=True,
            )

    st.divider()

    st.subheader("Market Depth Visualization")

    if buy_depth.empty and sell_depth.empty:
        st.info("Submit resting orders to view market depth.")
    else:
        depth_fig = go.Figure()

        if not buy_depth.empty:
            depth_fig.add_trace(
                go.Bar(
                    x=buy_depth["Price"],
                    y=buy_depth["Remaining"],
                    name="Buy Quantity",
                    marker_color="#16c784",
                )
            )

        if not sell_depth.empty:
            depth_fig.add_trace(
                go.Bar(
                    x=sell_depth["Price"],
                    y=sell_depth["Remaining"],
                    name="Sell Quantity",
                    marker_color="#ea3943",
                )
            )

        depth_fig.update_layout(
            template="plotly_dark",
            title="Quantity Available at Each Price",
            xaxis_title="Price",
            yaxis_title="Remaining Quantity",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            barmode="group",
        )

        st.plotly_chart(depth_fig, width="stretch")


# ============================================================
# 12. TRADE GRAPHS - CANDLESTICK CHART
# ============================================================

elif page == "Trade Graphs":

    st.subheader("Candlestick Trading Analytics")

    st.caption(
        "Professional trading chart using actual ChronosMatch executions."
    )

    if trades_df.empty:

        st.info(
            "No completed trades yet. Submit matching BUY and SELL "
            "orders to generate candlestick data."
        )

    else:

        graph_df = trades_df.copy().reset_index(drop=True)

        graph_df["Trade Number"] = range(
            1,
            len(graph_df) + 1,
        )

        total_volume = int(graph_df["Quantity"].sum())
        total_value = float(graph_df["Notional"].sum())

        average_price = (
            total_value / total_volume
            if total_volume > 0 else 0
        )

        highest_price = float(graph_df["Price"].max())
        lowest_price = float(graph_df["Price"].min())

        st.markdown("### Market Statistics")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Total Trades", len(graph_df))
        c2.metric("Total Volume", f"{total_volume:,}")
        c3.metric("Total Traded Value", format_money(total_value))
        c4.metric("Average Price", format_money(average_price))

        st.divider()

        st.markdown("### Candlestick Chart")

        trades_per_candle = st.selectbox(
            "Trades per candle",
            [1, 2, 3, 5, 10],
            index=2,
        )

        graph_df["Candle Group"] = (
            graph_df.index // trades_per_candle
        ) + 1

        candles = (
            graph_df.groupby("Candle Group", as_index=False)
            .agg(
                Open=("Price", "first"),
                High=("Price", "max"),
                Low=("Price", "min"),
                Close=("Price", "last"),
                Volume=("Quantity", "sum"),
            )
        )

        candle_fig = go.Figure()

        candle_fig.add_trace(
            go.Candlestick(
                x=candles["Candle Group"],
                open=candles["Open"],
                high=candles["High"],
                low=candles["Low"],
                close=candles["Close"],
                increasing_line_color="#16c784",
                decreasing_line_color="#ea3943",
                increasing_fillcolor="#16c784",
                decreasing_fillcolor="#ea3943",
                name="Execution Price",
            )
        )

        candle_fig.update_layout(
            template="plotly_dark",
            title="ChronosMatch Execution Candlesticks",
            xaxis_title="Candle Number",
            yaxis_title="Execution Price",
            paper_bgcolor="#111c2d",
            plot_bgcolor="#111c2d",
            height=520,
            xaxis_rangeslider_visible=False,
            margin=dict(l=30, r=30, t=60, b=30),
        )

        candle_fig.update_xaxes(
            showgrid=True,
            gridcolor="#26364e",
        )

        candle_fig.update_yaxes(
            showgrid=True,
            gridcolor="#26364e",
        )

        st.plotly_chart(
            candle_fig,
            width="stretch",
        )

        st.divider()

        st.markdown("### Trading Volume")

        volume_fig = go.Figure()

        volume_fig.add_trace(
            go.Bar(
                x=candles["Candle Group"],
                y=candles["Volume"],
                marker_color="#3b82f6",
                name="Volume",
            )
        )

        volume_fig.update_layout(
            template="plotly_dark",
            title="Volume per Candle",
            xaxis_title="Candle Number",
            yaxis_title="Traded Quantity",
            paper_bgcolor="#111c2d",
            plot_bgcolor="#111c2d",
            height=300,
        )

        st.plotly_chart(
            volume_fig,
            width="stretch",
        )

        st.divider()

        st.markdown("### Execution Price Movement")

        price_fig = px.line(
            graph_df,
            x="Trade Number",
            y="Price",
            markers=True,
            title="Execution Price by Trade",
        )

        price_fig.update_traces(
            line=dict(color="#3b82f6", width=2),
            marker=dict(size=8),
        )

        price_fig.update_layout(
            template="plotly_dark",
            xaxis_title="Trade Number",
            yaxis_title="Execution Price",
            paper_bgcolor="#111c2d",
            plot_bgcolor="#111c2d",
            height=350,
        )

        st.plotly_chart(
            price_fig,
            width="stretch",
        )

        st.divider()

        st.markdown("### OHLC Candle Data")

        st.dataframe(
            candles,
            width="stretch",
            hide_index=True,
        )

        st.caption(
            "OHLC means Open, High, Low and Close. Candles group "
            "actual executions by trade count. They are not time-based "
            "candles because the current trade data does not provide "
            "execution timestamps."
        )


# ============================================================
# 13. TRADE HISTORY
# ============================================================

elif page == "Trade History":

    st.subheader("Trade History")

    if trades_df.empty:

        st.info("No completed trades available.")

    else:

        filtered = trades_df.copy()

        c1, c2, c3 = st.columns(3)

        with c1:
            search_id = st.text_input(
                "Search Trade ID",
                placeholder="Enter trade ID",
            )

        with c2:
            min_price = float(trades_df["Price"].min())
            max_price = float(trades_df["Price"].max())

            # FIX: Streamlit slider cannot have equal min and max values.
            if min_price < max_price:
                price_range = st.slider(
                    "Execution Price Range",
                    min_value=min_price,
                    max_value=max_price,
                    value=(min_price, max_price),
                    key="trade_history_price_range",
                )
            else:
                st.info(
                    "All completed trades have the same execution price: "
                    f"{format_money(min_price)}"
                )
                price_range = (min_price, max_price)

        with c3:
            rows_to_show = st.selectbox(
                "Rows to display",
                [10, 25, 50, 100, "All"],
                index=1,
            )

        if search_id.strip():
            filtered = filtered[
                filtered["Trade ID"]
                .astype(str)
                .str.contains(
                    search_id.strip(),
                    case=False,
                )
            ]

        filtered = filtered[
            (filtered["Price"] >= price_range[0])
            & (filtered["Price"] <= price_range[1])
        ]

        if rows_to_show != "All":
            filtered = filtered.tail(int(rows_to_show))

        st.write(f"Matching trades: {len(filtered)}")

        st.dataframe(
            filtered.iloc[::-1],
            width="stretch",
            hide_index=True,
        )

        st.download_button(
            "Download Filtered Trade History CSV",
            data=filtered.to_csv(index=False),
            file_name="chronosmatch_trade_history.csv",
            mime="text/csv",
        )

        st.divider()

        a, b, c = st.columns(3)

        a.metric("Number of Trades", len(filtered))

        b.metric(
            "Average Price",
            format_money(
                filtered["Price"].mean()
                if not filtered.empty else 0
            ),
        )

        c.metric(
            "Total Traded Value",
            format_money(filtered["Notional"].sum()),
        )


# ============================================================
# 14. PERFORMANCE LAB
# ============================================================

elif page == "Performance Lab":

    st.subheader("Execution Performance")

    latency_values = st.session_state.latency_samples

    if latency_values:

        latency_series = pd.Series(
            latency_values,
            dtype="float64",
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Samples", len(latency_values))

        c2.metric(
            "Average Latency",
            f"{latency_series.mean():.4f} ms",
        )

        c3.metric(
            "P95 Latency",
            f"{latency_series.quantile(0.95):.4f} ms",
        )

        c4.metric(
            "P99 Latency",
            f"{latency_series.quantile(0.99):.4f} ms",
        )

        latency_df = pd.DataFrame({
            "Execution": range(1, len(latency_values) + 1),
            "Latency (ms)": latency_values,
        })

        st.divider()

        latency_fig = px.line(
            latency_df,
            x="Execution",
            y="Latency (ms)",
            markers=True,
            title="Local Order Submission Latency",
        )

        latency_fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        st.plotly_chart(latency_fig, width="stretch")

        histogram_fig = px.histogram(
            latency_df,
            x="Latency (ms)",
            nbins=20,
            title="Latency Distribution",
        )

        histogram_fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        st.plotly_chart(histogram_fig, width="stretch")

    else:
        st.info(
            "No latency samples yet. Submit simulation orders "
            "to collect local execution measurements."
        )

    st.caption(
        "These measurements are local Python order-submission processing "
        "times. They are not exchange latency or network latency."
    )


# ============================================================
# 15. RISK MONITOR
# ============================================================

elif page == "Risk Monitor":

    st.subheader("Risk Monitor")

    st.caption(
        "Basic order validation and exposure monitoring for simulation."
    )

    c1, c2, c3 = st.columns(3)

    c1.metric("Maximum Quantity", MAX_ORDER_QUANTITY)

    c2.metric(
        "Maximum Order Value",
        format_money(MAX_ORDER_VALUE),
    )

    c3.metric(
        "Current Open Orders",
        len(open_orders_df),
    )

    st.divider()

    if orders_df.empty:

        st.info("No orders available for risk analysis.")

    else:

        exposure = orders_df.copy()

        exposure["Order Value"] = (
            exposure["Price"] * exposure["Quantity"]
        )

        exposure["Remaining Value"] = (
            exposure["Price"] * exposure["Remaining"]
        )

        st.subheader("Order Exposure")

        st.dataframe(
            exposure[
                [
                    "Order ID",
                    "Side",
                    "Price",
                    "Quantity",
                    "Filled",
                    "Remaining",
                    "Order Value",
                    "Remaining Value",
                    "Status",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

        a, b = st.columns(2)

        a.metric(
            "Total Submitted Order Value",
            format_money(exposure["Order Value"].sum()),
        )

        b.metric(
            "Remaining Open Order Value",
            format_money(exposure["Remaining Value"].sum()),
        )

    st.warning(
        "This is a basic educational simulation risk monitor, "
        "not a production-grade financial risk system."
    )


# ============================================================
# 16. BACKTESTING
# ============================================================

elif page == "Backtesting":

    st.subheader("Backtesting Lab")

    st.info(
        "This page analyses recorded simulation trades. "
        "It does not download historical exchange market data."
    )

    if trades_df.empty:

        st.info("Complete simulated trades before running analysis.")

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
# 17. PAPER TRADING
# ============================================================

elif page == "Paper Trading":

    st.subheader("Paper Trading")

    st.info(
        "Paper trading is simulated trading. "
        "No real money or broker orders are involved."
    )

    try:

        trader = get_paper_trader()

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
# 18. UPSTOX LOCAL SIMULATOR
# ============================================================

elif page == "Upstox Simulator":

    st.subheader("Upstox-Style Local Order Simulator")

    st.warning(
        "This is a local simulator only. It is not connected to "
        "the official Upstox API or sandbox. No real orders are sent."
    )

    try:

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

                result = simulator.place_order(
                    symbol=local_symbol.strip().upper(),
                    side=local_side.lower(),
                    quantity=int(local_quantity),
                    price=float(local_price),
                )

                st.success(
                    f"Local order created successfully: {result}"
                )

        st.divider()

        st.markdown("### Local Order Management")

        local_orders = simulator.get_orders()

        open_local_orders = [
            order for order in local_orders
            if order.get("status") == "OPEN"
        ]

        st.metric(
            "Open Local Orders",
            len(open_local_orders),
        )

        if local_orders:

            st.dataframe(
                pd.DataFrame(local_orders),
                width="stretch",
                hide_index=True,
            )

            order_ids = [
                order.get("order_id")
                for order in open_local_orders
            ]

            if order_ids:

                st.markdown("### Modify or Cancel Order")

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

                            result = simulator.modify_order(
                                selected_order,
                                quantity=int(new_quantity),
                                price=float(new_price),
                            )

                            st.success(
                                f"Order modified: {result}"
                            )

                            st.rerun()

                with cancel_col:

                    if st.button(
                        "Cancel Selected Order",
                        width="stretch",
                    ):

                        result = simulator.cancel_order(
                            selected_order
                        )

                        st.success(
                            f"Order cancelled: {result}"
                        )

                        st.rerun()

            else:
                st.info("There are no open local orders.")

        else:
            st.info("No local simulator orders yet.")

    except Exception as exc:
        st.error(f"Local simulator error: {exc}")


# ============================================================
# 19. FOOTER
# ============================================================

st.divider()

st.markdown(
    """
    <div style="
        text-align:center;
        padding:18px 0;
        color:#91a1b7;
        font-size:0.78rem;
    ">
        <strong>ChronosMatch</strong> |
        Local HFT Matching Engine Simulation
        <br>
        Built with Python, Streamlit, Plotly and SQLite
        <br>
        Educational and testing purposes only.
        No real broker orders are placed.
    </div>
    """,
    unsafe_allow_html=True,
)