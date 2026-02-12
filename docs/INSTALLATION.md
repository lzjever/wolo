# Wolo Installation Guide

This document describes the various ways to install Wolo, including one-click installation scripts for different platforms.

## Table of Contents

- [Quick Start](#quick-start)
- [One-Click Installation](#one-click-installation)
- [Installation Methods](#installation-methods)
- [Manual Installation](#manual-installation)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

## Quick Start

```bash
# Recommended: One-click install
curl -fsSL https://raw.githubusercontent.com/mbos-agent/wolo/main/install.sh | bash

# Or: Using uv tool (fastest)
uv tool install mbos-wolo

# Or: Using pipx (official Python way)
pipx install mbos-wolo

# Or (macOS): Using Homebrew
brew install --formula https://raw.githubusercontent.com/mbos-agent/wolo/main/homebrew/wolo.rb
```

## One-Click Installation

Wolo provides platform-specific one-click installation scripts that handle all dependencies automatically.

### Linux / macOS

The shell script installer (`install.sh`) supports:
- Automatic Python detection
- Installation via `uv` (recommended), `pipx`, or `pip` (fallback)
- User or system-wide installation
- PATH configuration

```bash
# Basic installation (uses uv by default)
curl -fsSL https://raw.githubusercontent.com/mbos-agent/wolo/main/install.sh | bash

# Using wget
wget -qO- https://raw.githubusercontent.com/mbos-agent/wolo/main/install.sh | bash

# With specific installation method
METHOD=pipx curl -fsSL https://raw.githubusercontent.com/mbos-agent/wolo/main/install.sh | bash

# Download and inspect first
curl -O https://raw.githubusercontent.com/mbos-agent/wolo/main/install.sh
less install.sh
bash install.sh
```

### Windows

The PowerShell installer (`install.ps1`) supports:
- Python detection from common installation paths
- `py` launcher support
- Automatic PATH updates
- Virtual environment creation

```powershell
# Basic installation
irm https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.ps1 | iex

# Download and inspect first
Invoke-WebRequest -Uri https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.ps1 -OutFile install.ps1
Get-Content install.ps1
.\install.ps1
```

## Installation Methods

### 1. uv tool (Recommended)

The fastest and most modern Python package manager.

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install wolo
uv tool install mbos-wolo

# Upgrade
uv tool upgrade mbos-wolo

# Uninstall
uv tool uninstall mbos-wolo
```

**Benefits**:
- 10-100x faster than pip
- Creates isolated environment automatically
- Best dependency resolution
- Easy upgrade/downgrade

### 2. pipx (Official Python CLI installer)

Python's official recommendation for installing CLI tools.

```bash
# Install pipx if not already installed
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Install wolo
pipx install mbos-wolo

# Upgrade
pipx upgrade mbos-wolo

# Uninstall
pipx uninstall mbos-wolo
```

**Benefits**:
- Official Python recommendation
- Each tool in isolated virtualenv
- Stable and well-tested

### 3. Homebrew (macOS only)

Native macOS package manager experience.

```bash
# Install from formula URL
brew install --formula https://raw.githubusercontent.com/mbos-agent/wolo/main/homebrew/wolo.rb

# Or add tap first
brew tap mbos-agent/wolo
brew install wolo

# Upgrade
brew upgrade wolo

# Uninstall
brew uninstall wolo
```

**Benefits**:
- Native macOS experience
- Automatic dependency management
- Easy updates via `brew upgrade`

### 4. pip (Fallback)

Standard pip installation.

```bash
# User install (recommended, no sudo)
pip install --user mbos-wolo

# Or into a virtual environment
python3 -m venv ~/.venv/wolo
source ~/.venv/wolo/bin/activate
pip install mbos-wolo

# Upgrade
pip install --upgrade mbos-wolo
```

### 5. Docker

Completely isolated containerized installation.

```bash
# Pull image
docker pull ghcr.io/mbos-agent/wolo:latest

# Run with mounted config and workspace
docker run -it --rm \
  -v ~/.wolo:/root/.wolo \
  -v $(pwd):/workspace \
  -w /workspace \
  ghcr.io/mbos-agent/wolo:latest "your prompt"

# Create an alias for convenience
alias wolo='docker run -it --rm -v ~/.wolo:/root/.wolo -v $(pwd):/workspace -w /workspace ghcr.io/mbos-agent/wolo:latest'
```

**Benefits**:
- Complete isolation
- No Python installation needed
- Consistent across all platforms

## Manual Installation

### From Source

```bash
# Clone repository
git clone https://github.com/mbos-agent/wolo.git
cd wolo

# Using uv (recommended for development)
uv sync --group dev --all-extras

# Run in development mode
uv run wolo "your prompt"

# Or install editable
uv pip install -e .
```

### Using Makefile

```bash
# Install with dev dependencies
make dev-install

# Basic installation
make install
```

## Verification

After installation, verify Wolo is working:

```bash
# Check version
wolo --version

# Or using python module
python -m wolo --version

# View help
wolo --help

# Run a simple task
wolo "say hello"
```

## Post-Installation Configuration

```bash
# Create config directory
mkdir -p ~/.wolo

# Create config file
cat > ~/.wolo/config.yaml << 'EOF'
endpoints:
  - name: default
    model: gpt-4o
    api_base: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}  # Use env var for security
EOF

# Set API key
export OPENAI_API_KEY="your-api-key"

# Verify configuration
wolo config show
```

## Troubleshooting

### Python Not Found

**Error**: `Python 3 is not installed`

**Solution**: Install Python 3.10 or higher:
- **Linux**: `sudo apt install python3.12` (Debian/Ubuntu) or `sudo dnf install python3.12` (Fedora)
- **macOS**: `brew install python@3.12`
- **Windows**: Download from [python.org](https://www.python.org/downloads/)

### Command Not Found

**Error**: `wolo: command not found`

**Solution**: The installation directory is not in your PATH:

```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"

# Reload shell
source ~/.bashrc  # or source ~/.zshrc

# Verify
which wolo
```

### Permission Denied

**Error**: `Permission denied`

**Solution**: Use user install instead of system install:
```bash
pip install --user mbos-wolo
# or
uv tool install mbos-wolo
```

### uv Installation Fails

**Error**: UV installation fails

**Solution**: Use pipx instead:
```bash
python3 -m pip install --user pipx
pipx install mbos-wolo
```

## Uninstallation

```bash
# uv tool
uv tool uninstall mbos-wolo

# pipx
pipx uninstall mbos-wolo

# Homebrew
brew uninstall wolo

# pip
pip uninstall mbos-wolo

# Remove config and data (optional)
rm -rf ~/.wolo
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WOLO_API_KEY` | API key for LLM backend | - |
| `WOLO_MODEL` | Default model to use | - |
| `WOLO_BASE_URL` | API base URL | - |
| `WOLO_WILD_MODE` | Enable wild mode | `0` |

## Project-Local Configuration

For project isolation, create `.wolo/config.yaml` in your project directory:

```bash
mkdir -p myproject/.wolo
cat > myproject/.wolo/config.yaml << 'EOF'
endpoints:
  - name: default
    model: claude-3-opus
    api_base: https://api.anthropic.com/v1
    api_key: ${ANTHROPIC_API_KEY}
EOF

cd myproject
wolo "your prompt"  # Uses project config
```

## Next Steps

- [Security Guide](SECURITY.md)
- [Configuration Guide](CONFIGURATION.md)
- [Development Guide](DEVELOPMENT.md)
