"""Slash command handler for REPL mode.

Provides built-in slash commands for memory management and other features.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SlashResult:
    """Result of a slash command execution."""

    handled: bool  # Whether the command was handled
    output: str  # Output text to display
    inject_as_user_message: str | None = None  # If set, inject this as user message to agent


async def handle_slash_command(
    session_id: str, user_input: str, config=None, agent_config=None
) -> SlashResult:
    """Handle a slash command.

    Args:
        session_id: Current session ID
        user_input: Raw user input starting with '/'
        config: Wolo Config instance
        agent_config: Agent configuration

    Returns:
        SlashResult indicating whether the command was handled
    """
    parts = user_input.strip().split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if command == "/remember":
        return await _handle_remember(session_id, args, config)
    else:
        return SlashResult(handled=False, output="")


async def _handle_remember(session_id: str, args: str, config=None) -> SlashResult:
    """Handle /remember <instruction> — save long-term memory from the conversation.

    The instruction describes what specific knowledge to extract. For example:
        /remember how the XML report pipeline works end to end
        /remember the debugging steps we used to fix the auth bug
    """
    if not args:
        return SlashResult(
            handled=True,
            output="Usage: /remember <what to remember>\n"
            "  Save knowledge from the conversation as long-term memory.\n"
            "  Example: /remember how we fixed the authentication bug",
        )

    # Inject as user message so the LLM calls memory_save with focused extraction
    message = (
        f"Please save a memory about the following from our conversation: {args}\n"
        f"Use the memory_save tool with this as the summary."
    )
    return SlashResult(
        handled=True,
        output="",
        inject_as_user_message=message,
    )
