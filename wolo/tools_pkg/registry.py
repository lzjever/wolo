"""Tool registry helpers."""

import logging
from typing import Any

from wolo.tool_registry import get_registry

logger = logging.getLogger(__name__)


def get_all_tools(excluded_tools: set[str] = None) -> list[dict[str, Any]]:
    """Get all tool schemas for LLM API.

    Args:
        excluded_tools: Set of tool names to exclude (e.g., {"question"})

    Returns built-in tools plus any MCP tools.
    The skill tool schema is generated dynamically to include available skills.
    """
    if excluded_tools is None:
        excluded_tools = set()

    # Get built-in tools from registry
    tools = get_registry().get_llm_schemas()

    # Filter out excluded tools
    tools = [t for t in tools if t.get("function", {}).get("name") not in excluded_tools]

    # Replace static skill schema with dynamic one that includes available skills
    if "skill" not in excluded_tools:
        try:
            from wolo.skill_tool import get_skill_tool_schema

            dynamic_skill_schema = get_skill_tool_schema()
            # Replace the skill tool schema
            tools = [t for t in tools if t.get("function", {}).get("name") != "skill"]
            tools.append(dynamic_skill_schema)
        except ImportError:
            pass  # skill_tool not available
        except Exception as e:
            logger.warning(f"Failed to generate dynamic skill schema: {e}")

    # Add MCP tools if available
    try:
        from wolo.mcp_integration import get_mcp_tool_schemas

        mcp_tools = get_mcp_tool_schemas()
        # Filter MCP tools too
        mcp_tools = [
            t for t in mcp_tools if t.get("function", {}).get("name") not in excluded_tools
        ]
        tools.extend(mcp_tools)
    except ImportError:
        pass  # MCP integration not available
    except Exception as e:
        logger.warning(f"Failed to get MCP tools: {e}")

    return tools
