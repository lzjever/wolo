"""
Node.js availability checking.

Many MCP servers are implemented in Node.js and require npx to run.
This module provides utilities to check for Node.js availability
and provide helpful installation instructions.
"""

import logging
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def check_node_available() -> bool:
    """Check if Node.js is available."""
    return shutil.which("node") is not None


def check_npx_available() -> bool:
    """Check if npx is available."""
    return shutil.which("npx") is not None


def get_node_version() -> Optional[str]:
    """
    Get the installed Node.js version.
    
    Returns:
        Version string (e.g., "v20.10.0") or None if not installed
    """
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_npm_version() -> Optional[str]:
    """
    Get the installed npm version.
    
    Returns:
        Version string (e.g., "10.2.3") or None if not installed
    """
    try:
        result = subprocess.run(
            ["npm", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_installation_instructions() -> str:
    """Get Node.js installation instructions for the current platform."""
    import platform
    
    system = platform.system()
    
    instructions = [
        "Node.js is required for some MCP servers.",
        "",
        "Installation instructions:",
        "",
    ]
    
    if system == "Linux":
        # Detect distro
        distro = ""
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("ID="):
                        distro = line.strip().split("=")[1].strip('"')
                        break
        except Exception:
            pass
        
        if distro in ("arch", "manjaro"):
            instructions.extend([
                "  # Arch/Manjaro",
                "  sudo pacman -S nodejs npm",
            ])
        elif distro in ("ubuntu", "debian", "linuxmint"):
            instructions.extend([
                "  # Ubuntu/Debian",
                "  curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -",
                "  sudo apt-get install -y nodejs",
            ])
        elif distro in ("fedora", "rhel", "centos"):
            instructions.extend([
                "  # Fedora/RHEL",
                "  sudo dnf install nodejs npm",
            ])
        else:
            instructions.extend([
                "  # Using nvm (recommended)",
                "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash",
                "  nvm install --lts",
            ])
    
    elif system == "Darwin":
        instructions.extend([
            "  # macOS (Homebrew)",
            "  brew install node",
            "",
            "  # Or using nvm",
            "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash",
            "  nvm install --lts",
        ])
    
    elif system == "Windows":
        instructions.extend([
            "  # Windows (winget)",
            "  winget install OpenJS.NodeJS.LTS",
            "",
            "  # Or download from https://nodejs.org/",
        ])
    
    else:
        instructions.extend([
            "  # Download from https://nodejs.org/",
        ])
    
    return "\n".join(instructions)


def ensure_node_available(quiet: bool = False) -> bool:
    """
    Ensure Node.js/npx is available.
    
    If not available, prints installation instructions.
    
    Args:
        quiet: If True, don't print instructions
    
    Returns:
        True if Node.js is available
    """
    if check_npx_available():
        version = get_node_version()
        logger.debug(f"Node.js available: {version}")
        return True
    
    if not quiet:
        print("⚠️  Node.js/npx not found")
        print("")
        print(get_installation_instructions())
        print("")
    
    return False


class NodeNotAvailableError(Exception):
    """Node.js is not available but required."""
    
    def __init__(self, server_name: str):
        self.server_name = server_name
        super().__init__(
            f"MCP server '{server_name}' requires Node.js, but it's not installed. "
            f"Run 'wolo --check-node' for installation instructions."
        )
