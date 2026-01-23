"""Tests for execution modes."""

from wolo.modes import ExecutionMode, ModeConfig, QuotaConfig


def test_execution_mode_enum():
    """Test ExecutionMode enum values."""
    assert ExecutionMode.SOLO.value == "solo"
    assert ExecutionMode.COOP.value == "coop"
    assert ExecutionMode.REPL.value == "repl"


def test_mode_config_solo():
    """Test ModeConfig for SOLO mode."""
    config = ModeConfig.for_mode(ExecutionMode.SOLO)
    assert config.mode == ExecutionMode.SOLO
    assert config.enable_keyboard_shortcuts is True  # Changed: SOLO has shortcuts
    assert config.enable_question_tool is False  # SOLO: no questions
    assert config.enable_ui_state is True  # Changed: SOLO has UI
    assert config.exit_after_task is True
    assert config.wait_for_input_before_start is False


def test_mode_config_coop():
    """Test ModeConfig for COOP mode."""
    config = ModeConfig.for_mode(ExecutionMode.COOP)
    assert config.mode == ExecutionMode.COOP
    assert config.enable_keyboard_shortcuts is True
    assert config.enable_question_tool is True  # COOP: questions allowed
    assert config.enable_ui_state is True
    assert config.exit_after_task is True
    assert config.wait_for_input_before_start is False


def test_mode_config_repl():
    """Test ModeConfig for REPL mode."""
    config = ModeConfig.for_mode(ExecutionMode.REPL)
    assert config.mode == ExecutionMode.REPL
    assert config.enable_keyboard_shortcuts is True
    assert config.enable_question_tool is True
    assert config.enable_ui_state is True
    assert config.exit_after_task is False
    assert config.wait_for_input_before_start is False


def test_quota_config():
    """Test QuotaConfig."""
    quota = QuotaConfig(max_steps=50)
    assert quota.max_steps == 50
    assert quota.max_tokens is None
    assert quota.max_time_seconds is None

    # Test quota check
    assert quota.check_quota_exceeded(49) is False
    assert quota.check_quota_exceeded(50) is True
    assert quota.check_quota_exceeded(51) is True


def test_quota_config_default():
    """Test QuotaConfig default values."""
    quota = QuotaConfig()
    assert quota.max_steps == 100
    assert quota.max_tokens is None
    assert quota.max_time_seconds is None


def test_tool_filtering():
    """Test that tools can be filtered."""
    from wolo.tools import get_all_tools

    # Get all tools
    all_tools = get_all_tools()
    tool_names = {t["function"]["name"] for t in all_tools}

    # Verify question tool exists
    assert "question" in tool_names

    # Get tools excluding question
    filtered_tools = get_all_tools(excluded_tools={"question"})
    filtered_names = {t["function"]["name"] for t in filtered_tools}

    # Verify question tool is excluded
    assert "question" not in filtered_names
    # Verify other tools still exist
    assert "read" in filtered_names
    assert "write" in filtered_names
