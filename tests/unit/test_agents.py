"""Test suite for agent permissions."""

import pytest

from wolo.agents import (
    COMPACTION_AGENT,
    EXPLORE_AGENT,
    GENERAL_AGENT,
    PLAN_AGENT,
    check_permission,
    get_permissions,
)


class TestPermissionRules:
    """Test permission system."""

    def test_allow_all_permissions(self):
        """Test ALLOW_ALL ruleset."""
        permissions = get_permissions("allow_all")
        assert len(permissions) == 0

    def test_read_only_permissions(self):
        """Test READ_ONLY ruleset."""
        permissions = get_permissions("read_only")

        # Check allowed tools
        allowed = [p for p in permissions if p.action == "allow"]
        allowed_tools = {p.tool for p in allowed}
        assert "read" in allowed_tools
        assert "grep" in allowed_tools
        assert "glob" in allowed_tools

        # Check denied tools
        denied = [p for p in permissions if p.action == "deny"]
        denied_tools = {p.tool for p in denied}
        assert "write" in denied_tools
        assert "edit" in denied_tools
        assert "shell" in denied_tools
        assert "multiedit" in denied_tools

    def test_check_permission_allow(self):
        """Test permission check for allowed tool."""
        result = check_permission(GENERAL_AGENT, "read")
        assert result == "allow"

    def test_check_permission_deny(self):
        """Test permission check for denied tool."""
        result = check_permission(PLAN_AGENT, "write")
        assert result == "deny"

    def test_check_permission_default_allow(self):
        """Test that unspecified tools are allowed by default."""
        result = check_permission(GENERAL_AGENT, "unknown_tool")
        assert result == "allow"


class TestAgentConfigs:
    """Test agent configurations."""

    def test_general_agent_config(self):
        """Test general agent configuration."""
        assert GENERAL_AGENT.name == "general"
        assert GENERAL_AGENT.description is not None
        assert GENERAL_AGENT.system_prompt is not None
        assert len(GENERAL_AGENT.permissions) == 0  # Allow all

    def test_plan_agent_config(self):
        """Test plan agent configuration."""
        assert PLAN_AGENT.name == "plan"
        assert PLAN_AGENT.description is not None
        assert "READ-ONLY" in PLAN_AGENT.system_prompt

    def test_explore_agent_config(self):
        """Test explore agent configuration."""
        assert EXPLORE_AGENT.name == "explore"
        assert EXPLORE_AGENT.description is not None

    def test_compaction_agent_config(self):
        """Test compaction agent configuration."""
        assert COMPACTION_AGENT.name == "compaction"
        assert "summarize" in COMPACTION_AGENT.system_prompt.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
