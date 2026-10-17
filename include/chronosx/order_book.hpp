/**
 * @file order_book.hpp
 * @brief Limit Order Book — maintains bid and ask sides with price-time priority.
 *
 * ## Data Structure Choice
 *
 * Bid side: std::map<Price, PriceLevel, std::greater<Price>>
 *   → highest bid at begin() (best bid)
 *
 * Ask side: std::map<Price, PriceLevel, std::less<Price>>
 *   → lowest ask at begin() (best ask)
 *
 * std::map gives O(log N_prices) insert/erase/find on the price dimension,
 * which is acceptable for a portfolio-grade simulator where the number of
 * distinct price levels rarely exceeds a few thousand.
 *
 * O(1) cancellation by order ID is achieved via a separate index:
 *   order_price_index_: OrderId → Price
 * allowing the book to jump directly to the correct PriceLevel without
 * scanning the tree.
 *
 * ## Invariants (maintained after every operation)
 *   1. best_bid() < best_ask()  (no crossed book)
 *   2. Every PriceLevel in the map has at least one order (empty levels removed)
 *   3. PriceLevel::total_qty equals the sum of remaining_qty of all its orders
 *   4. order_price_index_ contains exactly the set of active order IDs
 *
 * ## Pool Ownership
 * OrderBook holds a reference to the ObjectPool<Order>. The MatchingEngine
 * owns the pool and passes it in. This avoids an extra level of indirection
 * and lets the engine reuse freed slots immediately.
 */

#pragma once

#include "types.hpp"
#include "order.hpp"
#include "price_level.hpp"
#include "memory_pool.hpp"

#include <map>
#include <optional>
#include <unordered_map>
#include <functional>
#include <cstddef>

namespace chronosx {

/// Maximum number of live orders in the book at any one time.
inline constexpr std::size_t kDefaultPoolCapacity = 1'000'000;

class OrderBook {
public:
    using Pool = ObjectPool<Order, kDefaultPoolCapacity>;

    explicit OrderBook(Pool& pool) noexcept : pool_(pool) {}

    // Non-copyable (references the external pool).
    OrderBook(const OrderBook&)            = delete;
    OrderBook& operator=(const OrderBook&) = delete;

    // ----------------------------------------------------------------
    // add_order — O(log N_prices)
    // Places `order` (already allocated from the pool) into the book.
    // Precondition: order.is_active() == true, order.order_id is unique.
    // ----------------------------------------------------------------
    void add_order(uint32_t pool_idx);

    // ----------------------------------------------------------------
    // cancel_order — O(log N_prices)
    // Removes the order with `id` from the book and returns it to pool.
    // Returns true on success, false if id is not in the book.
    // ----------------------------------------------------------------
    bool cancel_order(OrderId id);

    // ----------------------------------------------------------------
    // Best prices
    // ----------------------------------------------------------------
    [[nodiscard]] std::optional<Price>    best_bid()  const noexcept;
    [[nodiscard]] std::optional<Price>    best_ask()  const noexcept;
    [[nodiscard]] std::optional<int64_t>  spread()    const noexcept;

    // ----------------------------------------------------------------
    // Depth queries
    // ----------------------------------------------------------------
    [[nodiscard]] std::size_t bid_levels() const noexcept { return bids_.size(); }
    [[nodiscard]] std::size_t ask_levels() const noexcept { return asks_.size(); }
    [[nodiscard]] bool        is_empty()   const noexcept { return bids_.empty() && asks_.empty(); }

    /// Returns total resting quantity at `price` on the bid side (0 if absent).
    [[nodiscard]] Quantity bid_qty_at(Price price) const noexcept;
    /// Returns total resting quantity at `price` on the ask side (0 if absent).
    [[nodiscard]] Quantity ask_qty_at(Price price) const noexcept;

    // ----------------------------------------------------------------
    // Access top-of-book level (for matching engine use only)
    // ----------------------------------------------------------------
    /// Returns pointer to the best bid level, or nullptr if empty.
    [[nodiscard]] PriceLevel* best_bid_level() noexcept;
    /// Returns pointer to the best ask level, or nullptr if empty.
    [[nodiscard]] PriceLevel* best_ask_level() noexcept;

    /// Removes a price level if it is empty. Called after every match.
    void prune_empty_bid(Price price) noexcept;
    void prune_empty_ask(Price price) noexcept;

    /// Direct access to pool (needed by MatchingEngine).
    [[nodiscard]] Pool& pool() noexcept { return pool_; }

    // ----------------------------------------------------------------
    // Diagnostics
    // ----------------------------------------------------------------
    [[nodiscard]] std::size_t active_order_count() const noexcept {
        return order_price_index_.size();
    }

private:
    Pool& pool_;

    // Bid side: highest price first
    std::map<Price, PriceLevel, std::greater<Price>> bids_;
    // Ask side: lowest price first
    std::map<Price, PriceLevel, std::less<Price>>    asks_;

    // O(1) lookup: OrderId → resting Price (for cancellation)
    std::unordered_map<OrderId, Price> order_price_index_;

    // Internal helper: look up the level map for a given side
    PriceLevel* find_level(Side side, Price price) noexcept;
};

} // namespace chronosx
