# ChronosX — Design Document

## Overview

ChronosX is a simulation-mode, low-latency HFT Matching Engine written in C++20.
It targets correctness, cache efficiency, and zero heap allocation on the matching
path, while remaining comprehensible enough to be a portfolio showcase.

---

## 1. Fixed-Point Price Representation

### Rationale
`double` has only 15–17 significant decimal digits. Two prices that are logically
equal (e.g., computed via different floating-point paths) can compare unequal,
silently corrupting order book ordering.

### Implementation
```
using Price = int64_t;
// 1 tick = $0.0001 (4 decimal places)
// $12.3456 == 123456 ticks
// kPriceMult == 10000
```

All prices in ChronosX are tick-integer values. Display conversion divides by
`kPriceMult` only for human-readable output — never on the matching path.

**Overflow bound:** `int64_t` can represent prices up to ~$922 trillion at
4-decimal precision — well beyond any real instrument.

---

## 2. Order Struct — 64-byte Cache Line Alignment

### Rationale
Modern CPUs load memory in cache lines of 64 bytes. If an `Order` spans two
cache lines, accessing a single field can trigger two cache-line fetches.
Packing `Order` exactly into 64 bytes ensures each order node occupies one
cache line, maximising L1/L2 hit rate when sweeping a price level.

### Layout
```
Offset  0:  order_id       (8 bytes)   uint64_t
Offset  8:  price          (8 bytes)   int64_t
Offset 16:  initial_qty    (8 bytes)   uint64_t
Offset 24:  remaining_qty  (8 bytes)   uint64_t
Offset 32:  seq_num        (8 bytes)   uint64_t
Offset 40:  prev_idx       (4 bytes)   uint32_t  ← pool index, not pointer
Offset 44:  next_idx       (4 bytes)   uint32_t  ← pool index, not pointer
Offset 48:  type           (1 byte)    OrderType
Offset 49:  side           (1 byte)    Side
Offset 50:  status         (1 byte)    OrderStatus
Offset 51:  _pad           (13 bytes)  explicit padding
Total:       64 bytes
```

`static_assert(sizeof(Order) == 64)` and `static_assert(alignof(Order) == 64)`
are compile-time guards.

---

## 3. ObjectPool — Zero Heap Allocation

### Rationale
`malloc`/`new` on the hot matching path causes unpredictable latency:
- OS memory allocator lock contention under concurrent workloads
- TLB invalidations when pages are returned to the OS
- Cache eviction due to fragmented heap layout

### Implementation
```cpp
template<typename T, std::size_t Capacity>
class ObjectPool {
    std::array<T, Capacity>        storage_;   // Contiguous block
    std::array<uint32_t, Capacity> free_next_; // Intrusive free-list
    uint32_t                        free_head_;
};
```

- **Allocation:** Pop from free-list head → O(1), zero system calls.
- **Deallocation:** Push to free-list head → O(1).
- **Index vs pointer:** `uint32_t` pool indices are stable even if the array
  is embedded in another struct. Raw pointers would become invalid if the pool
  were ever moved.

---

## 4. Limit Order Book — Data Structure Choice

### Bid side: `std::map<Price, PriceLevel, std::greater<Price>>`
### Ask side: `std::map<Price, PriceLevel, std::less<Price>>`

#### Why std::map?
- `begin()` always returns the best price (O(1) top-of-book access).
- Insert and erase are O(log N_prices), where N_prices is the number of
  distinct active price levels — typically tens to hundreds, not millions.
- Nodes are only allocated at construction time of each new price level
  (not per order), so heap allocation frequency is proportional to the
  number of *price* ticks, not orders.

#### Why not a flat array?
Flat-array indexing (O(1) per price level) requires a fixed, known price range.
For a general-purpose simulator covering arbitrary instruments, `std::map` is
more correct. The flat-array optimisation can be added as a template policy
if performance profiling shows it is needed.

### Price Level — Intrusive Doubly-Linked FIFO Queue

```cpp
struct PriceLevel {
    Price    price;
    uint32_t head_idx;   // Pool index of FIFO front (oldest order)
    uint32_t tail_idx;   // Pool index of FIFO back  (newest order)
    Quantity total_qty;  // Cached sum (O(1) depth queries)
};
```

Orders within a level are linked via `Order::prev_idx` / `Order::next_idx`.
This is an **intrusive** list: the link fields are embedded in the `Order`
struct rather than in a wrapper node. This eliminates the wrapper allocation
and keeps all data needed for matching in the same 64-byte slot.

