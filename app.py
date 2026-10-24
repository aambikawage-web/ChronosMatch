
from __future__ import annotations

import random
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="ChronosMatch | Trading Simulator",
    page_icon="📈",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "chronosmatch_simulation.db"

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #080d1a, #11172a);
    color: #f5f7ff;
}
[data-testid="stSidebar"] {
    background: #0e1425;
}
[data-testid="stMetric"] {
    background: #171f34;
    border: 1px solid #303b58;
    border-radius: 12px;
    padding: 15px;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    return sqlite3.connect(DB_PATH, timeout=15)


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sim_orders (
                order_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                remaining_quantity INTEGER,
                status TEXT NOT NULL,
                latency_ms REAL DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sim_trades (
                trade_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                buy_order_id TEXT,
                sell_order_id TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sim_price_ticks (
                tick_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price REAL NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS risk_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                reason TEXT NOT NULL
            )
        """)

        # Migrate older sim_orders tables safely.
        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(sim_orders)"
            ).fetchall()
        }

        if "remaining_quantity" not in columns:
            conn.execute(
                "ALTER TABLE sim_orders "
                "ADD COLUMN remaining_quantity INTEGER"
            )
            if "quantity" in columns:
                conn.execute("""
                    UPDATE sim_orders
                    SET remaining_quantity = quantity
                    WHERE remaining_quantity IS NULL
                """)

        if "latency_ms" not in columns:
            conn.execute(
                "ALTER TABLE sim_orders "
                "ADD COLUMN latency_ms REAL DEFAULT 0"
            )

        # Ensure partially filled legacy rows have a quantity.
        conn.execute("""
            UPDATE sim_orders
            SET remaining_quantity = quantity
            WHERE remaining_quantity IS NULL
              AND status IN ('OPEN', 'PENDING')
        """)


init_db()


def read_table(table_name):
    allowed = {
        "sim_orders",
        "sim_trades",
        "sim_price_ticks",
        "risk_events",
    }
    if table_name not in allowed:
        raise ValueError("Invalid table")

    with get_connection() as conn:
        return pd.read_sql_query(
            f"SELECT * FROM {table_name}", conn
        )


def record_risk_event(symbol, side, price, quantity, reason):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO risk_events
            (event_id, timestamp, symbol, side, price, quantity, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            uuid.uuid4().hex,
            datetime.now().isoformat(timespec="seconds"),
            str(symbol or "UNKNOWN").upper(),
            str(side or "UNKNOWN").upper(),
            float(price or 0),
            int(quantity or 0),
            str(reason),
        ))


# ============================================================
# ORDER VALIDATION
# ============================================================

def validate_order(symbol, side, price, quantity):
    symbol = str(symbol).strip().upper()
    side = str(side).strip().upper()
    price = float(price)
    quantity = int(quantity)

    if not symbol:
        raise ValueError("Symbol cannot be empty.")
    if side not in ("BUY", "SELL"):
        raise ValueError("Side must be BUY or SELL.")
    if price <= 0:
        raise ValueError("Price must be greater than zero.")
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    max_qty = int(
        st.session_state.get("max_order_quantity", 1000)
    )
    max_notional = float(
        st.session_state.get("max_order_notional", 100000)
    )

    if quantity > max_qty:
        raise ValueError(
            f"Quantity {quantity} exceeds limit {max_qty}."
        )

    if price * quantity > max_notional:
        raise ValueError(
            f"Order notional {price * quantity:.2f} "
            f"exceeds limit {max_notional:.2f}."
        )

    return symbol, side, price, quantity


# ============================================================
# ORDER MATCHING ENGINE
# ============================================================

def submit_order(symbol, side, price, quantity):
    started = time.perf_counter()

    symbol, side, price, quantity = validate_order(
        symbol, side, price, quantity
    )

    order_id = uuid.uuid4().hex
    remaining = quantity

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO sim_orders
            (order_id, timestamp, symbol, side, price, quantity,
             remaining_quantity, status, latency_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_id,
            datetime.now().isoformat(timespec="milliseconds"),
            symbol,
            side,
            price,
            quantity,
            quantity,
            "OPEN",
            0.0,
        ))

        if side == "BUY":
            opposite_side = "SELL"
            condition = "price <= ?"
            ordering = "price ASC, timestamp ASC"
        else:
            opposite_side = "BUY"
            condition = "price >= ?"
            ordering = "price DESC, timestamp ASC"

        while remaining > 0:
            candidate = conn.execute(f"""
                SELECT order_id, price, remaining_quantity, quantity
                FROM sim_orders
                WHERE symbol = ?
                  AND side = ?
                  AND status IN ('OPEN', 'PARTIAL', 'PENDING')
                  AND COALESCE(remaining_quantity, quantity) > 0
                  AND {condition}
                  AND order_id != ?
                ORDER BY {ordering}
                LIMIT 1
            """, (
                symbol,
                opposite_side,
                price,
                order_id,
            )).fetchone()

            if candidate is None:
                break

            opposite_id, opposite_price, opposite_remaining, opposite_qty = candidate

            if opposite_remaining is None:
                opposite_remaining = opposite_qty

            traded_qty = min(remaining, int(opposite_remaining))
            execution_price = float(opposite_price)

            buy_id = order_id if side == "BUY" else opposite_id
            sell_id = opposite_id if side == "BUY" else order_id

            conn.execute("""
                INSERT INTO sim_trades
                (trade_id, timestamp, symbol, price, quantity,
                 buy_order_id, sell_order_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                uuid.uuid4().hex,
                datetime.now().isoformat(timespec="milliseconds"),
                symbol,
                execution_price,
                traded_qty,
                buy_id,
                sell_id,
            ))

            remaining -= traded_qty
            opposite_remaining = int(opposite_remaining) - traded_qty

            opposite_status = (
                "FILLED" if opposite_remaining == 0 else "PARTIAL"
            )

            conn.execute("""
                UPDATE sim_orders
                SET remaining_quantity = ?, status = ?
                WHERE order_id = ?
            """, (
                opposite_remaining,
                opposite_status,
                opposite_id,
            ))

        if remaining == 0:
            status = "FILLED"
        elif remaining < quantity:
            status = "PARTIAL"
        else:
            status = "OPEN"

        latency_ms = (time.perf_counter() - started) * 1000

        conn.execute("""
            UPDATE sim_orders
            SET remaining_quantity = ?, status = ?, latency_ms = ?
            WHERE order_id = ?
        """, (
            remaining,
            status,
            latency_ms,
            order_id,
        ))

    return {
        "order_id": order_id,
        "status": status,
        "remaining": remaining,
        "latency_ms": latency_ms,
    }


# ============================================================
# OPEN ORDERS — LEGACY SCHEMA COMPATIBILITY
# ============================================================

def get_open_orders():
    orders = read_table("sim_orders")

    if orders.empty:
        return orders

    if "remaining_quantity" not in orders.columns:
        if "quantity" not in orders.columns:
            return orders.iloc[0:0].copy()
        orders["remaining_quantity"] = orders["quantity"]

    if "status" not in orders.columns:
        return orders.iloc[0:0].copy()

    orders["status"] = orders["status"].astype(str).str.upper()
    orders["remaining_quantity"] = pd.to_numeric(
        orders["remaining_quantity"], errors="coerce"
    ).fillna(0)

    return orders[
        orders["status"].isin(["OPEN", "PARTIAL", "PENDING"])
        & (orders["remaining_quantity"] > 0)
    ].copy()


def get_open_exposure():
    orders = get_open_orders()

    if orders.empty:
        return 0.0

    return float(
        (orders["price"] * orders["remaining_quantity"]).sum()
    )


# ============================================================
# MARKET SIMULATOR
# ============================================================

def generate_market_order(symbol):
    side = random.choice(["BUY", "SELL"])
    price = round(random.uniform(95, 105), 2)
    quantity = random.randint(1, 100)

    try:
        return submit_order(symbol, side, price, quantity)
    except (ValueError, sqlite3.Error) as exc:
        record_risk_event(
            symbol, side, price, quantity, str(exc)
        )
        return {"error": str(exc)}


# ============================================================
# SIDEBAR
# ============================================================

st.title("📈 ChronosMatch")
st.caption(
    "High-frequency trading engine simulator | "
    "Educational use only — no live trading"
)

with st.sidebar:
    st.header("Configuration")

    selected_symbol = st.text_input(
        "Trading symbol", value="AAPL"
    ).strip().upper() or "AAPL"

    st.divider()
    st.subheader("Risk limits")

    st.number_input(
        "Maximum order quantity",
        min_value=1,
        max_value=1_000_000,
        value=1000,
        key="max_order_quantity",
    )

    st.number_input(
        "Maximum order notional",
        min_value=100.0,
        max_value=100_000_000.0,
        value=100000.0,
        step=1000.0,
        key="max_order_notional",
    )

    st.divider()
    st.subheader("Market simulator")

    simulation_count = st.slider(
        "Orders per run", 1, 25, 5
    )

    if st.button("Run market simulation", use_container_width=True):
        results = [
            generate_market_order(selected_symbol)
            for _ in range(simulation_count)
        ]
        successful = sum("error" not in item for item in results)
        st.success(f"{successful} orders submitted successfully.")
        st.rerun()


# ============================================================
# LOAD DATA
# ============================================================

orders = read_table("sim_orders")
trades = read_table("sim_trades")
ticks = read_table("sim_price_ticks")
risk_events = read_table("risk_events")

for frame in (orders, trades, ticks):
    if not frame.empty and "timestamp" in frame.columns:
        frame["timestamp"] = pd.to_datetime(
            frame["timestamp"], errors="coerce"
        )

symbol_orders = (
    orders[orders["symbol"] == selected_symbol].copy()
    if not orders.empty else orders.copy()
)

symbol_trades = (
    trades[trades["symbol"] == selected_symbol].copy()
    if not trades.empty else trades.copy()
)

open_orders = get_open_orders()

symbol_open_orders = (
    open_orders[open_orders["symbol"] == selected_symbol].copy()
    if not open_orders.empty else open_orders.copy()
)


# ============================================================
# DASHBOARD METRICS
# ============================================================

total_trades = len(symbol_trades)

total_volume = (
    int(symbol_trades["quantity"].sum())
    if not symbol_trades.empty else 0
)

average_price = 0.0
if total_volume and not symbol_trades.empty:
    average_price = float(
        (symbol_trades["price"] * symbol_trades["quantity"]).sum()
        / total_volume
    )

avg_latency = (
    float(pd.to_numeric(
        symbol_orders["latency_ms"], errors="coerce"
    ).fillna(0).mean())
    if not symbol_orders.empty and "latency_ms" in symbol_orders.columns
    else 0.0
)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Executions", f"{total_trades:,}")
m2.metric("Traded quantity", f"{total_volume:,}")
m3.metric("Average execution", f"${average_price:.2f}")
m4.metric("Open orders", f"{len(symbol_open_orders):,}")
m5.metric("Average latency", f"{avg_latency:.3f} ms")


# ============================================================
# TABS
# ============================================================

tab_overview, tab_submit, tab_book, tab_history, tab_analytics, tab_risk, tab_benchmark = st.tabs([
    "Market Overview",
    "Submit Orders",
    "Live Order Book",
    "Trade History & Filters",
    "Trading Analytics",
    "Risk Monitor",
    "Performance Benchmark",
])


# ============================================================
# MARKET OVERVIEW
# ============================================================

with tab_overview:
    st.subheader(f"Market overview — {selected_symbol}")

    left, right = st.columns(2)

    with left:
        st.markdown("### Recent trades")

        if symbol_trades.empty:
            st.info("No executions yet.")
        else:
            st.dataframe(
                symbol_trades.sort_values(
                    "timestamp", ascending=False
                ).head(10),
                use_container_width=True,
                hide_index=True,
            )

    with right:
        st.markdown("### Simulated price history")

        symbol_ticks = (
            ticks[ticks["symbol"] == selected_symbol]
            if not ticks.empty else ticks
        )

        if symbol_ticks.empty:
            st.info("No price ticks recorded.")
        else:
            st.plotly_chart(
                px.line(
                    symbol_ticks.sort_values("timestamp").tail(200),
                    x="timestamp",
                    y="price",
                ),
                use_container_width=True,
            )


# ============================================================
# SUBMIT ORDERS
# ============================================================

with tab_submit:
    st.subheader("Submit a simulated limit order")

    st.warning(
        "Simulation only. No real orders are transmitted."
    )

    with st.form("submit_order_form"):
        col1, col2 = st.columns(2)

        with col1:
            order_symbol = st.text_input(
                "Symbol", value=selected_symbol
            )
            order_side = st.selectbox("Side", ["BUY", "SELL"])

        with col2:
            order_price = st.number_input(
                "Limit price", min_value=0.01, value=100.0, step=0.01
            )
            order_quantity = st.number_input(
                "Quantity", min_value=1, value=10, step=1
            )

        submitted = st.form_submit_button(
            "Submit order", use_container_width=True
        )

    if submitted:
        try:
            result = submit_order(
                order_symbol,
                order_side,
                order_price,
                order_quantity,
            )
            st.success(
                f"Order submitted. Status: {result['status']}; "
                f"remaining: {result['remaining']}."
            )
            st.caption(
                f"Processing latency: {result['latency_ms']:.3f} ms"
            )
            st.rerun()

        except (ValueError, sqlite3.Error) as exc:
            record_risk_event(
                order_symbol,
                order_side,
                order_price,
                order_quantity,
                str(exc),
            )
            st.error(f"Order rejected: {exc}")


# ============================================================
# LIVE ORDER BOOK
# ============================================================

with tab_book:
    st.subheader(f"Open order book — {selected_symbol}")

    buys = symbol_open_orders[
        symbol_open_orders["side"].astype(str).str.upper() == "BUY"
    ].sort_values("price", ascending=False) if not symbol_open_orders.empty else symbol_open_orders

    sells = symbol_open_orders[
        symbol_open_orders["side"].astype(str).str.upper() == "SELL"
    ].sort_values("price", ascending=True) if not symbol_open_orders.empty else symbol_open_orders

    left, right = st.columns(2)

    with left:
        st.markdown("### Buy orders")
        st.dataframe(
            buys,
            use_container_width=True,
            hide_index=True,
        )

    with right:
        st.markdown("### Sell orders")
        st.dataframe(
            sells,
            use_container_width=True,
            hide_index=True,
        )

    best_bid = float(buys["price"].max()) if not buys.empty else None
    best_ask = float(sells["price"].min()) if not sells.empty else None

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Best bid", f"${best_bid:.2f}" if best_bid is not None else "—"
    )
    c2.metric(
        "Best ask", f"${best_ask:.2f}" if best_ask is not None else "—"
    )
    c3.metric(
        "Spread",
        f"${best_ask - best_bid:.2f}"
        if best_ask is not None and best_bid is not None else "—",
    )


# ============================================================
# TRADE HISTORY AND FILTERS
# ============================================================

with tab_history:
    st.subheader("Trade history and filters")

    if trades.empty:
        st.info("No trades are available yet.")
    else:
        filtered = trades.copy()

        symbols = sorted(
            filtered["symbol"].dropna().unique().tolist()
        )

        selected_symbols = st.multiselect(
            "Symbols",
            options=symbols,
            default=[selected_symbol]
            if selected_symbol in symbols else symbols,
        )

        filtered = filtered[
            filtered["symbol"].isin(selected_symbols)
        ]

        if not filtered.empty:
            valid_timestamps = filtered["timestamp"].dropna()

            if not valid_timestamps.empty:
                start = valid_timestamps.min().date()
                end = valid_timestamps.max().date()

                date_range = st.date_input(
                    "Date range", value=(start, end)
                )

                if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
                    start_date, end_date = date_range
                    filtered = filtered[
                        filtered["timestamp"].dt.date.between(
                            start_date, end_date
                        )
                    ]

        if not filtered.empty:
            min_price = float(filtered["price"].min())
            max_price = float(filtered["price"].max())

            if min_price == max_price:
                max_price = min_price + 0.01

            price_range = st.slider(
                "Price range",
                min_value=min_price,
                max_value=max_price,
                value=(min_price, max_price),
            )

            filtered = filtered[
                filtered["price"].between(*price_range)
            ]

        if not filtered.empty:
            min_qty = int(filtered["quantity"].min())
            max_qty = int(filtered["quantity"].max())

            if min_qty == max_qty:
                max_qty = min_qty + 1

            qty_range = st.slider(
                "Quantity range",
                min_value=min_qty,
                max_value=max_qty,
                value=(min_qty, max_qty),
            )

            filtered = filtered[
                filtered["quantity"].between(*qty_range)
            ]

        st.metric("Matching executions", len(filtered))
        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Download filtered trades CSV",
            data=filtered.to_csv(index=False).encode("utf-8"),
            file_name="chronosmatch_trades.csv",
            mime="text/csv",
        )


