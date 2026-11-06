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
            f"Order value cannot exceed "
            f"{format_money(MAX_ORDER_VALUE)}.",
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

        elapsed_ms = (time.perf_counter() - start) * 1000

        st.session_state.latency_samples.append({
            "Time": datetime.now().strftime("%H:%M:%S"),
            "Latency (ms)": elapsed_ms,
        })

        st.session_state.submitted_count += 1

        remaining = int(order["remaining_quantity"])
        filled = quantity - remaining

        if remaining == 0:
            message = (
                f"{side} order #{order['id']} fully filled: "
                f"{filled} shares at {format_money(price)}."
            )
        elif filled > 0:
            message = (
                f"{side} order #{order['id']} partially filled: "
                f"{filled} filled, {remaining} remaining."
            )
        else:
            message = (
                f"{side} order #{order['id']} submitted. "
                f"{remaining} shares remain open."
            )

        message += f" Processing time: {elapsed_ms:.3f} ms."
        set_message(message)

    except (ValueError, TypeError, KeyError) as exc:
        set_message(f"Order rejected: {exc}", "error")

    except Exception as exc:
        set_message(f"Order submission failed: {exc}", "error")


# ============================================================
# 5. DASHBOARD STYLING
# ============================================================

st.markdown(
    """
    <style>
    .stApp {
        background: #0b1020;
        color: #e5e7eb;
    }

    [data-testid="stSidebar"] {
        background: #111827;
        border-right: 1px solid #263247;
    }

    [data-testid="stMetric"] {
        background: #151d30;
        border: 1px solid #273449;
        padding: 16px;
        border-radius: 12px;
    }

    div[data-testid="stForm"] {
        background: #111827;
        border: 1px solid #273449;
        border-radius: 12px;
        padding: 18px;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid #273449;
        border-radius: 10px;
        overflow: hidden;
    }

    h1, h2, h3 {
        color: #f3f4f6;
    }

    .subtitle {
        color: #9ca3af;
        font-size: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 6. SIDEBAR
# ============================================================

st.sidebar.markdown("# ⚡ ChronosMatch")
st.sidebar.caption("High-Frequency Trading Simulator")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
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
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Active Instrument")
st.sidebar.info("AAPL — Apple Inc.")
st.sidebar.caption("Mode: Local simulation")
st.sidebar.caption("Database: chronosmatch_aapl.db")
st.sidebar.warning(
    "Simulation only. No live broker orders are sent."
)
st.sidebar.markdown("---")
st.sidebar.caption("ChronosMatch | Local matching engine")


# ============================================================
# 7. SHARED DATA AND METRICS
# ============================================================

orders_df = orders_dataframe()
trades_df = trades_dataframe()
open_df = open_orders_dataframe()

total_orders = len(orders_df)
total_trades = len(trades_df)
open_count = len(open_df)

filled_count = (
    int((orders_df["Remaining"] == 0).sum())
    if not orders_df.empty else 0
)

total_notional = (
    float(trades_df["Notional"].sum())
    if not trades_df.empty else 0.0
)

chart_template = "plotly_dark"
# ============================================================
# 8. TERMINAL OVERVIEW
# ============================================================

if page == "Terminal Overview":
    st.title("📈 Terminal Overview")
    st.markdown(
        '<p class="subtitle">AAPL order matching powered by '
        'ChronosMatch.</p>',
        unsafe_allow_html=True,
    )

    display_message()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Orders Submitted", total_orders)
    c2.metric("Orders Fully Filled", filled_count)
    c3.metric("Executed Trades", total_trades)
    c4.metric("Open Orders", open_count)

    st.markdown("---")
    left, right = st.columns([1.5, 1])

    with left:
        st.subheader("Recent Orders")

        if orders_df.empty:
            st.info("No orders have been submitted yet.")
        else:
            st.dataframe(
                orders_df.head(10),
                use_container_width=True,
                hide_index=True,
            )

    with right:
        st.subheader("Order Status")

        if orders_df.empty:
            st.info("Order status will appear here.")
        else:
            status_data = (
                orders_df["Status"]
                .value_counts()
                .rename_axis("Status")
                .reset_index(name="Count")
            )

            fig = px.pie(
                status_data,
                names="Status",
                values="Count",
                hole=0.55,
                title="Order Distribution",
            )
            fig.update_layout(
                template=chart_template,
                paper_bgcolor="#0b1020",
                plot_bgcolor="#0b1020",
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Recent Executed Trades")

    if trades_df.empty:
        st.info(
            "No executed trades yet. Submit matching BUY and SELL "
            "orders from Order Entry."
        )
    else:
        st.dataframe(
            trades_df.head(10),
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        "Order and trade tables are loaded from the persistent "
        "ChronosMatch engine database."
    )


# ============================================================
# 9. ORDER ENTRY
# ============================================================

elif page == "Order Entry":
    st.title("📝 Order Entry")
    st.markdown(
        '<p class="subtitle">Submit simulated AAPL orders.</p>',
        unsafe_allow_html=True,
    )

    display_message()

    c1, c2, c3 = st.columns(3)
    c1.metric("Instrument", DEFAULT_SYMBOL)
    c2.metric("Maximum Quantity", MAX_ORDER_QUANTITY)
    c3.metric(
        "Maximum Order Value",
        format_money(MAX_ORDER_VALUE),
    )

    st.markdown("---")
    buy_col, sell_col = st.columns(2)

    with buy_col:
        st.subheader("🟢 Buy AAPL")

        with st.form("buy_form"):
            buy_price = st.number_input(
                "Buy price ($)",
                min_value=0.01,
                value=DEFAULT_PRICE,
                step=0.50,
                format="%.2f",
            )

            buy_quantity = st.number_input(
                "Buy quantity",
                min_value=1,
                max_value=MAX_ORDER_QUANTITY,
                value=5,
                step=1,
            )

            st.caption(
                "Order value: "
                + format_money(buy_price * buy_quantity)
            )

            buy_clicked = st.form_submit_button(
                "Submit BUY Order",
                type="primary",
                use_container_width=True,
            )

            if buy_clicked:
                submit_simulation_order(
                    "BUY", buy_price, buy_quantity
                )
                st.rerun()

    with sell_col:
        st.subheader("🔴 Sell AAPL")

        with st.form("sell_form"):
            sell_price = st.number_input(
                "Sell price ($)",
                min_value=0.01,
                value=DEFAULT_PRICE,
                step=0.50,
                format="%.2f",
            )

            sell_quantity = st.number_input(
                "Sell quantity",
                min_value=1,
                max_value=MAX_ORDER_QUANTITY,
                value=5,
                step=1,
            )

            st.caption(
                "Order value: "
                + format_money(sell_price * sell_quantity)
            )

            sell_clicked = st.form_submit_button(
                "Submit SELL Order",
                type="primary",
                use_container_width=True,
            )

            if sell_clicked:
                submit_simulation_order(
                    "SELL", sell_price, sell_quantity
                )
                st.rerun()

    st.markdown("---")
    st.subheader("Pre-trade Validation")
    st.markdown(
        """
        - Only AAPL is enabled.
        - BUY and SELL orders are supported.
        - Price and quantity must be positive.
        - Maximum order quantity is 1,000 shares.
        - Maximum order value is $100,000.
        - Orders are processed by the local matching engine.
        """
    )


# ============================================================
# 10. MARKET DEPTH AND ORDER CANCELLATION
# ============================================================

elif page == "Market Depth":
    st.title("📊 Market Depth")
    st.markdown(
        '<p class="subtitle">Current active orders in the engine.</p>',
        unsafe_allow_html=True,
    )

    display_message()
    open_df = open_orders_dataframe()

    if open_df.empty:
        st.info("There are no open or partially filled orders.")

    else:
        buy_orders = open_df[open_df["Side"] == "BUY"]
        sell_orders = open_df[open_df["Side"] == "SELL"]

        bid_depth = (
            buy_orders.groupby("Price", as_index=False)["Remaining"]
            .sum()
            .rename(columns={"Remaining": "Quantity"})
            .sort_values("Price", ascending=False)
        )

        ask_depth = (
            sell_orders.groupby("Price", as_index=False)["Remaining"]
            .sum()
            .rename(columns={"Remaining": "Quantity"})
            .sort_values("Price", ascending=True)
        )

        left, right = st.columns(2)

        with left:
            st.subheader("Buy Side — Bids")

            if bid_depth.empty:
                st.info("No active BUY orders.")
            else:
                st.dataframe(
                    bid_depth,
                    use_container_width=True,
                    hide_index=True,
                )

                fig = px.bar(
                    bid_depth,
                    x="Quantity",
                    y="Price",
                    orientation="h",
                    title="Bid Depth",
                )
                fig.update_layout(
                    template=chart_template,
                    paper_bgcolor="#0b1020",
                    plot_bgcolor="#0b1020",
                )
                st.plotly_chart(fig, use_container_width=True)

        with right:
            st.subheader("Sell Side — Asks")

            if ask_depth.empty:
                st.info("No active SELL orders.")
            else:
                st.dataframe(
                    ask_depth,
                    use_container_width=True,
                    hide_index=True,
                )

                fig = px.bar(
                    ask_depth,
                    x="Quantity",
                    y="Price",
                    orientation="h",
                    title="Ask Depth",
                )
                fig.update_layout(
                    template=chart_template,
                    paper_bgcolor="#0b1020",
                    plot_bgcolor="#0b1020",
                )
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("All Active Orders")
        st.dataframe(
            open_df,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("---")
        st.subheader("Cancel an Active Order")

        order_options = open_df["Order ID"].astype(int).tolist()

        def format_order_option(order_id):
            selected = open_df[
                open_df["Order ID"].astype(int) == int(order_id)
            ].iloc[0]

            return (
                f"Order #{int(order_id)} | "
                f"{selected['Side']} | "
                f"${selected['Price']:,.2f} | "
                f"Remaining: {int(selected['Remaining'])}"
            )

        selected_order_id = st.selectbox(
            "Select an open order",
            options=order_options,
            format_func=format_order_option,
            key="cancel_order_select",
        )

        st.warning(
            "Cancellation removes the remaining quantity from the "
            "active order book. Trades already executed cannot "
            "be undone."
        )

        confirm_cancel = st.checkbox(
            "I confirm that I want to cancel this order.",
            key="confirm_cancel_order",
        )

        if st.button(
            "Cancel Selected Order",
            key="cancel_selected_order",
            disabled=not confirm_cancel,
            use_container_width=True,
        ):
            try:
                latest_open_df = open_orders_dataframe()
                latest_order_ids = (
                    latest_open_df["Order ID"].astype(int).tolist()
                )

                if int(selected_order_id) not in latest_order_ids:
                    set_message(
                        f"Order #{selected_order_id} is no longer active. "
                        "Refresh the page and select another order.",
                        "error",
                    )
                else:
                    engine = get_engine()
                    cancelled = engine.cancel_order(
                        int(selected_order_id)
                    )

                    if cancelled:
                        set_message(
                            f"Order #{selected_order_id} cancelled "
                            "successfully."
                        )
                    else:
                        set_message(
                            f"Order #{selected_order_id} could not be "
                            "cancelled. It may already be filled or "
                            "cancelled.",
                            "error",
                        )

            except Exception as exc:
                set_message(
                    f"Cancellation failed: {exc}",
                    "error",
                )

            st.rerun()

    st.caption(
        "Depth is derived from persisted active orders, not live "
        "exchange data. This dashboard operates in simulation mode."
    )


# ============================================================
# 11. TRADE HISTORY
# ============================================================

elif page == "Trade History":
    st.title("📚 Trade History")
    st.markdown(
        '<p class="subtitle">Persisted executions from ChronosMatch.</p>',
        unsafe_allow_html=True,
    )

    trades_df = trades_dataframe()

    if trades_df.empty:
        st.info("No trades have been executed yet.")

    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Executed Trades", len(trades_df))
        c2.metric(
            "Total Shares Traded",
            f"{int(trades_df['Quantity'].sum()):,}",
        )
        c3.metric(
            "Total Trade Notional",
            format_money(trades_df["Notional"].sum()),
        )

        st.markdown("---")
        st.dataframe(
            trades_df,
            use_container_width=True,
            hide_index=True,
        )

        csv_data = trades_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download Trade History CSV",
            data=csv_data,
            file_name="chronosmatch_aapl_trades.csv",
            mime="text/csv",
        )


# ============================================================
# 12. PERFORMANCE LAB
# ============================================================

elif page == "Performance Lab":
    st.title("⚡ Performance Lab")
    st.markdown(
        '<p class="subtitle">Local order-processing measurements.</p>',
        unsafe_allow_html=True,
    )

    latency_df = pd.DataFrame(
        st.session_state.latency_samples
    )

    if latency_df.empty:
        st.info("Submit orders to collect latency measurements.")

    else:
        average_latency = latency_df["Latency (ms)"].mean()
        minimum_latency = latency_df["Latency (ms)"].min()
        maximum_latency = latency_df["Latency (ms)"].max()

        c1, c2, c3 = st.columns(3)
        c1.metric("Average Latency", f"{average_latency:.3f} ms")
        c2.metric("Minimum Latency", f"{minimum_latency:.3f} ms")
        c3.metric("Maximum Latency", f"{maximum_latency:.3f} ms")

        fig = px.line(
            latency_df,
            x="Time",
            y="Latency (ms)",
            markers=True,
            title="Order Processing Latency",
        )
        fig.update_layout(
            template=chart_template,
            paper_bgcolor="#0b1020",
            plot_bgcolor="#0b1020",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            latency_df,
            use_container_width=True,
            hide_index=True,
        )

    st.warning(
        "Latency measurements reset with the Streamlit session. "
        "They include local Python and database overhead and are not "
        "exchange-grade HFT benchmarks."
    )


# ============================================================
# 13. RISK MONITOR
# ============================================================

elif page == "Risk Monitor":
    st.title("🛡️ Risk Monitor")
    st.markdown(
        '<p class="subtitle">Basic pre-trade limits and order exposure.</p>',
        unsafe_allow_html=True,
    )

    orders_df = orders_dataframe()
    open_df = open_orders_dataframe()

    submitted_notional = (
        float((orders_df["Price"] * orders_df["Quantity"]).sum())
        if not orders_df.empty else 0.0
    )

    open_notional = (
        float((open_df["Price"] * open_df["Remaining"]).sum())
        if not open_df.empty else 0.0
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Orders", len(orders_df))
    c2.metric("Open Orders", len(open_df))
    c3.metric("Open Order Notional", format_money(open_notional))

    st.markdown("---")
    st.subheader("Configured Risk Limits")

    limits_df = pd.DataFrame([
        {
            "Rule": "Enabled Instrument",
            "Value": DEFAULT_SYMBOL,
            "Status": "Enabled",
        },
        {
            "Rule": "Maximum Quantity per Order",
            "Value": str(MAX_ORDER_QUANTITY),
            "Status": "Enabled",
        },
        {
            "Rule": "Maximum Order Notional",
            "Value": format_money(MAX_ORDER_VALUE),
            "Status": "Enabled",
        },
        {
            "Rule": "Live Broker Trading",
            "Value": "Disabled",
            "Status": "Simulation only",
        },
    ])

    st.dataframe(
        limits_df,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.subheader("Persisted Orders")

    if orders_df.empty:
        st.info("No orders available.")
    else:
        st.dataframe(
            orders_df,
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        "Submitted notional is not the same as current account exposure. "
        "This page does not calculate positions, buying power, or P&L."
    )


# ============================================================
# 14. BACKTESTING
# ============================================================

elif page == "Backtesting":
    st.title("🧪 Backtesting")
    st.markdown(
        '<p class="subtitle">Analysis of recorded simulated executions.</p>',
        unsafe_allow_html=True,
    )

    trades_df = trades_dataframe()

    if trades_df.empty:
        st.info("No executed trades are available for analysis.")

    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Trade Records", len(trades_df))
        c2.metric(
            "Total Shares",
            f"{int(trades_df['Quantity'].sum()):,}",
        )
        c3.metric(
            "Total Notional",
            format_money(trades_df["Notional"].sum()),
        )

        st.markdown("---")
        st.subheader("Recorded Executions")
        st.dataframe(
            trades_df,
            use_container_width=True,
            hide_index=True,
        )

        fig = px.bar(
            trades_df,
            x="Trade ID",
            y="Notional",
            title="Notional per Trade Record",
            labels={
                "Trade ID": "Trade ID",
                "Notional": "Trade Notional ($)",
            },
        )
        fig.update_layout(
            template=chart_template,
            paper_bgcolor="#0b1020",
            plot_bgcolor="#0b1020",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Scope")
    st.markdown(
        """
        This page analyzes trades stored by the matching engine.
        It does not yet run a strategy against historical market prices.
        Historical price data, strategy rules, fees, and portfolio
        accounting would be needed for a full backtesting system.
        """
    )


# ============================================================
# 15. PAPER TRADING — SIMULATION ONLY
# ============================================================

elif page == "Paper Trading":
    st.title("🧪 Paper Trading")

    st.warning(
        "SIMULATION ONLY — No Upstox API requests, live market data, "
        "or real broker orders are used on this page."
    )

    trader = get_paper_trader()

    st.subheader("Place a Simulated Order")

    with st.form("paper_trading_order_form"):
        symbol = st.text_input(
            "Symbol",
            value="DEMO",
        ).strip().upper()

        side = st.selectbox(
            "Side",
            ["BUY", "SELL"],
        )

        quantity = st.number_input(
            "Quantity",
            min_value=1,
            max_value=MAX_ORDER_QUANTITY,
            value=1,
            step=1,
        )

        price = st.number_input(
            "Simulated Price",
            min_value=0.01,
            max_value=MAX_ORDER_VALUE,
            value=100.00,
            step=1.00,
        )

        order_value = float(quantity) * float(price)
        st.caption(
            f"Simulated order value: {format_money(order_value)}"
        )

        submitted = st.form_submit_button(
            "Place Paper Order",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if order_value > MAX_ORDER_VALUE:
            st.error(
                f"Order value cannot exceed "
                f"{format_money(MAX_ORDER_VALUE)}."
            )
        else:
            try:
                order = trader.place_order(
                    symbol=symbol,
                    side=side,
                    quantity=int(quantity),
                    price=float(price),
                )

                st.success("Paper order completed successfully.")
                st.json(order)

            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))

    st.markdown("---")
    st.subheader("Paper Order History")

    paper_orders = trader.get_orders()
    paper_df = pd.DataFrame(paper_orders)

    if paper_df.empty:
        st.info("No simulated paper orders yet.")
    else:
        c1, c2, c3 = st.columns(3)

        c1.metric("Paper Orders", len(paper_df))
        c2.metric(
            "Simulated Order Value",
            format_money(paper_df["simulated_value"].sum()),
        )
        c3.metric(
            "Simulated Quantity",
            int(paper_df["quantity"].sum()),
        )

        st.dataframe(
            paper_df,
            use_container_width=True,
            hide_index=True,
        )

        csv_data = paper_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download Paper Order History",
            data=csv_data,
            file_name="chronosmatch_paper_orders.csv",
            mime="text/csv",
        )

    st.caption(
        "Paper orders exist only in the current Streamlit session. "
        "They are not sent to Upstox and are not saved to the "
        "ChronosMatch matching-engine database."
    )
    # ============================================================
# 16. UPSTOX SIMULATOR — LOCAL SIMULATION ONLY
# ============================================================

elif page == "Upstox Simulator":

    st.title("🚀 Upstox Simulator")

    st.markdown(
        '<p class="subtitle">'
        'Local order placement, modification and cancellation simulator.'
        '</p>',
        unsafe_allow_html=True,
    )

    st.warning(
        "LOCAL SIMULATION ONLY — This is not the official Upstox "
        "sandbox. No Upstox API requests, authentication, live market "
        "data or real broker orders are used."
    )

    simulator = get_upstox_simulator()

    # --------------------------------------------------------
    # Simulator status
    # --------------------------------------------------------

    st.subheader("Simulator Status")

    c1, c2, c3 = st.columns(3)

    c1.metric("Environment", "LOCAL")
    c2.metric("Broker Connection", "Disabled")
    c3.metric("Real Orders", "Disabled")

    st.markdown("---")

    # --------------------------------------------------------
    # Place a simulated order
    # --------------------------------------------------------

    st.subheader("📝 Place Simulated Order")

    with st.form("upstox_local_order_form"):

        symbol = st.text_input(
            "Trading Symbol",
            value="DEMO",
        ).strip().upper()

        side = st.selectbox(
            "Order Side",
            ["BUY", "SELL"],
        )

        order_type = st.selectbox(
            "Order Type",
            ["LIMIT", "MARKET"],
        )

        quantity = st.number_input(
            "Quantity",
            min_value=1,
            max_value=MAX_ORDER_QUANTITY,
            value=1,
            step=1,
        )

        price = st.number_input(
            "Simulated Price",
            min_value=0.01,
            max_value=MAX_ORDER_VALUE,
            value=100.00,
            step=1.00,
        )

        order_value = float(quantity) * float(price)

        st.caption(
            f"Simulated order value: {format_money(order_value)}"
        )

        place_clicked = st.form_submit_button(
            "Place Local Simulated Order",
            type="primary",
            use_container_width=True,
        )

    if place_clicked:

        if not symbol:
            st.error("Please enter a trading symbol.")

        elif quantity > MAX_ORDER_QUANTITY:
            st.error("Maximum order quantity exceeded.")

        elif order_value > MAX_ORDER_VALUE:
            st.error(
                f"Order value cannot exceed "
                f"{format_money(MAX_ORDER_VALUE)}."
            )

        else:
            try:
                new_order = simulator.place_order(
                    symbol=symbol,
                    side=side,
                    quantity=int(quantity),
                    price=float(price),
                    order_type=order_type,
                )

                st.success("Local simulated order created successfully.")

                st.json(new_order)

            except (ValueError, TypeError, RuntimeError) as exc:
                st.error(f"Order rejected: {exc}")

            except Exception as exc:
                st.error(f"Unexpected error: {exc}")

    st.markdown("---")

    # --------------------------------------------------------
    # Order history
    # --------------------------------------------------------

    st.subheader("📋 Local Order History")

    local_orders = simulator.get_orders()

    local_df = pd.DataFrame(local_orders)

    if local_df.empty:

        st.info("No local simulated orders have been placed yet.")

    else:

        c1, c2, c3 = st.columns(3)

        c1.metric("Total Orders", len(local_df))

        c2.metric(
            "Open Orders",
            int((local_df["status"] == "OPEN").sum()),
        )

        c3.metric(
            "Cancelled Orders",
            int((local_df["status"] == "CANCELLED").sum()),
        )

        st.dataframe(
            local_df,
            use_container_width=True,
            hide_index=True,
        )

        csv_data = local_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download Local Order History",
            data=csv_data,
            file_name="upstox_local_orders.csv",
            mime="text/csv",
        )

    st.markdown("---")

    # --------------------------------------------------------
    # Modify an open order
    # --------------------------------------------------------

    st.subheader("✏️ Modify Local Order")

    open_local_orders = [
        order for order in local_orders
        if order.get("status") == "OPEN"
    ]

    if not open_local_orders:

        st.info("There are no OPEN local orders to modify.")

    else:

        order_ids = [
            order["order_id"] for order in open_local_orders
        ]

        selected_modify_id = st.selectbox(
            "Select order to modify",
            order_ids,
            key="local_modify_order",
        )

        with st.form("modify_local_order_form"):

            modify_quantity = st.number_input(
                "New Quantity",
                min_value=1,
                max_value=MAX_ORDER_QUANTITY,
                value=1,
                step=1,
            )

            modify_price = st.number_input(
                "New Price",
                min_value=0.01,
                max_value=MAX_ORDER_VALUE,
                value=100.00,
                step=1.00,
            )

            modify_clicked = st.form_submit_button(
                "Modify Local Order",
                use_container_width=True,
            )

        if modify_clicked:

            if modify_quantity * modify_price > MAX_ORDER_VALUE:

                st.error("Modified order value exceeds the maximum limit.")

            else:

                try:

                    updated_order = simulator.modify_order(
                        selected_modify_id,
                        quantity=int(modify_quantity),
                        price=float(modify_price),
                    )

                    st.success("Local order modified successfully.")

                    st.json(updated_order)

                except (ValueError, TypeError, RuntimeError) as exc:

                    st.error(f"Modification failed: {exc}")

                except Exception as exc:

                    st.error(f"Unexpected error: {exc}")

    st.markdown("---")

    # --------------------------------------------------------
    # Cancel an open order
    # --------------------------------------------------------

    st.subheader("❌ Cancel Local Order")

    # Refresh the order list after any changes.
    local_orders = simulator.get_orders()

    cancellable_orders = [
        order for order in local_orders
        if order.get("status") == "OPEN"
    ]

    if not cancellable_orders:

        st.info("There are no OPEN local orders to cancel.")

    else:

        cancel_ids = [
            order["order_id"] for order in cancellable_orders
        ]

        selected_cancel_id = st.selectbox(
            "Select order to cancel",
            cancel_ids,
            key="local_cancel_order",
        )

        confirm_local_cancel = st.checkbox(
            "I confirm cancellation of this local simulated order.",
            key="confirm_local_cancel",
        )

        if st.button(
            "Cancel Local Order",
            disabled=not confirm_local_cancel,
            use_container_width=True,
        ):

            try:

                cancelled_order = simulator.cancel_order(
                    selected_cancel_id
                )

                st.success("Local simulated order cancelled.")

                st.json(cancelled_order)

            except (ValueError, TypeError, RuntimeError) as exc:

                st.error(f"Cancellation failed: {exc}")

            except Exception as exc:

                st.error(f"Unexpected error: {exc}")

    st.markdown("---")

    # --------------------------------------------------------
    # Safety information
    # --------------------------------------------------------

    st.subheader("🔒 Simulation Safety")

    st.markdown(
        """
        - Environment: Local simulation.
        - Broker authentication: Not used.
        - Upstox API connection: Not used.
        - Live market data: Not used.
        - Real-money trading: Not supported.
        - Order placement: Local Python simulator only.
        - Order modification: Local simulator only.
        - Order cancellation: Local simulator only.
        """
    )

    st.caption(
        "Local simulator orders exist only in the current Streamlit "
        "session. Restarting the session may clear the order history."
    )


# ============================================================
# 17. FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "ChronosMatch HFT Terminal | AAPL | Local simulation | "
    "Persistent SQLite engine database | "
    "Upstox Local Simulator"
)