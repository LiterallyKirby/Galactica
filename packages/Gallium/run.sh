#!/usr/bin/env bash
set -euo pipefail


echo "----------------------------------"
echo "         Gallium Start!           " 
echo "----------------------------------"

# Check dependencies
command -v cargo >/dev/null 2>&1 || {
    echo "❌ Cargo not found. Install Rust first."
    exit 1
}

command -v glxinfo >/dev/null 2>&1 || {
    echo "⚠️  glxinfo not found. Install mesa-utils for driver checks."
}

# Force software rendering
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export LIBGL_DEBUG=verbose
export RUST_BACKTRACE=1

# Optional: more Mesa debug output
# export MESA_DEBUG=1

# Clean + build release
echo "🧹 Cleaning build..."
cargo clean

echo "🛠️  Building Gallium compositor..."
cargo build --release

echo "🧪 Checking Mesa renderer..."
if command -v glxinfo >/dev/null 2>&1; then
    glxinfo | grep "OpenGL renderer" || echo "⚠️  Could not verify renderer."
fi

echo "🔥 Running compositor..."
echo
./target/release/Galium 2>&1 | tee gallium.log

echo
echo "----------------------------------"
echo " Gallium compositor exited."
echo " Log saved to gallium.log"
echo "----------------------------------"
