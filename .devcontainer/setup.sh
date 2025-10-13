#!/bin/bash
set -e

echo "🌌 Setting up Galactica OS development environment..."

# Update system
pacman -Syu --noconfirm

# Install base development tools
pacman -S --noconfirm \
  base-devel \
  git \
  vim \
  neovim \
  curl \
  wget \
  cmake \
  ninja \
  pkgconf

# Install Rust (if not already installed by feature)
if ! command -v cargo &> /dev/null; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source $HOME/.cargo/env
fi

# Install Rust tools
cargo install cargo-edit cargo-watch cargo-expand

# Install Xen development libs (headers only, can't run Xen in container)
pacman -S --noconfirm \
  qemu-base \
  libvirt

# Install Wayland development libs
pacman -S --noconfirm \
  wayland \
  wayland-protocols \
  mesa \
  libxkbcommon \
  pixman \
  libinput \
  libdrm

# Install documentation tools
pacman -S --noconfirm \
  mdbook \
  graphviz

# Install archiso (for building ISOs later)
pacman -S --noconfirm archiso

# Setup git (if not configured)
if [ -z "$(git config --global user.name)" ]; then
    echo "⚠️  Configure git:"
    echo "    git config --global user.name 'Your Name'"
    echo "    git config --global user.email 'your@email.com'"
fi

# Create workspace structure
mkdir -p ~/workspace/{build,docs,tests}

# Install pre-commit hooks
cat > .git/hooks/pre-commit << 'HOOK'
#!/bin/bash
# Run cargo check before commit
if [ -d "packages/galactica-vmd" ]; then
    cd packages/galactica-vmd && cargo check || exit 1
fi
if [ -d "packages/galactica-compositor" ]; then
    cd packages/galactica-compositor && cargo check || exit 1
fi
HOOK
chmod +x .git/hooks/pre-commit

echo "✅ Development environment ready!"
echo ""
echo "📚 Next steps:"
echo "  1. cd packages/galactica-vmd && cargo init"
echo "  2. Start building!"
echo ""
echo "📖 Documentation:"
echo "  - Run 'make docs' to build documentation"
echo "  - Run 'make test' to run tests"