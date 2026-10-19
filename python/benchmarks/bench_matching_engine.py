#!/usr/bin/env python3
"""
ChronosX — Python Benchmarks
Measures throughput for key operations using timeit.
Run: python benchmarks/bench_matching_engine.py
"""
import timeit
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chronosx.matching_engine import MatchingEngine
from chronosx.types import Side, OrderStatus
from chronosx.oms import OrderManagementSystem, OrderRequest
from chronosx.risk_engine import RiskEngine
from chronosx.types import OrderType

ITERATIONS = 50_000


def bench_limit_insert():
    """Single resting limit order, no match."""
    engine = MatchingEngine()
    def run():
        engine2 = MatchingEngine()
        for i in range(1, ITERATIONS + 1):
            engine2.submit_limit(i, Side.Buy, 100_000, 10)
    t = timeit.timeit(run, number=1)
    print(f"  BM_LimitOrderInsert        {ITERATIONS / t:>12,.0f} orders/sec  ({t*1000:.1f} ms)")


def bench_one_to_one_match():
    """1 sell vs 1 buy — exact fill."""
    def run():
        engine = MatchingEngine()
        for i in range(0, ITERATIONS * 2, 2):
            engine.submit_limit(i + 1, Side.Sell, 100_000, 100)
            engine.submit_limit(i + 2, Side.Buy,  100_000, 100)
    t = timeit.timeit(run, number=1)
    rate = (ITERATIONS * 2) / t
    print(f"  BM_LimitOrderMatchOneToOne {rate:>12,.0f} orders/sec  ({t*1000:.1f} ms)")


def bench_market_sweep_10_levels():
    """Market buy sweeping 10 ask levels."""
    def run():
        for _ in range(ITERATIONS // 10):
            engine = MatchingEngine()
            for j in range(10):
                engine.submit_limit(j + 1, Side.Sell, 100_000 + j * 100, 10)
            engine.submit_market(99, Side.Buy, 100)
    t = timeit.timeit(run, number=1)
    rate = ITERATIONS / t
    print(f"  BM_MarketOrderSweep10Lvls  {rate:>12,.0f} sweeps/sec  ({t*1000:.1f} ms)")


def bench_cancel():
    """O(1) cancel from a large book."""
    def run():
        engine = MatchingEngine()
        for i in range(1, ITERATIONS + 1):
            engine.submit_limit(i, Side.Buy, 100_000 - i, 10)
        for i in range(1, ITERATIONS + 1):
            engine.cancel_order(i)
    t = timeit.timeit(run, number=1)
    rate = ITERATIONS / (t / 2)
    print(f"  BM_CancelOrder             {rate:>12,.0f} cancels/sec ({t*1000:.1f} ms)")


def bench_oms_full_pipeline():
    """Full stack: validate → risk → match."""
    risk = RiskEngine()
    def run():
        oms = OrderManagementSystem(risk)
        for i in range(0, ITERATIONS * 2, 2):
            oms.submit(OrderRequest(i+1, Side.Sell, OrderType.Limit, 100_000, 10))
            oms.submit(OrderRequest(i+2, Side.Buy,  OrderType.Limit, 100_000, 10))
    t = timeit.timeit(run, number=1)
    rate = (ITERATIONS * 2) / t
    print(f"  BM_OmsFullPipeline         {rate:>12,.0f} orders/sec  ({t*1000:.1f} ms)")


if __name__ == "__main__":
    print("\n=== ChronosX Python Benchmarks ===")
    print(f"  Iterations per benchmark: {ITERATIONS:,}\n")
    bench_limit_insert()
    bench_one_to_one_match()
    bench_market_sweep_10_levels()
    bench_cancel()
    bench_oms_full_pipeline()
    print()
