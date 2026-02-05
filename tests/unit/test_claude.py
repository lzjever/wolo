"""Tests for Claude compatibility module."""

import json

from wolo.claude.config import apply_claude_env, load_claude_config
from wolo.claude.mcp_config import (
    MCPServerConfig,
    load_claude_mcp_servers,
    merge_mcp_configs,
)
from wolo.claude.skill_loader import (
    find_matching_skills,
    load_claude_skills,
    load_skill,
    parse_frontmatter,
)


class TestClaudeConfig:
    """Tests for Claude configuration loading."""

    def test_load_nonexistent_config(self, tmp_path):
        """Test loading from non-existent directory."""
        config = load_claude_config(tmp_path / "nonexistent")
        assert not config.exists
        assert config.env == {}
        assert config.enabled_plugins == {}

    def test_load_empty_config(self, tmp_path):
        """Test loading from empty directory."""
        config = load_claude_config(tmp_path)
        assert config.exists
        assert config.env == {}
        assert config.enabled_plugins == {}

    def test_load_settings_json(self, tmp_path):
        """Test loading settings.json."""
        settings = {
            "env": {
                "API_KEY": "test-key",
                "DEBUG": "true",
            },
            "enabledPlugins": {
                "plugin-a": True,
                "plugin-b": False,
            },
        }
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps(settings))

        config = load_claude_config(tmp_path)
        assert config.exists
        assert config.env == {"API_KEY": "test-key", "DEBUG": "true"}
        assert config.enabled_plugins == {"plugin-a": True, "plugin-b": False}

    def test_apply_claude_env(self, tmp_path, monkeypatch):
        """Test applying Claude env vars."""
        settings = {"env": {"TEST_VAR": "test-value"}}
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps(settings))

        # Ensure TEST_VAR is not set
        monkeypatch.delenv("TEST_VAR", raising=False)

        config = load_claude_config(tmp_path)
        apply_claude_env(config)

        import os

        assert os.environ.get("TEST_VAR") == "test-value"


class TestParseFrontmatter:
    """Tests for YAML frontmatter parsing."""

    def test_parse_with_frontmatter(self):
        """Test parsing content with frontmatter."""
        content = """---
name: test-skill
description: A test skill
---

# Content here
"""
        frontmatter, body = parse_frontmatter(content)
        assert frontmatter["name"] == "test-skill"
        assert frontmatter["description"] == "A test skill"
        assert body.strip() == "# Content here"

    def test_parse_without_frontmatter(self):
        """Test parsing content without frontmatter."""
        content = "# Just content\n\nNo frontmatter here."
        frontmatter, body = parse_frontmatter(content)
        assert frontmatter == {}
        assert body == content

    def test_parse_empty_frontmatter(self):
        """Test parsing empty frontmatter."""
        content = """---
---

Content after empty frontmatter.
"""
        frontmatter, body = parse_frontmatter(content)
        assert frontmatter == {}
        assert "Content after" in body


class TestClaudeSkill:
    """Tests for Claude skill loading."""

    def test_load_skill(self, tmp_path):
        """Test loading a skill from directory."""
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: A test skill for testing
---

# Test Skill

This is a test skill.

## Usage

Use it like this.
""")

        skill = load_skill(skill_dir)
        assert skill is not None
        assert skill.name == "test-skill"
        assert skill.description == "A test skill for testing"
        assert "# Test Skill" in skill.content

    def test_load_skill_no_skill_md(self, tmp_path):
        """Test loading from directory without SKILL.md."""
        skill_dir = tmp_path / "empty-skill"
        skill_dir.mkdir()

        skill = load_skill(skill_dir)
        assert skill is None

    def test_skill_matches(self, tmp_path):
        """Test skill matching."""
        skill_dir = tmp_path / "ui-skill"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: ui-design
description: UI design and styling tools
---

# UI Design Skill
""")

        skill = load_skill(skill_dir)
        assert skill.matches("help me with UI design")
        assert skill.matches("ui-design")
        assert skill.matches("styling")
        assert not skill.matches("database migration")

    def test_load_claude_skills(self, tmp_path):
        """Test loading multiple skills."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create two skills
        for name in ["skill-a", "skill-b"]:
            skill_dir = skills_dir / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(f"""---
