"""Tests for compaction configuration."""

import pytest
from wolo.compaction.config import (
    CompactionConfig,
    SummaryPolicyConfig,
    ToolPruningPolicyConfig,
    get_default_config,
    load_compaction_config,
)


class TestGetDefaultConfig:
    """Tests for get_default_config function."""
    
    def test_returns_compaction_config(self):
        """Should return CompactionConfig instance."""
        config = get_default_config()
        assert isinstance(config, CompactionConfig)
    
    def test_default_enabled_true(self):
        """Default should have compaction enabled."""
        config = get_default_config()
        assert config.enabled is True
    
    def test_default_auto_compact_true(self):
        """Default should have auto_compact enabled."""
        config = get_default_config()
        assert config.auto_compact is True
    
    def test_default_check_interval_3(self):
        """Default check interval should be 3."""
        config = get_default_config()
        assert config.check_interval_steps == 3
    
    def test_default_overflow_threshold_0_9(self):
        """Default overflow threshold should be 0.9."""
        config = get_default_config()
        assert config.overflow_threshold == 0.9
    
    def test_default_reserved_tokens_2000(self):
        """Default reserved tokens should be 2000."""
        config = get_default_config()
        assert config.reserved_tokens == 2000
    
    def test_default_summary_policy(self):
        """Default should have summary policy with correct defaults."""
        config = get_default_config()
        assert config.summary_policy.enabled is True
        assert config.summary_policy.recent_exchanges_to_keep == 6
        assert config.summary_policy.summary_max_tokens is None
    
    def test_default_pruning_policy(self):
        """Default should have pruning policy with correct defaults."""
        config = get_default_config()
        assert config.tool_pruning_policy.enabled is True
        assert config.tool_pruning_policy.protect_recent_turns == 2
        assert config.tool_pruning_policy.protect_token_threshold == 40000
        assert config.tool_pruning_policy.minimum_prune_tokens == 20000


class TestLoadCompactionConfig:
    """Tests for load_compaction_config function."""
    
    def test_empty_dict_returns_defaults(self):
        """Empty dict should return default configuration."""
        config = load_compaction_config({})
        default = get_default_config()
        assert config.enabled == default.enabled
        assert config.auto_compact == default.auto_compact
    
    def test_none_returns_defaults(self):
        """None should return default configuration."""
        config = load_compaction_config(None)
        assert isinstance(config, CompactionConfig)
        assert config.enabled is True
    
    def test_override_enabled(self):
        """Should be able to override enabled."""
        config = load_compaction_config({"enabled": False})
        assert config.enabled is False
    
    def test_override_auto_compact(self):
        """Should be able to override auto_compact."""
        config = load_compaction_config({"auto_compact": False})
        assert config.auto_compact is False
    
    def test_override_check_interval(self):
        """Should be able to override check_interval_steps."""
        config = load_compaction_config({"check_interval_steps": 5})
        assert config.check_interval_steps == 5
    
    def test_override_overflow_threshold(self):
        """Should be able to override overflow_threshold."""
        config = load_compaction_config({"overflow_threshold": 0.8})
        assert config.overflow_threshold == 0.8
    
    def test_override_reserved_tokens(self):
        """Should be able to override reserved_tokens."""
        config = load_compaction_config({"reserved_tokens": 3000})
        assert config.reserved_tokens == 3000
    
    def test_override_summary_policy(self):
        """Should be able to override summary policy settings."""
        config = load_compaction_config({
            "summary_policy": {
                "enabled": False,
                "recent_exchanges_to_keep": 10,
            }
        })
        assert config.summary_policy.enabled is False
        assert config.summary_policy.recent_exchanges_to_keep == 10
    
    def test_override_pruning_policy(self):
        """Should be able to override pruning policy settings."""
        config = load_compaction_config({
            "tool_pruning_policy": {
                "protected_tools": ["read", "write"],
                "minimum_prune_tokens": 30000,
            }
        })
        assert config.tool_pruning_policy.protected_tools == ("read", "write")
        assert config.tool_pruning_policy.minimum_prune_tokens == 30000
    
    def test_partial_override_preserves_defaults(self):
        """Partial override should preserve other defaults."""
        config = load_compaction_config({
            "summary_policy": {
                "enabled": False,
            }
        })
        # enabled was overridden
        assert config.summary_policy.enabled is False
        # Other values should be defaults
        assert config.summary_policy.recent_exchanges_to_keep == 6
        assert config.summary_policy.summary_max_tokens is None
    
    def test_override_policy_priority(self):
        """Should be able to override policy priority."""
        config = load_compaction_config({
            "policy_priority": {
                "tool_pruning": 100,
                "summary": 50,
            }
        })
        assert config.policy_priority["tool_pruning"] == 100
        assert config.policy_priority["summary"] == 50


class TestSummaryPolicyConfig:
    """Tests for SummaryPolicyConfig."""
    
    def test_default_values(self):
        """Should have correct default values."""
        config = SummaryPolicyConfig()
        assert config.enabled is True
        assert config.recent_exchanges_to_keep == 6
        assert config.summary_max_tokens is None
        assert config.summary_prompt_template == ""
        assert config.include_tool_calls_in_summary is True


class TestToolPruningPolicyConfig:
    """Tests for ToolPruningPolicyConfig."""
    
    def test_default_values(self):
        """Should have correct default values."""
        config = ToolPruningPolicyConfig()
        assert config.enabled is True
        assert config.protect_recent_turns == 2
        assert config.protect_token_threshold == 40000
        assert config.minimum_prune_tokens == 20000
        assert config.protected_tools == ()
        assert "[pruned]" in config.replacement_text.lower() or "Output pruned" in config.replacement_text
