#!/bin/bash
# setup-build-env.sh - Run this first

# Create workspace
mkdir -p ~/paranoid-os/{build,src,output,tools}
cd ~/paranoid-os

# Install build dependencies (on your current Linux machine)
sudo apt update
sudo apt install -y \
    build-essential \
    git \
    wget \
    curl \
    libncurses-dev \
    bison \
    flex \
    libssl-dev \
    libelf-dev \
    bc \
    rsync \
    cpio \
    unzip \
    python3 \
    qemu-system-x86 \
    qemu-utils \
    ovmf \
    gpg

# Verify QEMU works
qemu-system-x86_64 --version

# Set up GPG for verification
gpg --keyserver hkps://keyserver.ubuntu.com --recv-keys \
    ABAF11C65A2970B130ABE3C479BE3E4300411886  # Linus Torvalds
    647F28654894E3BD457199BE38DBBDC86092693E  # Greg KH

echo "✅ Build environment ready"
