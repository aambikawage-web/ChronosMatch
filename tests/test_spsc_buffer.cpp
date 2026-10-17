#include <gtest/gtest.h>
#include "chronosx/spsc_ring_buffer.hpp"

#include <thread>
#include <vector>
#include <numeric>
#include <atomic>

using namespace chronosx;

// ---- Single-threaded correctness ----

TEST(SpscRingBuffer, InitiallyEmpty) {
    SpscRingBuffer<int, 8> buf;
    EXPECT_TRUE(buf.empty());
    EXPECT_EQ(buf.size_approx(), 0u);
}

TEST(SpscRingBuffer, PushAndPop) {
    SpscRingBuffer<int, 8> buf;
    ASSERT_TRUE(buf.push(42));
    int val = 0;
    ASSERT_TRUE(buf.pop(val));
    EXPECT_EQ(val, 42);
    EXPECT_TRUE(buf.empty());
}

TEST(SpscRingBuffer, FillsToCapacity) {
    SpscRingBuffer<int, 8> buf;  // usable capacity = 8 slots
    for (int i = 0; i < 8; ++i) {
        EXPECT_TRUE(buf.push(i));
    }
    // 9th push should fail (full)
    EXPECT_FALSE(buf.push(99));
}

TEST(SpscRingBuffer, PopFromEmptyReturnsFalse) {
    SpscRingBuffer<int, 4> buf;
    int val = 0;
    EXPECT_FALSE(buf.pop(val));
}

TEST(SpscRingBuffer, FifoOrdering) {
    SpscRingBuffer<int, 16> buf;
    for (int i = 0; i < 10; ++i) ASSERT_TRUE(buf.push(i));
    for (int i = 0; i < 10; ++i) {
        int val = -1;
        ASSERT_TRUE(buf.pop(val));
        EXPECT_EQ(val, i);
    }
}

TEST(SpscRingBuffer, WrapAround) {
    SpscRingBuffer<int, 4> buf;   // usable = 3
    ASSERT_TRUE(buf.push(1));
    ASSERT_TRUE(buf.push(2));
    int v = 0;
    ASSERT_TRUE(buf.pop(v));  // pop 1
    ASSERT_TRUE(buf.push(3)); // should reuse slot
    ASSERT_TRUE(buf.push(4)); // still room for one more
    ASSERT_TRUE(buf.pop(v)); EXPECT_EQ(v, 2);
    ASSERT_TRUE(buf.pop(v)); EXPECT_EQ(v, 3);
    ASSERT_TRUE(buf.pop(v)); EXPECT_EQ(v, 4);
    EXPECT_TRUE(buf.empty());
}

// ---- Multi-threaded producer/consumer ----

TEST(SpscRingBuffer, ProducerConsumerThread) {
    constexpr int kCount = 100'000;
    SpscRingBuffer<int, 4096> buf;
    std::atomic<bool> done{false};
    std::vector<int>  received;
    received.reserve(kCount);

    std::thread producer([&]() {
        for (int i = 0; i < kCount; ++i) {
            while (!buf.push(i)) { /* spin */ }
        }
        done.store(true, std::memory_order_release);
    });

    int val = 0;
    while (!done.load(std::memory_order_acquire) || !buf.empty()) {
        if (buf.pop(val)) received.push_back(val);
    }
    while (buf.pop(val)) received.push_back(val);

    producer.join();

    ASSERT_EQ(static_cast<int>(received.size()), kCount);
    for (int i = 0; i < kCount; ++i) {
        EXPECT_EQ(received[i], i) << "Mismatch at index " << i;
    }
}

TEST(SpscRingBuffer, CapacityQuery) {
    SpscRingBuffer<double, 64> buf;
    EXPECT_EQ(buf.capacity(), 64u);  // Full Capacity
}
