cmake_minimum_required(VERSION 3.15)

project(PRTOfflineReference LANGUAGES CXX)

find_package(Threads REQUIRED)
include(CTest)

add_executable(prt_offline_reference src/main.cpp)
target_compile_features(prt_offline_reference PRIVATE cxx_std_11)
target_link_libraries(prt_offline_reference PRIVATE Threads::Threads)

if(BUILD_TESTING)
    add_test(NAME offline_prt_alignment COMMAND prt_offline_reference --self-test)
endif()

if(MSVC)
    target_compile_options(prt_offline_reference PRIVATE /O2 /W4)
else()
    target_compile_options(prt_offline_reference PRIVATE -O3 -Wall -Wextra -Wpedantic)
endif()

install(TARGETS prt_offline_reference RUNTIME DESTINATION bin)
