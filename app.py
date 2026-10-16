
import streamlit as st
import pandas as pd

from database import (
    create_tables,
    get_active_orders,
    get_all_orders,
    get_all_trades
)
from chronosmatch import ChronosMatch


st.set_page_config(
    page_title="ChronosMatch HFT Engine",
    page_icon="📈",
    layout="wide"
)

create_tables()
engine = ChronosMatch()

st.title("📈 ChronosMatch")
st.caption(
    "High-Frequency Trading Engine | "
    "Python + SQLite | Educational Simulator"
)

st.info(
    "Simulation only. This dashboard does not connect "
    "to a real stock exchange or execute real trades."
)

orders = get_all_orders()
trades = get_all_trades()
active_orders = get_active_orders()

total_traded = sum(t["quantity"] for t in trades)
total_buy = sum(1 for o in orders if o["side"] == "buy")
total_sell = sum(1 for o in orders if o["side"] == "sell")

m1, m2, m3, m4 = st.columns(4)

m1.metric("Total Orders", len(orders))
m2.metric("Completed Trade Records", len(trades))
m3.metric("Units Traded", total_traded)
m4.metric("Active Orders", len(active_orders))

st.divider()

left, right = st.columns([1, 2])

with left:
    st.subheader("➕ Submit New Order")

    with st.form("new_order_form"):
        side = st.selectbox(
            "Order Side",
            ["buy", "sell"]
        )

        price = st.number_input(
            "Price",
            min_value=0.01,
            value=100.0,
            step=1.0,
            format="%.2f"
        )

        quantity = st.number_input(
            "Quantity",
            min_value=1,
            max_value=1000000,
            value=10,
            step=1
        )

        submitted = st.form_submit_button(
            "Submit Order",
            use_container_width=True
        )

    if submitted:
        try:
            engine.submit_order(
                side,
                price,
                int(quantity)
            )
            st.success(
                f"{side.upper()} order submitted successfully!"
            )
            st.rerun()

        except (ValueError, TypeError) as error:
            st.error(str(error))

with right:
    st.subheader("📚 Active Order Book")

    buy_orders = [
        o for o in active_orders if o["side"] == "buy"
    ]
    sell_orders = [
        o for o in active_orders if o["side"] == "sell"
    ]

    buy_orders.sort(key=lambda o: -o["price"])
    sell_orders.sort(key=lambda o: o["price"])

    buy_col, sell_col = st.columns(2)

    with buy_col:
        st.markdown("#### 🟢 Buy Orders")
        if buy_orders:
            st.dataframe(
                pd.DataFrame(buy_orders),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.write("No active buy orders.")

    with sell_col:
        st.markdown("#### 🔴 Sell Orders")
        if sell_orders:
            st.dataframe(
                pd.DataFrame(sell_orders),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.write("No active sell orders.")

st.divider()

st.subheader("💹 Completed Trade History")

if trades:
    st.dataframe(
        pd.DataFrame(trades),
        use_container_width=True,
        hide_index=True
    )
else:
    st.write("No trades recorded yet.")

st.divider()

st.subheader("🗂️ All Order Records")

if orders:
    st.dataframe(
        pd.DataFrame(orders),
        use_container_width=True,
        hide_index=True
    )
else:
    st.write("No orders recorded yet.")

st.caption(
    "Order status: OPEN = waiting for a match, "
    "PARTIAL = partially filled, FILLED = fully matched, "
    "HISTORICAL = legacy record from the earlier database version."
)

st.caption(
    "ChronosMatch project | Python | Streamlit | SQLite"
)
