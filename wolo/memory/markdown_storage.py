"""Markdown memory storage with mtime-based caching.

Provides efficient scanning of memory files with caching to avoid
re-reading unchanged files.
"""

import logging
from pathlib import Path

from wolo.memory.markdown_model import MarkdownMemory

logger = logging.getLogger(__name__)


class MarkdownMemoryStorage:
    """Storage for markdown memories with mtime-based caching.

    The cache stores file modification times to avoid re-reading
    unchanged files on subsequent scans.
    """

    def __init__(self, base_dir: Path):
        """Initialize storage.

        Args:
            base_dir: Directory containing memory markdown files
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Cache: file_path -> (mtime, memory)
        self._cache: dict[Path, tuple[float, MarkdownMemory]] = {}

    def scan_memories(self, force: bool = False) -> list[MarkdownMemory]:
        """Scan directory for memory files, using cache for unchanged files.

        Args:
            force: If True, ignore cache and re-read all files

        Returns:
            List of MarkdownMemory objects, sorted by created_at (newest first)
        """
        memories = []

        # Get all existing memory files
        existing_paths = set(self.base_dir.glob("*.md"))

        # Clean up cache entries for deleted files
        cached_paths = set(self._cache.keys())
        deleted_paths = cached_paths - existing_paths
        for deleted_path in deleted_paths:
            del self._cache[deleted_path]
            logger.debug(f"Removed deleted file from cache: {deleted_path}")

        for path in existing_paths:
            try:
                # Check cache
                mtime = path.stat().st_mtime
                if not force and path in self._cache:
                    cached_mtime, cached_memory = self._cache[path]
                    if cached_mtime == mtime:
                        memories.append(cached_memory)
                        continue

                # Read file
                memory = MarkdownMemory.from_file(path)
                self._cache[path] = (mtime, memory)
                memories.append(memory)

            except Exception as e:
                logger.warning(f"Failed to load memory {path}: {e}")

        # Sort by created_at descending
        memories.sort(key=lambda m: m.created_at, reverse=True)
        return memories

    def create_memory(
        self,
        title: str,
        content: str,
        tags: list[str] | None = None,
        source_session: str | None = None,
        max_content_size: int = 12000,
    ) -> MarkdownMemory:
        """Create and save a new memory.

        Args:
            title: Short descriptive title
            content: Markdown content
            tags: Optional list of tags
            source_session: Optional source session ID
            max_content_size: Maximum content length

        Returns:
            Newly created MarkdownMemory
        """
        memory = MarkdownMemory.create(
            base_dir=self.base_dir,
            title=title,
            content=content,
            tags=tags,
            source_session=source_session,
            max_content_size=max_content_size,
        )
        memory.save()

        # Update cache
        mtime = memory.file_path.stat().st_mtime
        self._cache[memory.file_path] = (mtime, memory)

        logger.debug(f"Created memory: {memory.id}")
        return memory

    def get_memory(self, memory_id: str) -> MarkdownMemory | None:
        """Get a memory by ID.

        Args:
            memory_id: Memory ID (filename without extension)

        Returns:
            MarkdownMemory or None if not found
        """
        # Try to find in cache first
        for path, (_, memory) in self._cache.items():
            if memory.id == memory_id:
                return memory

        # Search in filesystem
        for path in self.base_dir.glob("*.md"):
            if path.stem == memory_id:
                try:
                    memory = MarkdownMemory.from_file(path)
                    mtime = path.stat().st_mtime
                    self._cache[path] = (mtime, memory)
                    return memory
                except Exception as e:
                    logger.warning(f"Failed to load memory {path}: {e}")

        return None

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID.

        Args:
            memory_id: Memory ID to delete

        Returns:
            True if deleted, False if not found
        """
        for path in self.base_dir.glob("*.md"):
            if path.stem == memory_id:
                path.unlink()
                # Remove from cache
                if path in self._cache:
                    del self._cache[path]
                logger.debug(f"Deleted memory: {memory_id}")
                return True
        return False

    def search(self, query: str) -> list[MarkdownMemory]:
        """Search memories by query.

        Searches in title, tags, and content.

        Args:
            query: Search query string

        Returns:
            List of matching memories
        """
        query_lower = query.lower()
        results = []

        for memory in self.scan_memories():
            # Search in title
            if query_lower in memory.title.lower():
                results.append(memory)
                continue

            # Search in tags
            if any(query_lower in tag.lower() for tag in memory.tags):
                results.append(memory)
                continue

            # Search in content
            if query_lower in memory.content.lower():
                results.append(memory)
                continue

        return results

    def clear_cache(self) -> None:
        """Clear the memory cache."""
        self._cache.clear()


# Global storage instance
_storage: MarkdownMemoryStorage | None = None


def get_markdown_storage(base_dir: Path | None = None) -> MarkdownMemoryStorage:
    """Get or create a markdown storage instance.

    Args:
        base_dir: Optional base directory. If None, uses global storage.

    Returns:
        MarkdownMemoryStorage instance
    """
    if base_dir is not None:
        return MarkdownMemoryStorage(base_dir)

    global _storage
    if _storage is None:
        # Default to home directory
        _storage = MarkdownMemoryStorage(Path.home() / ".wolo" / "memories")
    return _storage


def set_markdown_storage(storage: MarkdownMemoryStorage) -> None:
    """Set the global markdown storage instance."""
    global _storage
    _storage = storage
