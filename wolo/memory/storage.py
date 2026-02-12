"""Memory storage for Wolo long-term memory.

Provides JSON-based storage with file locking for concurrent safety.
"""

import fcntl
import json
import logging
import os
from pathlib import Path

from wolo.memory.model import Memory

logger = logging.getLogger(__name__)


class MemoryStorage:
    """Storage for long-term memories with file locking.

    Directory structure:
    ~/.wolo/memories/
    ├── {memory_id}.json  # Individual memory files
    └── index.json        # Lightweight search index
    """

    def __init__(self, base_dir: Path | None = None):
        """Initialize MemoryStorage.

        Args:
            base_dir: Base directory for storage. Defaults to ~/.wolo/memories
        """
        self.base_dir = base_dir or (Path.home() / ".wolo" / "memories")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _memory_file(self, memory_id: str) -> Path:
        """Get the file path for a memory."""
        return self.base_dir / f"{memory_id}.json"

    def _index_file(self) -> Path:
        """Get the index file path."""
        return self.base_dir / "index.json"

    def _write_json(self, path: Path, data: dict) -> None:
        """Write JSON with file locking for safety."""
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file first, then rename (atomic)
        temp_path = path.with_suffix(".tmp")
        try:
            with open(temp_path, "w") as f:
                # Get exclusive lock
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())

                    # Atomic rename while lock is still held
                    temp_path.rename(path)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception as e:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise e

    def _read_json(self, path: Path) -> dict | None:
        """Read JSON with file locking."""
        if not path.exists():
            return None

        try:
            with open(path) as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to read {path}: {e}")
            return None

    def save(self, memory: Memory) -> str:
        """Save a memory to storage.

        Args:
            memory: Memory instance to save

        Returns:
            The memory ID
        """
        self._write_json(self._memory_file(memory.id), memory.to_dict())
        self._update_index(memory)
        logger.debug(f"Saved memory {memory.id[:12]}...")
        return memory.id

    def load(self, memory_id: str) -> Memory | None:
        """Load a memory by ID.

        Args:
            memory_id: Memory ID to load

        Returns:
            Memory instance or None if not found
        """
        data = self._read_json(self._memory_file(memory_id))
        if data:
            return Memory.from_dict(data)
        return None

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID.

        Args:
            memory_id: Memory ID to delete

        Returns:
            True if deleted, False if not found
        """
        path = self._memory_file(memory_id)
        if path.exists():
            path.unlink()
            self._remove_from_index(memory_id)
            logger.debug(f"Deleted memory {memory_id[:12]}...")
            return True
        return False

    def list_all(self) -> list[Memory]:
        """List all memories.

        Returns:
            List of all Memory instances, sorted by created_at (newest first)
        """
        memories = []
        for path in self.base_dir.glob("*.json"):
            if path.name == "index.json":
                continue
            data = self._read_json(path)
            if data and "id" in data and "title" in data:
                memories.append(Memory.from_dict(data))

        # Sort by created_at descending
        memories.sort(key=lambda m: m.created_at, reverse=True)
        return memories

    def search(self, query: str, tag_filter: str | None = None) -> list[Memory]:
        """Search memories by query string and optional tag filter.

        Args:
            query: Search query string
            tag_filter: Optional tag to filter by

        Returns:
            List of matching Memory instances, sorted by relevance
        """
        query_lower = query.lower()
        results = []

        for memory in self.list_all():
            # Tag filter
            if tag_filter and tag_filter not in memory.tags:
                continue

            # Search in title, summary, tags
            if (
                query_lower in memory.title.lower()
                or query_lower in memory.summary.lower()
                or any(query_lower in tag.lower() for tag in memory.tags)
            ):
                results.append(memory)

        return results

    def _update_index(self, memory: Memory) -> None:
        """Update the search index with a new or updated memory."""
        index = self._load_index() or {}

        index[memory.id] = {
            "id": memory.id,
            "title": memory.title,
            "summary": memory.summary,
            "tags": memory.tags,
            "created_at": memory.created_at,
        }

        self._write_json(self._index_file(), index)

    def _remove_from_index(self, memory_id: str) -> None:
        """Remove a memory from the search index."""
        index = self._load_index()
        if index and memory_id in index:
            del index[memory_id]
            self._write_json(self._index_file(), index)

    def _load_index(self) -> dict | None:
        """Load the search index."""
        return self._read_json(self._index_file())


# Global storage instance
_storage: MemoryStorage | None = None


def get_storage() -> MemoryStorage:
    """Get the global memory storage instance."""
    global _storage
    if _storage is None:
        _storage = MemoryStorage()
    return _storage
