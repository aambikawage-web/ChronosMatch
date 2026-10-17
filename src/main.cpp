/**
 * @file main.cpp
 * @brief ChronosX simulation entry point.
 *
 * Demonstrates:
 *   1. Limit order resting, partial fill, full fill
 *   2. Market order IOC sweep
 *   3. Cancellation
 *   4. Risk rejection
 *   5. SPSC ring-buffer throughput benchmark
 */

#include "chronosx/simulator.hpp"
#include "chronosx/types.hpp"

#include <iostream>
#include <iomanip>
#include <vector>
#include <string>

using namespace chronosx;

// ---- helpers -------------------------------------------------------

static void print_trades(const MatchResult& r) {
    for (const auto& t : r.trades) {
        std::cout << "   TRADE  agg=" << t.aggressor_id
                  << " rest=" << t.resting_id
                  << " price=" << std::fixed << std::setprecision(4)
                  << static_cast<double>(t.price) / kPriceMult
                  << " qty=" << t.qty << "\n";
    }
    if (r.cancel_event) {
        std::cout << "   CANCEL order=" << r.cancel_event->order_id
                  << " residual=" << r.cancel_event->remaining_qty << "\n";
    }
    if (r.reject_event) {
        std::cout << "   REJECT order=" << r.reject_event->order_id << "\n";
    }
}

static const char* status_str(OrderStatus s) {
    switch (s) {
        case OrderStatus::New:             return "New";
        case OrderStatus::PartiallyFilled: return "PartiallyFilled";
        case OrderStatus::Filled:          return "Filled";
        case OrderStatus::Cancelled:       return "Cancelled";
        case OrderStatus::Rejected:        return "Rejected";
    }
    return "Unknown";
}

// ---- main ----------------------------------------------------------

int main() {
    std::cout << "╔══════════════════════════════════════════════╗\n";
    std::cout << "║  ChronosX — HFT Matching Engine Simulator   ║\n";
    std::cout << "╚══════════════════════════════════════════════╝\n\n";

    // Configure risk limits
    // Price ticks: 1 tick = $0.0001, so $100.00 = 1,000,000 ticks
    // max_order_qty = 1000 shares
    // max_order_notional = $200,000.00 = 2,000,000,000 ticks²
    RiskLimits limits{
        .max_order_qty      = 1000,
        .max_order_notional = 2'000'000'000LL,
    };

    Simulator sim;
    sim.risk().set_limits(limits);

    std::vector<ScenarioEvent> events;

    // ── Scenario 1: Two resting ask orders, then a matching limit buy ──
    std::cout << "── Scenario 1: Limit orders and matching ──\n";

    // Resting sell at $100.00 (1,000,000 ticks), qty=50
    events.push_back({ ScenarioEvent::Kind::NewOrder,
        { .id=1, .side=Side::Sell, .type=OrderType::Limit,
          .price=1'000'000, .qty=50 } });

    // Resting sell at $100.00, qty=30
    events.push_back({ ScenarioEvent::Kind::NewOrder,
        { .id=2, .side=Side::Sell, .type=OrderType::Limit,
          .price=1'000'000, .qty=30 } });

    // Resting sell at $100.05 (1,000,500 ticks), qty=100
    events.push_back({ ScenarioEvent::Kind::NewOrder,
        { .id=3, .side=Side::Sell, .type=OrderType::Limit,
          .price=1'000'500, .qty=100 } });

    // Aggressive buy at $100.05, qty=90  → should match orders 1 and 2 fully,
    //                                       partial on order 3
    events.push_back({ ScenarioEvent::Kind::NewOrder,
        { .id=4, .side=Side::Buy, .type=OrderType::Limit,
          .price=1'000'500, .qty=90 } });

    auto results = sim.run_scenario(events);
    events.clear();

    for (std::size_t i = 0; i < results.size(); ++i) {
        std::cout << "  Order " << results[i].assigned_id
                  << " → " << status_str(results[i].match_result.final_status) << "\n";
        print_trades(results[i].match_result);
    }
    sim.print_book(std::cout);

    // ── Scenario 2: Market order IOC sweep ──
    std::cout << "\n── Scenario 2: Market order IOC sweep ──\n";
    // Orders 1 and 2 were fully filled. Order 3 has 90 filled, 10 remaining.
    // Send a market buy for 200 — should fill the remaining 10 of order 3,
    // then cancel the residual 190 (empty book).
    events.push_back({ ScenarioEvent::Kind::NewOrder,
        { .id=5, .side=Side::Buy, .type=OrderType::Market,
          .price=0, .qty=200 } });

    results = sim.run_scenario(events);
    events.clear();

    for (auto& r : results) {
        std::cout << "  Order " << r.assigned_id
                  << " → " << status_str(r.match_result.final_status) << "\n";
        print_trades(r.match_result);
    }
    sim.print_book(std::cout);

    // ── Scenario 3: Cancellation ──
    std::cout << "\n── Scenario 3: Cancellation ──\n";

    // Add a resting bid
    events.push_back({ ScenarioEvent::Kind::NewOrder,
        { .id=10, .side=Side::Buy, .type=OrderType::Limit,
          .price=990'000, .qty=100 } });
    // Cancel it
    events.push_back({ ScenarioEvent::Kind::Cancel,
        {}, 10 });

    results = sim.run_scenario(events);
    events.clear();

    for (auto& r : results) {
        std::cout << "  Order " << r.assigned_id
                  << " → " << status_str(r.match_result.final_status) << "\n";
        print_trades(r.match_result);
    }

    // ── Scenario 4: Risk rejection ──
    std::cout << "\n── Scenario 4: Risk rejection ──\n";

    // qty=5000 > max_order_qty=1000 → rejected
    events.push_back({ ScenarioEvent::Kind::NewOrder,
        { .id=20, .side=Side::Buy, .type=OrderType::Limit,
          .price=1'000'000, .qty=5000 } });

    results = sim.run_scenario(events);
    events.clear();

    for (auto& r : results) {
        std::cout << "  Order " << r.assigned_id
                  << " → " << status_str(r.match_result.final_status) << "\n";
        print_trades(r.match_result);
    }

    // ── Scenario 5: SPSC throughput demo ──
    std::cout << "\n── Scenario 5: SPSC Ring Buffer Throughput ──\n";
    constexpr std::size_t kDemoOrders = 100'000;
    const double throughput = sim.run_spsc_demo(kDemoOrders);
    std::cout << "  Orders processed : " << kDemoOrders << "\n";
    std::cout << "  Throughput       : "
              << std::fixed << std::setprecision(0)
              << throughput << " orders/sec\n";

    sim.print_summary(std::cout);

    std::cout << "\nDone.\n";
    return 0;
}
