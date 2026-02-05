# wolo/path_guard/persistence.py
"""Session persistence for PathGuard."""

import json
from datetime import datetime
from pathlib import Path


class PathGuardPersistence:
    """Persistence layer for PathGuard session data.

    This class handles saving and loading confirmed directories across
    session resumes. The data is stored in a JSON file within the
    session directory.

    Storage format:
        {
            "confirmed_dirs": ["/path1", "/path2", ...],
            "confirmation_count": 2,
            "last_updated": "2026-01-15T12:34:56.789012"
        }
    """

    def __init__(self, session_dir: Path) -> None:
        """Initialize the persistence layer.

        Args:
            session_dir: Base directory for session storage
        """
        self._session_dir = session_dir

    def _get_confirmation_file(self, session_id: str) -> Path:
        """Get the path to the confirmation file for a session.

        Args:
            session_id: Session identifier

        Returns:
            Path to the confirmation JSON file
        """
        return self._session_dir / session_id / "path_confirmations.json"

    def save_confirmed_dirs(self, session_id: str, confirmed_dirs: list[Path]) -> None:
        """Save confirmed directories for a session.

        Args:
            session_id: Session identifier
            confirmed_dirs: List of confirmed directory paths
        """
        file_path = self._get_confirmation_file(session_id)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "confirmed_dirs": [str(p) for p in confirmed_dirs],
            "confirmation_count": len(confirmed_dirs),
            "last_updated": datetime.now().isoformat(),
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_confirmed_dirs(self, session_id: str) -> list[Path]:
        """Load confirmed directories for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of confirmed directory paths, or empty list if file doesn't exist
        """
        file_path = self._get_confirmation_file(session_id)
        if not file_path.exists():
            return []

        with open(file_path) as f:
            data = json.load(f)

        return [Path(p) for p in data.get("confirmed_dirs", [])]
