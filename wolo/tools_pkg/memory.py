"""Memory tool implementations for Wolo long-term memory.

Provides tools for saving, recalling, listing, and deleting memories.
Uses LLM to generate structured memory content from conversation context.
"""

import json
import logging
from typing import Any

from wolo.memory import Memory, get_storage

logger = logging.getLogger(__name__)


# Prompt template for focused memory extraction
_SUMMARIZE_PROMPT = """You are a memory extraction system. The user wants you to remember specific knowledge from the conversation.

User's instruction on WHAT to remember:
{instruction}

Based on the user's instruction and the conversation context below, extract ONLY the relevant knowledge.

Return a JSON object with this exact structure:
```json
{{
  "title": "short descriptive title in a few words",
  "summary": "one sentence summary",
  "tags": ["tag1", "tag2"],
  "content": "detailed, well-structured content covering exactly what the user asked to remember"
}}
```

Rules:
- The "title" should be a short phrase (3-8 words) describing the memory
- The "content" should be comprehensive but focused ONLY on what the user asked
- Include code examples, file paths, and specific details from the conversation
- Do NOT include irrelevant conversation parts
- Return ONLY the JSON object, no other text

Conversation context:
{context}"""


async def _generate_memory_summary(
    instruction: str,
    messages: list[dict],
    config: Any,
) -> dict[str, Any] | None:
    """Generate structured memory summary using LLM.

    Uses a lightweight lexilux Chat client directly (not the full WoloLLMClient)
    with a short timeout and limited max_tokens to avoid blocking the tool executor.

    Args:
        instruction: User's description of what to remember
        messages: Recent conversation messages
        config: Wolo Config instance

    Returns:
        Dict with title, summary, tags, content or None on failure
    """
    import asyncio

    try:
        from lexilux import Chat

        # Lightweight client — short timeout, no debug overhead
        chat = Chat(
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            connect_timeout_s=10.0,
            read_timeout_s=60.0,
        )

        # Build context from recent messages (last 20 for more context)
        messages_text = json.dumps(messages[-20:], indent=2, ensure_ascii=False)

        prompt = _SUMMARIZE_PROMPT.format(
            instruction=instruction,
            context=messages_text,
        )

        # Call LLM with timeout — memory summarization shouldn't take long
        async def _call_llm() -> str:
            response_text = ""
            stream = await chat.astream(
                [{"role": "user", "content": prompt}],
                max_tokens=4096,
            )
            async for chunk in stream:
                if chunk.delta:
                    response_text += chunk.delta
            return response_text

        response_text = await asyncio.wait_for(_call_llm(), timeout=60.0)

        # Extract JSON from response
        response_text = response_text.strip()
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()

        return json.loads(response_text)

    except asyncio.TimeoutError:
        logger.warning("Memory summary LLM call timed out after 60s, falling back to direct save")
        return None
    except Exception as e:
        logger.error(f"Failed to generate memory summary: {e}")
        return None


async def memory_save_execute(
    summary: str,
    tags: list[str] | None = None,
    context: dict | None = None,
    session_id: str | None = None,
    messages: list | None = None,
    config: Any = None,
    max_content_size: int = 12000,
) -> dict[str, Any]:
    """Execute memory save tool.

    Args:
        summary: User's instruction on what to remember
        tags: Optional list of tags
        context: Optional context dict (workdir, description)
        session_id: Current session ID
        messages: Current session messages for LLM summarization
        config: Wolo Config for LLM access
        max_content_size: Max content length in chars

    Returns:
        Result dict with output and metadata
    """
    storage = get_storage()

    # If messages and config provided, use LLM to generate structured memory
    if messages and config:
        llm_result = await _generate_memory_summary(summary, messages, config)
        if llm_result:
            title = llm_result.get("title", summary[:50])
            content = llm_result.get("content", summary)
            extracted_tags = llm_result.get("tags", [])
            all_tags = list(set(extracted_tags + (tags or [])))
            summary_text = llm_result.get("summary", summary)
        else:
            # Fallback to user input
            title = summary[:50]
            content = summary
            all_tags = tags or []
            summary_text = summary
    else:
        # No LLM generation, use user input directly
        title = summary[:50]
        content = summary
        all_tags = tags or []
        summary_text = summary

    # Create memory with truncation
    memory = Memory.create(
        title=title,
        summary=summary_text,
        content=content,
        tags=all_tags,
        source_session=session_id,
        source_context=context,
        max_content_size=max_content_size,
    )

    # Save
    storage.save(memory)

    return {
        "output": f"Memory saved: {memory.id}\nTitle: {memory.title}\nTags: {', '.join(all_tags)}",
        "metadata": {
            "memory_id": memory.id,
            "title": memory.title,
            "tags": all_tags,
            "error": None,
        },
    }


