
from pathlib import Path
from datetime import datetime
import time

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

import database
from chronosmatch import ChronosMatch


# ============================================================
# 1. APPLICATION CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# Keep the dashboard's existing simulation database separate.
DASHBOARD_DB_PATH = BASE_DIR / "chronosmatch_simulation.db"

# Dedicated database for the AAPL ChronosMatch engine.
ENGINE_DB_PATH = BASE_DIR / "chronosmatch_aapl.db"

DEFAULT_SYMBOL = "AAPL"
DEFAULT_PRICE = 100.00

MAX_ORDER_QUANTITY = 1000
MAX_ORDER_VALUE = 100000.00

# Configure the engine database before creating the engine.
database.DB_NAME = ENGINE_DB_PATH

st.set_page_config(
    page_title="ChronosMatch | HFT Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 2. SESSION STATE
# ============================================================

SESSION_DEFAULTS = {
    "simulated_orders": [],
    "simulated_trades": [],
    "latency_samples": [],
    "throughput_samples": [],
    "last_order_message": "",
    "last_order_status": "",
    "order_counter": 0,
    "engine_instance": None,
}

for key, value in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def get_engine():
    """Create one engine instance per Streamlit session."""
    if st.session_state.engine_instance is None:
        st.session_state.engine_instance = ChronosMatch()

    return st.session_state.engine_instance


# ============================================================
# 3. HELPER FUNCTIONS
# ============================================================

def money(value):
    return f"${float(value):,.2f}"


def show_message(message, status="success"):
    st.session_state.last_order_message = message
    st.session_state.last_order_status = status


def validate_order(side, price, quantity):
    """Validate an order before submitting it to the engine."""

    if side not in ("BUY", "SELL"):
        return False, "Order side must be BUY or SELL."

    if price <= 0:
        return False, "Price must be greater than zero."

    if quantity <= 0:
        return False, "Quantity must be greater than zero."

    if quantity > MAX_ORDER_QUANTITY:
        return False, (
            f"Maximum quantity per order is "
            f"{MAX_ORDER_QUANTITY} shares."
        )

    if price * quantity > MAX_ORDER_VALUE:
        return False, (
            f"Order value cannot exceed "
            f"{money(MAX_ORDER_VALUE)}."
        )

    return True, "Order validation successful."


def submit_simulation_order(side, price, quantity):
    """
    Submit an AAPL-only simulated order to ChronosMatch.

    No live broker API is called. This dashboard is for
    local engine testing and simulation.
    """

    side = str(side).upper()
    price = float(price)
    quantity = int(quantity)

    valid, message = validate_order(side, price, quantity)

    if not valid:
        show_message(message, "error")
        return

    engine = get_engine()

    previous_trade_count = len(engine.trades)
    start_time = time.perf_counter()

    try:
        # ChronosMatch expects lowercase order sides.
        result = engine.submit_order(
            side.lower(),
            price,
            quantity,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        st.session_state.latency_samples.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "latency_ms": elapsed_ms,
        })

        st.session_state.order_counter += 1

        remaining = quantity

        if isinstance(result, dict):
            remaining = int(
                result.get("remaining_quantity", quantity)
            )

        filled = max(0, quantity - remaining)

        order_record = {
            "Order ID": (
                result.get("id", st.session_state.order_counter)
                if isinstance(result, dict)
                else st.session_state.order_counter
            ),
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Symbol": DEFAULT_SYMBOL,
            "Side": side,
            "Price": price,
            "Quantity": quantity,
            "Filled": filled,
            "Remaining": remaining,
            "Status": (
                "FILLED" if remaining == 0
                else "PARTIALLY FILLED" if filled > 0
                else "OPEN"
            ),
        }

        st.session_state.simulated_orders.append(order_record)

        # Capture only trades created by this order.
        new_trades = engine.trades[previous_trade_count:]

        for trade in new_trades:
            trade_record = dict(trade)

            # Add display fields without removing engine fields.
            trade_record.setdefault(
                "Timestamp",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            trade_record.setdefault("Symbol", DEFAULT_SYMBOL)

            st.session_state.simulated_trades.append(trade_record)

        if remaining == 0:
            status_text = (
                f"{side} order filled: {filled} AAPL shares "
                f"at {money(price)}."
            )
        elif filled > 0:
            status_text = (
                f"{side} order partially filled: {filled} shares "
                f"filled, {remaining} remaining."
            )
        else:
            status_text = (
                f"{side} order submitted. "
                f"{remaining} shares remain open."
            )

        status_text += f" Processing time: {elapsed_ms:.3f} ms."
        show_message(status_text, "success")

    except Exception as exc:
        show_message(
            f"Order submission failed: {exc}",
            "error",
        )


def orders_dataframe():
    return pd.DataFrame(st.session_state.simulated_orders)


def trades_dataframe():
    return pd.DataFrame(st.session_state.simulated_trades)


def get_open_orders():
    df = orders_dataframe()

    if df.empty:
        return df

    return df[df["Remaining"] > 0].copy()


def get_completed_trades():
    df = trades_dataframe()

    if df.empty:
        return df

    return df


def display_last_order_message():
    message = st.session_state.last_order_message
    status = st.session_state.last_order_status

    if not message:
        return

    if status == "error":
        st.error(message)
    else:
        st.success(message)


def metric_card(label, value, help_text=None):
    st.metric(label=label, value=value, help=help_text)


# ============================================================
# 4. CUSTOM DASHBOARD STYLE
# ============================================================

st.markdown(
    """
    <style>
    .stApp {
        background-color: #0b1020;
        color: #e5e7eb;
    }

    [data-testid="stSidebar"] {
        background-color: #111827;
    }

    [data-testid="stMetric"] {
        background-color: #151d30;
        border: 1px solid #273449;
        padding: 15px;
        border-radius: 12px;
    }

    div[data-testid="stForm"] {
        background-color: #111827;
        padding: 18px;
        border-radius: 12px;
        border: 1px solid #273449;
    }

    h1, h2, h3 {
        color: #f3f4f6;
    }

    .small-note {
        color: #9ca3af;
        font-size: 13px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 5. SIDEBAR NAVIGATION
# ============================================================

st.sidebar.title("⚡ ChronosMatch")
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
    ],
)

st.sidebar.markdown("---")

st.sidebar.subheader("Active Instrument")
st.sidebar.info("AAPL — Apple Inc.")

st.sidebar.caption("Mode: Local simulation")
st.sidebar.caption("Engine database: chronosmatch_aapl.db")

st.sidebar.markdown("---")
st.sidebar.warning(
    "Simulation only. This application does not submit live orders."
)


# ============================================================
# 6. SHARED METRICS
# ============================================================

orders_df = orders_dataframe()
trades_df = trades_dataframe()
open_orders_df = get_open_orders()

total_orders = len(orders_df)
total_trades = len(trades_df)

if not orders_df.empty:
    filled_orders = int((orders_df["Remaining"] == 0).sum())
    open_order_count = int((orders_df["Remaining"] > 0).sum())
else:
    filled_orders = 0
    open_order_count = 0

if not trades_df.empty:
    total_trade_volume = 0

    for trade in st.session_state.simulated_trades:
        try:
            qty = trade.get(
                "quantity",
                trade.get("Quantity", trade.get("qty", 0)),
            )
            total_trade_volume += int(qty or 0)
        except (TypeError, ValueError):
            pass
else:
    total_trade_volume = 0


# ============================================================
# 7. TERMINAL OVERVIEW
# ============================================================

if page == "Terminal Overview":

    st.title("📈 Terminal Overview")
    st.caption(
        "AAPL order-matching dashboard powered by ChronosMatch."
    )

    display_last_order_message()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card("Orders Submitted", total_orders)

    with col2:
        metric_card("Orders Fully Filled", filled_orders)

    with col3:
        metric_card("Executed Trades", total_trades)

    with col4:
        metric_card("Open Orders", open_order_count)

    st.markdown("---")

    left, right = st.columns([1.5, 1])

    with left:
        st.subheader("Recent Orders")

        if orders_df.empty:
            st.info("No orders submitted yet.")
        else:
            st.dataframe(
                orders_df.tail(10).iloc[::-1],
                use_container_width=True,
                hide_index=True,
            )

    with right:
        st.subheader("Order Status")

        if orders_df.empty:
            st.info("Order status will appear here.")
        else:
            status_counts = (
                orders_df["Status"]
                .value_counts()
                .rename_axis("Status")
                .reset_index(name="Count")
            )

            fig = px.pie(
                status_counts,
                names="Status",
                values="Count",
                hole=0.55,
                title="Order Distribution",
            )

            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0b1020",
                plot_bgcolor="#0b1020",
            )

            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Recent Executed Trades")

    if trades_df.empty:
        st.info(
            "No trades yet. Submit a SELL order and a matching BUY "
            "order from Order Entry to test the matching engine."
        )
    else:
        st.dataframe(
            trades_df.tail(10).iloc[::-1],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown(
        '<p class="small-note">All figures shown here are based on '
        'orders and trades recorded in the current Streamlit session. '
        'The engine itself uses the dedicated AAPL database.</p>',
        unsafe_allow_html=True,
    )


# ============================================================
# 8. ORDER ENTRY
# ============================================================

elif page == "Order Entry":

    st.title("📝 Order Entry")
    st.caption("Submit simulated AAPL BUY and SELL orders.")

    display_last_order_message()

    info1, info2, info3 = st.columns(3)

    with info1:
        st.metric("Instrument", DEFAULT_SYMBOL)

    with info2:
        st.metric("Maximum Quantity", MAX_ORDER_QUANTITY)

    with info3:
        st.metric("Maximum Order Value", money(MAX_ORDER_VALUE))

    st.markdown("---")

    buy_col, sell_col = st.columns(2)

    with buy_col:
        st.subheader("🟢 Buy AAPL")

        with st.form("buy_order_form"):
            buy_price = st.number_input(
                "Buy price ($)",
                min_value=0.01,
                max_value=1000000.00,
                value=DEFAULT_PRICE,
                step=0.50,
                format="%.2f",
                key="buy_price",
            )

            buy_quantity = st.number_input(
                "Buy quantity",
                min_value=1,
                max_value=MAX_ORDER_QUANTITY,
                value=5,
                step=1,
                key="buy_quantity",
            )

            st.caption(
                f"Estimated order value: "
                f"{money(buy_price * buy_quantity)}"
            )

            buy_submit = st.form_submit_button(
                "Submit BUY Order",
                type="primary",
                use_container_width=True,
            )

            if buy_submit:
                submit_simulation_order(
                    "BUY",
                    buy_price,
                    buy_quantity,
                )
                st.rerun()

    with sell_col:
        st.subheader("🔴 Sell AAPL")

        with st.form("sell_order_form"):
            sell_price = st.number_input(
                "Sell price ($)",
                min_value=0.01,
                max_value=1000000.00,
                value=DEFAULT_PRICE,
                step=0.50,
                format="%.2f",
                key="sell_price",
            )

            sell_quantity = st.number_input(
                "Sell quantity",
                min_value=1,
                max_value=MAX_ORDER_QUANTITY,
                value=5,
                step=1,
                key="sell_quantity",
            )

            st.caption(
                f"Estimated order value: "
                f"{money(sell_price * sell_quantity)}"
            )

            sell_submit = st.form_submit_button(
                "Submit SELL Order",
                type="primary",
                use_container_width=True,
            )

            if sell_submit:
                submit_simulation_order(
                    "SELL",
                    sell_price,
                    sell_quantity,
                )
                st.rerun()

    st.markdown("---")
    st.subheader("Order Validation Rules")

    st.markdown(
        """
        - Only the AAPL instrument is enabled.
        - Order side must be BUY or SELL.
        - Price and quantity must be greater than zero.
        - Maximum quantity is 1,000 shares per order.
        - Maximum order value is $100,000.
        - Orders are processed by the local ChronosMatch engine.
        - No real broker API or live market order is used.
        """
    )


# ============================================================
# 9. MARKET DEPTH
# ============================================================

elif page == "Market Depth":

    st.title("📊 Market Depth")
    st.caption("Open AAPL orders from the current session.")

    open_orders_df = get_open_orders()

    if open_orders_df.empty:
        st.info(
            "No open orders. Submit unmatched BUY or SELL orders "
            "from Order Entry to populate the simulated book."
        )
    else:
        buy_orders = open_orders_df[
            open_orders_df["Side"] == "BUY"
        ].copy()

        sell_orders = open_orders_df[
            open_orders_df["Side"] == "SELL"
        ].copy()

        buy_depth = (
            buy_orders.groupby("Price", as_index=False)["Remaining"]
            .sum()
            .rename(columns={"Remaining": "Quantity"})
            .sort_values("Price", ascending=False)
        )

        sell_depth = (
            sell_orders.groupby("Price", as_index=False)["Remaining"]
            .sum()
            .rename(columns={"Remaining": "Quantity"})
            .sort_values("Price", ascending=True)
        )

        left, right = st.columns(2)

        with left:
            st.subheader("Buy Side — Bids")

            if buy_depth.empty:
                st.info("No open BUY orders.")
            else:
                st.dataframe(
                    buy_depth,
                    use_container_width=True,
                    hide_index=True,
                )

                fig_buy = px.bar(
                    buy_depth,
                    x="Quantity",
                    y="Price",
                    orientation="h",
                    title="Bid Depth",
                )

                fig_buy.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="#0b1020",
                    plot_bgcolor="#0b1020",
                )

                st.plotly_chart(
                    fig_buy,
                    use_container_width=True,
                )

        with right:
            st.subheader("Sell Side — Asks")

            if sell_depth.empty:
                st.info("No open SELL orders.")
            else:
                st.dataframe(
                    sell_depth,
                    use_container_width=True,
                    hide_index=True,
                )

                fig_sell = px.bar(
                    sell_depth,
                    x="Quantity",
                    y="Price",
                    orientation="h",
                    title="Ask Depth",
                )

                fig_sell.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="#0b1020",
                    plot_bgcolor="#0b1020",
                )

                st.plotly_chart(
                    fig_sell,
                    use_container_width=True,
                )

        st.markdown("---")
        st.subheader("Open Order Details")

        st.dataframe(
            open_orders_df,
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        "This page displays the dashboard's session-level order "
        "records. It is not a live exchange order book."
    )


# ============================================================
# 10. TRADE HISTORY
# ============================================================

elif page == "Trade History":

    st.title("📚 Trade History")
    st.caption("Trades generated by the local matching engine.")

    trades_df = trades_dataframe()

    if trades_df.empty:
        st.info(
            "No executed trades found in this session. For a simple "
            "test, submit SELL 5 at $100, then BUY 3 at $100."
        )
    else:
        st.metric("Recorded Trade Events", len(trades_df))

        st.dataframe(
            trades_df.iloc[::-1],
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
# 11. PERFORMANCE LAB
# ============================================================

elif page == "Performance Lab":

    st.title("⚡ Performance Lab")
    st.caption(
        "Measure order-processing latency during this dashboard session."
    )

    latency_df = pd.DataFrame(
        st.session_state.latency_samples
    )

    if latency_df.empty:
        st.info(
            "No performance measurements yet. Submit several orders "
            "from Order Entry to collect latency samples."
        )
    else:
        average_latency = latency_df["latency_ms"].mean()
        min_latency = latency_df["latency_ms"].min()
        max_latency = latency_df["latency_ms"].max()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Average Latency",
                f"{average_latency:.3f} ms",
            )

        with col2:
            st.metric(
                "Minimum Latency",
                f"{min_latency:.3f} ms",
            )

        with col3:
            st.metric(
                "Maximum Latency",
                f"{max_latency:.3f} ms",
            )

        fig = px.line(
            latency_df,
            x="time",
            y="latency_ms",
            markers=True,
            title="Order Processing Latency",
            labels={
                "time": "Submission Time",
                "latency_ms": "Latency (ms)",
            },
        )

        fig.update_layout(
            template="plotly_dark",
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
        "These measurements include local Python execution overhead. "
        "They are not exchange-grade latency or a formal HFT benchmark."
    )


# ============================================================
# 12. RISK MONITOR
# ============================================================

elif page == "Risk Monitor":

    st.title("🛡️ Risk Monitor")
    st.caption("Basic pre-trade limits for simulated AAPL orders.")

    orders_df = orders_dataframe()

    total_order_value = 0.0

    if not orders_df.empty:
        total_order_value = float(
            (orders_df["Price"] * orders_df["Quantity"]).sum()
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Orders Submitted", total_orders)

    with col2:
        st.metric("Total Submitted Notional", money(total_order_value))

    with col3:
        st.metric("Open Orders", open_order_count)

    st.markdown("---")
    st.subheader("Configured Limits")

    limits_df = pd.DataFrame(
        [
            {
                "Risk Rule": "Instrument",
                "Configured Value": DEFAULT_SYMBOL,
                "Status": "Enabled",
            },
            {
                "Risk Rule": "Maximum Quantity Per Order",
                "Configured Value": str(MAX_ORDER_QUANTITY),
                "Status": "Enabled",
            },
            {
                "Risk Rule": "Maximum Order Notional",
                "Configured Value": money(MAX_ORDER_VALUE),
                "Status": "Enabled",
            },
            {
                "Risk Rule": "Live Trading",
                "Configured Value": "Disabled",
                "Status": "Simulation only",
            },
        ]
    )

    st.dataframe(
        limits_df,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.subheader("Order Validation")

    if orders_df.empty:
        st.info("No orders have been submitted.")
    else:
        st.dataframe(
            orders_df[
                [
                    "Order ID",
                    "Side",
                    "Price",
                    "Quantity",
                    "Status",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        "This is a basic simulation risk monitor, not a complete "
        "portfolio risk engine. It does not calculate real account "
        "exposure, buying power, or broker positions."
    )


# ============================================================
# 13. BACKTESTING
# ============================================================

elif page == "Backtesting":

    st.title("🧪 Backtesting")
    st.caption(
        "Review recorded simulated trades. This is not a historical "
        "market-data backtest."
    )

    trades_df = trades_dataframe()

    if trades_df.empty:
        st.info(
            "No executed trades are available. Submit matching orders "
            "to generate trade records."
        )
    else:
        st.metric("Recorded Trade Events", len(trades_df))

        st.subheader("Trade Records")

        st.dataframe(
            trades_df,
            use_container_width=True,
            hide_index=True,
        )

        # Estimate trade notional only when quantity and price fields
        # can be identified in the engine's trade records.
        trade_rows = []

        for trade in st.session_state.simulated_trades:
            price = trade.get(
                "price",
                trade.get("Price", trade.get("trade_price")),
            )

            quantity = trade.get(
                "quantity",
                trade.get("Quantity", trade.get("qty")),
            )

            try:
                if price is not None and quantity is not None:
                    trade_rows.append({
                        "Price": float(price),
                        "Quantity": int(quantity),
                        "Notional": float(price) * int(quantity),
                    })
            except (TypeError, ValueError):
                continue

        if trade_rows:
            metrics_df = pd.DataFrame(trade_rows)

            st.subheader("Recorded Trade Notional")

            st.metric(
                "Total Trade Notional",
                money(metrics_df["Notional"].sum()),
            )

            fig = px.bar(
                metrics_df.reset_index(),
                x="index",
                y="Notional",
                title="Notional by Recorded Trade",
                labels={
                    "index": "Trade Index",
                    "Notional": "Notional ($)",
                },
            )

            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0b1020",
                plot_bgcolor="#0b1020",
            )

            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Backtesting Limitations")

    st.markdown(
        """
        - The application does not download historical AAPL prices.
        - No strategy is evaluated against historical market data.
        - Current results reflect only orders submitted in this session.
        - Profit and loss are not calculated unless the engine's trade
          records and position accounting are extended appropriately.
        """
    )


# ============================================================
# 14. FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "ChronosMatch | Local order-matching simulation | AAPL only"
)
