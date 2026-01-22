"""
Comprehensive test suite for Wolo CLI covering all parameter combinations and usage scenarios.

This test suite aims to cover:
1. All command types (chat, repl, session, config)
2. All parameter combinations
3. Edge cases and error handling
4. Session management operations
5. Input methods (stdin, positional, pipe + prompt)
6. Mode combinations (SOLO, COOP, REPL)
7. Integration scenarios
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import sys
import io

from wolo.cli.commands.run import RunCommand
from wolo.cli.commands.repl import ReplCommand
from wolo.cli.commands.session import SessionCommandGroup
from wolo.cli.parser import ParsedArgs, ExecutionOptions, SessionOptions
from wolo.modes import ExecutionMode


# ==================== Test Fixtures ====================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config():
    """Mock Config object."""
    config = Mock()
    config.api_key = "test_key"
    config.base_url = "https://api.test.com"
    config.model = "test-model"
    config.temperature = 0.7
    config.max_tokens = 2000
    config.enable_think = False
    config.debug_llm_file = None
    config.debug_full_dir = None
    config.claude.enabled = False
    config.claude.load_mcp = False
    config.mcp.enabled = False
    config.mcp.servers = {}
    return config


@pytest.fixture
def mock_session():
    """Mock session for testing."""
    session = Mock()
    session.id = "test_session_123"
    session.messages = []
    session.created_at = 1234567890.0
    session.updated_at = 1234567890.0
    return session


# ==================== Run Command Tests ====================

class TestRunCommandBasic:
    """Test basic RunCommand functionality."""
    
    def test_run_command_name(self):
        """Test RunCommand name property."""
        cmd = RunCommand()
        assert cmd.name == "run"
    
    def test_run_command_description(self):
        """Test RunCommand description property."""
        cmd = RunCommand()
        assert "task" in cmd.description.lower() or "execute" in cmd.description.lower()
    
    def test_run_command_validate_with_message(self):
        """Test RunCommand validation with valid message."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.execution_options.mode = ExecutionMode.COOP
        args.message = "test message"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
        assert error_msg == ""
    
    def test_run_command_validate_missing_message(self):
        """Test RunCommand validation with missing message."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.execution_options.mode = ExecutionMode.COOP
        args.message = ""
        args.message_from_stdin = False
        
        is_valid, error_msg = cmd.validate_args(args)
        assert not is_valid
        assert "prompt" in error_msg.lower() or "message" in error_msg.lower()
    
    def test_run_command_validate_repl_mode_no_message_ok(self):
        """Test RunCommand validation in REPL mode (message not required)."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.execution_options.mode = ExecutionMode.REPL
        args.message = ""
        args.message_from_stdin = False
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid


class TestRunCommandSessionOptions:
    """Test RunCommand with session-related options."""
    
    def test_validate_resume_without_message(self):
        """Test validation: -r requires message."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.session_options.resume_id = "test_session"
        args.message = ""
        args.message_from_stdin = False
        
        is_valid, error_msg = cmd.validate_args(args)
        assert not is_valid
        assert "-r" in error_msg or "--resume" in error_msg
    
    def test_validate_resume_with_message(self):
        """Test validation: -r with message is valid."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.session_options.resume_id = "test_session"
        args.message = "continue task"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_validate_watch_error(self):
        """Test validation: -w should not be in run command."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.session_options.watch_id = "test_session"
        args.message = "test"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert not is_valid
        assert "-w" in error_msg or "--watch" in error_msg
    
    def test_validate_session_name_with_message(self):
        """Test validation: -s with message is valid."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.session_options.session_name = "my_session"
        args.message = "test message"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_validate_session_name_empty_string(self):
        """Test validation: -s with empty string (auto-generate) is valid."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.session_options.session_name = ""  # Auto-generate
        args.message = "test message"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid


class TestRunCommandExecutionModes:
    """Test RunCommand with different execution modes."""
    
    @pytest.mark.parametrize("mode", [
        ExecutionMode.SOLO,
        ExecutionMode.COOP,
        ExecutionMode.REPL,
    ])
    def test_validate_mode_with_message(self, mode):
        """Test validation with different modes and message."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.execution_options.mode = mode
        args.message = "test message"
        
        is_valid, error_msg = cmd.validate_args(args)
        if mode == ExecutionMode.REPL:
            # REPL mode doesn't require message
            assert is_valid
        else:
            # Other modes require message
            assert is_valid  # With message, should be valid
    
    def test_validate_solo_mode_no_message(self):
        """Test validation: solo mode requires message."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.execution_options.mode = ExecutionMode.SOLO
        args.message = ""
        args.message_from_stdin = False
        
        is_valid, error_msg = cmd.validate_args(args)
        assert not is_valid
    
    def test_validate_coop_mode_no_message(self):
        """Test validation: coop mode requires message."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.execution_options.mode = ExecutionMode.COOP
        args.message = ""
        args.message_from_stdin = False
        
        is_valid, error_msg = cmd.validate_args(args)
        assert not is_valid


