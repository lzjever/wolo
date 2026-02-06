"""PathGuard initialization helpers for CLI command entry points."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def initialize_path_guard_for_session(
    config: Any,
    session_id: str | None,
    workdir: str | None,
    cli_paths: list[str] | None = None,
) -> None:
    """Initialize PathGuard middleware for a command execution session."""
    from wolo.session import load_path_confirmations
    from wolo.tools_pkg.path_guard_executor import initialize_path_guard_middleware

    config_paths = getattr(config.path_safety, "allowed_write_paths", [])
    max_confirmations = getattr(config.path_safety, "max_confirmations_per_session", None)
    audit_denied = getattr(config.path_safety, "audit_denied", True)
    audit_log_file = getattr(config.path_safety, "audit_log_file", None)
    wild_mode = getattr(config.path_safety, "wild_mode", False)

    session_confirmed: list[Path] = []
    if session_id:
        session_confirmed = load_path_confirmations(session_id)

    initialize_path_guard_middleware(
        config_paths=config_paths,
        cli_paths=cli_paths or [],
        workdir=workdir,
        confirmed_dirs=session_confirmed,
        max_confirmations_per_session=max_confirmations,
        audit_denied=audit_denied,
        audit_log_file=str(audit_log_file) if audit_log_file else None,
        wild_mode=wild_mode,
    )
