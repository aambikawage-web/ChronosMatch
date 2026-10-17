#include "chronosx/oms.hpp"
#include <cassert>

namespace chronosx {

// ============================================================
// Constructor
// ============================================================
OrderManagementSystem::OrderManagementSystem(RiskEngine& risk) noexcept
    : risk_(risk)
    , engine_()
    , next_auto_id_(1)
{}

// ============================================================
// submit
// ============================================================
OmsResponse OrderManagementSystem::submit(const OrderRequest& req) {
    OmsResponse resp;
    const OrderId id = assign_id(req.id);
    resp.assigned_id = id;

    // Step 1: OMS parameter validation
    auto reject = validate(req, id);
    if (reject.has_value()) {
        resp.match_result.reject_event  = *reject;
        resp.match_result.final_status  = OrderStatus::Rejected;
        status_map_[id] = OrderStatus::Rejected;
        return resp;
    }

    // Step 2: Pre-trade risk check (skip for market orders — price is irrelevant)
    const Price risk_price = (req.type == OrderType::Market) ? 0 : req.price;
    if (req.type == OrderType::Limit) {
        const RiskResult rr = risk_.check_order(req.side, risk_price, req.qty);
        if (rr != RiskResult::Approved) {
            resp.match_result.reject_event = RejectEvent{.order_id = id, .reason = rr};
            resp.match_result.final_status = OrderStatus::Rejected;
            status_map_[id] = OrderStatus::Rejected;
            return resp;
        }
    }

    // Step 3: Route to matching engine
    status_map_[id] = OrderStatus::New;

    if (req.type == OrderType::Limit) {
        resp.match_result = engine_.submit_limit(id, req.side, req.price, req.qty);
    } else {
        resp.match_result = engine_.submit_market(id, req.side, req.qty);
    }

    apply_result(id, resp.match_result);
    return resp;
}

// ============================================================
// cancel
// ============================================================
OmsResponse OrderManagementSystem::cancel(OrderId id) {
    OmsResponse resp;
    resp.assigned_id = id;

    // Check existence and current status
    auto it = status_map_.find(id);
    if (it == status_map_.end()) {
        resp.match_result.reject_event = RejectEvent{
            .order_id = id,
            .reason   = RiskResult::RejectedUnknown,
        };
        resp.match_result.final_status = OrderStatus::Rejected;
        return resp;
    }

    const OrderStatus current = it->second;
    if (current == OrderStatus::Filled   ||
        current == OrderStatus::Cancelled ||
        current == OrderStatus::Rejected) {
        // Already in a terminal state — cannot cancel
        resp.match_result.reject_event = RejectEvent{
            .order_id = id,
            .reason   = RiskResult::RejectedUnknown,
        };
        resp.match_result.final_status = current;
        return resp;
    }

    resp.match_result = engine_.cancel_order(id);
    apply_result(id, resp.match_result);
    return resp;
}

// ============================================================
// get_status / order_exists
// ============================================================
std::optional<OrderStatus> OrderManagementSystem::get_status(OrderId id) const noexcept {
    auto it = status_map_.find(id);
    if (it == status_map_.end()) return std::nullopt;
    return it->second;
}

bool OrderManagementSystem::order_exists(OrderId id) const noexcept {
    return status_map_.contains(id);
}

// ============================================================
// assign_id — internal
// ============================================================
OrderId OrderManagementSystem::assign_id(OrderId requested) {
    if (requested == kInvalidOrderId) {
        return next_auto_id_++;
    }
    return requested;
}

// ============================================================
// validate — internal OMS-level validation
// ============================================================
std::optional<RejectEvent> OrderManagementSystem::validate(
        const OrderRequest& req, OrderId id) const noexcept {

    // Duplicate ID check
    if (status_map_.contains(id)) {
        return RejectEvent{.order_id = id, .reason = RiskResult::RejectedUnknown};
    }

    // Quantity must be positive
    if (req.qty == 0) {
        return RejectEvent{.order_id = id, .reason = RiskResult::RejectedQty};
    }

    // Limit orders must have a positive price
    if (req.type == OrderType::Limit && req.price <= 0) {
        return RejectEvent{.order_id = id, .reason = RiskResult::RejectedNotional};
    }

    return std::nullopt;
}

// ============================================================
// apply_result — synchronise status_map_ with engine result
// ============================================================
void OrderManagementSystem::apply_result(OrderId id, const MatchResult& result) {
    status_map_[id] = result.final_status;
}

} // namespace chronosx