---

## 5. O(1) Cancellation

### Mechanism
```
order_price_index_: unordered_map<OrderId, Price>
```

When a cancel request arrives for `OrderId X`:
1. Look up `price = order_price_index_[X]` → O(1) average.
2. Find the correct map (bid or ask) and price level → O(log N_prices).
3. Walk the level's intrusive list to find the node with `order_id == X`.
4. `level.remove_order(idx, pool)` → O(1) doubly-linked removal.
5. `pool.free(ptr)` → O(1).

The walk in step 3 is O(k) where k is the number of orders at that price.
In a live market, k is typically small (< 10). A future optimisation would
add a second index `order_pool_index_: unordered_map<OrderId, uint32_t>` to
make step 3 O(1) at the cost of extra memory.

---

## 6. SPSC Ring Buffer — Memory Ordering Analysis

```cpp
alignas(64) std::atomic<size_t> tail_{0};   // Producer-owned cache line
alignas(64) std::atomic<size_t> head_{0};   // Consumer-owned cache line
T buffer_[Capacity];
```

### push() (producer thread)
```
load head_  with acquire   ← syncs with consumer's release store to head_
write buffer_[tail & mask]  ← plain store (producer owns this slot)
store tail_ with release    ← makes element visible before tail update
```

### pop() (consumer thread)
```
load tail_  with acquire   ← syncs with producer's release store to tail_
read  buffer_[head & mask]  ← plain load (consumer now owns this slot)
store head_ with release    ← makes freed slot visible before head update
```

### Why `alignas(64)`?
Without it, `head_` and `tail_` may share a cache line. A write by the producer
to `tail_` would invalidate the consumer's cache line containing `head_`, and
vice versa — even though neither thread is accessing the other's variable.
This **false sharing** can cause 10–30× latency spikes. Separate cache lines
eliminate it.

### Capacity must be power-of-two
Modular indexing via `& (Capacity - 1)` is a single instruction. `% Capacity`
(for non-power-of-two) is a division, which is 20–80 cycles on modern CPUs.

---

## 7. Pre-Trade Risk Engine

Checks (in order):
1. `qty > max_order_qty` → `RejectedQty`
2. `price × qty > max_order_notional` → `RejectedNotional`

### Overflow-Safe Notional
```cpp
// GCC/Clang:
__int128 product = (__int128)price * (__int128)qty;
if (product > INT64_MAX) → overflow

// MSVC:
if (qty > 0 && price > INT64_MAX / qty) → overflow
```

At 4 decimal places, a $1,000,000.00 price is `10,000,000,000` ticks.
With qty=1,000 that's `10^13`, well within `int64_t` range (~9.2×10^18).
The overflow check is still important for robustly rejecting malformed orders.

---

## 8. Matching Rules — Precise Specification

### Limit Order Matching
```
while aggressor.remaining_qty > 0:
    level = best_opposite_level()
    if level is None: break
    if aggressor is Buy  and aggressor.price < level.price: break
    if aggressor is Sell and aggressor.price > level.price: break
    
    resting = level.head   # FIFO: oldest first
    fill_qty = min(aggressor.remaining_qty, resting.remaining_qty)
    fill_price = resting.price  # Maker price (resting order's price)
    
    emit TradeEvent(aggressor.id, resting.id, fill_price, fill_qty)
    aggressor.remaining_qty -= fill_qty
    resting.remaining_qty   -= fill_qty
    
    if resting is fully filled:
        remove resting from level and pool
    else:
        resting.status = PartiallyFilled
    
    prune empty levels

if aggressor.remaining_qty > 0:
    add aggressor to book (rests)
    aggressor.status = New or PartiallyFilled
else:
    aggressor.status = Filled
    free aggressor from pool
```

### Market Order (IOC)
Same loop, but the price constraint check is skipped. If residual > 0 after
exhausting the book, emit `CancelEvent` and free the order. Never rests.

### Book Invariant after every operation
- `best_bid() < best_ask()` (no crossed book)
- Every price level has `total_qty > 0` and `head_idx != kNullIdx`
- `order_price_index_.size() == active_order_count_in_book`

---

## 9. Module Dependency Graph

```
types.hpp
   └── order.hpp
         └── memory_pool.hpp
               └── price_level.hpp
                     └── order_book.hpp
                           └── matching_engine.hpp
                                 ├── risk_engine.hpp
                                 └── oms.hpp
                                       └── simulator.hpp

spsc_ring_buffer.hpp (independent, used by simulator.hpp)
```
