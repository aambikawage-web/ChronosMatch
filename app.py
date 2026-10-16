import streamlit as st
import pandas as pd
from database import create_tables, get_active_orders, get_all_orders, get_all_trades
from chronosmatch import ChronosMatch

st.set_page_config(
    page_title="ChronosMatch | Trading Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root {
    --bg: #202442;
    --panel: #252a4c;
    --panel2: #1d223f;
    --line: #3a426b;
    --text: #e2e7fb;
    --muted: #9ba7cc;
    --green: #16b981;
    --red: #ef5365;
}

.stApp {
    background: var(--bg);
    color: var(--text);
    font-family: Inter, sans-serif;
}

[data-testid="stHeader"] {
    background: #202442;
}

.block-container {
    padding: 1rem 1rem 1rem;
    max-width: 100%;
}

h1, h2, h3, h4, p, label {
    color: var(--text);
}

[data-testid="stSidebar"] {
    background: #191d37;
    border-right: 1px solid var(--line);
}

[data-testid="stMetric"] {
    background: var(--panel2);
    border: 1px solid var(--line);
    padding: 9px 12px;
    border-radius: 5px;
}

[data-testid="stMetricLabel"] {
    color: var(--muted);
}

[data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace;
}

[data-testid="stDataFrame"] {
    border: 1px solid var(--line);
    border-radius: 4px;
}

.stButton button, .stFormSubmitButton button {
    border-radius: 4px;
    border: 1px solid var(--line);
    font-weight: 700;
}

div[data-testid="stForm"] {
    background: var(--panel2);
    border: 1px solid var(--line);
    padding: 12px;
    border-radius: 5px;
}

.terminalbar {
    background: #191d37;
    border: 1px solid var(--line);
    padding: 8px 12px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
}

.brand {
    font-size: 20px;
    font-weight: 800;
    letter-spacing: -.5px;
}

.brand span {
    color: #8da4ff;
}

.topmeta {
    font: 11px 'IBM Plex Mono', monospace;
    color: #c5ccec;
    text-align: right;
}

.panelhead {
    background: #2a3055;
    border: 1px solid var(--line);
    padding: 7px 10px;
    font-size: 12px;
    font-weight: 700;
    margin-bottom: 0;
}

.panelbody {
    background: var(--panel);
    border: 1px solid var(--line);
    padding: 8px;
    margin-bottom: 8px;
}

.smallnote {
    font-size: 11px;
    color: var(--muted);
}

div[data-testid="stPlotlyChart"] {
    background: var(--panel);
    border: 1px solid var(--line);
}
</style>
""", unsafe_allow_html=True)

create_tables()
engine = ChronosMatch()


def num(value, default=0.0):
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def qty(order):
    return max(
        0,
        int(num(order.get(
            "remaining_quantity",
            order.get("quantity", 0)
        )))
    )


def price(value):
    return "—" if value is None else f"{num(value):,.2f}"


orders = get_all_orders() or []
trades = get_all_trades() or []
active = get_active_orders() or []

buys = sorted(
    [o for o in active if str(o.get("side", "")).lower() == "buy"],
    key=lambda o: num(o.get("price")),
    reverse=True,
)

sells = sorted(
    [o for o in active if str(o.get("side", "")).lower() == "sell"],
    key=lambda o: num(o.get("price")),
)

bid = max((num(o.get("price")) for o in buys), default=None)
ask = min((num(o.get("price")) for o in sells), default=None)

spread = (
    ask - bid
    if ask is not None and bid is not None
    else None
)

units = sum(int(num(t.get("quantity"))) for t in trades)

st.markdown("""
<div class="terminalbar">
    <div>
        <div class="brand">◈ ChronosMatch <span>XT</span></div>
        <div class="smallnote">
            SIMULATED MATCHING ENGINE · ORDER BOOK · EXECUTION MONITOR
        </div>
    </div>
    <div class="topmeta">
        <span style="color:#16b981">● SIMULATION</span>
        &nbsp; ENGINE READY
        <br>LOCAL DATA ONLY · NO LIVE EXCHANGE
    </div>
