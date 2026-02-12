"""Memory tool implementations for Wolo long-term memory.

Provides tools for saving memories using markdown format.
Uses LLM to generate structured memory content from conversation context.
"""

import json
import logging
from typing import Any

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
    from wolo.memory import get_markdown_storage

    # Get storage directory from config
    memories_dir = config.memories_dir if config else None
    storage = get_markdown_storage(memories_dir)

    # If messages and config provided, use LLM to generate structured memory
    if messages and config:
        llm_result = await _generate_memory_summary(summary, messages, config)
        if llm_result:
            title = llm_result.get("title", summary[:50])
            content = llm_result.get("content", summary)
            extracted_tags = llm_result.get("tags", [])
            all_tags = list(set(extracted_tags + (tags or [])))
        else:
            # Fallback to user input
            title = summary[:50]
            content = summary
            all_tags = tags or []
    else:
        # No LLM generation, use user input directly
        title = summary[:50]
        content = summary
        all_tags = tags or []

    # Create memory using markdown storage
    memory = storage.create_memory(
        title=title,
        content=content,
        tags=all_tags,
        source_session=session_id,
        max_content_size=max_content_size,
    )

    # Invalidate scanner cache so next LLM call sees the new memory
    from wolo.memory.scanner import get_scanner

    scanner = get_scanner(memories_dir)
    scanner.invalidate_cache()

    return {
        "output": f"Memory saved: {memory.id}\nTitle: {memory.title}\nTags: {', '.join(all_tags)}",
        "metadata": {
            "memory_id": memory.id,
            "title": memory.title,
            "tags": all_tags,
            "error": None,
        },
    }


# Note: memory_list, memory_recall, memory_delete functions removed.
# Memory management is now done directly via filesystem (.wolo/memories/*.md files).
# Memories are automatically loaded/scanned before each LLM call.


def load_memories_for_session(queries: list[str], config: Any = None) -> str | None:
    """Load memories by ID or search query and return formatted context.

    Tries exact ID match first, then search. Combines all found memories
    into a single string suitable for injection into the session.

    Args:
        queries: List of memory IDs or search queries
        config: Optional config to determine storage location

    Returns:
        Formatted memory context string, or None if no memories found
    """
    from wolo.memory import MarkdownMemory, get_markdown_storage

    memories_dir = config.memories_dir if config else None
    storage = get_markdown_storage(memories_dir)
    loaded: list[MarkdownMemory] = []

    for query in queries:
        # Try exact ID match first
        exact = storage.get_memory(query)
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
    unique: list[MarkdownMemory] = []
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
