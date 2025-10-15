cmake_minimum_required(VERSION 3.10)
project(gallium C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra -Wpedantic -DWLR_USE_UNSTABLE")
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Find dependencies
find_package(PkgConfig REQUIRED)
pkg_check_modules(WLR REQUIRED wlroots-0.19)
pkg_check_modules(WAYLAND_SERVER REQUIRED wayland-server)
pkg_check_modules(WAYLAND_PROTOS REQUIRED wayland-protocols)
pkg_check_modules(LIBINPUT REQUIRED libinput)
pkg_check_modules(XKBCOMMON REQUIRED xkbcommon)

# Find Xen libraries (they don't have .pc files, use find_library)
find_library(XENCTRL_LIB NAMES xenctrl REQUIRED)
find_library(XENEVTCHN_LIB NAMES xenevtchn REQUIRED)
find_library(XENSTORE_LIB NAMES xenstore REQUIRED)
find_path(XEN_INCLUDE_DIR NAMES xenctrl.h PATH_SUFFIXES xen)

if(NOT XEN_INCLUDE_DIR)
    message(FATAL_ERROR "Xen headers not found")
endif()

message(STATUS "Found libxenctrl: ${XENCTRL_LIB}")
message(STATUS "Found libxenevtchn: ${XENEVTCHN_LIB}")
message(STATUS "Found libxenstore: ${XENSTORE_LIB}")
message(STATUS "Found Xen headers: ${XEN_INCLUDE_DIR}")

# Find wayland-scanner
find_program(WAYLAND_SCANNER wayland-scanner REQUIRED)

# Get wayland-protocols datadir
execute_process(
    COMMAND pkg-config --variable=pkgdatadir wayland-protocols
    OUTPUT_VARIABLE WAYLAND_PROTOS_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

# Generate xdg-shell protocol files
add_custom_command(
    OUTPUT xdg-shell-protocol.h xdg-shell-protocol.c
    COMMAND ${WAYLAND_SCANNER} server-header 
        ${WAYLAND_PROTOS_DIR}/stable/xdg-shell/xdg-shell.xml
        ${CMAKE_CURRENT_BINARY_DIR}/xdg-shell-protocol.h
    COMMAND ${WAYLAND_SCANNER} private-code
        ${WAYLAND_PROTOS_DIR}/stable/xdg-shell/xdg-shell.xml
        ${CMAKE_CURRENT_BINARY_DIR}/xdg-shell-protocol.c
    DEPENDS ${WAYLAND_PROTOS_DIR}/stable/xdg-shell/xdg-shell.xml
    COMMENT "Generating xdg-shell protocol"
)

# Add executable (include xen.c if you have it)
add_executable(gallium
    src/main.c
    src/xen.c
    ${CMAKE_CURRENT_BINARY_DIR}/xdg-shell-protocol.c
)

# Include directories
target_include_directories(gallium PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_BINARY_DIR}
    ${WLR_INCLUDE_DIRS}
    ${WAYLAND_SERVER_INCLUDE_DIRS}
    ${LIBINPUT_INCLUDE_DIRS}
    ${XKBCOMMON_INCLUDE_DIRS}
    ${XEN_INCLUDE_DIR}
)

# Link libraries
target_link_libraries(gallium PRIVATE
    ${WLR_LIBRARIES}
    ${WAYLAND_SERVER_LIBRARIES}
    ${LIBINPUT_LIBRARIES}
    ${XKBCOMMON_LIBRARIES}
    ${XENCTRL_LIB}
    ${XENEVTCHN_LIB}
    ${XENSTORE_LIB}
)

# Installation
install(TARGETS gallium DESTINATION bin)
