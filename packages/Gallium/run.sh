#!/usr/bin/env bash
set -e

BUILD_DIR="build"

# Software rendering
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export WLR_RENDERER_ALLOW_SOFTWARE=1
export XDG_RUNTIME_DIR=/tmp/xdg-run-$$
mkdir -p "$XDG_RUNTIME_DIR"

# Setup Meson
if [ ! -f "$BUILD_DIR/build.ninja" ]; then
    meson setup "$BUILD_DIR"
fi

# Build
ninja -C "$BUILD_DIR"

# Run
echo "✅ Launching Galium-vanilla compositor"
"$BUILD_DIR/galium-vanilla"