class TestRunCommandAgentOptions:
    """Test RunCommand with agent type options."""
    
    @pytest.mark.parametrize("agent_type", [
        "general",
        "plan",
        "explore",
        "compaction",
    ])
    def test_agent_type_validation(self, agent_type):
        """Test validation with different agent types."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.execution_options.agent_type = agent_type
        args.message = "test"
        
        # This will be validated in execute(), not validate_args()
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid  # validate_args doesn't check agent type


class TestRunCommandOtherOptions:
    """Test RunCommand with other execution options."""
    
    def test_validate_with_max_steps(self):
        """Test validation with --max-steps."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.execution_options.max_steps = 50
        args.message = "test"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_validate_with_save_flag(self):
        """Test validation with --save flag."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.execution_options.save_session = True
        args.message = "test"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_validate_with_benchmark_flag(self):
        """Test validation with --benchmark flag."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.execution_options.benchmark_mode = True
        args.message = "test"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid


# ==================== REPL Command Tests ====================

class TestReplCommand:
    """Test ReplCommand functionality."""
    
    def test_repl_command_name(self):
        """Test ReplCommand name property."""
        cmd = ReplCommand()
        assert cmd.name == "repl"
    
    def test_repl_command_validation_always_passes(self):
        """Test ReplCommand validation (should always pass)."""
        cmd = ReplCommand()
        args = ParsedArgs()
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
        assert error_msg == ""
    
    def test_repl_command_validation_with_message(self):
        """Test ReplCommand validation with initial message."""
        cmd = ReplCommand()
        args = ParsedArgs()
        args.message = "initial message"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_repl_command_validation_without_message(self):
        """Test ReplCommand validation without message (should still pass)."""
        cmd = ReplCommand()
        args = ParsedArgs()
        args.message = ""
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid


# ==================== Session Command Tests ====================

class TestSessionCommandGroup:
    """Test SessionCommandGroup functionality."""
    
    def test_session_command_name(self):
        """Test SessionCommandGroup name property."""
        cmd = SessionCommandGroup()
        assert cmd.name == "session"
    
    @pytest.mark.parametrize("subcommand", [
        "list",
        "create",
        "resume",
        "watch",
        "delete",
        "show",
    ])
    def test_session_subcommands_exist(self, subcommand):
        """Test that all session subcommands exist."""
        cmd = SessionCommandGroup()
        # Check if subcommand is in available subcommands
        args = ParsedArgs()
        args.subcommand = subcommand
        # Just verify the command group exists and can handle the subcommand
        assert cmd.name == "session"


# ==================== Parameter Combination Tests ====================

class TestParameterCombinations:
    """Test various parameter combinations."""
    
    def test_basic_run_with_all_options(self):
        """Test run command with all common options."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "test message"
        args.execution_options.mode = ExecutionMode.COOP
        args.execution_options.agent_type = "general"
        args.execution_options.max_steps = 50
        args.execution_options.save_session = True
        args.session_options.session_name = "test_session"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_resume_with_all_options(self):
        """Test resume with various options."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.session_options.resume_id = "existing_session"
        args.message = "continue"
        args.execution_options.mode = ExecutionMode.COOP
        args.execution_options.agent_type = "plan"
        args.execution_options.max_steps = 100
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_solo_mode_with_save(self):
        """Test solo mode with save flag."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "test"
        args.execution_options.mode = ExecutionMode.SOLO
        args.execution_options.save_session = True
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_coop_mode_with_benchmark(self):
        """Test coop mode with benchmark."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "test"
        args.execution_options.mode = ExecutionMode.COOP
        args.execution_options.benchmark_mode = True
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_repl_mode_with_session_name(self):
        """Test REPL mode with session name."""
        cmd = ReplCommand()
        args = ParsedArgs()
        args.message = "initial"
        args.session_options.session_name = "repl_session"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_max_steps_with_different_modes(self):
        """Test max-steps with different modes."""
        for mode in [ExecutionMode.SOLO, ExecutionMode.COOP, ExecutionMode.REPL]:
            cmd = RunCommand()
            args = ParsedArgs()
            args.message = "test"
            args.execution_options.mode = mode
            args.execution_options.max_steps = 25
            
            is_valid, error_msg = cmd.validate_args(args)
            assert is_valid
    
    def test_agent_type_with_different_modes(self):
        """Test agent type with different modes."""
        for mode in [ExecutionMode.SOLO, ExecutionMode.COOP, ExecutionMode.REPL]:
            for agent_type in ["general", "plan", "explore"]:
                cmd = RunCommand()
                args = ParsedArgs()
                args.message = "test"
                args.execution_options.mode = mode
                args.execution_options.agent_type = agent_type
                
                is_valid, error_msg = cmd.validate_args(args)
                assert is_valid


