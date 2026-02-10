#!/usr/bin/env python3
"""
Wolo Universal Installation Script
Cross-platform installer that works on Linux, macOS, and Windows

Usage:
    curl -sSL https://raw.githubusercontent.com/mbos-agent/wolo/main/scripts/install.py | python3 -
    python3 install.py [--method pip|uv|source]
"""

import os
import sys
import subprocess
import tempfile
import shutil
import platform
import urllib.request
from pathlib import Path
from typing import Optional

# ANSI color codes
class Colors:
    BLUE = "\033[0;34m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    RED = "\033[0;31m"
    NC = "\033[0m"  # No Color

    @staticmethod
    def strip(s: str) -> str:
        """Remove ANSI color codes from string"""
        import re
        return re.sub(r"\033\[[0-9;]+m", "", s)

# Configuration
REPO_URL = "https://github.com/lzjever/wolo"
PYPI_PACKAGE = "mbos-wolo"
PYTHON_MIN_VERSION = (3, 10)
PYTHON_MAX_VERSION = (3, 15)

def log_info(msg: str):
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {msg}")

def log_success(msg: str):
    print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {msg}")

def log_warn(msg: str):
    print(f"{Colors.YELLOW}[WARN]{Colors.NC} {msg}")

def log_error(msg: str):
    print(f"{Colors.RED}[ERROR]{Colors.NC} {msg}", file=sys.stderr)

def run_command(cmd: list, capture: bool = True) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            check=False
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 1, "", f"Command not found: {cmd[0]}"

def check_python_version() -> tuple[bool, str]:
    """Check if Python version is compatible"""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    if version.major != 3:
        return False, f"Python 3 is required, found {version_str}"

    if version < PYTHON_MIN_VERSION:
        return False, f"Python {PYTHON_MIN_VERSION[0]}.{PYTHON_MIN_VERSION[1]}+ is required, found {version_str}"

    if version >= (PYTHON_MAX_VERSION[0] + 1, 0):
        return False, f"Python < {PYTHON_MAX_VERSION[0] + 1}.0 is required, found {version_str}"

    return True, version_str

def find_pip() -> Optional[str]:
    """Find pip executable"""
    for pip_cmd in ["pip", "pip3"]:
        code, _, _ = run_command([pip_cmd, "--version"])
        if code == 0:
            return pip_cmd

    # Try python -m pip
    code, _, _ = run_command([sys.executable, "-m", "pip", "--version"])
    if code == 0:
        return f"{sys.executable} -m pip"

    return None

def install_uv() -> bool:
    """Install uv package manager"""
    system = platform.system().lower()
    log_info("Installing uv...")

    if system == "windows":
        install_cmd = ["powershell", "-c", "irm https://astral.sh/uv/install.ps1 | iex"]
    else:
        # Linux/macOS
        install_cmd = ["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"]

    code, stdout, stderr = run_command(install_cmd, capture=False)

    if code == 0:
        # Update PATH for current session
        uv_path = Path.home() / ".local" / "bin"
        if uv_path.exists():
            os.environ["PATH"] = str(uv_path) + os.pathsep + os.environ.get("PATH", "")

        # Verify uv is available
        code, _, _ = run_command(["uv", "--version"])
        return code == 0

    return False

def install_via_pip(user: bool = True) -> bool:
    """Install wolo using pip"""
    pip_cmd = find_pip()
    if not pip_cmd:
        log_error("pip not found. Please install pip first.")
        return False

    log_info(f"Installing wolo via pip...")

    cmd = pip_cmd.split() + ["install", "--upgrade", PYPI_PACKAGE]
    if user:
        cmd.insert(3, "--user")

    code, stdout, stderr = run_command(cmd, capture=False)

    if code != 0 and user:
        # Try without --user flag
        log_warn("User install failed, trying system-wide install...")
        cmd = [c for c in cmd if c != "--user"]
        code, stdout, stderr = run_command(cmd, capture=False)

    return code == 0

def install_via_uv() -> bool:
    """Install wolo using uv"""
    # Check if uv is available
    code, _, _ = run_command(["uv", "--version"])
    if code != 0:
        if not install_uv():
            log_warn("uv installation failed, falling back to pip")
            return install_via_pip()

    log_info("Installing wolo via uv...")

    wolo_home = Path(os.environ.get("WOLO_HOME", Path.home() / ".wolo"))
    wolo_venv = wolo_home / "venv"

    # Create virtual environment
    wolo_home.mkdir(parents=True, exist_ok=True)

    log_info(f"Creating virtual environment at {wolo_venv}...")

    code, _, _ = run_command(["uv", "venv", str(wolo_venv)])
    if code != 0:
        # Fall back to python -m venv
        code, _, _ = run_command([sys.executable, "-m", "venv", str(wolo_venv)])
        if code != 0:
            log_warn("Failed to create virtual environment, falling back to pip")
            return install_via_pip()

    # Install wolo
    python_path = wolo_venv / ("Scripts/python.exe" if platform.system() == "Windows" else "bin/python")
    code, _, _ = run_command(["uv", "pip", "install", "-U", PYPI_PACKAGE, "--python", str(python_path)])

    if code == 0:
        # Create wrapper script
        create_wrapper_script(wolo_venv)
        return True

    return False

def create_wrapper_script(venv_path: Path):
    """Create wrapper script for wolo"""
    system = platform.system()
    bin_dir = Path.home() / ("bin" if system != "Windows" else "")
    bin_dir.mkdir(parents=True, exist_ok=True)

    if system == "Windows":
        # Create batch file
        batch_path = bin_dir / "wolo.bat"
        with open(batch_path, "w") as f:
            f.write(f"@echo off\n")
            f.write(f"set WOLO_HOME=%USERPROFILE%\\.wolo\n")
            f.write(f'"%WOLO_HOME%\\venv\\Scripts\\python.exe" -m wolo %*\n')
    else:
        # Create shell script
        script_path = bin_dir / "wolo"
        with open(script_path, "w") as f:
            f.write("#!/usr/bin/env bash\n")
            f.write(f'WOLO_HOME=${{WOLO_HOME:-$HOME/.wolo}}\n')
            f.write(f'WOLO_VENV="$WOLO_HOME/venv"\n')
            f.write(f'if [ -f "$WOLO_VENV/bin/python" ]; then\n')
            f.write(f'    exec "$WOLO_VENV/bin/python" -m wolo "$@"\n')
            f.write(f'else\n')
            f.write(f'    echo "Error: wolo is not installed properly."\n')
            f.write(f'    exit 1\n')
            f.write(f'fi\n')
        os.chmod(script_path, 0o755)

def install_from_source() -> bool:
    """Install wolo from source"""
    log_info("Installing wolo from source...")

    # Check for git
    code, _, _ = run_command(["git", "--version"])
    if code != 0:
        log_error("git is not installed. Please install git first.")
        return False

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        clone_path = temp_path / "wolo-temp"

        # Clone repository
        log_info("Cloning repository...")
        code, _, _ = run_command(["git", "clone", "--depth", "1", REPO_URL, str(clone_path)])
        if code != 0:
            log_error("Failed to clone repository")
            return False

        # Build and install
        log_info("Building and installing...")
        code, _, _ = run_command([sys.executable, "-m", "pip", "install", "build"], capture=False)
        if code != 0:
            log_warn("Failed to install build tool, trying anyway...")

        os.chdir(clone_path)
        code, _, _ = run_command([sys.executable, "-m", "build"], capture=False)
        if code != 0:
            log_error("Build failed")
            return False

        # Find wheel
        dist_path = clone_path / "dist"
        wheels = list(dist_path.glob("*.whl"))
        if wheels:
            code, _, _ = run_command([sys.executable, "-m", "pip", "install", str(wheels[0])])
            return code == 0

    return False

def verify_installation() -> bool:
    """Verify wolo is installed and working"""
    log_info("Verifying installation...")

    # Try python -m wolo
    code, stdout, stderr = run_command([sys.executable, "-m", "wolo", "--version"])

    if code == 0:
        log_success(f"wolo {Colors.strip(stdout).strip()} is installed!")
        return True

    return False

def show_post_install():
    """Show post-installation information"""
    print()
    log_success("Wolo installation complete!")
    print()
    print("Quick Start:")
    print("  wolo \"your prompt here\"    # Run a task")
    print("  wolo chat                   # Start interactive mode")
    print("  wolo config init            # First-time setup")
    print()
    print("Configuration:")
    print(f"  Config file: {Path.home() / '.wolo' / 'config.yaml'}")
    print("  Set API key: export WOLO_API_KEY=\"your-key-here\"")
    print()
    print("For more information:")
    print(f"  GitHub: {REPO_URL}")
    print(f"  Docs:   {REPO_URL}#readme")
    print()

def main():
    """Main installation flow"""
    print()
    print(f"{Colors.BLUE}╔═══════════════════════════════════════════════════════╗")
    print(f"║              Wolo One-Click Installer                 ║")
    print(f"╚═══════════════════════════════════════════════════════╝{Colors.NC}")
    print()

    # Check Python version
    valid, version = check_python_version()
    if not valid:
        log_error(version)
        sys.exit(1)

    log_info(f"Python version: {version}")

    # Determine installation method
    install_method = os.environ.get("WOLO_INSTALL_METHOD", "auto")

    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--method", "-m"]:
            if len(sys.argv) > 2:
                install_method = sys.argv[2]
            else:
                log_error("--method requires an argument (pip, uv, or source)")
                sys.exit(1)
        elif sys.argv[1] in ["--help", "-h"]:
            print("Usage: python3 install.py [--method pip|uv|source]")
            print()
            print("Options:")
            print("  --method, -m    Installation method (pip, uv, source)")
            print("  --help, -h      Show this help message")
            print()
            print("Environment variables:")
            print("  WOLO_INSTALL_METHOD    Installation method (auto, pip, uv, source)")
            sys.exit(0)

    if install_method == "auto":
        # Check if uv is available
        code, _, _ = run_command(["uv", "--version"])
        install_method = "uv" if code == 0 else "pip"

    log_info(f"Installation method: {install_method}")

    # Install
    success = False
    match install_method:
        case "uv":
            success = install_via_uv()
        case "pip":
            success = install_via_pip()
        case "source":
            success = install_from_source()
        case _:
            log_error(f"Unknown installation method: {install_method}")
            sys.exit(1)

    if not success:
        log_error("Installation failed")
        sys.exit(1)

    # Verify
    if not verify_installation():
        log_error("Installation verification failed")
        log_info("Please check your Python installation and try again.")
        sys.exit(1)

    show_post_install()

if __name__ == "__main__":
    main()