# ============================================================
# TRADING ANALYTICS
# ============================================================

with tab_analytics:
    st.subheader("Trading analytics")

    analytics = trades[
        trades["symbol"] == selected_symbol
    ].copy() if not trades.empty else trades.copy()

    if analytics.empty:
        st.info("No executions to analyze yet.")
    else:
        analytics["notional"] = (
            analytics["price"] * analytics["quantity"]
        )

        qty = int(analytics["quantity"].sum())
        notional = float(analytics["notional"].sum())
        vwap = notional / qty if qty else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Executions", len(analytics))
        c2.metric("Quantity", f"{qty:,}")
        c3.metric("Notional", f"${notional:,.2f}")
        c4.metric("VWAP", f"${vwap:.4f}")

        left, right = st.columns(2)

        with left:
            volume_by_symbol = trades.groupby(
                "symbol", as_index=False
            )["quantity"].sum()

            st.plotly_chart(
                px.bar(
                    volume_by_symbol,
                    x="symbol",
                    y="quantity",
                    title="Volume by symbol",
                ),
                use_container_width=True,
            )

        with right:
            analytics["trade_date"] = analytics["timestamp"].dt.date
            daily = analytics.groupby(
                "trade_date", as_index=False
            )["quantity"].sum()

            st.plotly_chart(
                px.line(
                    daily,
                    x="trade_date",
                    y="quantity",
                    markers=True,
                    title="Daily traded quantity",
                ),
                use_container_width=True,
            )

        st.markdown("### Buy and sell participation")

        st.caption(
            "Each execution has both a buyer and a seller. "
            "The trade table stores executions, not separate "
            "buyer-side and seller-side records."
        )

        st.dataframe(pd.DataFrame([
            {
                "Side": "BUY",
                "Executions": len(analytics),
                "Quantity": qty,
                "Notional": notional,
            },
            {
                "Side": "SELL",
                "Executions": len(analytics),
                "Quantity": qty,
                "Notional": notional,
            },
        ]), use_container_width=True, hide_index=True)

        if not symbol_orders.empty and "latency_ms" in symbol_orders.columns:
            st.plotly_chart(
                px.histogram(
                    symbol_orders,
                    x="latency_ms",
                    title="Order-processing latency",
                ),
                use_container_width=True,
            )