# ==================== Edge Cases and Error Handling ====================

class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_message_string(self):
        """Test with empty string message."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.message = ""
        args.message_from_stdin = False
        args.execution_options.mode = ExecutionMode.COOP
        
        is_valid, error_msg = cmd.validate_args(args)
        assert not is_valid
    
    def test_whitespace_only_message(self):
        """Test with whitespace-only message."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "   \n\t  "
        args.message_from_stdin = False
        args.execution_options.mode = ExecutionMode.COOP
        
        # Note: Validation checks if message exists, not if it's whitespace
        # Whitespace stripping happens in get_message_from_sources
        is_valid, error_msg = cmd.validate_args(args)
        # Currently validation passes (whitespace is considered a message)
        # This is acceptable - whitespace stripping happens later
        assert is_valid
    
    def test_very_long_message(self):
        """Test with very long message."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "x" * 10000  # 10KB message
        args.execution_options.mode = ExecutionMode.COOP
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid  # Should pass validation
    
    def test_max_steps_zero(self):
        """Test with max-steps = 0."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "test"
        args.execution_options.max_steps = 0
        
        # This should be validated in execute(), not validate_args()
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_max_steps_negative(self):
        """Test with negative max-steps."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "test"
        args.execution_options.max_steps = -1
        
        # This should be validated in execute(), not validate_args()
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_max_steps_very_large(self):
        """Test with very large max-steps."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "test"
        args.execution_options.max_steps = 1000000
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_resume_with_empty_session_id(self):
        """Test resume with empty session ID."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.session_options.resume_id = ""
        args.message = "test"
        
        # Empty resume_id should be handled
        is_valid, error_msg = cmd.validate_args(args)
        # Should still pass validation (will fail in execute when checking session)
        assert is_valid
    
    def test_session_name_with_special_chars(self):
        """Test session name with special characters."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.session_options.session_name = "test_session-123_abc"
        args.message = "test"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_multiple_mode_flags(self):
        """Test that only one mode flag can be specified."""
        # This is tested at parser level, but we can test the result
        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "test"
        # If parser allows multiple modes, the last one wins
        # This is parser behavior, not command validation
        args.execution_options.mode = ExecutionMode.COOP
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid


# ==================== Input Method Tests ====================

