"""Memory module for Wolo long-term memory.

This module provides persistent memory storage across sessions:
- Memory: Data class for memory entries
- MemoryStorage: JSON-based storage with file locking
- MemoryIndex: Lightweight search indexing
"""

from wolo.memory.model import Memory
from wolo.memory.storage import MemoryStorage, get_storage

__all__ = ["Memory", "MemoryStorage", "get_storage"]
