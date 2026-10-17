/**
 * @file risk_engine.hpp
 * @brief Pre-trade risk engine — synchronous, zero-allocation, O(1).
 *
 * The risk engine is the first gate every new order passes through.
 * If any check fails, the order is rejected before it ever touches the book.
 *
 * ## Checks (in evaluation order)
 *   1. Quantity limit  : qty  > max_order_qty   → RejectedQty
 *   2. Notional limit  : price × qty > max_order_notional → RejectedNotional
 *
 * ## Fixed-Point Arithmetic
 * Notional is computed as Price (int64_t ticks) × Quantity (uint64_t).
 * To avoid overflow, we use __int128 for the intermediate product on GCC/Clang,
 * and a checked-multiply on MSVC.
 *
 * ## Thread Safety
 * Not thread-safe; designed to be called from the engine's single core thread.
 */

#pragma once

#include "types.hpp"
#include <cstdint>

namespace chronosx {

struct RiskLimits {
    Quantity max_order_qty      {10'000};           ///< Max shares/contracts per order
    Price    max_order_notional {500'000'000LL};    ///< Max price×qty (ticks²), e.g. $50000.0000
};

class RiskEngine {
public:
    explicit RiskEngine(const RiskLimits& limits = RiskLimits{}) noexcept
        : limits_(limits) {}

    // ----------------------------------------------------------------
    // check_order — O(1), no allocation
    // Returns RiskResult::Approved if the order may proceed, otherwise
    // the specific rejection reason.
    // ----------------------------------------------------------------
    [[nodiscard]] RiskResult check_order(Side    side,
                                         Price   price,
                                         Quantity qty) const noexcept;

    // ----------------------------------------------------------------
    // Configuration
    // ----------------------------------------------------------------
    void set_limits(const RiskLimits& limits) noexcept { limits_ = limits; }
    [[nodiscard]] const RiskLimits& limits() const noexcept { return limits_; }

private:
    RiskLimits limits_;

    /// Overflow-safe multiplication returning false on overflow.
    [[nodiscard]] static bool safe_multiply(Price price,
                                            Quantity qty,
                                            int64_t& result) noexcept;
};

} // namespace chronosx