</div>
""", unsafe_allow_html=True)

m1, m2, m3, m4, m5 = st.columns(5)

m1.metric("Orders", len(orders))
m2.metric("Executions", len(trades))
m3.metric("Units traded", f"{units:,}")
m4.metric("Best bid", price(bid))
m5.metric("Best ask", price(ask))

page = st.radio(
    "Workspace",
    ["Trading Terminal", "Market Depth", "Order History", "Analytics"],
    horizontal=True,
    label_visibility="collapsed",
)

if page == "Trading Terminal":

    chart_col, depth_col, watch_col = st.columns(
        [5.0, 5.4, 1.8],
        gap="small",
    )

    with chart_col:
        st.markdown(
            '<div class="panelhead">▦ CHART · SIMULATED EXECUTION PRICE</div>',
            unsafe_allow_html=True,
        )

        st.caption("SYMBOL: CM-SIM · TIMEFRAME: 1m · Local simulator")

        try:
            import plotly.graph_objects as go

            trade_df = pd.DataFrame(trades)

            if not trade_df.empty and "price" in trade_df.columns:
                values = pd.to_numeric(
                    trade_df["price"],
                    errors="coerce",
                ).dropna().tolist()
            else:
                values = []

            illustrative = not bool(values)

            if illustrative:
                values = [
                    100.0, 100.5, 99.8, 100.2, 99.6, 100.7,
                    100.4, 101.0, 100.2, 100.8, 100.5, 101.2
                ]

            x = list(range(len(values)))
            opens = [values[0]] + values[:-1]
            highs = [
                max(a, b) + (0.25 if illustrative else 0)
                for a, b in zip(opens, values)
            ]
            lows = [
                min(a, b) - (0.25 if illustrative else 0)
                for a, b in zip(opens, values)
            ]

            fig = go.Figure()

            fig.add_trace(go.Candlestick(
                x=x,
                open=opens,
                high=highs,
                low=lows,
                close=values,
                increasing_line_color="#18b887",
                decreasing_line_color="#ef5365",
                increasing_fillcolor="#168b70",
                decreasing_fillcolor="#c74358",
                name="Price",
            ))

            fig.add_trace(go.Bar(
                x=x,
                y=[1 + (i % 5) for i in range(len(values))],
                yaxis="y2",
                marker_color="#5363a4",
                opacity=0.45,
                name="Activity",
            ))

            if illustrative:
                fig.add_annotation(
                    text="ILLUSTRATIVE DATA · NO EXECUTIONS YET",
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.92,
                    showarrow=False,
                    font=dict(color="#aab6d9", size=10),
                )

            fig.update_layout(
                height=355,
                margin=dict(l=8, r=8, t=8, b=8),
                paper_bgcolor="#252a4c",
                plot_bgcolor="#252a4c",
                font=dict(color="#c4cbe8", family="IBM Plex Mono"),
                xaxis_rangeslider_visible=False,
                xaxis=dict(gridcolor="#353b61", title=None),
                yaxis=dict(
                    gridcolor="#353b61",
                    title=None,
                    side="right",
                ),
                yaxis2=dict(
                    overlaying="y",
                    side="left",
                    showgrid=False,
                    visible=False,
                ),
                legend=dict(orientation="h", y=1.02, x=0),
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"displayModeBar": False},
            )

            st.caption(
                "Recorded executions are plotted when available. "
                "Placeholder candles are illustrative only."
            )

        except ImportError:
            st.info("Install Plotly using: pip install plotly")

        st.markdown(
            '<div class="panelhead">▤ TIME & SALES</div>',
            unsafe_allow_html=True,
        )

        if trades:
            st.dataframe(
                pd.DataFrame(trades).tail(8),
                hide_index=True,
                use_container_width=True,
                height=220,
            )
        else:
            st.info("No executions yet. Matched trades will appear here.")

    with depth_col:
        st.markdown(
            '<div class="panelhead">▥ MARKET DEPTH · BID / ASK</div>',
            unsafe_allow_html=True,
        )

        depth_rows = []

        for order in buys[:10]:
            depth_rows.append({
                "Bid Qty": qty(order),
                "Bid": num(order.get("price")),
                "Ask": None,
                "Ask Qty": None,
            })

        for i, order in enumerate(sells[:10]):
            if i < len(depth_rows):
                depth_rows[i]["Ask"] = num(order.get("price"))
                depth_rows[i]["Ask Qty"] = qty(order)
            else:
                depth_rows.append({
                    "Bid Qty": None,
                    "Bid": None,
                    "Ask": num(order.get("price")),
                    "Ask Qty": qty(order),
                })

        if depth_rows:
            st.dataframe(
                pd.DataFrame(depth_rows),
                hide_index=True,
                use_container_width=True,
                height=370,
            )
        else:
            st.info("Submit simulated orders to populate market depth.")

        b1, b2, b3 = st.columns(3)
        b1.metric("Best Bid", price(bid))
        b2.metric("Best Ask", price(ask))
        b3.metric("Spread", price(spread))

        st.markdown(
            '<div class="panelhead">▤ ORDER BOOK</div>',
            unsafe_allow_html=True,
        )

        if active:
            st.dataframe(
                pd.DataFrame(active),
                hide_index=True,
                use_container_width=True,
                height=200,
            )
        else:
            st.caption("No active orders.")

    with watch_col:
        st.markdown(
            '<div class="panelhead">☷ WATCHLIST</div>',
            unsafe_allow_html=True,
        )

        st.markdown("""
        <div class="panelbody">
            <b>CM-SIM</b><br>
            <span class="smallnote">ChronosMatch</span>
        </div>
        """, unsafe_allow_html=True)

        last_price = (
            trades[-1].get("price")
            if trades else None
        )

        st.metric("Last", price(last_price))
        st.metric("Net change", "—")

        st.markdown(
            '<div class="panelhead">ORDER ENTRY</div>',
            unsafe_allow_html=True,
        )

        with st.form("terminal_order_form"):
            side = st.radio(
                "Side",
                ["buy", "sell"],
                horizontal=True,
            )

            order_price = st.number_input(
                "Limit price",
                min_value=0.01,
                value=100.00,
                step=0.50,
                format="%.2f",
            )

            quantity = st.number_input(
                "Quantity",
                min_value=1,
                max_value=1_000_000,
                value=10,
                step=1,
            )

            submitted = st.form_submit_button(
                "SUBMIT ORDER",
                use_container_width=True,
            )

        if submitted:
            try:
                engine.submit_order(
                    side,
                    float(order_price),
                    int(quantity),
                )
                st.success(f"{side.upper()} order submitted.")
                st.rerun()
            except Exception as error:
                st.error(f"Order failed: {error}")

        st.caption("Local simulator only; no real orders are sent.")

        if st.button("↻ Refresh", use_container_width=True):
            st.rerun()

    st.markdown(
        '<div class="panelhead">▤ ORDER HISTORY</div>',
        unsafe_allow_html=True,
    )

    if orders:
        st.dataframe(
            pd.DataFrame(orders).tail(12),
            hide_index=True,
            use_container_width=True,
            height=240,
        )
    else:
        st.caption("Order history is empty.")

elif page == "Market Depth":

    a, b, c = st.columns(3)
    a.metric("Best bid", price(bid))
    b.metric("Best ask", price(ask))
    c.metric("Spread", price(spread))

    left, right = st.columns(2)

    with left:
        st.subheader("BUY SIDE · BIDS")
        st.dataframe(
            pd.DataFrame(buys),
            hide_index=True,
            use_container_width=True,
        )

    with right:
        st.subheader("SELL SIDE · ASKS")
        st.dataframe(
            pd.DataFrame(sells),
            hide_index=True,
            use_container_width=True,
        )

    st.subheader("Aggregated Market Depth")

    try:
        import plotly.graph_objects as go

        fig = go.Figure()

        if buys:
            bid_df = pd.DataFrame([
                {"price": num(o.get("price")), "qty": qty(o)}
                for o in buys
            ])
            bid_df = (
                bid_df.groupby("price", as_index=False)["qty"]
                .sum()
                .sort_values("price")
            )

            fig.add_trace(go.Bar(
                x=bid_df["price"],
                y=bid_df["qty"],
                name="Bids",
                marker_color="#16b981",
            ))

        if sells:
            ask_df = pd.DataFrame([
                {"price": num(o.get("price")), "qty": qty(o)}
                for o in sells
            ])
            ask_df = (
                ask_df.groupby("price", as_index=False)["qty"]
                .sum()
                .sort_values("price")
            )

            fig.add_trace(go.Bar(
                x=ask_df["price"],
                y=ask_df["qty"],
                name="Asks",
                marker_color="#ef5365",
            ))

        fig.update_layout(
            barmode="overlay",
            height=330,
            paper_bgcolor="#252a4c",
            plot_bgcolor="#252a4c",
            font_color="#dfe6fb",
            xaxis_gridcolor="#353b61",
            yaxis_gridcolor="#353b61",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"displayModeBar": False},
        )

    except ImportError:
        st.info("Install Plotly using: pip install plotly")

elif page == "Order History":

    st.subheader("Order History")

    if orders:
        df = pd.DataFrame(orders)

        c1, c2 = st.columns(2)

        side_filter = c1.selectbox(
            "Side",
            ["All", "buy", "sell"],
        )

        statuses = (
            ["All"] + sorted(df["status"].dropna().astype(str).unique().tolist())
            if "status" in df else ["All"]
        )

        status_filter = c2.selectbox("Status", statuses)

        if side_filter != "All" and "side" in df:
            df = df[
                df["side"].astype(str).str.lower() == side_filter
            ]

        if status_filter != "All" and "status" in df:
            df = df[df["status"].astype(str) == status_filter]

        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
        )

        st.download_button(
            "Download CSV",
            df.to_csv(index=False).encode("utf-8"),
            file_name="chronosmatch_orders.csv",
            mime="text/csv",
        )
    else:
        st.info("No orders recorded yet.")

elif page == "Analytics":

    st.subheader("Execution Analytics")

    c1, c2 = st.columns(2)
    c1.metric("Executions", len(trades))
    c2.metric("Units traded", f"{units:,}")

    if trades:
        trade_df = pd.DataFrame(trades)

        if "price" in trade_df.columns:
            trade_df["price"] = pd.to_numeric(
                trade_df["price"],
                errors="coerce",
            )
            st.line_chart(
                trade_df["price"].dropna(),
                height=280,
            )

        st.dataframe(
            trade_df,
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info(
            "No executions yet. Analytics will appear after "
            "compatible orders are matched."
        )

st.caption(
    "CHRONOSMATCH · Educational matching-engine simulator · "
    "Prices shown are local simulation data, not live exchange quotes."
)