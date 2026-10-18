/**
 * @file order.hpp
 * @brief Order struct — the fundamental unit of the matching engine.
 *
 * Layout is carefully designed to fit within a 64-byte cache line.
 * No virtual functions, no std::string, no heap pointers.
 *
 * Intrusive linked-list links (prev_idx / next_idx) use pool indices
 * rather than raw pointers so the pool can be freely relocated in memory
 * without invalidating any links.
 *
 * Sentinel value for prev_idx / next_idx: kNullIdx (UINT32_MAX).
 */

#pragma once

#include "types.hpp"
#include <cstdint>

namespace chronosx {

/// Sentinel pool-index meaning "no node" (analogous to nullptr).
inline constexpr uint32_t kNullIdx = UINT32_MAX;

/**
 * @brief A single order node, 64 bytes exactly.
 *
 * Memory layout (little-endian, no implicit padding assumed):
 *   Offset  0 :  order_id       (8 bytes)
 *   Offset  8 :  price          (8 bytes)
 *   Offset 16 :  initial_qty    (8 bytes)
 *   Offset 24 :  remaining_qty  (8 bytes)
 *   Offset 32 :  seq_num        (8 bytes)
 *   Offset 40 :  prev_idx       (4 bytes)
 *   Offset 44 :  next_idx       (4 bytes)
 *   Offset 48 :  type           (1 byte)
 *   Offset 49 :  side           (1 byte)
 *   Offset 50 :  status         (1 byte)
 *   Offset 51 :  _pad           (13 bytes)  → total = 64 bytes
 */
struct alignas(64) Order {
    OrderId     order_id     {kInvalidOrderId};
    Price       price        {kInvalidPrice};
    Quantity    initial_qty  {0};
    Quantity    remaining_qty{0};
    SeqNum      seq_num      {0};

    // Intrusive doubly-linked list within a price level (pool indices).
    uint32_t    prev_idx     {kNullIdx};
    uint32_t    next_idx     {kNullIdx};

    OrderType   type         {OrderType::Limit};
    Side        side         {Side::Buy};
    OrderStatus status       {OrderStatus::Rejected}; // Unallocated slots are NOT active

private:
    // Explicit padding to guarantee 64-byte size on all targets.
    [[maybe_unused]] uint8_t _pad[13]{};

public:
    // ---- Helpers ----

    [[nodiscard]] bool is_active() const noexcept {
        return status == OrderStatus::New ||
               status == OrderStatus::PartiallyFilled;
    }

    [[nodiscard]] bool is_fully_filled() const noexcept {
        return remaining_qty == 0;
    }

    [[nodiscard]] Quantity filled_qty() const noexcept {
        return initial_qty - remaining_qty;
    }
};

static_assert(sizeof(Order) == 64,
    "Order must be exactly 64 bytes (one cache line). "
    "Adjust padding if the compiler complains.");

static_assert(alignof(Order) == 64,
    "Order must be 64-byte aligned for cache-line isolation.");

} // namespace chronosx
