/**
 * @file memory_pool.hpp
 * @brief Fixed-capacity, O(1) object pool with an intrusive free-list.
 *
 * ## Design Rationale
 * Standard containers like std::deque or std::list call malloc/free on every
 * node insertion/removal, causing unpredictable latency spikes on the hot
 * trading path (OS jitter, TLB pressure, cache thrashing).
 *
 * ObjectPool pre-allocates a contiguous array of T at construction time and
 * manages recycling with a singly-linked free-list embedded inside unused
 * slots. This gives:
 *   - O(1) allocation   (pop the free-list head)
 *   - O(1) deallocation (push to the free-list head)
 *   - Zero heap calls after construction
 *   - Cache-friendly: all objects live in a single contiguous block
 *
 * ## Constraints
 *   - Not thread-safe. The owning engine thread is the sole user.
 *   - Capacity is fixed at compile time (template parameter).
 *   - T must be default-constructible.
 *   - alloc() returns nullptr when the pool is exhausted.
 *
 * ## Index vs. Pointer
 * The free-list is stored as uint32_t indices, not raw pointers, so the pool
 * array can be embedded in any struct without relocation concerns.
 */

#pragma once

#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <new>
#include <type_traits>

namespace chronosx {

template <typename T, std::size_t Capacity>
class ObjectPool {
    static_assert(Capacity > 0, "Capacity must be > 0");
    static_assert(Capacity <= UINT32_MAX, "Capacity must fit in uint32_t");
    static_assert(std::is_default_constructible_v<T>,
                  "T must be default-constructible");

public:
    ObjectPool() {
        // Build the initial free-list: 0 → 1 → 2 → … → Capacity-1 → kEnd
        for (uint32_t i = 0; i < static_cast<uint32_t>(Capacity) - 1; ++i) {
            free_next_[i] = i + 1;
        }
        free_next_[Capacity - 1] = kEnd;
        free_head_ = 0;
        allocated_count_ = 0;
    }

    // Non-copyable, non-movable (owns fixed memory).
    ObjectPool(const ObjectPool&)            = delete;
    ObjectPool& operator=(const ObjectPool&) = delete;
    ObjectPool(ObjectPool&&)                 = delete;
    ObjectPool& operator=(ObjectPool&&)      = delete;

    // ----------------------------------------------------------------
    // alloc() — O(1)
    // Returns a pointer to an initialised slot, or nullptr if full.
    // The returned object is placement-new'd (constructor is called).
    // ----------------------------------------------------------------
    [[nodiscard]] T* alloc() noexcept {
        if (free_head_ == kEnd) [[unlikely]] {
            return nullptr;  // Pool exhausted
        }
        const uint32_t idx = free_head_;
        free_head_ = free_next_[idx];
        ++allocated_count_;
        T* obj = &storage_[idx];
        new (obj) T{};  // placement-new: call default constructor
        return obj;
    }

    // ----------------------------------------------------------------
    // free(ptr) — O(1)
    // Returns the slot at ptr back to the free-list.
    // Calls the destructor.
    // Precondition: ptr must have been returned by alloc() on this pool.
    // ----------------------------------------------------------------
    void free(T* ptr) noexcept {
        assert(ptr != nullptr);
        const uint32_t idx = index_of(ptr);
        assert(idx < Capacity);
        ptr->~T();                  // destructor
        free_next_[idx] = free_head_;
        free_head_ = idx;
        --allocated_count_;
    }

    // ----------------------------------------------------------------
    // index_of(ptr) — O(1), useful for intrusive linked-lists
    // ----------------------------------------------------------------
    [[nodiscard]] uint32_t index_of(const T* ptr) const noexcept {
        const auto diff = ptr - storage_.data();
        assert(diff >= 0 && static_cast<std::size_t>(diff) < Capacity);
        return static_cast<uint32_t>(diff);
    }

    // ----------------------------------------------------------------
    // at(idx) — O(1) random access by pool index
    // ----------------------------------------------------------------
    [[nodiscard]] T& at(uint32_t idx) noexcept {
        assert(idx < Capacity);
        return storage_[idx];
    }

    [[nodiscard]] const T& at(uint32_t idx) const noexcept {
        assert(idx < Capacity);
        return storage_[idx];
    }

    // ----------------------------------------------------------------
    // Capacity / usage queries
    // ----------------------------------------------------------------
    [[nodiscard]] static constexpr std::size_t capacity() noexcept { return Capacity; }
    [[nodiscard]] std::size_t allocated() const noexcept { return allocated_count_; }
    [[nodiscard]] std::size_t available() const noexcept { return Capacity - allocated_count_; }
    [[nodiscard]] bool        full()      const noexcept { return free_head_ == kEnd; }
    [[nodiscard]] bool        empty()     const noexcept { return allocated_count_ == 0; }

private:
    static constexpr uint32_t kEnd = UINT32_MAX;  // Sentinel: end of free-list

    // Contiguous storage for T objects.
    // alignas(alignof(T)) ensures each slot is properly aligned.
    alignas(alignof(T)) std::array<T, Capacity> storage_{};

    // Intrusive free-list: free_next_[i] is the index of the next free slot
    // after slot i, or kEnd if it's the last free slot.
    std::array<uint32_t, Capacity> free_next_{};

    uint32_t    free_head_       {0};
    std::size_t allocated_count_ {0};
};

} // namespace chronosx
