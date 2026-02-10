# Scripts

This directory contains utility scripts for development and testing.

## Installation Scripts

### install.sh (Linux / macOS)

One-click installation script for Unix-like systems.

**Usage:**
```bash
curl -sSL https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.sh | bash
```

**Features:**
- Automatic Python detection (3.10-3.15)
- Supports multiple installation methods (uv, pip, source)
- User or system-wide installation
- PATH configuration reminders
- Colorized output

**Environment Variables:**
- `WOLO_INSTALL_METHOD`: Installation method (auto, uv, pip, source)
- `WOLO_HOME`: Installation directory (default: ~/.wolo)

### install.ps1 (Windows)

PowerShell one-click installation script for Windows.

**Usage:**
```powershell
irm https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.ps1 | iex
```

**Features:**
- Python detection from common paths
- `py` launcher support
- Virtual environment via uv
- Creates batch and PowerShell wrappers
- PATH update reminders

### install.py (Universal)

Python-based cross-platform installer.

**Usage:**
```bash
python3 -c "$(curl -sSL https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.py)"
python3 install.py --method uv
python3 install.py --help
```

**Features:**
- Cross-platform compatibility
- Command-line argument support
- Detailed error messages
- Can be inspected before running

## Development Scripts

## generate_release_notes.py

**Main script for generating release notes.** Used by GitHub Actions workflows and can be run locally for testing.

**Usage:**
```bash
# Output to stdout
python3 scripts/generate_release_notes.py 0.1.1

# Output to file
python3 scripts/generate_release_notes.py 0.1.1 release_notes.md
```

**What it does:**
- Extracts changelog section from CHANGELOG.md for the given version
- Falls back to git commits if changelog entry not found
- Adds installation instructions automatically
- Can output to stdout or file

**Features:**
- Standalone Python script (no external dependencies)
- Used by GitHub Actions workflow
- Can be tested independently
- Handles version extraction and git commit fallback

**Testing:**
```bash
# Test with different versions
python3 scripts/generate_release_notes.py 0.1.1
python3 scripts/generate_release_notes.py 0.1.0

# Test output to file
python3 scripts/generate_release_notes.py 0.1.1 /tmp/test_notes.md
cat /tmp/test_notes.md
```

## test_release_notes.sh

Test script for release notes generation. Wrapper script that uses `generate_release_notes.py` to test release notes locally.

**Usage:**
```bash
# Test with default version (0.1.0)
bash scripts/test_release_notes.sh

# Test with specific version
bash scripts/test_release_notes.sh 0.1.2
```

**What it does:**
- Calls `generate_release_notes.py` (same script used by GitHub Actions)
- Generates release notes with installation instructions
- Saves output to `test_release_notes_<version>.md`
- Shows preview of how it will appear in GitHub

**Output:**
- Creates `test_release_notes_<version>.md` file in the project root
- You can preview the markdown rendering in your editor
- Use this to verify formatting before creating a real release

**Note:** This script is a convenience wrapper around `generate_release_notes.py`. It ensures you're testing with the exact same logic that GitHub Actions will use.