name: {name}
description: Skill {name}
---

# {name}
""")

        skills = load_claude_skills(skills_dir)
        assert len(skills) == 2
        names = {s.name for s in skills}
        assert names == {"skill-a", "skill-b"}

    def test_find_matching_skills(self, tmp_path):
        """Test finding matching skills."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create skills
        for name, desc in [
            ("ui-design", "UI design tools"),
            ("api-client", "API client generation"),
        ]:
            skill_dir = skills_dir / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(f"""---
name: {name}
description: {desc}
---

# {name}
""")

        skills = load_claude_skills(skills_dir)

        # Find UI skill
        matches = find_matching_skills(skills, "help me design a UI")
        assert len(matches) == 1
        assert matches[0].name == "ui-design"

        # Find API skill
        matches = find_matching_skills(skills, "generate API client")
        assert len(matches) == 1
        assert matches[0].name == "api-client"


class TestMCPServerConfig:
    """Tests for MCP server configuration."""

    def test_requires_node(self):
        """Test Node.js requirement detection."""
        npx_server = MCPServerConfig(
            name="test",
            command="npx",
            args=["-y", "@test/server"],
        )
        assert npx_server.requires_node()

        python_server = MCPServerConfig(
            name="test",
            command="python",
            args=["-m", "test_server"],
        )
        assert not python_server.requires_node()

    def test_to_dict(self):
        """Test conversion to dictionary."""
        server = MCPServerConfig(
            name="test-server",
            command="npx",
            args=["-y", "@test/server"],
            env={"API_KEY": "xxx"},
            enabled=True,
        )

        d = server.to_dict()
        assert d["name"] == "test-server"
        assert d["command"] == "npx"
        assert d["args"] == ["-y", "@test/server"]
        assert d["env"] == {"API_KEY": "xxx"}
        assert d["enabled"] is True

    def test_load_claude_mcp_servers_nonexistent(self, tmp_path):
        """Test loading from non-existent config."""
        servers = load_claude_mcp_servers(tmp_path / "nonexistent.json")
        assert servers == {}

    def test_load_claude_mcp_servers(self, tmp_path):
        """Test loading MCP servers from config."""
        config = {
            "mcpServers": {
                "web-search": {
                    "command": "npx",
                    "args": ["-y", "@anthropic/mcp-server-web-search"],
                    "env": {"BRAVE_API_KEY": "xxx"},
                },
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@anthropic/mcp-server-filesystem", "/home"],
                },
            }
        }

        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text(json.dumps(config))

        servers = load_claude_mcp_servers(config_path)
        assert len(servers) == 2
        assert "web-search" in servers
        assert "filesystem" in servers

        ws = servers["web-search"]
        assert ws.command == "npx"
        assert ws.args == ["-y", "@anthropic/mcp-server-web-search"]
        assert ws.env == {"BRAVE_API_KEY": "xxx"}

    def test_merge_mcp_configs(self):
        """Test merging MCP configurations."""
        claude_servers = {
            "web-search": MCPServerConfig(
                name="web-search", command="npx", args=["claude-version"]
            ),
            "filesystem": MCPServerConfig(name="filesystem", command="npx", args=["fs"]),
        }

        wolo_servers = {
            "web-search": MCPServerConfig(
                name="web-search", command="python", args=["wolo-version"]
            ),
            "custom": MCPServerConfig(name="custom", command="python", args=["custom"]),
        }

        merged = merge_mcp_configs(claude_servers, wolo_servers)

        # Wolo overrides Claude
        assert merged["web-search"].command == "python"
        assert merged["web-search"].args == ["wolo-version"]

        # Claude-only server preserved
        assert merged["filesystem"].command == "npx"

        # Wolo-only server added
        assert merged["custom"].command == "python"
