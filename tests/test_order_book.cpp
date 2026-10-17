#include <gtest/gtest.h>
#include "chronosx/order_book.hpp"
#include "chronosx/memory_pool.hpp"

using namespace chronosx;

// ---- Test fixture ----

class OrderBookTest : public ::testing::Test {
protected:
    OrderBook::Pool pool;
    OrderBook       book{pool};

    // Helper: allocate an order in the pool and return its index
    uint32_t make_order(OrderId id, Side side, Price price, Quantity qty) {
        Order* o = pool.alloc();
        if (!o) throw std::runtime_error("pool exhausted in test");
        o->order_id      = id;
        o->side          = side;
        o->price         = price;
        o->initial_qty   = qty;
        o->remaining_qty = qty;
        o->seq_num       = id;  // reuse id as seq for simplicity
        o->type          = OrderType::Limit;
        o->status        = OrderStatus::New;
        o->prev_idx      = kNullIdx;
        o->next_idx      = kNullIdx;
        return pool.index_of(o);
    }
};

// ---- Basic add / best price ----

TEST_F(OrderBookTest, EmptyBookHasNoBestBidAsk) {
    EXPECT_FALSE(book.best_bid().has_value());
    EXPECT_FALSE(book.best_ask().has_value());
    EXPECT_FALSE(book.spread().has_value());
}

TEST_F(OrderBookTest, AddBidUpdatesbestBid) {
    book.add_order(make_order(1, Side::Buy, 1000, 10));
    ASSERT_TRUE(book.best_bid().has_value());
    EXPECT_EQ(*book.best_bid(), Price{1000});
}

TEST_F(OrderBookTest, AddAskUpdatesbestAsk) {
    book.add_order(make_order(1, Side::Sell, 1050, 10));
    ASSERT_TRUE(book.best_ask().has_value());
    EXPECT_EQ(*book.best_ask(), Price{1050});
}

TEST_F(OrderBookTest, BidSideSortedDescending) {
    book.add_order(make_order(1, Side::Buy, 1000, 10));
    book.add_order(make_order(2, Side::Buy, 1020, 20));
    book.add_order(make_order(3, Side::Buy,  980, 30));
    // Best bid should be the highest: 1020
    EXPECT_EQ(*book.best_bid(), Price{1020});
}

TEST_F(OrderBookTest, AskSideSortedAscending) {
    book.add_order(make_order(1, Side::Sell, 1050, 10));
    book.add_order(make_order(2, Side::Sell, 1030, 20));
    book.add_order(make_order(3, Side::Sell, 1070, 30));
    // Best ask should be the lowest: 1030
    EXPECT_EQ(*book.best_ask(), Price{1030});
}

TEST_F(OrderBookTest, SpreadCalculation) {
    book.add_order(make_order(1, Side::Buy,  1000, 10));
    book.add_order(make_order(2, Side::Sell, 1050, 10));
    ASSERT_TRUE(book.spread().has_value());
    EXPECT_EQ(*book.spread(), int64_t{50});  // 1050 - 1000
}

// ---- Qty at level ----

TEST_F(OrderBookTest, BidQtyAtLevel) {
    book.add_order(make_order(1, Side::Buy, 1000, 10));
    book.add_order(make_order(2, Side::Buy, 1000, 30));
    EXPECT_EQ(book.bid_qty_at(1000), Quantity{40});
    EXPECT_EQ(book.bid_qty_at(999),  Quantity{0});
}

TEST_F(OrderBookTest, AskQtyAtLevel) {
    book.add_order(make_order(1, Side::Sell, 1050, 15));
    book.add_order(make_order(2, Side::Sell, 1050, 25));
    EXPECT_EQ(book.ask_qty_at(1050), Quantity{40});
}

// ---- Active order count ----

TEST_F(OrderBookTest, ActiveOrderCount) {
    EXPECT_EQ(book.active_order_count(), 0u);
    book.add_order(make_order(1, Side::Buy,  1000, 10));
    book.add_order(make_order(2, Side::Sell, 1050, 10));
    EXPECT_EQ(book.active_order_count(), 2u);
}

// ---- Cancel ----

TEST_F(OrderBookTest, CancelExistingOrder) {
    book.add_order(make_order(1, Side::Buy, 1000, 10));
    EXPECT_TRUE(book.cancel_order(1));
    EXPECT_EQ(book.active_order_count(), 0u);
    EXPECT_FALSE(book.best_bid().has_value());
}

TEST_F(OrderBookTest, CancelNonExistentOrderReturnsFalse) {
    EXPECT_FALSE(book.cancel_order(999));
}

TEST_F(OrderBookTest, CancelRemovesEmptyPriceLevel) {
    book.add_order(make_order(1, Side::Buy, 1000, 10));
    book.cancel_order(1);
    EXPECT_EQ(book.bid_levels(), 0u);
}

TEST_F(OrderBookTest, CancelOneOfTwoOrdersAtSameLevel) {
    book.add_order(make_order(1, Side::Buy, 1000, 10));
    book.add_order(make_order(2, Side::Buy, 1000, 20));
    EXPECT_TRUE(book.cancel_order(1));
    EXPECT_EQ(book.bid_qty_at(1000), Quantity{20});
    EXPECT_EQ(book.bid_levels(), 1u);
}

TEST_F(OrderBookTest, CancelPreservesOtherLevels) {
    book.add_order(make_order(1, Side::Buy, 1000, 10));
    book.add_order(make_order(2, Side::Buy, 990,  20));
    EXPECT_TRUE(book.cancel_order(1));
    EXPECT_EQ(*book.best_bid(), Price{990});
    EXPECT_EQ(book.bid_levels(), 1u);
}

// ---- Prune ----

TEST_F(OrderBookTest, PruneEmptyBidLevelRemovesIt) {
    book.add_order(make_order(1, Side::Buy, 1000, 10));
    // Manually empty the level qty (simulating a fill)
    auto* lv = book.best_bid_level();
    ASSERT_NE(lv, nullptr);
    lv->total_qty = 0;
    lv->head_idx  = kNullIdx;
    lv->tail_idx  = kNullIdx;
    book.prune_empty_bid(1000);
    EXPECT_FALSE(book.best_bid().has_value());
}

// ---- is_empty ----

TEST_F(OrderBookTest, IsEmptyWhenNoOrders) {
    EXPECT_TRUE(book.is_empty());
    book.add_order(make_order(1, Side::Buy, 1000, 10));
    EXPECT_FALSE(book.is_empty());
}
