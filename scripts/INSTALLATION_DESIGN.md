# Wolo One-Click Installation Scripts - Design Summary

## Overview

Created three one-click installation scripts for Wolo that enable users to install the program with a single command. The scripts support multiple platforms (Linux, macOS, Windows) and installation methods (uv, pip, source).

## Files Created

### 1. `scripts/install.sh` (Linux / macOS)
- **Lines:** ~270
- **Features:**
  - Automatic platform and architecture detection
  - Python version validation (3.10-3.15)
  - uv installation with fallback to pip
  - User/system-wide installation options
  - Wrapper script creation for uv method
  - PATH configuration reminders
  - Colorized console output
  - Installation verification

### 2. `scripts/install.ps1` (Windows)
- **Lines:** ~280
- **Features:**
  - Python detection from common installation paths
  - Support for Python launcher (`py`)
  - uv installation via PowerShell
  - Virtual environment creation
  - Batch and PowerShell wrapper scripts
  - PATH update reminders
  - Windows-specific error handling

### 3. `scripts/install.py` (Universal)
- **Lines:** ~330
- **Features:**
  - Pure Python implementation
  - Cross-platform compatibility
  - Command-line argument support (`--method`, `--help`)
  - Python version checking
  - uv installation with pip fallback
  - Wrapper script creation
  - Works on any platform with Python 3.10+

## Installation Methods Supported

| Method | Description | When Used |
|--------|-------------|-----------|
| `auto` | Automatically selects uv or pip | Default |
| `uv` | Uses uv package manager (10-100x faster) | When available |
| `pip` | Standard pip installation | Fallback |
| `source` | Install from git repository | Development/edge |

## Usage Examples

### Linux / macOS
```bash
# Basic installation
curl -sSL https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.sh | bash

# With specific method
WOLO_INSTALL_METHOD=uv bash <(curl -sSL https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.sh)
```

### Windows
```powershell
# Basic installation
irm https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.ps1 | iex

# Download and inspect first
Invoke-WebRequest -Uri https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.ps1 -OutFile install.ps1
.\install.ps1
```

### Universal (Python)
```bash
# Direct execution
python3 -c "$(curl -sSL https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.py)"

# Download and run
curl -O https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.py
python3 install.py --method uv
```

## Documentation Updates

### Updated Files

1. **README.md**
   - Added one-click installation section at the top
   - Provided platform-specific commands
   - Documented installation methods

2. **docs/INSTALLATION.md** (new)
   - Comprehensive installation guide
   - Troubleshooting section
   - Uninstallation instructions
   - Environment variable reference

3. **scripts/README.md** (updated)
   - Added installation scripts documentation
   - Usage examples for each script

## Security Considerations

All scripts support inspection before execution:

```bash
# Download and inspect
curl -O https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.sh
less install.sh

# Run after inspection
bash install.sh
```

## Installation Flow

```
1. Detect platform and architecture
   ↓
2. Check Python version (3.10-3.15)
   ↓
3. Determine installation method (auto/uv/pip/source)
   ↓
4. Install/verify uv (if using uv method)
   ↓
5. Create virtual environment (uv method)
   ↓
6. Install mbos-wolo package
   ↓
7. Create wrapper scripts
   ↓
8. Verify installation
   ↓
9. Show post-install instructions
```

## Post-Installation

After installation, users can:
- Run `wolo --version` to verify
- Run `wolo config init` for first-time setup
- Set `WOLO_API_KEY` environment variable
- Start using `wolo "prompt"` or `wolo chat`

## File Permissions

The shell scripts have been made executable:
```bash
chmod +x scripts/install.sh scripts/install.py
```

## Next Steps

To complete the release script implementation:

1. **Test the scripts** on different platforms:
   - Linux (Ubuntu, Debian, Fedora, Arch)
   - macOS (Intel, Apple Silicon)
   - Windows (10, 11)

2. **Update GitHub releases** to include installation instructions

3. **Consider creating standalone binaries** using PyInstaller or similar

4. **Add CI/CD tests** to verify installation scripts work

5. **Publish to PyPI** if not already done

## Compatibility Matrix

| Platform | Script | Python | UV | Pip | Source |
|----------|--------|--------|-----|-----|--------|
| Linux | install.sh | 3.10-3.15 | ✅ | ✅ | ✅ |
| macOS | install.sh | 3.10-3.15 | ✅ | ✅ | ✅ |
| Windows | install.ps1 | 3.10-3.15 | ✅ | ✅ | ✅ |
| Any | install.py | 3.10-3.15 | ✅ | ✅ | ✅ |
