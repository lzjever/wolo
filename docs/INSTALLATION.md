# Wolo Installation Guide

This document describes the various ways to install Wolo, including one-click installation scripts for different platforms.

## Table of Contents

- [One-Click Installation](#one-click-installation)
- [Installation Methods](#installation-methods)
- [Manual Installation](#manual-installation)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

## One-Click Installation

Wolo provides platform-specific one-click installation scripts that handle all dependencies automatically.

### Linux / macOS

The shell script installer (`install.sh`) supports:
- Automatic Python detection
- Installation via `uv` (fast) or `pip` (fallback)
- User or system-wide installation
- PATH configuration

```bash
# Basic installation
curl -sSL https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.sh | bash

# With specific installation method
WOLO_INSTALL_METHOD=uv bash <(curl -sSL https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.sh)

# Download and inspect first
curl -O https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.sh
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

### Universal Python Installer

The Python installer (`install.py`) works on all platforms and provides:
- Cross-platform compatibility
- Command-line argument support
- Detailed error messages

```bash
# Using curl
python3 -c "$(curl -sSL https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.py)"

# Using wget
python3 -c "$(wget -qO- https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.py)"

# Download and run
curl -O https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.py
python3 install.py --method uv
```

## Installation Methods

### Auto (Default)

Automatically selects the best available method:
1. Checks if `uv` is installed
2. Falls back to `pip` if not available

```bash
WOLO_INSTALL_METHOD=auto bash install.sh
```

### UV Method

Uses the `uv` package manager for fast installation:

```bash
# Install via installer
WOLO_INSTALL_METHOD=uv bash install.sh

# Or manually
uv pip install mbos-wolo
```

Benefits:
- 10-100x faster than pip
- Creates isolated virtual environment
- Better dependency resolution

### PIP Method

Standard pip installation:

```bash
# Install via installer
WOLO_INSTALL_METHOD=pip bash install.sh

# Or manually
pip install mbos-wolo

# User install (no sudo required)
pip install --user mbos-wolo
```

### Source Method

Installs directly from the git repository:

```bash
WOLO_INSTALL_METHOD=source bash install.sh
```

This method:
- Clones the repository
- builds the package
- Installs the wheel

## Manual Installation

### From PyPI

```bash
# Using uv
uv pip install mbos-wolo

# Using pip
pip install mbos-wolo

# Upgrade
pip install --upgrade mbos-wolo
```

### From Source

```bash
# Clone repository
git clone https://github.com/mbos-agent/wolo.git
cd wolo

# Using uv (recommended)
uv sync

# Using pip
pip install -e .

# With development dependencies
pip install -e ".[dev]"
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

# Run a simple task
wolo "echo hello world"
```

Expected output:
```
[INFO] Wolo vX.Y.Z
...
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

**Solution**: The installation directory is not in your PATH. Add it:

**Linux / macOS**:
```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"

# Or use python module directly
python -m wolo "your prompt"
```

**Windows**:
```powershell
# Add to user PATH
$env:Path += ";$env:USERPROFILE\bin"

# Or use python module directly
python -m wolo "your prompt"
```

### Permission Denied

**Error**: `Permission denied` when running install script

**Solution**: Make the script executable:
```bash
chmod +x install.sh
./install.sh
```

### UV Installation Fails

**Error**: UV installation fails

**Solution**: Use pip instead:
```bash
WOLO_INSTALL_METHOD=pip bash install.sh
```

### Virtual Environment Issues

**Error**: Virtual environment creation fails

**Solution**: Ensure python-venv is installed:
```bash
# Debian/Ubuntu
sudo apt install python3-venv

# Fedora
sudo dnf install python3-virtualenv

# macOS (using Homebrew)
brew install python-tk@3.12
```

## Uninstallation

### Remove Package

```bash
# If installed via pip
pip uninstall mbos-wolo

# If installed via uv
uv pip uninstall mbos-wolo
```

### Remove Configuration

```bash
# Remove config directory
rm -rf ~/.wolo

# Remove wrapper scripts
rm -f ~/.local/bin/wolo  # Linux/macOS
rm -f ~/bin/wolo.bat     # Windows
```

### Clean Virtual Environment (UV Installation)

```bash
# Remove wolo virtual environment
rm -rf ~/.wolo/venv
```

## Environment Variables

The installation scripts respect the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `WOLO_INSTALL_METHOD` | Installation method (auto, uv, pip, source) | `auto` |
| `WOLO_HOME` | Installation directory | `~/.wolo` |
| `WOLO_API_KEY` | API key for LLM backend | - |
| `WOLO_MODEL` | Default model to use | - |
| `WOLO_API_BASE` | API base URL | - |

## Post-Installation

After installation, configure Wolo:

```bash
# Initialize configuration
wolo config init

# Set API key
export WOLO_API_KEY="your-api-key-here"

# Verify configuration
wolo config show
```

## Next Steps

- [Configuration Guide](CONFIGURATION.md)
- [User Guide](USER_GUIDE.md)
- [Development Guide](DEVELOPMENT.md)
