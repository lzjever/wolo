"""Environment variable tools."""

import os
from typing import Any


async def get_env_execute(name: str, default: str = "") -> dict[str, Any]:
    """Get an environment variable value."""

    value = os.getenv(name, default)

    if value:
        # Hide sensitive values
        is_sensitive = any(
            keyword in name.lower() for keyword in ["key", "secret", "password", "token"]
        )
        display_value = "***HIDDEN***" if is_sensitive else value
        return {
            "title": f"get_env: {name}",
            "output": f"{name}={display_value}",
            "metadata": {"name": name, "exists": True, "is_sensitive": is_sensitive},
        }
    else:
        return {
            "title": f"get_env: {name}",
            "output": f"{name} is not set" + (f", using default: {default}" if default else ""),
            "metadata": {"name": name, "exists": False},
        }
