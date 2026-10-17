#include <gtest/gtest.h>
#include "chronosx/memory_pool.hpp"
#include "chronosx/order.hpp"

using namespace chronosx;

// Small pool for fast tests
using SmallPool = ObjectPool<Order, 8>;

TEST(ObjectPool, InitialCapacity) {
    SmallPool pool;
    EXPECT_EQ(pool.capacity(), 8u);
    EXPECT_EQ(pool.allocated(), 0u);
    EXPECT_EQ(pool.available(), 8u);
    EXPECT_FALSE(pool.full());
    EXPECT_TRUE(pool.empty());
}

TEST(ObjectPool, SingleAllocAndFree) {
    SmallPool pool;
    Order* o = pool.alloc();
    ASSERT_NE(o, nullptr);
    EXPECT_EQ(pool.allocated(), 1u);
    EXPECT_EQ(pool.available(), 7u);

    pool.free(o);
    EXPECT_EQ(pool.allocated(), 0u);
    EXPECT_EQ(pool.available(), 8u);
}

TEST(ObjectPool, AllocsUntilFull) {
    SmallPool pool;
    Order* ptrs[8];
    for (int i = 0; i < 8; ++i) {
        ptrs[i] = pool.alloc();
        ASSERT_NE(ptrs[i], nullptr);
    }
    EXPECT_TRUE(pool.full());

    // One more alloc should return nullptr
    Order* overflow = pool.alloc();
    EXPECT_EQ(overflow, nullptr);

    // Free one — should succeed
    pool.free(ptrs[0]);
    EXPECT_FALSE(pool.full());
    EXPECT_EQ(pool.available(), 1u);
}

TEST(ObjectPool, IndexOfIsConsistent) {
    SmallPool pool;
    Order* o = pool.alloc();
    ASSERT_NE(o, nullptr);
    uint32_t idx = pool.index_of(o);
    EXPECT_EQ(&pool.at(idx), o);
}

TEST(ObjectPool, FreeListReusesSlotsInLIFOOrder) {
    SmallPool pool;
    Order* a = pool.alloc();
    Order* b = pool.alloc();
    uint32_t idx_a = pool.index_of(a);
    uint32_t idx_b = pool.index_of(b);

    pool.free(b);
    pool.free(a);

    // Next two allocs should reuse a then b (LIFO free-list)
    Order* a2 = pool.alloc();
    Order* b2 = pool.alloc();
    EXPECT_EQ(pool.index_of(a2), idx_a);
    EXPECT_EQ(pool.index_of(b2), idx_b);
}

TEST(ObjectPool, AllocReturnsInitialisedObject) {
    SmallPool pool;
    Order* o = pool.alloc();
    ASSERT_NE(o, nullptr);
    // Default-constructed order should have sentinel values
    EXPECT_EQ(o->order_id, kInvalidOrderId);
    EXPECT_EQ(o->prev_idx, kNullIdx);
    EXPECT_EQ(o->next_idx, kNullIdx);
}

TEST(ObjectPool, LargeCapacity) {
    constexpr std::size_t N = 1024;
    ObjectPool<Order, N> pool;
    EXPECT_EQ(pool.capacity(), N);
    EXPECT_EQ(pool.available(), N);

    std::vector<Order*> ptrs;
    ptrs.reserve(N);
    for (std::size_t i = 0; i < N; ++i) {
        Order* o = pool.alloc();
        ASSERT_NE(o, nullptr);
        ptrs.push_back(o);
    }
    EXPECT_TRUE(pool.full());

    for (Order* o : ptrs) pool.free(o);
    EXPECT_TRUE(pool.empty());
}
