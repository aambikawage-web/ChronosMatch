/**
 * @file oms.hpp
 * @brief Order Management System — lifecycle tracking and validation gateway.
 *
 * The OMS sits above the MatchingEngine and RiskEngine.
 * Its responsibilities:
 *   1. Validate incoming order parameters (qty > 0, price > 0 for limits,
 *      no duplicate IDs, valid enums).
 *   2. Run the pre-trade risk check.
 *   3. Forward accepted orders to the MatchingEngine.
 *   4. Maintain an authoritative OrderStatus map for every order ever submitted.
 *   5. Expose a cancellation API.
 *
 * ## Status Lifecycle
 *
 *   New ──────────────────────── Filled
 *    │                              ▲
 *    ├──► PartiallyFilled ──────────┘
 *    │
 *    ├──► Cancelled  (client cancel or IOC residual)
 *    │
 *    └──► Rejected   (OMS validation or risk failure)
 *
 * ## ID Generation
 * The OMS auto-assigns monotonically increasing OrderIds if the caller passes
 * kInvalidOrderId (0). Otherwise the caller-provided ID is used after a
 * uniqueness check.
 */

#pragma once

#include "types.hpp"
#include "matching_engine.hpp"
#include "risk_engine.hpp"

#include <unordered_map>
#include <optional>

namespace chronosx {

/// Parameters for submitting a new order.
struct OrderRequest {
    OrderId   id       {kInvalidOrderId};  ///< 0 = auto-assign
    Side      side     {Side::Buy};
    OrderType type     {OrderType::Limit};
    Price     price    {0};               ///< Ignored for market orders
    Quantity  qty      {0};
};

/// Full response from OMS after processing a request.
struct OmsResponse {
    OrderId     assigned_id {kInvalidOrderId};
    MatchResult match_result;
};

class OrderManagementSystem {
public:
    explicit OrderManagementSystem(RiskEngine& risk) noexcept;

    // Non-copyable.
    OrderManagementSystem(const OrderManagementSystem&)            = delete;
    OrderManagementSystem& operator=(const OrderManagementSystem&) = delete;

    // ----------------------------------------------------------------
    // submit — validate → risk-check → route to engine
    // ----------------------------------------------------------------
    [[nodiscard]] OmsResponse submit(const OrderRequest& req);

    // ----------------------------------------------------------------
    // cancel — forward to engine, update status
    // ----------------------------------------------------------------
    [[nodiscard]] OmsResponse cancel(OrderId id);

    // ----------------------------------------------------------------
    // Status queries
    // ----------------------------------------------------------------
    [[nodiscard]] std::optional<OrderStatus> get_status(OrderId id) const noexcept;
    [[nodiscard]] bool order_exists(OrderId id) const noexcept;

    // ----------------------------------------------------------------
    // Accessors
    // ----------------------------------------------------------------
    [[nodiscard]] const MatchingEngine& engine()   const noexcept { return engine_; }
    [[nodiscard]] MatchingEngine&       engine()         noexcept { return engine_; }
    [[nodiscard]] const OrderBook&      book()     const noexcept { return engine_.book(); }
    [[nodiscard]] std::size_t           order_count() const noexcept {
        return status_map_.size();
    }

private:
    RiskEngine&       risk_;
    MatchingEngine    engine_;
    OrderId           next_auto_id_{1};

    // Authoritative status for every order (submitted, cancelled, or rejected).
    std::unordered_map<OrderId, OrderStatus> status_map_;

    // ----------------------------------------------------------------
    // Internal helpers
    // ----------------------------------------------------------------
    OrderId assign_id(OrderId requested_id);
    void    apply_result(OrderId id, const MatchResult& result);

    /// OMS-level parameter validation (before risk check).
    [[nodiscard]] std::optional<RejectEvent> validate(const OrderRequest& req,
                                                      OrderId             id) const noexcept;
};

} // namespace chronosx
