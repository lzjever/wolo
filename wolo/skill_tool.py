"""
Skill tool for on-demand skill loading.

OpenCode-style implementation where:
- Available skills are listed in tool description
- Agent decides when to load a skill
- Skill content is returned as tool output
"""

import logging

logger = logging.getLogger(__name__)


def get_skill_tool_schema() -> dict:
    """
    Generate skill tool schema with available skills listed in description.

    The description dynamically includes all available skills so the Agent
    can see what skills are available and decide when to load them.

    Returns:
        Tool schema dict for LLM
    """
    from wolo.mcp_integration import get_claude_skills

    skills = get_claude_skills()

    if not skills:
        description = (
            "Load a skill to get detailed instructions for a specific task. "
            "No skills are currently available."
        )
    else:
        # Build XML-style skill list like OpenCode
        skill_entries = []
        for skill in skills:
            skill_entries.append(
                f"  <skill>\n"
                f"    <name>{skill.name}</name>\n"
                f"    <description>{skill.description}</description>\n"
                f"  </skill>"
            )
        skill_list = "\n".join(skill_entries)

        description = (
            "Load a skill to get detailed instructions for a specific task. "
            "Skills provide specialized knowledge and step-by-step guidance. "
            "Use this when a task matches an available skill's description.\n"
            f"<available_skills>\n{skill_list}\n</available_skills>"
        )

    return {
        "type": "function",
        "function": {
            "name": "skill",
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The skill identifier from available_skills (e.g., 'ui-ux-pro-max')",
                    }
                },
                "required": ["name"],
            },
        },
    }


async def skill_execute(name: str) -> str:
    """
    Load and return skill content.

    Args:
        name: Skill name to load

    Returns:
        Skill content as formatted string, or error message if not found
    """
    from wolo.mcp_integration import get_claude_skills

    skills = get_claude_skills()
    skill = next((s for s in skills if s.name == name), None)

    if not skill:
        available = ", ".join(s.name for s in skills) or "none"
        logger.warning(f"Skill '{name}' not found. Available: {available}")
        return f'Skill "{name}" not found. Available skills: {available}'

    logger.info(f"Loading skill: {name}")

    # Get skill content with resolved paths
    content = skill.get_system_prompt()

    # Format output similar to OpenCode
    output = [
        f"## Skill: {skill.name}",
        "",
        f"**Base directory**: {skill.skill_dir}",
        "",
        content.strip(),
    ]

    return "\n".join(output)
