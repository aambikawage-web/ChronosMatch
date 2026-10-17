cmake_minimum_required(VERSION 3.20)
project(ChronosX
    VERSION 1.0.0
    DESCRIPTION "Low-Latency HFT Matching Engine Simulator"
    LANGUAGES CXX
)

# ============================================================
# C++20 Standard
# ============================================================
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ============================================================
# Options
# ============================================================
option(BUILD_TESTING    "Build unit tests"       ON)
option(BUILD_BENCHMARKS "Build micro-benchmarks" ON)

# ============================================================
# Dependencies — fetched BEFORE any compile flags so that
# FetchContent targets do NOT inherit our strict warnings.
# ============================================================
include(cmake/Dependencies.cmake)

# ============================================================
# Per-project warning flags (applied only to our targets)
# ============================================================
if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
    set(CHRONOSX_WARN_FLAGS
        -Wall -Wextra -Wpedantic
        -Wshadow -Wconversion -Wsign-conversion
    )
    set(CHRONOSX_OPT_FLAGS -O3 -march=native)
    if(CMAKE_BUILD_TYPE STREQUAL "Debug")
        set(CHRONOSX_SAN_FLAGS -g -fsanitize=address,undefined)
        set(CHRONOSX_SAN_LINK  -fsanitize=address,undefined)
    endif()
elseif(MSVC)
    set(CHRONOSX_WARN_FLAGS /W4 /WX /permissive- /Zc:__cplusplus /utf-8)
    set(CHRONOSX_OPT_FLAGS  /O2)
endif()

# ============================================================
# Helper: apply our flags to a target without polluting deps
# ============================================================
function(chronosx_set_flags target)
    target_compile_options(${target} PRIVATE
        ${CHRONOSX_OPT_FLAGS}
        ${CHRONOSX_WARN_FLAGS}
        ${CHRONOSX_SAN_FLAGS}
    )
    if(CHRONOSX_SAN_LINK)
        target_link_options(${target} PRIVATE ${CHRONOSX_SAN_LINK})
    endif()
endfunction()

# ============================================================
# Core Library (chronosx_lib)
# ============================================================
add_library(chronosx_lib STATIC
    src/order_book.cpp
    src/matching_engine.cpp
    src/oms.cpp
    src/risk_engine.cpp
    src/simulator.cpp
)

target_include_directories(chronosx_lib PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

target_compile_features(chronosx_lib PUBLIC cxx_std_20)
chronosx_set_flags(chronosx_lib)

# ============================================================
# Simulation Executable (chronosx_sim)
# ============================================================
add_executable(chronosx_sim src/main.cpp)
target_link_libraries(chronosx_sim PRIVATE chronosx_lib)
chronosx_set_flags(chronosx_sim)

# ============================================================
# Tests
# ============================================================
if(BUILD_TESTING)
    enable_testing()
    add_subdirectory(tests)
endif()

# ============================================================
# Benchmarks
# ============================================================
if(BUILD_BENCHMARKS)
    add_subdirectory(benchmarks)
endif()
