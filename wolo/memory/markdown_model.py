"""Markdown memory model for Wolo long-term memory.

Memory files are stored as markdown with YAML frontmatter:

```markdown
---
title: How to Cook Pasta
tags: [cooking, italian]
created_at: 2026-02-12T10:30:00
updated_at: 2026-02-12T10:30:00
source_session: AgentName_260212_103000
---

# How to Cook Pasta

## Ingredients
- Pasta
- Water
- Salt
```
"""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


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
class MarkdownMemory:
    """A memory entry stored as markdown with YAML frontmatter.

    Attributes:
        file_path: Path to the markdown file
        title: Short descriptive title
        tags: List of tags for categorization
        created_at: Creation timestamp
        updated_at: Last update timestamp
        source_session: Session ID where this memory was created
        content: Markdown content
    """

    file_path: Path
    title: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    source_session: str | None = None
    content: str = ""

    @property
    def id(self) -> str:
        """Memory ID derived from filename."""
        return self.file_path.stem

    @classmethod
    def from_file(cls, path: Path) -> "MarkdownMemory":
        """Load a memory from a markdown file.

        Args:
            path: Path to the markdown file

        Returns:
            MarkdownMemory instance

        Raises:
            ValueError: If file format is invalid
        """
        content = path.read_text(encoding="utf-8")

        # Parse YAML frontmatter
        if not content.startswith("---"):
            raise ValueError(f"Memory file {path} missing YAML frontmatter")

        # Find end of frontmatter
        fm_end = content.find("\n---", 4)
        if fm_end == -1:
            raise ValueError(f"Memory file {path} has malformed frontmatter")

        frontmatter = content[4:fm_end]
        body = content[fm_end + 5 :].strip()

        # Parse frontmatter (simple YAML-like parsing)
        metadata = {}
        for line in frontmatter.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()

                # Parse tags list
                if key == "tags":
                    if value.startswith("[") and value.endswith("]"):
                        tags_str = value[1:-1]
                        metadata["tags"] = [
                            t.strip().strip('"').strip("'")
                            for t in tags_str.split(",")
                            if t.strip()
                        ]
                    else:
                        metadata["tags"] = []
                elif key in ("created_at", "updated_at"):
                    # Parse ISO format datetime
                    try:
                        metadata[key] = datetime.fromisoformat(value)
                    except ValueError:
                        metadata[key] = datetime.now()
                elif key == "source_session":
                    metadata[key] = value if value and value != "null" else None
                else:
                    metadata[key] = value

        return cls(
            file_path=path,
            title=metadata.get("title", path.stem),
            tags=metadata.get("tags", []),
            created_at=metadata.get("created_at", datetime.now()),
            updated_at=metadata.get("updated_at", datetime.now()),
            source_session=metadata.get("source_session"),
            content=body,
        )

    def to_markdown(self) -> str:
        """Convert memory to markdown format with YAML frontmatter."""
        # Build frontmatter
        lines = ["---"]
        lines.append(f"title: {self.title}")

        # Format tags
        if self.tags:
            tags_str = ", ".join(self.tags)
            lines.append(f"tags: [{tags_str}]")
        else:
            lines.append("tags: []")

        lines.append(f"created_at: {self.created_at.isoformat()}")
        lines.append(f"updated_at: {self.updated_at.isoformat()}")

        if self.source_session:
            lines.append(f"source_session: {self.source_session}")

        lines.append("---")
        lines.append("")
        lines.append(self.content)

        return "\n".join(lines)

    def save(self) -> None:
        """Save memory to its file path."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(self.to_markdown(), encoding="utf-8")

    @classmethod
    def create(
        cls,
        base_dir: Path,
        title: str,
        content: str,
        tags: list[str] | None = None,
        source_session: str | None = None,
        max_content_size: int = 12000,
    ) -> "MarkdownMemory":
        """Create a new memory with auto-generated ID and timestamps.

        Args:
            base_dir: Directory to store the memory file
            title: Short descriptive title
            content: Markdown content
            tags: Optional list of tags
            source_session: Optional source session ID
            max_content_size: Maximum content length in characters

        Returns:
            New MarkdownMemory instance
        """
        now = datetime.now()
        timestamp = now.strftime("%y%m%d_%H%M%S")
        slug = _slugify(title)
        filename = f"memory-{slug}_{timestamp}.md"
        file_path = base_dir / filename

        # Truncate content if too long
        if len(content) > max_content_size:
            content = content[:max_content_size] + "\n\n[... truncated]"

        return cls(
            file_path=file_path,
            title=title,
            tags=tags or [],
            created_at=now,
            updated_at=now,
            source_session=source_session,
            content=content,
        )
