#include <gtest/gtest.h>
#include "chronosx/types.hpp"
#include "chronosx/order.hpp"

using namespace chronosx;

// ---- types.hpp ----

TEST(Types, PriceMultiplierIsCorrect) {
    EXPECT_EQ(kPriceMult, 10000);
}

TEST(Types, InvalidSentinels) {
    EXPECT_EQ(kInvalidOrderId, OrderId{0});
    EXPECT_EQ(kInvalidPrice,   std::numeric_limits<Price>::min());
}

TEST(Types, SideEnumValues) {
    EXPECT_EQ(static_cast<uint8_t>(Side::Buy),  0);
    EXPECT_EQ(static_cast<uint8_t>(Side::Sell), 1);
}

TEST(Types, OrderTypeEnumValues) {
    EXPECT_EQ(static_cast<uint8_t>(OrderType::Limit),  0);
    EXPECT_EQ(static_cast<uint8_t>(OrderType::Market), 1);
}

TEST(Types, OrderStatusEnumValues) {
    EXPECT_EQ(static_cast<uint8_t>(OrderStatus::New),             0);
    EXPECT_EQ(static_cast<uint8_t>(OrderStatus::PartiallyFilled), 1);
    EXPECT_EQ(static_cast<uint8_t>(OrderStatus::Filled),          2);
    EXPECT_EQ(static_cast<uint8_t>(OrderStatus::Cancelled),       3);
    EXPECT_EQ(static_cast<uint8_t>(OrderStatus::Rejected),        4);
}

TEST(Types, TradeEventDefaultInit) {
    TradeEvent t;
    EXPECT_EQ(t.aggressor_id, kInvalidOrderId);
    EXPECT_EQ(t.resting_id,   kInvalidOrderId);
    EXPECT_EQ(t.price,        kInvalidPrice);
    EXPECT_EQ(t.qty,          Quantity{0});
}

// ---- order.hpp ----

TEST(Order, SizeIsExactlySixtyFourBytes) {
    EXPECT_EQ(sizeof(Order), 64u);
}

TEST(Order, AlignmentIsSixtyFour) {
    EXPECT_EQ(alignof(Order), 64u);
}

TEST(Order, DefaultInit) {
    Order o;
    EXPECT_EQ(o.order_id,      kInvalidOrderId);
    EXPECT_EQ(o.price,         kInvalidPrice);
    EXPECT_EQ(o.initial_qty,   Quantity{0});
    EXPECT_EQ(o.remaining_qty, Quantity{0});
    EXPECT_EQ(o.prev_idx,      kNullIdx);
    EXPECT_EQ(o.next_idx,      kNullIdx);
    EXPECT_FALSE(o.is_active());
}

TEST(Order, IsActiveWhenNew) {
    Order o;
    o.status = OrderStatus::New;
    EXPECT_TRUE(o.is_active());
}

TEST(Order, IsActiveWhenPartiallyFilled) {
    Order o;
    o.status = OrderStatus::PartiallyFilled;
    EXPECT_TRUE(o.is_active());
}

TEST(Order, IsNotActiveWhenFilled) {
    Order o;
    o.status = OrderStatus::Filled;
    EXPECT_FALSE(o.is_active());
}

TEST(Order, IsNotActiveWhenCancelled) {
    Order o;
    o.status = OrderStatus::Cancelled;
    EXPECT_FALSE(o.is_active());
}

TEST(Order, FilledQtyCalculation) {
    Order o;
    o.initial_qty   = 100;
    o.remaining_qty = 60;
    EXPECT_EQ(o.filled_qty(), Quantity{40});
}

TEST(Order, IsFullyFilledWhenRemainingZero) {
    Order o;
    o.remaining_qty = 0;
    EXPECT_TRUE(o.is_fully_filled());
}

TEST(Order, NullIdxSentinel) {
    EXPECT_EQ(kNullIdx, UINT32_MAX);
}
