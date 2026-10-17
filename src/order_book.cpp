#include "chronosx/order_book.hpp"
#include <cassert>
#include <stdexcept>

namespace chronosx {

// ============================================================
// add_order
// ============================================================
void OrderBook::add_order(uint32_t pool_idx) {
    Order& order = pool_.at(pool_idx);
    assert(order.is_active());
    assert(order.order_id != kInvalidOrderId);

    const Price p = order.price;
    const Side  s = order.side;

    if (s == Side::Buy) {
        auto& level = bids_[p];
        level.price = p;
        level.append_order(pool_idx, pool_);
    } else {
        auto& level = asks_[p];
        level.price = p;
        level.append_order(pool_idx, pool_);
    }

    order_price_index_[order.order_id] = p;
}

// ============================================================
// cancel_order
// ============================================================
bool OrderBook::cancel_order(OrderId id) {
    auto it = order_price_index_.find(id);
    if (it == order_price_index_.end()) {
        return false;  // Order not in book
    }

    const Price price = it->second;

    // Find and remove from the correct side
    auto bid_it = bids_.find(price);
    if (bid_it != bids_.end()) {
        PriceLevel& level = bid_it->second;
        // Walk the FIFO queue to find this order's pool index
        uint32_t idx = level.head_idx;
        while (idx != kNullIdx) {
            if (pool_.at(idx).order_id == id) {
                level.remove_order(idx, pool_);
                pool_.free(&pool_.at(idx));
                if (level.empty()) bids_.erase(bid_it);
                order_price_index_.erase(it);
                return true;
            }
            idx = pool_.at(idx).next_idx;
        }
    }

    auto ask_it = asks_.find(price);
    if (ask_it != asks_.end()) {
        PriceLevel& level = ask_it->second;
        uint32_t idx = level.head_idx;
        while (idx != kNullIdx) {
            if (pool_.at(idx).order_id == id) {
                level.remove_order(idx, pool_);
                pool_.free(&pool_.at(idx));
                if (level.empty()) asks_.erase(ask_it);
                order_price_index_.erase(it);
                return true;
            }
            idx = pool_.at(idx).next_idx;
        }
    }

    // Index was stale — shouldn't happen under correct usage
    order_price_index_.erase(it);
    return false;
}

// ============================================================
// best_bid / best_ask / spread
// ============================================================
std::optional<Price> OrderBook::best_bid() const noexcept {
    if (bids_.empty()) return std::nullopt;
    return bids_.begin()->first;
}

std::optional<Price> OrderBook::best_ask() const noexcept {
    if (asks_.empty()) return std::nullopt;
    return asks_.begin()->first;
}

std::optional<int64_t> OrderBook::spread() const noexcept {
    auto bid = best_bid();
    auto ask = best_ask();
    if (!bid || !ask) return std::nullopt;
    return *ask - *bid;
}

// ============================================================
// Depth queries
// ============================================================
Quantity OrderBook::bid_qty_at(Price price) const noexcept {
    auto it = bids_.find(price);
    if (it == bids_.end()) return 0;
    return it->second.total_qty;
}

Quantity OrderBook::ask_qty_at(Price price) const noexcept {
    auto it = asks_.find(price);
    if (it == asks_.end()) return 0;
    return it->second.total_qty;
}

// ============================================================
// best_bid_level / best_ask_level
// ============================================================
PriceLevel* OrderBook::best_bid_level() noexcept {
    if (bids_.empty()) return nullptr;
    return &bids_.begin()->second;
}

PriceLevel* OrderBook::best_ask_level() noexcept {
    if (asks_.empty()) return nullptr;
    return &asks_.begin()->second;
}

// ============================================================
// prune_empty_bid / prune_empty_ask
// ============================================================
void OrderBook::prune_empty_bid(Price price) noexcept {
    auto it = bids_.find(price);
    if (it != bids_.end() && it->second.empty()) {
        bids_.erase(it);
    }
}

void OrderBook::prune_empty_ask(Price price) noexcept {
    auto it = asks_.find(price);
    if (it != asks_.end() && it->second.empty()) {
        asks_.erase(it);
    }
}

// ============================================================
// Internal: find_level
// ============================================================
PriceLevel* OrderBook::find_level(Side side, Price price) noexcept {
    if (side == Side::Buy) {
        auto it = bids_.find(price);
        return (it != bids_.end()) ? &it->second : nullptr;
    } else {
        auto it = asks_.find(price);
        return (it != asks_.end()) ? &it->second : nullptr;
    }
}

} // namespace chronosx
