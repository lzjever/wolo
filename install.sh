#!/bin/bash
#
# Wolo Installer - Universal installation script for Mac and Linux
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/xxx/wolo/main/install.sh | bash
#   or
#   wget -qO- https://raw.githubusercontent.com/xxx/wolo/main/install.sh | bash
#
# Options:
#   METHOD=uv      - Use uv tool install (default, recommended)
#   METHOD=pipx    - Use pipx install
#   METHOD=pip     - Use pip --user install (not recommended)
#   VERSION=x.x.x  - Install specific version
#
# Examples:
#   METHOD=pipx curl -fsSL ... | bash
#   VERSION=1.0.0 curl -fsSL ... | bash

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
WOLO_REPO="mbos-agent/wolo"
WOLO_PYPI="mbos-wolo"
METHOD="${METHOD:-uv}"
VERSION="${VERSION:-}"
PREFIX="${PREFIX:-$HOME/.local}"

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

detect_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macos" ;;
        Linux*)     echo "linux" ;;
        *)          echo "unknown" ;;
    esac
}

detect_arch() {
    case "$(uname -m)" in
        x86_64|amd64)   echo "x86_64" ;;
        arm64|aarch64)  echo "arm64" ;;
        *)              echo "unknown" ;;
    esac
}

check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON=python3
    elif command -v python &> /dev/null; then
        PYTHON=python
    else
        error "Python 3 is required but not found. Please install Python 3.10+ first."
    fi

    PY_VERSION=$($PYTHON --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    info "Found Python $PY_VERSION"

    # Check version >= 3.10
    MAJOR=$(echo $PY_VERSION | cut -d'.' -f1)
    MINOR=$(echo $PY_VERSION | cut -d'.' -f2)
    if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]); then
        error "Python 3.10+ is required. Found Python $PY_VERSION"
    fi
}

install_uv() {
    if command -v uv &> /dev/null; then
        success "uv is already installed"
        return 0
    fi

    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Add to PATH for current session
    export PATH="$HOME/.local/bin:$PATH"

    if command -v uv &> /dev/null; then
        success "uv installed successfully"
    else
        error "Failed to install uv"
    fi
}

install_pipx() {
    if command -v pipx &> /dev/null; then
        success "pipx is already installed"
        return 0
    fi

    info "Installing pipx..."
    $PYTHON -m pip install --user pipx
    $PYTHON -m pipx ensurepath

    # Add to PATH for current session
    export PATH="$HOME/.local/bin:$PATH"

    if command -v pipx &> /dev/null; then
        success "pipx installed successfully"
    else
        error "Failed to install pipx"
    fi
}

install_wolo_uv() {
    info "Installing wolo with uv..."

    if [ -n "$VERSION" ]; then
        uv tool install "$WOLO_PYPI==$VERSION"
    else
        uv tool install "$WOLO_PYPI"
    fi

    success "wolo installed with uv"
}

install_wolo_pipx() {
    info "Installing wolo with pipx..."

    if [ -n "$VERSION" ]; then
        pipx install "$WOLO_PYPI==$VERSION"
    else
        pipx install "$WOLO_PYPI"
    fi

    success "wolo installed with pipx"
}

install_wolo_pip() {
    warn "pip install is not recommended. Consider using uv or pipx instead."

    info "Installing wolo with pip..."

    $PYTHON -m pip install --user "$WOLO_PYPI"

    success "wolo installed with pip"
}

verify_installation() {
    info "Verifying installation..."

    if command -v wolo &> /dev/null; then
        WOLO_VERSION=$(wolo --version 2>&1 || echo "unknown")
        success "wolo is installed: $WOLO_VERSION"
        echo ""
        echo -e "${GREEN}Installation complete!${NC}"
        echo ""
        echo "Quick start:"
        echo "  wolo \"your prompt here\"           # Run in solo mode"
        echo "  wolo --coop \"your prompt\"         # Run with questions enabled"
        echo "  wolo --repl                        # Start interactive REPL"
        echo ""
        echo "Documentation: https://github.com/$WOLO_REPO"
    else
        error "Installation verification failed. 'wolo' command not found."
    fi
}

print_banner() {
    echo ""
    echo "╔════════════════════════════════════════════╗"
    echo "║           Wolo Installer v1.0              ║"
    echo "║     AI Agent CLI for Mac & Linux           ║"
    echo "╚════════════════════════════════════════════╝"
    echo ""
}

main() {
    print_banner

    OS=$(detect_os)
    ARCH=$(detect_arch)
    info "Detected: $OS on $ARCH"

    check_python

    case "$METHOD" in
        uv)
            install_uv
            install_wolo_uv
            ;;
        pipx)
            install_pipx
            install_wolo_pipx
            ;;
        pip)
            install_wolo_pip
            ;;
        *)
            error "Unknown installation method: $METHOD. Use uv, pipx, or pip."
            ;;
    esac

    verify_installation
}

main "$@"