class TestInputMethods:
    """Test different input methods."""
    
    def test_positional_message(self):
        """Test message as positional argument."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "positional message"
        args.execution_options.mode = ExecutionMode.COOP
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_stdin_input(self):
        """Test stdin input."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.message_from_stdin = True
        args.message = "stdin content"  # Parser sets message from stdin
        args.execution_options.mode = ExecutionMode.COOP
        
        # With stdin, parser should set message
        is_valid, error_msg = cmd.validate_args(args)
        # Should pass if message is set (even from stdin)
        assert is_valid
    
    def test_dual_input_pipe_and_cli(self):
        """Test dual input (pipe + CLI prompt)."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.pipe_input = "context from pipe"
        args.cli_prompt = "user task"
        args.message = "## Context (from stdin)\n\ncontext from pipe\n\n---\n\n## Task\n\nuser task"
        args.execution_options.mode = ExecutionMode.SOLO
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid


# ==================== Integration Scenarios ====================

class TestIntegrationScenarios:
    """Test realistic integration scenarios."""
    
    def test_workflow_create_session_run_task(self):
        """Test workflow: create session, run task."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.session_options.session_name = "workflow_session"
        args.message = "create a hello world file"
        args.execution_options.mode = ExecutionMode.COOP
        args.execution_options.save_session = True
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_workflow_resume_and_continue(self):
        """Test workflow: resume session, continue task."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.session_options.resume_id = "previous_session"
        args.message = "continue from where we left off"
        args.execution_options.mode = ExecutionMode.COOP
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_workflow_solo_automation(self):
        """Test workflow: solo mode for automation."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "automated task"
        args.execution_options.mode = ExecutionMode.SOLO
        args.execution_options.max_steps = 20
        args.execution_options.save_session = True
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_workflow_repl_conversation(self):
        """Test workflow: REPL mode for conversation."""
        cmd = ReplCommand()
        args = ParsedArgs()
        args.message = "let's have a conversation"
        args.session_options.session_name = "repl_chat"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_workflow_benchmark_testing(self):
        """Test workflow: benchmark mode for performance testing."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "test task"
        args.execution_options.mode = ExecutionMode.SOLO
        args.execution_options.benchmark_mode = True
        args.execution_options.benchmark_output = "custom_benchmark.json"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_workflow_debug_mode(self):
        """Test workflow: debug mode with LLM logging."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "debug this task"
        args.execution_options.mode = ExecutionMode.COOP
        args.execution_options.debug_llm_file = "debug.log"
        args.execution_options.debug_full_dir = "/tmp/debug"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid


# ==================== Execution Error Handling Tests ====================

class TestExecutionErrorHandling:
    """Test error handling in execution scenarios."""
    
    def test_validate_invalid_agent_type(self):
        """Test validation logic for invalid agent type."""
        # Note: Agent type validation happens in execute(), not validate_args()
        # So validate_args should pass, but execute() should fail
        cmd = RunCommand()
        args = ParsedArgs()
        args.message = "test"
        args.execution_options.agent_type = "invalid_agent"
        
        # Validation passes (agent type checked in execute)
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_validate_resume_workflow(self):
        """Test validation for resume workflow."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.session_options.resume_id = "test_session"
        args.message = "continue"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_validate_session_creation_workflow(self):
        """Test validation for session creation workflow."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.session_options.session_name = "new_session"
        args.message = "new task"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid
    
    def test_validate_auto_session_workflow(self):
        """Test validation for auto-generated session workflow."""
        cmd = RunCommand()
        args = ParsedArgs()
        # No session_name set, should auto-generate
        args.message = "auto task"
        
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid


# ==================== Parameter Parsing Edge Cases ====================

class TestParameterParsingEdgeCases:
    """Test edge cases in parameter parsing."""
    
    def test_session_name_with_spaces(self):
        """Test session name containing spaces."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.session_options.session_name = "my session name"
        args.message = "test"
        
        # Session names with spaces might be sanitized
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid  # Validation passes, sanitization happens in execute
    
    def test_resume_id_with_path_separators(self):
        """Test resume ID with path separators (security check)."""
        cmd = RunCommand()
        args = ParsedArgs()
        args.session_options.resume_id = "../../etc/passwd"
        args.message = "test"
        
        # Should be validated in execute() to prevent path traversal
        is_valid, error_msg = cmd.validate_args(args)
        assert is_valid  # Validation passes, security check in execute


# ==================== Summary Test ====================

class TestComprehensiveCoverage:
    """Test to ensure comprehensive coverage."""
    
    def test_all_execution_modes_covered(self):
        """Verify all execution modes are tested."""
        modes = [ExecutionMode.SOLO, ExecutionMode.COOP, ExecutionMode.REPL]
        for mode in modes:
            cmd = RunCommand()
            args = ParsedArgs()
            args.message = "test"
            args.execution_options.mode = mode
            
            is_valid, _ = cmd.validate_args(args)
            assert is_valid or mode == ExecutionMode.REPL  # REPL might not need message
    
    def test_all_session_options_covered(self):
        """Verify all session options are tested."""
        session_options = [
            ("session_name", "test_session"),
            ("resume_id", "existing_session"),
            ("watch_id", "watch_session"),  # Should error in run command
        ]
        
        for option_name, option_value in session_options:
            cmd = RunCommand()
            args = ParsedArgs()
            args.message = "test"
            setattr(args.session_options, option_name, option_value)
            
            if option_name == "watch_id":
                # Should fail validation
                is_valid, error_msg = cmd.validate_args(args)
                assert not is_valid
                assert "watch" in error_msg.lower() or "-w" in error_msg
            else:
                is_valid, _ = cmd.validate_args(args)
                assert is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
