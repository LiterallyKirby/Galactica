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
pkg_check_modules(XENCTRL REQUIRED xenctrl)
pkg_check_modules(XENSTORE REQUIRED xenstore)

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

# Add executable
add_executable(gallium
    src/main.c
    ${CMAKE_CURRENT_BINARY_DIR}/xdg-shell-protocol.c
)

# Include directories
target_include_directories(gallium PRIVATE
    ${CMAKE_CURRENT_BINARY_DIR}
    ${WLR_INCLUDE_DIRS}
    ${WAYLAND_SERVER_INCLUDE_DIRS}
    ${LIBINPUT_INCLUDE_DIRS}
    ${XKBCOMMON_INCLUDE_DIRS}
)

# Link libraries
target_link_libraries(gallium PRIVATE
    ${WLR_LIBRARIES}
    ${WAYLAND_SERVER_LIBRARIES}
    ${LIBINPUT_LIBRARIES}
    ${XKBCOMMON_LIBRARIES}
)

# Installation
install(TARGETS gallium DESTINATION bin)
