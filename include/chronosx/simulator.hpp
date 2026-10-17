/**
 * @file simulator.hpp
 * @brief High-level simulation harness wrapping OMS + RiskEngine.
 *
 * Provides a convenient single-object entry-point for scripted scenarios
 * and replay-style testing.  The SPSC ring buffer integration is demonstrated
 * here: a background producer thread pushes OrderRequests into the ring buffer
 * while the main thread (consumer) drains and processes them.
 */

#pragma once

#include "types.hpp"
#include "oms.hpp"
#include "risk_engine.hpp"
#include "spsc_ring_buffer.hpp"

#include <vector>
#include <functional>
#include <string>
#include <iosfwd>

namespace chronosx {

/// A scripted order event for scenario replay.
struct ScenarioEvent {
    enum class Kind : uint8_t { NewOrder, Cancel };
    Kind        kind  {Kind::NewOrder};
    OrderRequest req  {};
    OrderId     cancel_id{kInvalidOrderId};
};

/// Ring-buffer capacity for SPSC demo (must be a power of 2).
inline constexpr std::size_t kSimRingCapacity = 4096;

/**
 * @brief Simulation harness.
 *
 * Usage:
 *   Simulator sim;
 *   sim.risk().set_limits({.max_order_qty = 5000, .max_order_notional = 1'000'000'000LL});
 *   auto results = sim.run_scenario(events);
 *   sim.print_summary(std::cout);
 */
class Simulator {
public:
    Simulator();

    // ----------------------------------------------------------------
    // Scenario replay (synchronous, single-threaded)
    // ----------------------------------------------------------------
    std::vector<OmsResponse> run_scenario(const std::vector<ScenarioEvent>& events);

    // ----------------------------------------------------------------
    // SPSC demo: producer pushes events into ring buffer, consumer drains
    // Runs for `num_events` orders, returns throughput in events/second.
    // ----------------------------------------------------------------
    double run_spsc_demo(std::size_t num_events);

    // ----------------------------------------------------------------
    // Diagnostics
    // ----------------------------------------------------------------
    void print_summary(std::ostream& out) const;
    void print_book(std::ostream& out)    const;

    // ----------------------------------------------------------------
    // Accessors
    // ----------------------------------------------------------------
    [[nodiscard]] RiskEngine&              risk()   noexcept { return risk_; }
    [[nodiscard]] OrderManagementSystem&   oms()    noexcept { return oms_;  }
    [[nodiscard]] const OrderBook&         book()   const noexcept;

private:
    RiskEngine              risk_;
    OrderManagementSystem   oms_;
};

} // namespace chronosx
