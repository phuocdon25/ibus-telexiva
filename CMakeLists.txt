# SPDX-License-Identifier: GPL-3.0-or-later
cmake_minimum_required(VERSION 3.25)
project(ibus-telexiva VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(TELEXIVA_BUILD_TESTS "Build tests" ON)
option(TELEXIVA_WARNINGS_AS_ERRORS "Treat compiler warnings as errors" ON)

function(telexiva_warnings target)
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
    if(TELEXIVA_WARNINGS_AS_ERRORS)
        target_compile_options(${target} PRIVATE -Werror)
    endif()
endfunction()

# --- Core: quy tắc Telex, không phụ thuộc IBus (NFR-005) --------------------
add_library(telexiva_core STATIC src/core/telex.cpp src/core/composer.cpp)
target_include_directories(telexiva_core PUBLIC src/core/include)
telexiva_warnings(telexiva_core)

# --- Công cụ dòng lệnh: thử nhanh và so khớp với prototype Python -----------
add_executable(telexiva-telex tools/telex_cli.cpp)
target_link_libraries(telexiva-telex PRIVATE telexiva_core)
telexiva_warnings(telexiva-telex)

# --- Tests -------------------------------------------------------------------
if(TELEXIVA_BUILD_TESTS)
    enable_testing()
    find_package(Catch2 3 REQUIRED)
    include(Catch)

    add_executable(telexiva_core_tests tests/core/test_telex.cpp tests/core/test_composer.cpp)
    target_link_libraries(telexiva_core_tests PRIVATE telexiva_core Catch2::Catch2WithMain)
    target_compile_definitions(telexiva_core_tests PRIVATE
        TELEXIVA_CASES_TSV="${CMAKE_SOURCE_DIR}/tests/data/telex_cases.tsv")
    telexiva_warnings(telexiva_core_tests)
    catch_discover_tests(telexiva_core_tests)

    # So khớp C++ với prototype Python trên hàng trăm nghìn chuỗi phím.
    find_package(Python3 COMPONENTS Interpreter)
    if(Python3_FOUND)
        add_test(NAME parity_with_python_prototype
                 COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tests/parity/parity_check.py
                         $<TARGET_FILE:telexiva-telex>)
        # Chạy lâu (~1 phút): bỏ qua khi test nhanh bằng `ctest -LE slow`.
        set_tests_properties(parity_with_python_prototype PROPERTIES LABELS slow TIMEOUT 900)
    endif()
endif()
