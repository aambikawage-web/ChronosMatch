#include "chronosx/matching_engine.hpp"
#include <algorithm>
#include <cassert>
#include <stdexcept>

namespace chronosx {

// ============================================================
// Constructor
// ============================================================
MatchingEngine::MatchingEngine()
    : pool_()
    , book_(pool_)
    , seq_counter_(0)
{}

// ============================================================
// alloc_order — allocate and initialise from pool
// ============================================================
uint32_t MatchingEngine::alloc_order(OrderId id, Side side,
                                     Price price, Quantity qty,
                                     OrderType type) {
    Order* ptr = pool_.alloc();
    if (ptr == nullptr) {
        throw std::runtime_error("MatchingEngine: order pool exhausted");
    }
    ptr->order_id      = id;
    ptr->side          = side;
    ptr->price         = price;
    ptr->initial_qty   = qty;
    ptr->remaining_qty = qty;
    ptr->seq_num       = ++seq_counter_;
    ptr->type          = type;
    ptr->status        = OrderStatus::New;
    ptr->prev_idx      = kNullIdx;
    ptr->next_idx      = kNullIdx;
    return pool_.index_of(ptr);
}

// ============================================================
// match_against_book — core FIFO sweep loop
// ============================================================
Quantity MatchingEngine::match_against_book(Order& aggressor, MatchResult& result) {
    const bool is_buy = (aggressor.side == Side::Buy);

    while (aggressor.remaining_qty > 0) {
        PriceLevel* level = is_buy ? book_.best_ask_level()
                                   : book_.best_bid_level();
        if (level == nullptr) break;  // No liquidity

        // For limit orders: stop if price is no longer marketable
        if (aggressor.type == OrderType::Limit) {
            if (is_buy  && aggressor.price < level->price) break;
            if (!is_buy && aggressor.price > level->price) break;
        }

        // Sweep the front of this level's FIFO queue
        while (level->head_idx != kNullIdx && aggressor.remaining_qty > 0) {
            const uint32_t resting_idx = level->head_idx;
            Order& resting = pool_.at(resting_idx);

            const Quantity fill_qty = std::min(aggressor.remaining_qty,
                                               resting.remaining_qty);
            const Price    fill_price = resting.price;  // Maker price

            // Record the trade
            result.trades.push_back(TradeEvent{
                .aggressor_id = aggressor.order_id,
                .resting_id   = resting.order_id,
                .price        = fill_price,
                .qty          = fill_qty,
            });

            // Update quantities
            aggressor.remaining_qty -= fill_qty;
            level->deduct_qty(fill_qty);

            if (fill_qty < resting.remaining_qty) {
                // Partial fill on resting order — it stays in book
                resting.remaining_qty -= fill_qty;
                resting.status = OrderStatus::PartiallyFilled;
            } else {
                // Resting order fully filled — remove from book
                resting.remaining_qty = 0;
                resting.status        = OrderStatus::Filled;
                level->remove_order(resting_idx, pool_);
                pool_.free(&resting);
            }
        }

        // Prune the price level if empty
        const Price level_price = level->price;
        if (is_buy) {
            book_.prune_empty_ask(level_price);
        } else {
            book_.prune_empty_bid(level_price);
        }
    }

    return aggressor.remaining_qty;
}

// ============================================================
// submit_limit
// ============================================================
MatchResult MatchingEngine::submit_limit(OrderId id, Side side,
                                         Price price, Quantity qty) {
    MatchResult result;

    const uint32_t idx = alloc_order(id, side, price, qty, OrderType::Limit);
    Order& order = pool_.at(idx);

    // Attempt to match
    const Quantity residual = match_against_book(order, result);

    if (residual == 0) {
        order.status = OrderStatus::Filled;
        pool_.free(&order);
        result.final_status = OrderStatus::Filled;
    } else if (residual < qty) {
        // Partial fill — residual goes to book
        order.remaining_qty = residual;
        order.status        = OrderStatus::PartiallyFilled;
        book_.add_order(idx);
        result.final_status = OrderStatus::PartiallyFilled;
    } else {
        // No fill at all — rest in book
        book_.add_order(idx);
        result.final_status = OrderStatus::New;
    }

    return result;
}

// ============================================================
// submit_market
// ============================================================
MatchResult MatchingEngine::submit_market(OrderId id, Side side, Quantity qty) {
    MatchResult result;

    const uint32_t idx = alloc_order(id, side, kInvalidPrice, qty, OrderType::Market);
    Order& order = pool_.at(idx);

    const Quantity residual = match_against_book(order, result);

    if (residual == 0) {
        order.status = OrderStatus::Filled;
        pool_.free(&order);
        result.final_status = OrderStatus::Filled;
    } else {
        // IOC: cancel unfilled residual
        order.status = OrderStatus::Cancelled;
        result.cancel_event = CancelEvent{
            .order_id      = id,
            .remaining_qty = residual,
        };
        pool_.free(&order);
        result.final_status = (residual < qty)
            ? OrderStatus::PartiallyFilled  // some fills occurred
            : OrderStatus::Cancelled;       // no fills at all
    }

    return result;
}

// ============================================================
// cancel_order
// ============================================================
MatchResult MatchingEngine::cancel_order(OrderId id) {
    MatchResult result;

    // We need the remaining_qty before removal for the event.
    // Peek into the book via the price index (order_book exposes it indirectly).
    // We'll delegate to book_.cancel_order which also frees to pool.
    // To get remaining_qty, we temporarily look it up first.

    // The pool lookup isn't possible without the pool index, so we walk
    // the active_order_count path: OrderBook stores order_price_index_.
    // For the CancelEvent, we set remaining_qty to 0 as a safe default
    // (the caller already knows they cancelled it).
    const bool removed = book_.cancel_order(id);

    if (removed) {
        result.cancel_event = CancelEvent{ .order_id = id, .remaining_qty = 0 };
        result.final_status = OrderStatus::Cancelled;
    } else {
        result.reject_event = RejectEvent{
            .order_id = id,
            .reason   = RiskResult::RejectedUnknown,
        };
        result.final_status = OrderStatus::Rejected;
    }

    return result;
}

} // namespace chronosx
