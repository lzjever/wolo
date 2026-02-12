"""Memory scanner for injecting memory context into LLM calls.

Scans memory files and formats them as context for the LLM.
"""

import logging
from pathlib import Path

from wolo.memory.markdown_storage import MarkdownMemoryStorage, get_markdown_storage

logger = logging.getLogger(__name__)


class MemoryScanner:
    """Scans memories and formats them for LLM context injection.

    The scanner is called before each LLM call to inject relevant
    memory context into the conversation. Results are cached based
    on file modification times for efficiency.
    """

    MAX_MEMORY_CHARS = 50000  # Maximum total characters for memory context

    def __init__(self, storage: MarkdownMemoryStorage):
        """Initialize scanner.

        Args:
            storage: MarkdownMemoryStorage instance to scan
        """
        self.storage = storage
        self._last_scan_count = 0
        # Cache for formatted context string
        self._cached_context: str | None = None
        self._cache_dir_mtime: float = 0.0

    def _get_dir_mtime(self) -> float:
        """Get the most recent modification time in the memories directory.

        Returns 0 if directory is empty or doesn't exist.
        """
        try:
            mtimes = [p.stat().st_mtime for p in self.storage.base_dir.glob("*.md") if p.is_file()]
            return max(mtimes) if mtimes else 0.0
        except OSError:
            return 0.0

    def scan_and_format(self) -> str | None:
        """Scan memories and format as LLM context string.

        Uses caching to avoid re-formatting unchanged memory files.

        Returns:
            Formatted memory context string, or None if no memories
        """
        # Check if cache is still valid
        current_mtime = self._get_dir_mtime()
        if self._cached_context is not None and current_mtime == self._cache_dir_mtime:
            logger.debug("Memory context: using cached result")
            return self._cached_context if self._cached_context else None

        # Cache miss or invalidated - rebuild
        memories = self.storage.scan_memories()
        self._last_scan_count = len(memories)

        if not memories:
            self._cached_context = None
            self._cache_dir_mtime = current_mtime
            return None

        # Build context string
        lines = [
            "# Long-Term Memory",
            "",
            "The following memories have been saved from previous conversations.",
            "Use this context to maintain continuity across sessions.",
            "",
        ]

        total_chars = 0
        included_count = 0

        for memory in memories:
            # Format each memory
            memory_block = self._format_memory(memory)

            # Check character limit
            if total_chars + len(memory_block) > self.MAX_MEMORY_CHARS:
                # Truncate this memory or skip
                remaining = self.MAX_MEMORY_CHARS - total_chars
                if remaining > 200:  # Only include if meaningful space left
                    memory_block = memory_block[:remaining] + "\n...[truncated]"
                    lines.append(memory_block)
                    included_count += 1
                break

            lines.append(memory_block)
            total_chars += len(memory_block)
            included_count += 1

        if included_count == 0:
            self._cached_context = None
            self._cache_dir_mtime = current_mtime
            return None

        logger.debug(
            f"Memory context: {included_count}/{len(memories)} memories, {total_chars} chars (rebuilt)"
        )

        self._cached_context = "\n".join(lines)
        self._cache_dir_mtime = current_mtime
        return self._cached_context

    def _format_memory(self, memory) -> str:
        """Format a single memory for context."""
        lines = [f"## {memory.title}"]

        # Add metadata
        meta_parts = []
        if memory.tags:
            meta_parts.append(f"tags: {', '.join(memory.tags)}")
        if memory.source_session:
            meta_parts.append(f"session: {memory.source_session}")
        if meta_parts:
            lines.append(f"({'; '.join(meta_parts)})")

        lines.append("")
        # Add content (limit per-memory size)
        content = memory.content
        if len(content) > 5000:
            content = content[:5000] + "\n...[truncated]"
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")

        return "\n".join(lines)

    @property
    def last_scan_count(self) -> int:
        """Number of memories found in last scan."""
        return self._last_scan_count

    def invalidate_cache(self) -> None:
        """Invalidate the formatted context cache.

        Call this after creating/updating/deleting memories to ensure
        the next scan_and_format() call rebuilds the context.
        """
        self._cached_context = None
        self._cache_dir_mtime = 0.0


# Global scanner instance
_scanner: MemoryScanner | None = None


def get_scanner(memories_dir: Path | None = None) -> MemoryScanner:
    """Get or create a memory scanner.

    Args:
        memories_dir: Optional directory for memories. If None, uses default.

    Returns:
        MemoryScanner instance
    """
    global _scanner

    storage = get_markdown_storage(memories_dir)

    # Create new scanner if needed or if storage directory changed
    if _scanner is None or _scanner.storage.base_dir != storage.base_dir:
        _scanner = MemoryScanner(storage)

    return _scanner


def set_scanner(scanner: MemoryScanner) -> None:
    """Set the global scanner instance."""
    global _scanner
    _scanner = scanner
