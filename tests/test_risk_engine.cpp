#include <gtest/gtest.h>
#include "chronosx/risk_engine.hpp"

using namespace chronosx;

class RiskEngineTest : public ::testing::Test {
protected:
    RiskLimits limits{
        .max_order_qty      = 1000,
        .max_order_notional = 1'000'000'000LL,  // price×qty ≤ this
    };
    RiskEngine risk{limits};
};

TEST_F(RiskEngineTest, ApprovedWhenWithinBothLimits) {
    // qty=100, price=5000 → notional=500,000 < 1,000,000,000
    auto r = risk.check_order(Side::Buy, 5000, 100);
    EXPECT_EQ(r, RiskResult::Approved);
}

TEST_F(RiskEngineTest, RejectedWhenQtyExceedsLimit) {
    auto r = risk.check_order(Side::Buy, 5000, 1001);
    EXPECT_EQ(r, RiskResult::RejectedQty);
}

TEST_F(RiskEngineTest, RejectedWhenNotionalExceedsLimit) {
    // qty=1000 (within limit), price=2,000,000 → notional=2,000,000,000 > limit
    auto r = risk.check_order(Side::Buy, 2'000'000, 1000);
    EXPECT_EQ(r, RiskResult::RejectedNotional);
}

TEST_F(RiskEngineTest, QtyCheckTakesPriorityOverNotional) {
    // qty violates limit AND notional would also be huge — should return qty rejection
    auto r = risk.check_order(Side::Buy, 2'000'000, 9999);
    EXPECT_EQ(r, RiskResult::RejectedQty);
}

TEST_F(RiskEngineTest, BoundaryQtyExactLimit) {
    // qty == max_order_qty exactly → should be approved
    auto r = risk.check_order(Side::Sell, 100, 1000);
    EXPECT_EQ(r, RiskResult::Approved);
}

TEST_F(RiskEngineTest, BoundaryQtyOnePastLimit) {
    auto r = risk.check_order(Side::Sell, 100, 1001);
    EXPECT_EQ(r, RiskResult::RejectedQty);
}

TEST_F(RiskEngineTest, BoundaryNotionalExactLimit) {
    // notional == max exactly → Approved
    // limits_.max_order_notional = 1_000_000_000
    // Find price × qty = 1,000,000,000: price=1,000,000, qty=1000
    auto r = risk.check_order(Side::Buy, 1'000'000, 1000);
    EXPECT_EQ(r, RiskResult::Approved);
}

TEST_F(RiskEngineTest, SetLimitsUpdatesConfiguration) {
    RiskLimits new_limits{.max_order_qty = 1, .max_order_notional = 1};
    risk.set_limits(new_limits);
    // qty=2 should now be rejected
    auto r = risk.check_order(Side::Buy, 1, 2);
    EXPECT_EQ(r, RiskResult::RejectedQty);
}

TEST_F(RiskEngineTest, SideDoesNotAffectOutcome) {
    auto r_buy  = risk.check_order(Side::Buy,  5000, 100);
    auto r_sell = risk.check_order(Side::Sell, 5000, 100);
    EXPECT_EQ(r_buy,  RiskResult::Approved);
    EXPECT_EQ(r_sell, RiskResult::Approved);
}

TEST_F(RiskEngineTest, ZeroPriceNotRejectedByNotionalCheck) {
    // Market orders have price=0; notional check should not reject on zero price
    auto r = risk.check_order(Side::Buy, 0, 500);
    EXPECT_EQ(r, RiskResult::Approved);
}
