add_executable(chronosx_bench
    bench_matching_engine.cpp
)

target_link_libraries(chronosx_bench
    PRIVATE
        chronosx_lib
        benchmark::benchmark_main
)

target_compile_features(chronosx_bench PRIVATE cxx_std_20)
chronosx_set_flags(chronosx_bench)
