/**
 * @file price_level.hpp
 * @brief A single price level in the limit order book.
 *
 * Each price level maintains an intrusive doubly-linked FIFO queue of orders,
 * referenced by pool indices rather than raw pointers.
 *
 * FIFO ordering within a level enforces time-priority: orders at the same
 * price are matched in the order they arrived (earliest first).
 *
 * The total_qty cache avoids O(N) traversal when querying depth at a level.
 * It must be kept in sync on every add/remove.
 */

#pragma once

#include "types.hpp"
#include "order.hpp"
#include "memory_pool.hpp"
#include <cassert>
#include <cstdint>

namespace chronosx {

/**
 * @brief Represents all orders resting at a single price point.
 *
 * Orders are stored as an intrusive doubly-linked list using ObjectPool
 * indices. head_idx is the oldest order (matched first); tail_idx is newest.
 */
struct PriceLevel {
    Price    price    {kInvalidPrice};
    uint32_t head_idx {kNullIdx};   ///< Front of FIFO queue (matched first)
    uint32_t tail_idx {kNullIdx};   ///< Back  of FIFO queue (matched last)
    Quantity total_qty{0};          ///< Cached sum of remaining_qty across all orders

    [[nodiscard]] bool empty() const noexcept { return head_idx == kNullIdx; }

    // ----------------------------------------------------------------
    // append_order  — O(1)
    // Enqueues `order` at the tail (newest / last to be matched).
    // ----------------------------------------------------------------
    template <std::size_t Cap>
    void append_order(uint32_t idx, ObjectPool<Order, Cap>& pool) noexcept {
        Order& order = pool.at(idx);
        order.prev_idx = tail_idx;
        order.next_idx = kNullIdx;

        if (tail_idx != kNullIdx) {
            pool.at(tail_idx).next_idx = idx;
        } else {
            head_idx = idx;   // First order in level
        }
        tail_idx = idx;
        total_qty += order.remaining_qty;
    }

    // ----------------------------------------------------------------
    // remove_order — O(1)
    // Unlinks `idx` from the doubly-linked list.
    // Does NOT free the slot back to the pool — caller is responsible.
    // ----------------------------------------------------------------
    template <std::size_t Cap>
    void remove_order(uint32_t idx, ObjectPool<Order, Cap>& pool) noexcept {
        Order& order = pool.at(idx);
        assert(total_qty >= order.remaining_qty);
        total_qty -= order.remaining_qty;

        const uint32_t prev = order.prev_idx;
        const uint32_t next = order.next_idx;

        if (prev != kNullIdx) pool.at(prev).next_idx = next;
        else                  head_idx = next;

        if (next != kNullIdx) pool.at(next).prev_idx = prev;
        else                  tail_idx = prev;

        order.prev_idx = kNullIdx;
        order.next_idx = kNullIdx;
    }

    // ----------------------------------------------------------------
    // deduct_qty — O(1)
    // Adjusts total_qty after a partial fill (order stays in book).
    // ----------------------------------------------------------------
    void deduct_qty(Quantity executed) noexcept {
        assert(total_qty >= executed);
        total_qty -= executed;
    }
};

} // namespace chronosx
