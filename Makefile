.PHONY: all clean test docs build-vmd build-compositor help

# Colors for output
CYAN := \033[0;36m
GREEN := \033[0;32m
RED := \033[0;31m
RESET := \033[0m

all: build-vmd build-compositor

help:
	@echo "$(CYAN)Galactica OS Development$(RESET)"
	@echo ""
	@echo "Available targets:"
	@echo "  $(GREEN)build-vmd$(RESET)        - Build VM manager daemon"
	@echo "  $(GREEN)build-compositor$(RESET) - Build Wayland compositor"
	@echo "  $(GREEN)test$(RESET)             - Run all tests"
	@echo "  $(GREEN)docs$(RESET)             - Build documentation"
	@echo "  $(GREEN)clean$(RESET)            - Clean build artifacts"
	@echo "  $(GREEN)iso$(RESET)              - Build Galactica ISO (requires root)"
	@echo "  $(GREEN)dev-vmd$(RESET)          - Run VM manager in dev mode"
	@echo "  $(GREEN)dev-compositor$(RESET)   - Run compositor in dev mode"

# VM Manager Daemon
build-vmd:
	@echo "$(CYAN)Building galactica-vmd...$(RESET)"
	cd packages/galactica-vmd && cargo build --release
	@echo "$(GREEN)✅ Built: packages/galactica-vmd/target/release/galactica-vmd$(RESET)"

dev-vmd:
	cd packages/galactica-vmd && cargo watch -x 'run'

test-vmd:
	cd packages/galactica-vmd && cargo test

# Compositor
build-compositor:
	@echo "$(CYAN)Building galactica-compositor...$(RESET)"
	cd packages/Gallium && cargo build --release
	@echo "$(GREEN)✅ Built!"

dev-compositor:
	cd packages/Gallium && ./run.sh

test-compositor:
	cd packages/Gallium && cargo test

# All tests
test: test-vmd test-compositor
	@echo "$(GREEN)✅ All tests passed$(RESET)"

# Documentation
docs:
	@echo "$(CYAN)Building documentation...$(RESET)"
	mdbook build docs/
	@echo "$(GREEN)✅ Docs built: docs/book/index.html$(RESET)"

docs-serve:
	mdbook serve docs/ --open

# ISO building (later phase)
iso:
	@echo "$(CYAN)Building Galactica OS ISO...$(RESET)"
	cd iso && sudo mkarchiso -v -w work/ -o out/ .

# Cleanup
clean:
	@echo "$(CYAN)Cleaning build artifacts...$(RESET)"
	cd packages/galactica-vmd && cargo clean
	cd packages/galactica-compositor && cargo clean
	rm -rf docs/book/
	@echo "$(GREEN)✅ Cleaned$(RESET)"

# Initialize projects
init:
	@echo "$(CYAN)Initializing Rust projects...$(RESET)"
	cd packages/galactica-vmd && cargo init --name galactica-vmd
	cd packages/galactica-compositor && cargo init --name galactica-compositor
	cd packages/galactica-installer && cargo init --name galactica-installer
	@echo "$(GREEN)✅ Projects initialized$(RESET)"
