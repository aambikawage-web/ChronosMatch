#include "chronosx/risk_engine.hpp"
#include <cstdint>
#include <cstdlib>  // std::abs

namespace chronosx {

// ============================================================
// safe_multiply — overflow-safe Price × Quantity → int64_t
// ============================================================
bool RiskEngine::safe_multiply(Price price, Quantity qty, int64_t& result) noexcept {
    if (price <= 0) {
        result = 0;
        return true;  // Zero/negative price: notional = 0, not a concern here
    }

#if defined(__GNUC__) || defined(__clang__)
    // Use __int128 on GCC/Clang to detect overflow cheaply
    __int128 product = static_cast<__int128>(price) *
                       static_cast<__int128>(qty);
    if (product > static_cast<__int128>(INT64_MAX)) {
        return false;  // Overflow
    }
    result = static_cast<int64_t>(product);
    return true;
#else
    // MSVC: manual overflow check before multiply
    if (qty > 0 &&
        static_cast<uint64_t>(price) > static_cast<uint64_t>(INT64_MAX / static_cast<int64_t>(qty))) {
        return false;
    }
    result = price * static_cast<int64_t>(qty);
    return true;
#endif
}

// ============================================================
// check_order
// ============================================================
RiskResult RiskEngine::check_order(Side    /*side*/,
                                   Price   price,
                                   Quantity qty) const noexcept {
    // Check 1: Quantity limit
    if (qty > limits_.max_order_qty) {
        return RiskResult::RejectedQty;
    }

    // Check 2: Notional limit (price × qty)
    int64_t notional = 0;
    if (!safe_multiply(price, qty, notional)) {
        // Multiply overflowed — notional is astronomically large
        return RiskResult::RejectedNotional;
    }
    if (notional > limits_.max_order_notional) {
        return RiskResult::RejectedNotional;
    }

    return RiskResult::Approved;
}

} // namespace chronosx
