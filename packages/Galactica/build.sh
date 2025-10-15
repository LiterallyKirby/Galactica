#!/bin/bash
set -e

PROJECT_NAME="gallium"
BUILD_DIR="build"
INSTALL_PREFIX="${INSTALL_PREFIX:-.}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Building ${PROJECT_NAME}...${NC}"

# Check dependencies
check_deps() {
    local missing=0
    local deps=("cmake" "pkg-config" "wayland-scanner" "gcc")
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            echo -e "${RED}Error: $dep not found${NC}"
            missing=$((missing + 1))
        fi
    done
    
    if [ $missing -gt 0 ]; then
        echo -e "${RED}Missing $missing dependencies${NC}"
        exit 1
    fi
}

# Create build directory
setup_build() {
    if [ ! -d "$BUILD_DIR" ]; then
        mkdir -p "$BUILD_DIR"
        echo -e "${GREEN}Created build directory${NC}"
    fi
    
    cd "$BUILD_DIR"
}

# Configure
configure() {
    echo -e "${YELLOW}Configuring...${NC}"
    cmake -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" ..
}

# Build
build() {
    echo -e "${YELLOW}Compiling...${NC}"
    make -j"$(nproc)"
}

# Install
install_binary() {
    echo -e "${YELLOW}Installing...${NC}"
    make install
}

# Run
run() {
    echo -e "${GREEN}Build successful!${NC}"
    echo -e "${YELLOW}To run:${NC}"
    echo "  ./$BUILD_DIR/$PROJECT_NAME"
}

# Main
check_deps
setup_build
configure
build
install_binary
run
