/**
 * @file types.hpp
 * @brief Fundamental domain types for ChronosX HFT Matching Engine.
 *
 * Design decisions:
 *  - All prices are stored as integer ticks (int64_t) to avoid floating-point
 *    rounding errors. One tick = 0.0001 units (4 decimal places).
 *    Example: $12.3456 is stored as 123456.
 *  - Quantities are unsigned 64-bit integers.
 *  - OrderId and SeqNum are unsigned 64-bit counters, monotonically increasing.
 *  - No heap allocation in this header.
 */

#pragma once

#include <cstdint>
#include <limits>

namespace chronosx {

// ============================================================
// Primitive aliases
// ============================================================

/// Order identifier. Unique per engine lifetime. Monotonically increasing.
using OrderId = uint64_t;

/// Price in fixed-point integer ticks (4 decimal places).
/// $1.0000 == 10000 ticks.  $0.0001 == 1 tick.
using Price = int64_t;

/// Order quantity (number of units/shares/contracts).
using Quantity = uint64_t;

/// Arrival sequence number assigned by the engine; used for FIFO tie-breaking.
using SeqNum = uint64_t;

// ============================================================
// Sentinels
// ============================================================

/// Invalid/uninitialised price sentinel.
inline constexpr Price kInvalidPrice = std::numeric_limits<Price>::min();

/// Invalid/uninitialised order id sentinel.
inline constexpr OrderId kInvalidOrderId = 0;

/// Number of decimal places encoded in a Price tick.
inline constexpr int kPriceDecimals = 4;

/// Multiplier: multiply a decimal price by this to get ticks.
inline constexpr int64_t kPriceMult = 10000;

// ============================================================
// Enumerations
// ============================================================

/// Which side of the order book an order rests on (or aggresses against).
enum class Side : uint8_t {
    Buy  = 0,
    Sell = 1,
};

/// Supported order types.
enum class OrderType : uint8_t {
    Limit  = 0,  ///< Rests if not immediately matchable.
    Market = 1,  ///< Sweeps opposite side; unfilled residual is cancelled (IOC).
};

/// Lifecycle state of an order.
enum class OrderStatus : uint8_t {
    New              = 0,  ///< Accepted, not yet matched.
    PartiallyFilled  = 1,  ///< At least one fill; residual remains in book.
    Filled           = 2,  ///< Fully executed; no residual.
    Cancelled        = 3,  ///< Cancelled by client or IOC residual.
    Rejected         = 4,  ///< Rejected by OMS/risk before entering the book.
};

/// Result of a pre-trade risk check.
enum class RiskResult : uint8_t {
    Approved           = 0,
    RejectedQty        = 1,  ///< Order quantity exceeds max allowed.
    RejectedNotional   = 2,  ///< Order notional (price × qty) exceeds max allowed.
    RejectedUnknown    = 3,
};

// ============================================================
// Event structures (emitted by the matching engine)
// ============================================================

/**
 * @brief Immutable record of a single execution between two orders.
 *
 * The engine executes at the *resting* order's price (maker price).
 * The aggressor_id is the incoming order; resting_id is the order
 * already sitting in the book.
 */
struct TradeEvent {
    OrderId  aggressor_id{kInvalidOrderId};
    OrderId  resting_id{kInvalidOrderId};
    Price    price{kInvalidPrice};
    Quantity qty{0};
};

/**
 * @brief Notification that an order was cancelled (by client or IOC residual).
 */
struct CancelEvent {
    OrderId  order_id{kInvalidOrderId};
    Quantity remaining_qty{0};
};

/**
 * @brief Notification that an order was rejected by OMS or risk engine.
 */
struct RejectEvent {
    OrderId    order_id{kInvalidOrderId};
    RiskResult reason{RiskResult::RejectedUnknown};
};

} // namespace chronosx
