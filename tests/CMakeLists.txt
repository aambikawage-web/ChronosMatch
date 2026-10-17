add_executable(chronosx_tests
    test_types.cpp
    test_object_pool.cpp
    test_spsc_buffer.cpp
    test_order_book.cpp
    test_matching_engine.cpp
    test_oms.cpp
    test_risk_engine.cpp
)

target_link_libraries(chronosx_tests
    PRIVATE
        chronosx_lib
        GTest::gtest_main
)

target_compile_features(chronosx_tests PRIVATE cxx_std_20)
chronosx_set_flags(chronosx_tests)

include(GoogleTest)
gtest_discover_tests(chronosx_tests)
