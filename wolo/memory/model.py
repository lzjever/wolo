"""Memory data model for Wolo long-term memory."""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime


def _slugify(text: str, max_len: int = 30) -> str:
    """Convert text to a filesystem-safe slug.

    Examples:
        "处理XML报表流程" -> "处理XML报表流程"
        "Debug async code" -> "debug-async-code"
        "a/b:c?d" -> "a-b-c-d"
    """
    # Replace filesystem-unsafe chars with dash
    slug = re.sub(r'[/\\:*?"<>|.\s]+', "-", text.strip())
    # Collapse multiple dashes
    slug = re.sub(r"-{2,}", "-", slug)
    # Strip leading/trailing dashes
    slug = slug.strip("-")
    # Truncate
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or uuid.uuid4().hex[:8]


@dataclass
class Memory:
    """A memory entry for long-term knowledge storage.

    Attributes:
        id: Unique identifier ({title_slug}_{YYMMDD_HHMMSS})
        title: Short descriptive title (AI-generated)
        summary: One-line summary of the memory
        tags: List of tags for categorization
        content: Detailed content (LLM-generated structured summary)
        created_at: ISO 8601 timestamp
        updated_at: ISO 8601 timestamp
        source_session: Session ID where this memory was created
        source_context: Additional context (workdir, description, etc.)
    """

    id: str
    title: str
    summary: str
    tags: list[str]
    content: str
    created_at: str
    updated_at: str
    source_session: str | None = None
    source_context: dict | None = None

    @classmethod
    def create(
        cls,
        title: str,
        summary: str,
        content: str,
        tags: list[str] | None = None,
        source_session: str | None = None,
        source_context: dict | None = None,
        max_content_size: int = 12000,
    ) -> "Memory":
        """Create a new Memory with auto-generated ID and timestamps.

        The ID is formed as: {title_slug}_{YYMMDD_HHMMSS}
        Content is truncated to max_content_size characters.

        Args:
            title: Short descriptive title
            summary: One-line summary
            content: Detailed content
            tags: Optional list of tags
            source_session: Optional source session ID
            source_context: Optional source context dict
            max_content_size: Maximum content length in characters (default 12000)

        Returns:
            New Memory instance
        """
        now = datetime.now()
        timestamp = now.strftime("%y%m%d_%H%M%S")
        iso_time = now.isoformat()

        slug = _slugify(title)
        memory_id = f"{slug}_{timestamp}"

        # Truncate content if too long
        if len(content) > max_content_size:
            content = content[:max_content_size] + "\n\n[... truncated]"

        return cls(
            id=memory_id,
            title=title,
            summary=summary,
            tags=tags or [],
            content=content,
            created_at=iso_time,
            updated_at=iso_time,
            source_session=source_session,
            source_context=source_context,
        )

    def to_dict(self) -> dict:
        """Convert Memory to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "tags": self.tags,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_session": self.source_session,
            "source_context": self.source_context,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Memory":
        """Create Memory from dictionary (JSON deserialization)."""
        return cls(
            id=data["id"],
            title=data["title"],
            summary=data["summary"],
            tags=data.get("tags", []),
            content=data["content"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            source_session=data.get("source_session"),
            source_context=data.get("source_context"),
        )
