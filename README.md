# ChronosX — Low-Latency HFT Matching Engine Simulator

> A simulation-mode, cache-optimised C++20 Limit Order Book and Matching Engine
> implementing Price-Time Priority (FIFO), a lock-free SPSC ring buffer, a
> pre-allocated object pool, and a pre-trade risk engine.

[![CI](https://github.com/YOUR_USERNAME/chronosx-hft-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/chronosx-hft-engine/actions)

---

## ✨ Features

| Feature                     | Details                                                   |
|-----------------------------|-----------------------------------------------------------|
| **Language / Standard**     | C++20, CMake 3.20+                                        |
| **Order types**             | Limit (GTC), Market (IOC residual)                        |
| **Price representation**    | `int64_t` fixed-point ticks (no floating point)           |
| **Order storage**           | Pre-allocated `ObjectPool<Order, N>` — zero heap on path  |
| **Order book**              | `std::map` + intrusive doubly-linked FIFO per price level |
| **Cancellation**            | O(1) via `order_price_index_` hash map                    |
| **Thread communication**    | Lock-free `SpscRingBuffer<T,N>` with acquire-release      |
| **Pre-trade risk**          | Max qty + max notional checks (overflow-safe `__int128`)  |
| **Unit tests**              | 50+ GoogleTest cases across 7 files                       |
| **Microbenchmarks**         | 6 Google Benchmark scenarios                              |
| **CI**                      | GitHub Actions: Ubuntu GCC-13 + Windows MSVC-2022         |

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────┐
│                   Simulator / main.cpp                 │
└───────────────────────┬────────────────────────────────┘
                        │
          ┌─────────────▼──────────────┐
          │  OrderManagementSystem     │  ← lifecycle + status tracking
          │  (OMS)                     │
          └──────┬──────────┬──────────┘
                 │          │
    ┌────────────▼─┐   ┌────▼──────────────┐
    │ RiskEngine   │   │  MatchingEngine   │  ← price-time priority
    │ qty / notional│   │                   │
    └──────────────┘   └────────┬──────────┘
                                │
                    ┌───────────▼───────────┐
                    │      OrderBook        │
                    │  Bids: map (desc)     │
                    │  Asks: map (asc)      │
                    │  Index: id → price    │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │   ObjectPool<Order>   │  ← pre-allocated, O(1)
                    └───────────────────────┘

    SpscRingBuffer<OrderRequest, N>   ← producer ↔ consumer thread
```

**Data flow for a new order:**
1. OMS validates parameters (qty > 0, price > 0 for limits, unique ID).
2. `RiskEngine::check_order()` evaluates qty and notional limits.
3. `MatchingEngine::submit_limit()` attempts to match against the opposite book.
4. Trades are emitted as `TradeEvent` structs; filled orders are returned to pool.
5. Unfilled residual is added to the book (limit) or cancelled (market).

---

## 📁 Project Structure

```
chronosx/
├── .github/workflows/ci.yml         # CI: Ubuntu GCC-13 + Windows MSVC
├── cmake/Dependencies.cmake         # FetchContent: GoogleTest + Benchmark
├── include/chronosx/
│   ├── types.hpp                    # Price, Quantity, enums, events
│   ├── order.hpp                    # Order struct (64 bytes, cache-line)
│   ├── memory_pool.hpp              # ObjectPool<T,N> — O(1) alloc/free
│   ├── spsc_ring_buffer.hpp         # Lock-free SPSC queue
│   ├── price_level.hpp              # PriceLevel — intrusive FIFO
│   ├── order_book.hpp               # Limit Order Book
│   ├── matching_engine.hpp          # Core matching loop
│   ├── risk_engine.hpp              # Pre-trade risk checks
│   ├── oms.hpp                      # Order Management System
│   └── simulator.hpp                # Simulation harness
├── src/
│   ├── order_book.cpp
│   ├── matching_engine.cpp
│   ├── risk_engine.cpp
│   ├── oms.cpp
│   ├── simulator.cpp
│   └── main.cpp                     # 5-scenario simulation demo
├── tests/
│   ├── test_types.cpp               # Type layout and sentinel tests
│   ├── test_object_pool.cpp         # Pool alloc/free/overflow
│   ├── test_spsc_buffer.cpp         # Single + multi-threaded SPSC
│   ├── test_order_book.cpp          # Book add/cancel/best price
│   ├── test_matching_engine.cpp     # Matching rules (20+ cases)
│   ├── test_oms.cpp                 # Full OMS lifecycle
│   └── test_risk_engine.cpp         # Qty/notional boundary tests
├── benchmarks/
│   └── bench_matching_engine.cpp    # 6 Google Benchmark scenarios
├── docs/
│   ├── DESIGN.md                    # Architecture & design rationale
│   └── REFERENCE_ANALYSIS.md       # Reference repo analysis
└── CMakeLists.txt
```

---

## 🔨 Building

### Prerequisites
- **Windows:** Visual Studio 2022 (Community or Build Tools) with C++ workload, CMake 3.20+
- **Linux / macOS:** GCC 13+ or Clang 16+, CMake 3.20+, `ninja` (optional)
- **Internet access** for first build (FetchContent downloads GoogleTest + Benchmark)

### Build & Test

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/chronosx-hft-engine.git
cd chronosx-hft-engine

# Configure (Release)
cmake -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBUILD_BENCHMARKS=ON

# Build
cmake --build build --config Release -j4

# Run tests
ctest --test-dir build --output-on-failure -C Release

# Run simulation demo
./build/Release/chronosx_sim.exe   # Windows
./build/chronosx_sim               # Linux
```

### Debug build (with AddressSanitizer on Linux/macOS)
```bash
cmake -B build_dbg -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON
cmake --build build_dbg -j4
ctest --test-dir build_dbg --output-on-failure
```

---

## 📊 Benchmark Results (indicative — run on your machine)

```bash
./build/Release/chronosx_bench
```

| Benchmark                    | Description                          |
|------------------------------|--------------------------------------|
| `BM_LimitOrderInsert`        | Single resting order, no match       |
| `BM_LimitOrderMatchOneToOne` | 1 sell vs 1 buy, exact fill          |
| `BM_MarketOrderSweep10Levels`| Market buy sweeping 10 ask levels    |
| `BM_CancelOrder`             | Cancel from 1000-order book          |
| `BM_ThroughputMixed`         | Alternating buy/sell stream          |
| `BM_OmsFullPipeline`         | Full OMS path (validate+risk+match)  |

> **Target:** > 1 million orders/sec on a modern desktop CPU at Release optimisation.

---

## 🧪 Sample Simulation Output

```
╔══════════════════════════════════════════════╗
║  ChronosX — HFT Matching Engine Simulator   ║
╚══════════════════════════════════════════════╝

── Scenario 1: Limit orders and matching ──
  Order 1 → New
  Order 2 → New
  Order 3 → New
  Order 4 → PartiallyFilled
   TRADE  agg=4 rest=1 price=100.0000 qty=50
   TRADE  agg=4 rest=2 price=100.0000 qty=30
   TRADE  agg=4 rest=3 price=100.0500 qty=10

── Scenario 2: Market order IOC sweep ──
  Order 5 → PartiallyFilled
   TRADE  agg=5 rest=3 price=100.0500 qty=10
   CANCEL order=5 residual=190

── Scenario 3: Cancellation ──
  Order 10 → New
  Order 10 → Cancelled
   CANCEL order=10 residual=0

── Scenario 4: Risk rejection ──
  Order 20 → Rejected

── Scenario 5: SPSC Ring Buffer Throughput ──
  Orders processed : 100000
  Throughput       : 2500000 orders/sec
```

---

## 🎯 Design Decisions & Trade-offs

| Decision                          | Rationale                                                   |
|-----------------------------------|-------------------------------------------------------------|
| `int64_t` prices (fixed-point)    | Eliminates IEEE 754 rounding; exact equality comparisons    |
| `ObjectPool` over `std::list`     | Zero malloc/free after startup; contiguous = cache-friendly |
| Pool indices vs raw pointers      | Stable under pool relocation; fits in 4 bytes               |
| `std::map` for price levels       | O(log N_prices) with O(1) top-of-book; correct for general instruments |
| Intrusive doubly-linked list      | O(1) FIFO cancel; no wrapper node allocation                |
| SPSC over mutex queue             | No kernel transitions; acquire-release with no locks        |
| OMS as a separate layer           | Decouples validation/tracking from the matching core        |
| Market order = IOC                | Simplest correct definition; documented explicitly          |

---

## 📖 Documentation

- [`docs/DESIGN.md`](docs/DESIGN.md) — Deep-dive on data structures, memory layout, SPSC ordering, and matching pseudocode
- [`docs/REFERENCE_ANALYSIS.md`](docs/REFERENCE_ANALYSIS.md) — Reference repository analysis and improvement rationale

---

## ⚖️ Attribution

ChronosX is independently designed and implemented. It was inspired by the
architectural concept of time-priority matching engines, including the naming
convention of the `chronosmatch-hft-engine` reference (which was inaccessible
at the time of development — HTTP 404).

Architectural patterns referenced from:
- Liquibook (IRESS)
- hyper-core-engine (Darkangex)
- Published HFT engineering discussions on Hacker News and r/algotrading

---

## 📄 License

MIT License. See `LICENSE` for details.
