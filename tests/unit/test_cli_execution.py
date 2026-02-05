"""Tests for cli/execution.py - execution functions for running tasks, REPL, and watch modes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wolo.cli.exit_codes import ExitCode
from wolo.modes import ExecutionMode


class TestRunSingleTaskMode:
    """Tests for run_single_task_mode function."""

    @pytest.fixture
    def base_mocks(self):
        """Create base mocks for run_single_task_mode."""
        # Functions imported at module level: patch via wolo.cli.execution.<name>
        # Functions imported inline: patch at their original module
        with (
            # Inline import in function body -> patch at original module
            patch(
                "wolo.session.get_or_create_agent_display_name", return_value="Claude"
            ),
            # Module-level imports -> patch via wolo.cli.execution
            patch("wolo.cli.execution.get_manager") as mock_get_manager,
            patch("wolo.cli.execution.create_ui") as mock_create_ui,
            patch("wolo.cli.execution.add_user_message"),
            # Inline import -> patch at original module
            patch("wolo.cli.events.show_agent_start"),
            # Inline import -> patch at original module
            patch(
                "wolo.watch_server.start_watch_server", new_callable=AsyncMock
            ) as mock_watch,
            # Module-level import -> patch via wolo.cli.execution
            patch("wolo.cli.execution.set_watch_server"),
            patch("wolo.cli.execution.agent_loop", new_callable=AsyncMock) as mock_agent_loop,
            patch("wolo.cli.execution.save_session"),
            patch("wolo.cli.execution.remove_manager"),
            # Inline import -> patch at original module
            patch("wolo.session.clear_session_pid"),
            # Inline import -> patch at original module
            patch("wolo.watch_server.stop_watch_server", new_callable=AsyncMock),
            patch(
                "wolo.cli.execution.WoloLLMClient.close_all_sessions", new_callable=AsyncMock
            ),
            # Inline import -> patch at original module
            patch("wolo.mcp_integration.shutdown_mcp", new_callable=AsyncMock),
        ):
            # Setup control mock
            mock_control = MagicMock()
            mock_get_manager.return_value = mock_control

            # Setup UI mock
            mock_ui = MagicMock()
            mock_keyboard = MagicMock()
            mock_create_ui.return_value = (mock_ui, mock_keyboard)

            # Setup watch server mock
            mock_watch.return_value = MagicMock()

            # Setup agent loop result
            mock_result = MagicMock()
            mock_result.finish_reason = "end_turn"
            mock_result.parts = []
            mock_agent_loop.return_value = mock_result

            yield {
                "control": mock_control,
                "ui": mock_ui,
                "keyboard": mock_keyboard,
                "agent_loop": mock_agent_loop,
                "watch": mock_watch,
            }

    @pytest.mark.asyncio
    async def test_successful_execution(self, base_mocks):
        """Test successful execution returns SUCCESS."""
        from wolo.cli.execution import run_single_task_mode
        from wolo.config import Config
        from wolo.modes import ModeConfig, QuotaConfig

        config = MagicMock(spec=Config)
        agent_config = MagicMock()
        mode_config = ModeConfig.for_mode(ExecutionMode.COOP)
        quota_config = QuotaConfig(max_steps=100)

        result = await run_single_task_mode(
            config=config,
            session_id="test-session",
            agent_config=agent_config,
            mode_config=mode_config,
            quota_config=quota_config,
            message_text="Test message",
            save_session_flag=False,
            benchmark_mode=False,
            benchmark_output="",
            question_handler=None,
        )

        assert result == ExitCode.SUCCESS
        base_mocks["agent_loop"].assert_called_once()
        base_mocks["keyboard"].start.assert_called_once()
        base_mocks["keyboard"].stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_returns_interrupted(self, base_mocks):
        """Test that KeyboardInterrupt returns INTERRUPTED."""
        from wolo.cli.execution import run_single_task_mode
        from wolo.config import Config
        from wolo.modes import ModeConfig, QuotaConfig

        base_mocks["agent_loop"].side_effect = KeyboardInterrupt()

        config = MagicMock(spec=Config)
        agent_config = MagicMock()
        mode_config = ModeConfig.for_mode(ExecutionMode.COOP)
        quota_config = QuotaConfig(max_steps=100)

        result = await run_single_task_mode(
            config=config,
            session_id="test-session",
            agent_config=agent_config,
            mode_config=mode_config,
            quota_config=quota_config,
            message_text="Test message",
            save_session_flag=False,
            benchmark_mode=False,
            benchmark_output="",
            question_handler=None,
        )

        assert result == ExitCode.INTERRUPTED

    @pytest.mark.asyncio
    async def test_error_handling_returns_error(self, base_mocks):
        """Test that errors return ERROR."""
        from wolo.cli.execution import run_single_task_mode
        from wolo.config import Config
        from wolo.modes import ModeConfig, QuotaConfig

        base_mocks["agent_loop"].side_effect = RuntimeError("Test error")

        config = MagicMock(spec=Config)
        agent_config = MagicMock()
        mode_config = ModeConfig.for_mode(ExecutionMode.COOP)
        quota_config = QuotaConfig(max_steps=100)

        result = await run_single_task_mode(
            config=config,
            session_id="test-session",
            agent_config=agent_config,
            mode_config=mode_config,
            quota_config=quota_config,
            message_text="Test message",
            save_session_flag=False,
            benchmark_mode=False,
            benchmark_output="",
            question_handler=None,
        )

        assert result == ExitCode.ERROR

    @pytest.mark.asyncio
    async def test_disables_question_tool_when_configured(self, base_mocks):
        """Test that question tool is excluded when enable_question_tool is False."""
        from wolo.cli.execution import run_single_task_mode
        from wolo.config import Config
        from wolo.modes import ModeConfig, QuotaConfig

        config = MagicMock(spec=Config)
        agent_config = MagicMock()
        mode_config = ModeConfig.for_mode(ExecutionMode.SOLO)
        quota_config = QuotaConfig(max_steps=100)

        await run_single_task_mode(
            config=config,
            session_id="test-session",
            agent_config=agent_config,
            mode_config=mode_config,
            quota_config=quota_config,
            message_text="Test message",
            save_session_flag=False,
            benchmark_mode=False,
            benchmark_output="",
            question_handler=None,
        )

        # Check that excluded_tools includes "question"
        call_kwargs = base_mocks["agent_loop"].call_args[1]
        assert "question" in call_kwargs["excluded_tools"]

    @pytest.mark.asyncio
    async def test_benchmark_mode_returns_success(self, base_mocks, tmp_path):
        """Test benchmark mode completes successfully."""
        from wolo.cli.execution import run_single_task_mode
        from wolo.config import Config
        from wolo.modes import ModeConfig, QuotaConfig

        config = MagicMock(spec=Config)
        agent_config = MagicMock()
        mode_config = ModeConfig.for_mode(ExecutionMode.COOP)
        quota_config = QuotaConfig(max_steps=100)

        benchmark_file = tmp_path / "benchmark.json"

        # Benchmark mode should work even if metrics return None
        result = await run_single_task_mode(
            config=config,
            session_id="test-session",
            agent_config=agent_config,
            mode_config=mode_config,
            quota_config=quota_config,
            message_text="Test message",
            save_session_flag=False,
            benchmark_mode=True,
            benchmark_output=str(benchmark_file),
            question_handler=None,
        )

        # Should still return success even if metrics export returns None
        assert result == ExitCode.SUCCESS

    @pytest.mark.asyncio
    async def test_ui_disabled_mode(self, base_mocks):
        """Test execution with UI disabled."""
        from wolo.cli.execution import run_single_task_mode
        from wolo.config import Config
        from wolo.modes import ModeConfig, QuotaConfig

        config = MagicMock(spec=Config)
        agent_config = MagicMock()
        # Create a custom mode config with UI disabled
        mode_config = ModeConfig(
            mode=ExecutionMode.SOLO,
            enable_keyboard_shortcuts=False,
            enable_question_tool=False,
            enable_ui_state=False,  # UI disabled
            exit_after_task=True,
            wait_for_input_before_start=False,
        )
        quota_config = QuotaConfig(max_steps=100)

        result = await run_single_task_mode(
            config=config,
            session_id="test-session",
            agent_config=agent_config,
            mode_config=mode_config,
            quota_config=quota_config,
            message_text="Test message",
            save_session_flag=False,
            benchmark_mode=False,
            benchmark_output="",
            question_handler=None,
        )

        assert result == ExitCode.SUCCESS
        # Keyboard should not be started in silent mode
        base_mocks["keyboard"].start.assert_not_called()


class TestRunReplMode:
    """Tests for run_repl_mode function."""

    @pytest.fixture
    def base_mocks(self):
        """Create base mocks for run_repl_mode."""
        # Functions imported at module level: patch via wolo.cli.execution.<name>
        # Functions imported inline: patch at their original module
        with (
            # Inline import -> patch at original module
            patch(
                "wolo.session.get_or_create_agent_display_name", return_value="Claude"
            ),
            # Module-level imports -> patch via wolo.cli.execution
            patch("wolo.cli.execution.get_manager") as mock_get_manager,
            patch("wolo.cli.execution.create_ui") as mock_create_ui,
            # Inline import -> patch at original module
            patch("wolo.question_ui.setup_question_handler"),
            # Module-level import -> patch via wolo.cli.execution
            patch("wolo.cli.execution.add_user_message"),
            # Inline import -> patch at original module
            patch("wolo.cli.events.show_agent_start"),
            # Inline import -> patch at original module
            patch(
                "wolo.watch_server.start_watch_server", new_callable=AsyncMock
            ) as mock_watch,
            # Module-level import -> patch via wolo.cli.execution
            patch("wolo.cli.execution.set_watch_server"),
            patch("wolo.cli.execution.agent_loop", new_callable=AsyncMock) as mock_agent_loop,
            patch("wolo.cli.execution.save_session"),
            patch("wolo.cli.execution.remove_manager"),
            # Inline import -> patch at original module
            patch("wolo.session.clear_session_pid"),
            # Inline import -> patch at original module
            patch("wolo.watch_server.stop_watch_server", new_callable=AsyncMock),
            patch(
                "wolo.cli.execution.WoloLLMClient.close_all_sessions", new_callable=AsyncMock
            ),
            # Inline import -> patch at original module (note: mcp_integration not mcp)
            patch("wolo.mcp_integration.shutdown_mcp", new_callable=AsyncMock),
        ):
            # Setup control mock
            mock_control = MagicMock()
            mock_get_manager.return_value = mock_control

            # Setup UI mock with async prompt_for_input
            mock_ui = MagicMock()
            mock_ui.prompt_for_input = AsyncMock(return_value="")  # Default: exit on empty
            mock_keyboard = MagicMock()
            mock_create_ui.return_value = (mock_ui, mock_keyboard)

            # Setup watch server mock
            mock_watch.return_value = MagicMock()

            # Setup agent loop result
            mock_result = MagicMock()
            mock_result.finish_reason = "end_turn"
            mock_result.parts = []
            mock_agent_loop.return_value = mock_result

            yield {
                "control": mock_control,
                "ui": mock_ui,
                "keyboard": mock_keyboard,
                "agent_loop": mock_agent_loop,
                "watch": mock_watch,
            }

    @pytest.mark.asyncio
    async def test_repl_exits_on_empty_input(self, base_mocks):
        """Test REPL exits gracefully on empty input after initial message."""
        from wolo.cli.execution import run_repl_mode
        from wolo.config import Config
        from wolo.modes import ModeConfig, QuotaConfig

        # First call processes initial message, second call returns empty (exit)
        base_mocks["ui"].prompt_for_input = AsyncMock(return_value="")

        config = MagicMock(spec=Config)
        agent_config = MagicMock()
        mode_config = ModeConfig.for_mode(ExecutionMode.COOP)
        quota_config = QuotaConfig(max_steps=100)

        result = await run_repl_mode(
            config=config,
            session_id="test-session",
            agent_config=agent_config,
            mode_config=mode_config,
            quota_config=quota_config,
            initial_message="First message",
            save_session_flag=False,
            benchmark_mode=False,
            benchmark_output="",
        )

        assert result == ExitCode.SUCCESS
        base_mocks["agent_loop"].assert_called_once()

    @pytest.mark.asyncio
    async def test_repl_continues_on_error(self, base_mocks):
        """Test REPL continues after an error in agent loop."""
        from wolo.cli.execution import run_repl_mode
        from wolo.config import Config
        from wolo.modes import ModeConfig, QuotaConfig

        # First call raises error, next prompt returns empty (exit)
        mock_result = MagicMock()
        mock_result.finish_reason = "end_turn"
        base_mocks["agent_loop"].side_effect = [RuntimeError("Test error"), mock_result]
        base_mocks["ui"].prompt_for_input = AsyncMock(return_value="")

        config = MagicMock(spec=Config)
        agent_config = MagicMock()
        mode_config = ModeConfig.for_mode(ExecutionMode.COOP)
        quota_config = QuotaConfig(max_steps=100)

        result = await run_repl_mode(
            config=config,
            session_id="test-session",
            agent_config=agent_config,
            mode_config=mode_config,
            quota_config=quota_config,
            initial_message="First message",
            save_session_flag=False,
            benchmark_mode=False,
            benchmark_output="",
        )

        # REPL should exit successfully after error recovery
        assert result == ExitCode.SUCCESS
        # Control should be reset after error
        base_mocks["control"].reset.assert_called()



class TestRunWatchMode:
    """Tests for run_watch_mode function."""

    @pytest.mark.asyncio
    async def test_session_not_found(self):
        """Test watch mode returns error when session not found."""
        from wolo.cli.execution import run_watch_mode

        with patch("wolo.session.get_session_status") as mock_status:
            mock_status.return_value = {"exists": False}

            result = await run_watch_mode("nonexistent-session")

            assert result == ExitCode.SESSION_ERROR

    @pytest.mark.asyncio
    async def test_session_not_running(self):
        """Test watch mode returns error when session is not running."""
        from wolo.cli.execution import run_watch_mode

        with patch("wolo.session.get_session_status") as mock_status:
            mock_status.return_value = {
                "exists": True,
                "is_running": False,
            }

            result = await run_watch_mode("stopped-session")

            assert result == ExitCode.SESSION_ERROR

    @pytest.mark.asyncio
    async def test_watch_server_not_available(self):
        """Test watch mode returns error when watch server is not available."""
        from wolo.cli.execution import run_watch_mode

        with patch("wolo.session.get_session_status") as mock_status:
            mock_status.return_value = {
                "exists": True,
                "is_running": True,
                "watch_server_available": False,
                "pid": 12345,
            }

            result = await run_watch_mode("no-watch-session")

            assert result == ExitCode.SESSION_ERROR

    @pytest.mark.asyncio
    async def test_socket_not_found(self, tmp_path):
        """Test watch mode handles missing socket file."""
        from wolo.cli.execution import run_watch_mode

        with (
            patch("wolo.session.get_session_status") as mock_status,
            patch("wolo.cli.utils.print_session_info"),
            patch(
                "asyncio.open_unix_connection",
                new_callable=AsyncMock,
                side_effect=FileNotFoundError(),
            ),
        ):
            mock_status.return_value = {
                "exists": True,
                "is_running": True,
                "watch_server_available": True,
                "pid": 12345,
            }

            result = await run_watch_mode("test-session")

            assert result == ExitCode.SESSION_ERROR

    @pytest.mark.asyncio
    async def test_connection_refused(self):
        """Test watch mode handles connection refused."""
        from wolo.cli.execution import run_watch_mode

        with (
            patch("wolo.session.get_session_status") as mock_status,
            patch("wolo.cli.utils.print_session_info"),
            patch(
                "asyncio.open_unix_connection",
                new_callable=AsyncMock,
                side_effect=ConnectionRefusedError(),
            ),
        ):
            mock_status.return_value = {
                "exists": True,
                "is_running": True,
                "watch_server_available": True,
                "pid": 12345,
            }

            result = await run_watch_mode("test-session")

            assert result == ExitCode.SESSION_ERROR


