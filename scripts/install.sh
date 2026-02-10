#!/usr/bin/env bash
# Wolo One-Click Installation Script
# Supports: Linux, macOS
# Usage: curl -sSL https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.sh | bash

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/mbos-agent/wolo"
INSTALL_METHOD="${WOLO_INSTALL_METHOD:-auto}" # auto, pip, uv, pyflow
PYTHON_MIN_VERSION="3.10"
PYTHON_MAX_VERSION="3.15"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

detect_platform() {
    OS_TYPE=$(uname -s)
    ARCH_TYPE=$(uname -m)

    case "$OS_TYPE" in
        Linux*)
            PLATFORM="linux"
            ;;
        Darwin*)
            PLATFORM="macos"
            ;;
        *)
            log_error "Unsupported platform: $OS_TYPE"
            exit 1
            ;;
    esac

    log_info "Detected platform: $PLATFORM ($ARCH_TYPE)"
}

check_python() {
    log_info "Checking Python version..."

    # Check for python3 command
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed. Please install Python $PYTHON_MIN_VERSION or higher."
        log_info "Visit: https://www.python.org/downloads/"
        exit 1
    fi

    PYTHON_CMD=$(command -v python3)
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')

    log_info "Found Python: $PYTHON_VERSION"

    # Parse version
    MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
    MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")

    if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]; }; then
        log_error "Python $PYTHON_MIN_VERSION or higher is required. Found: $PYTHON_VERSION"
        exit 1
    fi

    log_success "Python version check passed"
}

check_pip() {
    log_info "Checking for pip..."
    if ! $PYTHON_CMD -m pip --version &> /dev/null; then
        log_error "pip is not installed. Please install pip first."
        log_info "Run: python3 -m ensurepip --upgrade"
        exit 1
    fi
    log_success "pip is available"
}

install_uv() {
    log_info "Installing uv (fast Python package installer)..."

    case "$PLATFORM" in
        linux)
            UV_INSTALL_URL="https://astral.sh/uv/install.sh"
            ;;
        macos)
            UV_INSTALL_URL="https://astral.sh/uv/install.sh"
            ;;
    esac

    if command -v curl &> /dev/null; then
        curl -LsSf "$UV_INSTALL_URL" | sh
    elif command -v wget &> /dev/null; then
        wget -qO- "$UV_INSTALL_URL" | sh
    else
        log_error "Neither curl nor wget is available"
        exit 1
    fi

    # Add to PATH for current session
    export PATH="$HOME/.local/bin:$PATH"

    if command -v uv &> /dev/null; then
        log_success "uv installed successfully"
    else
        log_warn "uv installation may have failed. Falling back to pip."
        INSTALL_METHOD="pip"
    fi
}

install_via_pip() {
    log_info "Installing wolo via pip..."

    # Try user install first (doesn't require sudo)
    if $PYTHON_CMD -m pip install --user mbos-wolo 2>/dev/null; then
        log_success "wolo installed to user directory"
        WOLO_CMD="$PYTHON_CMD -m wolo"

        # Check if user bin is in PATH
        USER_BIN="$HOME/.local/bin"
        if [[ ":$PATH:" != *":$USER_BIN:"* ]]; then
            log_warn "$USER_BIN is not in PATH. Add it with:"
            echo "  export PATH=\"$USER_BIN:\$PATH\""
            log_info "Or use: $PYTHON_CMD -m wolo"
        fi
    else
        # Fall back to system install (may require sudo)
        log_info "Trying system-wide installation..."
        if $PYTHON_CMD -m pip install mbos-wolo; then
            log_success "wolo installed system-wide"
            WOLO_CMD="wolo"
        else
            log_error "Failed to install wolo"
            exit 1
        fi
    fi
}

