/**
 * @file matching_engine.hpp
 * @brief Core matching engine — price-time priority order matching.
 *
 * ## Matching Rules
 *
 * ### Limit Orders
 *   1. Check if the incoming order is marketable (bid ≥ best ask, or ask ≤ best bid).
 *   2. While marketable and residual qty > 0, consume resting orders at the best
 *      opposite price, FIFO within each level.
 *   3. Execute at the RESTING order's price (maker price).
 *   4. After fills: remove fully filled resting orders from book and return to pool.
 *   5. If residual remains after sweeping all matchable levels, add to book.
 *
 * ### Market Orders
 *   1. Sweep the opposite side greedily, regardless of price.
 *   2. Execute at each resting order's price.
 *   3. If the book is empty before the order is filled, the unfilled residual
 *      is CANCELLED (IOC semantics). A CancelEvent is emitted.
 *   4. Market orders NEVER rest in the book.
 *
 * ### Cancellations
 *   1. Look up the order in the book's index.
 *   2. Remove from its price level.
 *   3. Return pool slot.
 *   4. Emit CancelEvent.
 *
 * ## Result type
 * MatchResult bundles all events emitted during processing one order.
 * Callers inspect trades, cancel_event, and reject_event.
 */

#pragma once

#include "types.hpp"
#include "order.hpp"
#include "order_book.hpp"
#include "memory_pool.hpp"

#include <vector>
#include <optional>

namespace chronosx {

struct MatchResult {
    std::vector<TradeEvent>      trades;
    std::optional<CancelEvent>   cancel_event;   ///< Set if residual was cancelled
    std::optional<RejectEvent>   reject_event;   ///< Set if order was rejected
    OrderStatus                  final_status {OrderStatus::Rejected};
};

class MatchingEngine {
public:
    using Pool = OrderBook::Pool;

    MatchingEngine();

    // Non-copyable.
    MatchingEngine(const MatchingEngine&)            = delete;
    MatchingEngine& operator=(const MatchingEngine&) = delete;

    // ----------------------------------------------------------------
    // submit_limit — O(log N_prices + M_fills)
    // Processes an incoming limit order.
    // id must be unique. Returns MatchResult with trade events.
    // ----------------------------------------------------------------
    [[nodiscard]] MatchResult submit_limit(OrderId  id,
                                           Side     side,
                                           Price    price,
                                           Quantity qty);

    // ----------------------------------------------------------------
    // submit_market — O(M_fills)
    // Processes an incoming market order (IOC semantics on residual).
    // ----------------------------------------------------------------
    [[nodiscard]] MatchResult submit_market(OrderId  id,
                                            Side     side,
                                            Quantity qty);

    // ----------------------------------------------------------------
    // cancel_order — O(log N_prices)
    // Cancels the resting order with `id`.
    // Returns MatchResult with cancel_event set on success.
    // ----------------------------------------------------------------
    [[nodiscard]] MatchResult cancel_order(OrderId id);

    // ----------------------------------------------------------------
    // Accessors
    // ----------------------------------------------------------------
    [[nodiscard]] const OrderBook& book()     const noexcept { return book_; }
    [[nodiscard]] OrderBook&       book()           noexcept { return book_; }
    [[nodiscard]] uint64_t         seq_counter()    const noexcept { return seq_counter_; }

private:
    Pool       pool_;
    OrderBook  book_;
    SeqNum     seq_counter_{0};

    // Internal: allocate an Order from the pool and initialise its fields.
    [[nodiscard]] uint32_t alloc_order(OrderId id, Side side,
                                       Price price, Quantity qty,
                                       OrderType type);

    // Internal matching loop: sweeps the opposite side of `aggressor`.
    // Fills trades into `result`. Returns final remaining_qty of aggressor.
    Quantity match_against_book(Order& aggressor, MatchResult& result);
};

} // namespace chronosx