# ============================================================
# RISK MONITOR
# ============================================================

with tab_risk:
    st.subheader("Risk monitoring")

    current_open = get_open_orders()
    exposure = get_open_exposure()

    r1, r2, r3 = st.columns(3)
    r1.metric("Risk events", len(risk_events))
    r2.metric("Open orders", len(current_open))
    r3.metric("Open-order notional", f"${exposure:,.2f}")

    max_notional = float(
        st.session_state.get("max_order_notional", 100000)
    )

    if exposure > max_notional:
        st.warning(
            "Open-order notional exceeds the configured limit. "
            "Existing orders are not automatically cancelled."
        )

    max_qty = int(
        st.session_state.get("max_order_quantity", 1000)
    )

    if (
        not current_open.empty
        and (current_open["remaining_quantity"] > max_qty).any()
    ):
        st.warning(
            "One or more existing orders exceed the current "
            "quantity limit."
        )

    st.markdown("### Rejection history")

    if risk_events.empty:
        st.info("No rejected orders recorded.")
    else:
        st.dataframe(
            risk_events.sort_values(
                "timestamp", ascending=False
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Export risk events CSV",
            data=risk_events.to_csv(index=False).encode("utf-8"),
            file_name="chronosmatch_risk_events.csv",
            mime="text/csv",
        )


# ============================================================
# PERFORMANCE BENCHMARK
# ============================================================

with tab_benchmark:
    st.subheader("Performance benchmark")

    st.warning(
        "Benchmark orders use a separate temporary database. "
        "This is a local simulation, not an exchange benchmark."
    )

    count = st.selectbox(
        "Number of orders",
        [25, 50, 100, 250, 500],
        index=2,
    )

    if "benchmark_results" not in st.session_state:
        st.session_state.benchmark_results = []

    if st.button("Run benchmark", type="primary"):
        import tempfile

        original_path = DB_PATH
        latencies = []
        wall_start = time.perf_counter()
        temp_path = None

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                DB_PATH = Path(temp_dir) / "benchmark.db"
                init_db()

                for i in range(count):
                    side = "BUY" if i % 2 == 0 else "SELL"
                    price = 100.0 if side == "BUY" else 101.0

                    start = time.perf_counter()

                    submit_order(
                        "BENCH",
                        side,
                        price,
                        random.randint(1, 100),
                    )

                    latencies.append(
                        (time.perf_counter() - start) * 1000
                    )

        except Exception as exc:
            st.error(f"Benchmark failed: {exc}")

        finally:
            DB_PATH = original_path

        wall_time = time.perf_counter() - wall_start

        if latencies:
            sorted_latencies = sorted(latencies)
            mean_latency = sum(latencies) / len(latencies)
            p95_index = min(
                len(sorted_latencies) - 1,
                int(0.95 * len(sorted_latencies)),
            )
            p95_latency = sorted_latencies[p95_index]
            throughput = len(latencies) / wall_time if wall_time else 0

            result = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "orders": len(latencies),
                "mean_latency_ms": mean_latency,
                "p95_latency_ms": p95_latency,
                "wall_time_seconds": wall_time,
                "throughput_orders_per_second": throughput,
            }

            st.session_state.benchmark_results.append(result)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Orders", len(latencies))
            c2.metric("Mean latency", f"{mean_latency:.3f} ms")
            c3.metric("P95 latency", f"{p95_latency:.3f} ms")
            c4.metric("Throughput", f"{throughput:.1f} orders/sec")

            st.caption(f"Total wall time: {wall_time:.4f} seconds")

            st.plotly_chart(
                px.line(
                    x=list(range(1, len(latencies) + 1)),
                    y=latencies,
                    labels={
                        "x": "Order number",
                        "y": "Latency (ms)",
                    },
                    title="Per-order latency",
                ),
                use_container_width=True,
            )

    st.markdown("### Benchmark history")

    benchmark_df = pd.DataFrame(
        st.session_state.benchmark_results
    )

    if benchmark_df.empty:
        st.info("Run a benchmark to see results.")
    else:
        st.dataframe(
            benchmark_df,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Download benchmark CSV",
            data=benchmark_df.to_csv(index=False).encode("utf-8"),
            file_name="chronosmatch_benchmark.csv",
            mime="text/csv",
        )

        if len(benchmark_df) >= 2:
            st.plotly_chart(
                px.bar(
                    benchmark_df.reset_index(),
                    x="index",
                    y="throughput_orders_per_second",
                    labels={
                        "index": "Run",
                        "throughput_orders_per_second":
                            "Orders per second",
                    },
                    title="Throughput comparison",
                ),
                use_container_width=True,
            )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "ChronosMatch | Local order-matching simulation | "
    "No live trading or broker connection."
)