install_via_uv() {
    log_info "Installing wolo via uv..."

    if ! command -v uv &> /dev/null; then
        install_uv
    fi

    # Create a virtual environment and install
    WOLO_HOME="${WOLO_HOME:-$HOME/.wolo}"
    WOLO_VENV="$WOLO_HOME/venv"

    mkdir -p "$WOLO_HOME"

    log_info "Creating virtual environment at $WOLO_VENV..."
    uv venv "$WOLO_VENV" 2>/dev/null || $PYTHON_CMD -m venv "$WOLO_VENV"

    log_info "Installing wolo..."
    uv pip install -U mbos-wolo --python "$WOLO_VENV/bin/python"

    # Create wrapper script
    WRAPPER_DIR="$HOME/.local/bin"
    mkdir -p "$WRAPPER_DIR"

    cat > "$WRAPPER_DIR/wolo" << 'EOF'
#!/usr/bin/env bash
WOLO_HOME="${WOLO_HOME:-$HOME/.wolo}"
WOLO_VENV="$WOLO_HOME/venv"
if [ -f "$WOLO_VENV/bin/python" ]; then
    exec "$WOLO_VENV/bin/python" -m wolo "$@"
else
    echo "Error: wolo is not installed properly. Please run the installer again."
    exit 1
fi
EOF

    chmod +x "$WRAPPER_DIR/wolo"

    log_success "wolo installed via uv"
    WOLO_CMD="wolo"

    # PATH reminder
    if [[ ":$PATH:" != *":$WRAPPER_DIR:"* ]]; then
        log_warn "$WRAPPER_DIR is not in PATH. Add it with:"
        echo "  export PATH=\"$WRAPPER_DIR:\$PATH\""
    fi
}

install_from_source() {
    log_info "Installing wolo from source..."

    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"

    log_info "Cloning repository..."
    if command -v git &> /dev/null; then
        git clone --depth 1 "$REPO_URL" wolo-temp
        cd wolo-temp
    else
        log_error "git is not installed. Please install git first."
        exit 1
    fi

    log_info "Building and installing..."
    $PYTHON_CMD -m build
    $PYTHON_CMD -m pip install dist/*.whl

    cd -
    rm -rf "$TEMP_DIR"

    log_success "wolo installed from source"
    WOLO_CMD="wolo"
}

verify_installation() {
    log_info "Verifying installation..."

    # Use full path or python -m
    if $PYTHON_CMD -m wolo --version &> /dev/null; then
        VERSION=$($PYTHON_CMD -m wolo --version 2>&1)
        log_success "wolo $VERSION is installed and working!"
    else
        log_error "Installation verification failed"
        log_info "Please check your Python installation and try again."
        exit 1
    fi
}

show_post_install() {
    echo ""
    log_success "Wolo installation complete!"
    echo ""
    echo "Quick Start:"
    echo "  wolo \"your prompt here\"    # Run a task"
    echo "  wolo chat                   # Start interactive mode"
    echo "  wolo config init            # First-time setup"
    echo ""
    echo "Configuration:"
    echo "  Config file: ~/.wolo/config.yaml"
    echo "  Set API key: export WOLO_API_KEY=\"your-key-here\""
    echo ""
    echo "For more information:"
    echo "  GitHub: $REPO_URL"
    echo "  Docs:   https://github.com/mbos-agent/wolo#readme"
    echo ""
}

# Main installation flow
main() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║              Wolo One-Click Installer                 ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    detect_platform
    check_python

    # Determine installation method
    if [ "$INSTALL_METHOD" = "auto" ]; then
        if command -v uv &> /dev/null; then
            INSTALL_METHOD="uv"
        else
            INSTALL_METHOD="pip"
        fi
    fi

    log_info "Installation method: $INSTALL_METHOD"

    case "$INSTALL_METHOD" in
        uv)
            check_pip
            install_via_uv
            ;;
        pip)
            check_pip
            install_via_pip
            ;;
        source)
            check_pip
            install_from_source
            ;;
        *)
            log_error "Unknown installation method: $INSTALL_METHOD"
            exit 1
            ;;
    esac

    verify_installation
    show_post_install
}

# Run main function
main "$@"
