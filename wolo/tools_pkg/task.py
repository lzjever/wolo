"""Task execution tools."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def task_execute(
    agent: str, message: str, description: str = "", parent_session_id: str = "", config: Any = None
) -> dict[str, Any]:
    """
    Execute a task by spawning a subagent.

    Args:
        agent: Agent type (general, plan, explore)
        message: Task message for the subagent
        description: Optional description for logging
        parent_session_id: Parent session ID
        config: Wolo config object

    Returns:
        Result dict with the subagent's response
    """
    from wolo.agent import agent_loop
    from wolo.agents import get_agent
    from wolo.metrics import MetricsCollector
    from wolo.session import add_user_message, create_subsession, get_session_messages

    # Get agent config
    agent_config = get_agent(agent)

    # Create subsession
    subsession_id = create_subsession(parent_session_id, agent)
    logger.info(f"Created subsession {subsession_id[:8]}... with {agent} agent")

    # Track subagent session in parent metrics
    collector = MetricsCollector()
    parent_metrics = collector.get_session(parent_session_id)
    if parent_metrics:
        parent_metrics.record_subagent_session(subsession_id)

    # Add user message to subsession
    add_user_message(subsession_id, message)

    # Run agent loop in subsession
    try:
        result = await agent_loop(config, subsession_id, agent_config)

        # Extract response from result
        text_parts = [p.text for p in result.parts if hasattr(p, "text")]
        response_text = "\n".join(text_parts).strip()

        output = f"Subagent ({agent}) response:\n{response_text}"

        # Get message count
        messages = get_session_messages(subsession_id)
        metadata = {
            "subsession_id": subsession_id,
            "agent": agent,
            "message_count": len(messages),
            "finish_reason": result.finish_reason,
        }

        return {"title": description or f"task: {agent}", "output": output, "metadata": metadata}

    except Exception as e:
        logger.error(f"Subagent error: {e}")
        return {
            "title": description or f"task: {agent}",
            "output": f"Subagent error: {e}",
            "metadata": {"error": str(e), "subsession_id": subsession_id},
        }
