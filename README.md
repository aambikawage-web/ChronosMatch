# ChronosX — Low-Latency HFT Matching Engine Simulator

> A simulation-mode, cache-optimised C++20 limit order book and matching engine implementing price-time priority (FIFO), an SPSC ring buffer, a pre-allocated object pool, and a pre-trade risk engine.

## Features

- C++20 and CMake
- Limit and market order simulation
- Integer-based price ticks
- Limit order book with price-time priority
- Order cancellation and partial fills
- Pre-allocated object pool
- Single-producer, single-consumer ring buffer
- Pre-trade risk checks
- Automated tests and microbenchmarks
- GitHub Actions CI

*Feature availability and test coverage must be verified against the implementation before claiming everything is complete.*

## Project Structure

```text
ChronosMatch-Zero-Copy-High-Frequency-Trading-Engine/
├── .github/
│   └── workflows/
├── benchmarks/
├── build/
├── cmake/
├── docs/
├── include/
│   └── chronosx/
├── src/
├── tests/
├── .gitignore
├── CMakeLists.txt
└── README.md
```

## Build and Test

Prerequisites: a compatible C++20 compiler and CMake.

```bash
cmake -B build -DBUILD_TESTING=ON
cmake --build build --config Release
ctest --test-dir build --output-on-failure -C Release
```

Check the CMake configuration for the exact supported compiler versions and optional benchmark dependencies.

## Project Goals

- Implement a deterministic matching engine.
- Enforce price-time priority.
- Validate order and risk limits.
- Test cancellation, partial fills, and edge cases.
- Measure throughput and latency using reproducible benchmarks.
- Document architectural trade-offs and known limitations.

## Safety

This is an educational trading-engine simulator. It is not connected to a live exchange and must not be treated as production trading infrastructure.

## Attribution

This project uses the following repository as a reference for architectural study:

https://github.com/ameetairodagi6-oss/chronosmatch-hft-engine

The implementation, licensing obligations, and attribution requirements should be reviewed before reusing any third-party code.

## License

See the repository's `LICENSE` file for the applicable license terms.