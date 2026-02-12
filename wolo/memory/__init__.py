"""Memory module for Wolo long-term memory.

This module provides persistent memory storage across sessions:
- Memory: Data class for memory entries (legacy JSON format)
- MemoryStorage: JSON-based storage with file locking (legacy)
- MarkdownMemory: Data class for markdown memory entries
- MarkdownMemoryStorage: Markdown-based storage with caching
- MemoryScanner: Scans and formats memories for LLM context injection
"""

# Legacy JSON-based memory (kept for backward compatibility)
# New markdown-based memory
from wolo.memory.markdown_model import MarkdownMemory
from wolo.memory.markdown_storage import (
    MarkdownMemoryStorage,
    get_markdown_storage,
    set_markdown_storage,
)
from wolo.memory.model import Memory
from wolo.memory.scanner import MemoryScanner, get_scanner, set_scanner
from wolo.memory.storage import MemoryStorage, get_storage

__all__ = [
    # Legacy
    "Memory",
    "MemoryStorage",
    "get_storage",
    # New
    "MarkdownMemory",
    "MarkdownMemoryStorage",
    "get_markdown_storage",
    "set_markdown_storage",
    "MemoryScanner",
    "get_scanner",
    "set_scanner",
]
