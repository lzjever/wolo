import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from wolo.cli.commands.run import RunCommand
from wolo.cli.parser import ParsedArgs
from wolo.modes import ExecutionMode


def _make_args() -> ParsedArgs:
    args = ParsedArgs()
    args.execution_options.mode = ExecutionMode.SOLO
    args.execution_options.agent_type = "general"
    args.execution_options.max_steps = 10
    args.execution_options.no_banner = False
    args.execution_options.wild_mode = False
    args.execution_options.wild_mode_explicit = False
    args.execution_options.allow_paths = []
    args.execution_options.save_session = False
    args.execution_options.benchmark_mode = False
    args.execution_options.benchmark_output = ""
    args.execution_options.no_color = True
    args.execution_options.output_style = "minimal"
    args.execution_options.show_reasoning = False
    args.execution_options.json_output = False
    args.message = "do work"
    args.cli_prompt = "do work"
    return args


def test_solo_mode_forces_wild_when_not_explicit(capsys):
    args = _make_args()
    command = RunCommand()
    config = MagicMock()
    config.path_safety = SimpleNamespace(wild_mode=False)
    config.claude = SimpleNamespace(enabled=False)
    config.mcp = SimpleNamespace(enabled=False)

    fake_execution = types.ModuleType("wolo.cli.execution")

    async def _fake_single_task_mode(*args, **kwargs):
        return 0

    fake_execution.run_single_task_mode = _fake_single_task_mode

    with (
        patch("wolo.config.Config.is_first_run", return_value=False),
        patch("wolo.config.Config.from_env", return_value=config),
        patch("wolo.agents.AGENTS", {"general": object()}),
        patch("wolo.agents.get_agent", return_value=MagicMock()),
        patch("wolo.agent_names.get_random_agent_name", return_value="test-agent"),
        patch("wolo.session.create_session", return_value="sid-1"),
        patch("wolo.session.check_and_set_session_pid", return_value=True),
        patch("wolo.cli.path_guard.initialize_path_guard_for_session"),
        patch("wolo.cli.events.setup_event_handlers"),
        patch.dict(sys.modules, {"wolo.cli.execution": fake_execution}),
        patch("wolo.cli.utils.print_session_info") as mock_print_session_info,
    ):
        result = command.execute(args)

    assert result == 0
    assert config.path_safety.wild_mode is True
    mock_print_session_info.assert_not_called()
    captured = capsys.readouterr()
    assert "SOLO mode enables --wild automatically" in captured.err


def test_solo_mode_explicit_wild_does_not_warn(capsys):
    args = _make_args()
    args.execution_options.wild_mode = True
    args.execution_options.wild_mode_explicit = True
    command = RunCommand()
    config = MagicMock()
    config.path_safety = SimpleNamespace(wild_mode=False)
    config.claude = SimpleNamespace(enabled=False)
    config.mcp = SimpleNamespace(enabled=False)

    fake_execution = types.ModuleType("wolo.cli.execution")

    async def _fake_single_task_mode(*args, **kwargs):
        return 0

    fake_execution.run_single_task_mode = _fake_single_task_mode

    with (
        patch("wolo.config.Config.is_first_run", return_value=False),
        patch("wolo.config.Config.from_env", return_value=config),
        patch("wolo.agents.AGENTS", {"general": object()}),
        patch("wolo.agents.get_agent", return_value=MagicMock()),
        patch("wolo.agent_names.get_random_agent_name", return_value="test-agent"),
        patch("wolo.session.create_session", return_value="sid-1"),
        patch("wolo.session.check_and_set_session_pid", return_value=True),
        patch("wolo.cli.path_guard.initialize_path_guard_for_session"),
        patch("wolo.cli.events.setup_event_handlers"),
        patch.dict(sys.modules, {"wolo.cli.execution": fake_execution}),
        patch("wolo.cli.utils.print_session_info") as mock_print_session_info,
    ):
        result = command.execute(args)

    assert result == 0
    assert config.path_safety.wild_mode is True
    mock_print_session_info.assert_not_called()
    captured = capsys.readouterr()
    assert "SOLO mode enables --wild automatically" not in captured.err