async def memory_list_execute(tag_filter: str | None = None) -> dict[str, Any]:
    """Execute memory list tool.

    Args:
        tag_filter: Optional tag to filter by

    Returns:
        Result dict with output and metadata
    """
    storage = get_storage()
    memories = storage.list_all()

    # Filter by tag if specified
    if tag_filter:
        memories = [m for m in memories if tag_filter in m.tags]

    if not memories:
        output = "No memories found" + (f" with tag '{tag_filter}'" if tag_filter else "")
        return {
            "output": output,
            "metadata": {"count": 0, "memories": [], "error": None},
        }

    # Format output
    lines = [f"Found {len(memories)} memory(s):\n"]
    for mem in memories:
        tags_str = ", ".join(mem.tags) if mem.tags else "none"
        lines.append(
            f"  [{mem.id}] {mem.title}\n"
            f"    {mem.summary}\n"
            f"    Tags: {tags_str}  |  Created: {mem.created_at}"
        )

    return {
        "output": "\n".join(lines),
        "metadata": {
            "count": len(memories),
            "memories": [
                {"id": m.id, "title": m.title, "summary": m.summary, "tags": m.tags}
                for m in memories
            ],
            "error": None,
        },
    }


async def memory_recall_execute(query: str) -> dict[str, Any]:
    """Execute memory recall/search tool.

    Args:
        query: Search query string (or memory ID for exact match)

    Returns:
        Result dict with output and metadata
    """
    storage = get_storage()

    # Try exact ID match first
    exact = storage.load(query)
    if exact:
        memories = [exact]
    else:
        memories = storage.search(query)

    if not memories:
        return {
            "output": f"No memories found matching '{query}'",
            "metadata": {"count": 0, "memories": [], "error": None},
        }

    # Format output - include full content for recalled memories
    lines = [f"Found {len(memories)} memory(s) matching '{query}':\n"]
    for mem in memories:
        tags_str = ", ".join(mem.tags) if mem.tags else "none"
        lines.append(
            f"  [{mem.id}] {mem.title}\n"
            f"    {mem.summary}\n"
            f"    Tags: {tags_str}\n"
            f"    Content:\n{mem.content}\n"
            f"    Created: {mem.created_at}"
        )

    return {
        "output": "\n".join(lines),
        "metadata": {
            "count": len(memories),
            "memories": [
                {
                    "id": m.id,
                    "title": m.title,
                    "summary": m.summary,
                    "tags": m.tags,
                    "content": m.content,
                }
                for m in memories
            ],
            "error": None,
        },
    }


async def memory_delete_execute(memory_id: str) -> dict[str, Any]:
    """Execute memory delete tool.

    Args:
        memory_id: Memory ID to delete

    Returns:
        Result dict with output and metadata
    """
    storage = get_storage()
    deleted = storage.delete(memory_id)

    if deleted:
        return {
            "output": f"Memory deleted: {memory_id}",
            "metadata": {"memory_id": memory_id, "error": None},
        }
    else:
        return {
            "output": f"Memory not found: {memory_id}",
            "metadata": {"memory_id": memory_id, "error": "not_found"},
        }


def load_memories_for_session(queries: list[str]) -> str | None:
    """Load memories by ID or search query and return formatted context.

    Tries exact ID match first, then search. Combines all found memories
    into a single string suitable for injection into the session.

    Args:
        queries: List of memory IDs or search queries

    Returns:
        Formatted memory context string, or None if no memories found
    """
    storage = get_storage()
    loaded: list[Memory] = []

    for query in queries:
        # Try exact ID match first
        exact = storage.load(query)
        if exact:
            loaded.append(exact)
        else:
            # Search by query
            results = storage.search(query)
            loaded.extend(results)

    if not loaded:
        return None

    # Deduplicate by ID while preserving order
    seen: set[str] = set()
    unique: list[Memory] = []
    for mem in loaded:
        if mem.id not in seen:
            seen.add(mem.id)
            unique.append(mem)

    # Format as context block
    parts = ["[Loaded memories]"]
    for mem in unique:
        tags_str = ", ".join(mem.tags) if mem.tags else "none"
        parts.append(f"\n--- Memory: {mem.title} (tags: {tags_str}) ---\n{mem.content}")
    parts.append("\n[End of loaded memories]")

    return "\n".join(parts)
