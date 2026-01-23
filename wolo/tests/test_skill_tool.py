"""Tests for skill tool."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("mcp")
import wolo.mcp_integration  # noqa: F401 - ensure module is loaded so patch("wolo.mcp_integration.get_claude_skills") can resolve


class TestGetSkillToolSchema:
    """Tests for get_skill_tool_schema function."""

    def test_schema_with_no_skills(self):
        """Test schema generation when no skills are available."""
        with patch("wolo.mcp_integration.get_claude_skills", return_value=[]):
            from wolo.skill_tool import get_skill_tool_schema

            schema = get_skill_tool_schema()

            assert schema["type"] == "function"
            assert schema["function"]["name"] == "skill"
            assert "No skills are currently available" in schema["function"]["description"]
            assert "name" in schema["function"]["parameters"]["properties"]

    def test_schema_with_skills(self):
        """Test schema generation with available skills."""
        # Create mock skills
        mock_skill1 = MagicMock()
        mock_skill1.name = "test-skill"
        mock_skill1.description = "A test skill for testing"

        mock_skill2 = MagicMock()
        mock_skill2.name = "another-skill"
        mock_skill2.description = "Another skill"

        with patch(
            "wolo.mcp_integration.get_claude_skills", return_value=[mock_skill1, mock_skill2]
        ):
            from wolo.skill_tool import get_skill_tool_schema

            schema = get_skill_tool_schema()

            assert schema["type"] == "function"
            assert schema["function"]["name"] == "skill"

            desc = schema["function"]["description"]
            assert "<available_skills>" in desc
            assert "<name>test-skill</name>" in desc
            assert "<name>another-skill</name>" in desc
            assert "<description>A test skill for testing</description>" in desc

    def test_schema_parameters(self):
        """Test that schema has correct parameters."""
        with patch("wolo.mcp_integration.get_claude_skills", return_value=[]):
            from wolo.skill_tool import get_skill_tool_schema

            schema = get_skill_tool_schema()

            params = schema["function"]["parameters"]
            assert params["type"] == "object"
            assert "name" in params["properties"]
            assert params["properties"]["name"]["type"] == "string"
            assert "name" in params["required"]


class TestSkillExecute:
    """Tests for skill_execute function."""

    @pytest.mark.asyncio
    async def test_execute_found_skill(self):
        """Test loading an existing skill."""
        mock_skill = MagicMock()
        mock_skill.name = "test-skill"
        mock_skill.skill_dir = Path("/test/skills/test-skill")
        mock_skill.get_system_prompt.return_value = (
            "# Test Skill Content\n\nThis is the skill content."
        )

        with patch("wolo.mcp_integration.get_claude_skills", return_value=[mock_skill]):
            from wolo.skill_tool import skill_execute

            result = await skill_execute("test-skill")

            assert "## Skill: test-skill" in result
            assert "**Base directory**:" in result
            assert "Test Skill Content" in result

    @pytest.mark.asyncio
    async def test_execute_skill_not_found(self):
        """Test error when skill is not found."""
        mock_skill = MagicMock()
        mock_skill.name = "existing-skill"

        with patch("wolo.mcp_integration.get_claude_skills", return_value=[mock_skill]):
            from wolo.skill_tool import skill_execute

            result = await skill_execute("nonexistent-skill")

            assert 'Skill "nonexistent-skill" not found' in result
            assert "existing-skill" in result

    @pytest.mark.asyncio
    async def test_execute_no_skills_available(self):
        """Test error when no skills are available."""
        with patch("wolo.mcp_integration.get_claude_skills", return_value=[]):
            from wolo.skill_tool import skill_execute

            result = await skill_execute("any-skill")

            assert 'Skill "any-skill" not found' in result
            assert "Available skills: none" in result


class TestSkillToolIntegration:
    """Integration tests for skill tool with tool registry."""

    def test_skill_in_registry(self):
        """Test that SKILL is registered in tool registry."""
        from wolo.tool_registry import get_registry

        registry = get_registry()
        spec = registry.get("skill")

        assert spec is not None
        assert spec.name == "skill"
        assert spec.icon == "📚"
        assert spec.show_output is True

    def test_skill_brief_formatter(self):
        """Test skill brief formatter."""
        from wolo.tool_registry import SKILL

        brief = SKILL.format_brief({"name": "ui-ux-pro-max"})

        assert "📚" in brief
        assert "ui-ux-pro-max" in brief

    def test_skill_llm_schema(self):
        """Test skill LLM schema generation."""
        from wolo.tool_registry import SKILL

        schema = SKILL.to_llm_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "skill"
        assert "name" in schema["function"]["parameters"]["properties"]


class TestGetAllToolsWithSkill:
    """Test get_all_tools includes dynamic skill schema."""

    def test_get_all_tools_includes_skill(self):
        """Test that get_all_tools includes skill tool."""
        with patch("wolo.mcp_integration.get_claude_skills", return_value=[]):
            from wolo.tools import get_all_tools

            tools = get_all_tools()

            skill_tools = [t for t in tools if t.get("function", {}).get("name") == "skill"]
            assert len(skill_tools) == 1

    def test_get_all_tools_dynamic_skill_description(self):
        """Test that skill tool has dynamic description with skills."""
        mock_skill = MagicMock()
        mock_skill.name = "dynamic-skill"
        mock_skill.description = "A dynamically loaded skill"

        with patch("wolo.mcp_integration.get_claude_skills", return_value=[mock_skill]):
            from wolo.tools import get_all_tools

            tools = get_all_tools()

            skill_tools = [t for t in tools if t.get("function", {}).get("name") == "skill"]
            assert len(skill_tools) == 1

            desc = skill_tools[0]["function"]["description"]
            assert "<name>dynamic-skill</name>" in desc
