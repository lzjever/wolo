"""
Flexible argument parser for Wolo CLI.

Supports:
- Options in any position
- Pipeline input (stdin)
- = syntax (--option=value)
- -- separator
- Dual input (pipe + CLI prompt concatenation)
- Conflict detection for mutually exclusive options
"""

import select
import sys
from dataclasses import dataclass, field

from wolo.modes import ExecutionMode

# Short to long option mapping
SHORT_OPTIONS = {
    "-s": "--session",
    "-r": "--resume",
    "-l": "--list",
    "-w": "--watch",
    "-h": "--help",
    "-a": "--agent",
    "-m": "--model",
    "-n": "--max-steps",
    "-C": "--workdir",
    "-P": "--allow-path",
    "-W": "--wild",
}

# Options that require values
OPTIONS_NEEDING_VALUE = {
    "--session",
    "-s",
    "--resume",
    "-r",
    "--watch",
    "-w",
    "--agent",
    "-a",
    "--base-url",
    "--model",
    "-m",
    "--log-level",
    "--max-steps",
    "-n",
    "--api-key",
    "--debug-llm",
    "--debug-full",
    "--benchmark-output",
    "--output-style",
    "--workdir",
    "--allow-path",
    "-C",
    "-P",
}

# Valid output style choices
OUTPUT_STYLE_CHOICES = {"minimal", "default", "verbose"}

# Mutually exclusive option groups
MUTUALLY_EXCLUSIVE_GROUPS = [
    # Execution modes (only one allowed)
    {"--solo", "--coop", "--repl"},
    # Session creation vs resume (can't do both)
    {"--session", "-s", "--resume", "-r"},
]

# Options that can be specified multiple times
MULTI_VALUE_OPTIONS: set[str] = {"allow-path", "--allow-path", "-P"}

# Template for combining pipe input with CLI prompt
DUAL_INPUT_TEMPLATE = """## Context (from stdin)

{pipe_input}

---

## Task

{user_prompt}
"""


@dataclass
class ExecutionOptions:
    """Execution-related options."""

    mode: ExecutionMode = ExecutionMode.SOLO  # Default changed to SOLO
    agent_type: str = "general"
    base_url: str | None = None  # Direct LLM service base URL (bypasses config file)
    api_key: str | None = None
    model: str | None = None
    max_steps: int = 100
    log_level: str | None = None
    save_session: bool = False
    benchmark_mode: bool = False
    benchmark_output: str = "benchmark_results.json"
    debug_llm_file: str | None = None
    debug_full_dir: str | None = None
    # Output style options
    output_style: str | None = None  # minimal, default, verbose (None = use config)
    no_color: bool = False
    no_banner: bool = False  # Suppress session info banner
    show_reasoning: bool | None = None  # None = use config default
    json_output: bool = False
    # Working directory
    workdir: str | None = None  # Working directory for the session
    # Additional allowed paths for PathGuard (repeatable)
    allow_paths: list[str] = field(default_factory=list)
    # Wild mode: bypass safety checks and restrictions
    wild_mode: bool = False
    # Whether wild mode was explicitly set by CLI flag.
    wild_mode_explicit: bool = False


@dataclass
class SessionOptions:
    """Session-related quick options."""

    session_name: str | None = None  # -s, --session
    resume_id: str | None = None  # -r, --resume
    watch_id: str | None = None  # -w, --watch


@dataclass
class ParsedArgs:
    """Parsed command-line arguments."""

    command_type: str = "default"
    subcommand: str | None = None
    execution_options: ExecutionOptions = field(default_factory=ExecutionOptions)
    session_options: SessionOptions = field(default_factory=SessionOptions)
    # Combined message (after dual input processing)
    message: str = ""
    message_from_stdin: bool = False
    # Separate tracking for dual input
    pipe_input: str | None = None
    cli_prompt: str | None = None
    positional_args: list[str] = field(default_factory=list)


def combine_inputs(pipe_input: str | None, cli_prompt: str | None) -> tuple[str, bool]:
    """
    Combine pipe input and CLI prompt into final message.

    Args:
        pipe_input: Content from stdin (may be None or empty)
        cli_prompt: Content from CLI arguments (may be None or empty)

    Returns:
        (combined_message, has_message)

    Rules:
        1. Both provided → Concatenate using DUAL_INPUT_TEMPLATE
        2. Only pipe → Use pipe content
        3. Only CLI → Use CLI content
        4. Neither → Return ("", False)
    """
    pipe_input = (pipe_input or "").strip()
    cli_prompt = (cli_prompt or "").strip()

    if pipe_input and cli_prompt:
        # Both provided - concatenate
        message = DUAL_INPUT_TEMPLATE.format(pipe_input=pipe_input, user_prompt=cli_prompt)
        return (message, True)
    elif pipe_input:
        return (pipe_input, True)
    elif cli_prompt:
        return (cli_prompt, True)
    else:
        return ("", False)


def validate_option_conflicts(options: dict) -> tuple[bool, str]:
    """
    Validate that no mutually exclusive options are used together.

    Args:
        options: Parsed options dictionary

    Returns:
        (is_valid, error_message)

    Example:
        >>> validate_option_conflicts({"--solo": True, "--coop": True})
        (False, "Error: --solo and --coop are mutually exclusive")
    """
    for group in MUTUALLY_EXCLUSIVE_GROUPS:
        found = []
        for opt in group:
            # Check both with and without -- prefix
            key_with_prefix = opt
            key_without_prefix = opt.lstrip("-")
            if key_with_prefix in options or key_without_prefix in options:
                found.append(opt)

        if len(found) > 1:
            return (False, f"Error: {' and '.join(found)} are mutually exclusive")

    return (True, "")


class FlexibleArgumentParser:
    """
    Flexible argument parser supporting:
    - Options in any position
    - Pipeline input (stdin)
    - = syntax (--option=value)
    - -- separator
    - Dual input (pipe + CLI prompt)
    """

    def parse(self, args: list[str], check_stdin: bool = True) -> ParsedArgs:
        """
        Parse command-line arguments with flexible positioning.

        Args:
            args: Command-line arguments (without program name)
            check_stdin: Whether to check for stdin input

        Returns:
            ParsedArgs object
        """
        result = ParsedArgs()

        # 1. Check stdin first
        if check_stdin:
            stdin_msg = self._read_stdin_if_available()
            if stdin_msg:
                result.pipe_input = stdin_msg
                result.message_from_stdin = True

        # 2. Parse command-line arguments
        options = {}
        positional = []
        option_expecting_value = None
        in_options = True
        i = 0

        while i < len(args):
            arg = args[i]

            # -- separator
            if arg == "--":
                in_options = False
                positional.extend(args[i + 1 :])
                break

            # Options
            if in_options and arg.startswith("-"):
                # Handle previous option expecting value
                if option_expecting_value:
                    options[option_expecting_value] = None
                    option_expecting_value = None

                if arg.startswith("--"):
                    # Long option
                    if "=" in arg:
                        key, value = arg[2:].split("=", 1)
                        options[key] = value
                        options[f"--{key}"] = value  # Also store with -- prefix for lookup
                    else:
                        key = arg[2:]
                        if self._option_needs_value(key):
                            option_expecting_value = key
                        else:
                            options[key] = True
                            options[f"--{key}"] = True  # Also store with -- prefix for lookup
                else:
                    # Short option
                    if len(arg) == 2:
                        key = arg
                        if self._option_needs_value(key):
                            option_expecting_value = key
                        else:
                            options[key] = True
                            # Also store long form if mapped
                            long_opt = SHORT_OPTIONS.get(key)
                            if long_opt:
                                options[long_opt] = True
                                options[long_opt[2:]] = True  # Without -- prefix
                    else:
                        # Combined short options -abc
                        for char in arg[1:]:
                            opt = f"-{char}"
                            if not self._option_needs_value(opt):
                                options[opt] = True
                            else:
                                # First option needing value gets the next arg
                                options[opt] = args[i + 1] if i + 1 < len(args) else None
                                if i + 1 < len(args):
                                    i += 1
                                break
            else:
                # Positional argument or option value
                if option_expecting_value:
                    # Check if this is a multi-value option
                    if option_expecting_value in MULTI_VALUE_OPTIONS:
                        # Store in canonical key to preserve command-line order.
                        if option_expecting_value.startswith("--"):
                            canonical = option_expecting_value
                        elif option_expecting_value.startswith("-"):
                            canonical = SHORT_OPTIONS.get(
                                option_expecting_value, option_expecting_value
                            )
                        else:
                            canonical = f"--{option_expecting_value}"

                        if canonical not in options:
                            options[canonical] = []
                        options[canonical].append(arg)

                        # Keep legacy key mirror for compatibility with existing lookups.
                        if option_expecting_value != canonical:
                            if option_expecting_value not in options:
                                options[option_expecting_value] = []
                            options[option_expecting_value].append(arg)
                    else:
                        options[option_expecting_value] = arg
                        # Also store with -- prefix for lookup
                        if not option_expecting_value.startswith("--"):
                            options[f"--{option_expecting_value}"] = arg
                    option_expecting_value = None
                else:
                    positional.append(arg)

            i += 1

        # Handle last option expecting value
        if option_expecting_value:
            options[option_expecting_value] = None

        # Apply options to result
        self._apply_options(result, options)

        # Set positional arguments and CLI prompt
        result.positional_args = positional
        result.cli_prompt = " ".join(positional) if positional else None

        # Combine inputs using dual input handling
        result.message, _ = combine_inputs(result.pipe_input, result.cli_prompt)

        return result

    def _read_stdin_if_available(self) -> str | None:
        """
        Read from stdin if available.

        For pipes (non-TTY), reads all data until EOF (blocking until the writing
        end closes). In Unix pipes, EOF is signaled when the writing process closes
        its stdout, which indicates the end of the data stream.

        For TTYs, uses non-blocking check to avoid blocking interactive input.

        Returns:
            Content string or None
        """
        if sys.stdin.isatty():
            # Interactive terminal - use non-blocking check
            try:
                if hasattr(select, "select"):
                    ready, _, _ = select.select([sys.stdin], [], [], 0)
                    if ready:
                        return sys.stdin.read().strip()
                else:
                    # Windows fallback
                    try:
                        import msvcrt

                        if msvcrt.kbhit():
                            return sys.stdin.read().strip()
                    except ImportError:
                        pass
            except (OSError, AttributeError):
                pass
            return None

        # For pipes, read all data until EOF
        # sys.stdin.read() will block until the writing end closes (EOF)
        # This is the correct behavior for: cmd1 | cmd2
        try:
            data = sys.stdin.read()
            if data.strip():
                return data.strip()
        except Exception:
            pass

        return None

    def _option_needs_value(self, option: str) -> bool:
        """Check if option requires a value."""
        # Normalize short options
        if option.startswith("-") and len(option) == 2:
            long_opt = SHORT_OPTIONS.get(option)
            if long_opt:
                return long_opt in OPTIONS_NEEDING_VALUE
        # Check with --
        if not option.startswith("-"):
            return f"--{option}" in OPTIONS_NEEDING_VALUE
        return option in OPTIONS_NEEDING_VALUE

    def _apply_options(self, result: ParsedArgs, options: dict) -> None:
        """Apply parsed options to ParsedArgs."""
        # Session options
        if "--session" in options or "-s" in options:
            result.session_options.session_name = options.get("--session") or options.get("-s")
        if "--resume" in options or "-r" in options:
            result.session_options.resume_id = options.get("--resume") or options.get("-r")
        if "--watch" in options or "-w" in options:
            result.session_options.watch_id = options.get("--watch") or options.get("-w")

        # Execution mode: --solo / --coop / --repl
        if "--solo" in options or "solo" in options:
            result.execution_options.mode = ExecutionMode.SOLO
        elif "--coop" in options or "coop" in options:
            result.execution_options.mode = ExecutionMode.COOP
        elif "--repl" in options or "repl" in options:
            result.execution_options.mode = ExecutionMode.REPL
        # Default is SOLO (set in ExecutionOptions dataclass)

        if "--agent" in options or "-a" in options:
            result.execution_options.agent_type = (
                options.get("--agent") or options.get("-a") or "general"
            )
        if "--base-url" in options or "base-url" in options:
            result.execution_options.base_url = options.get("--base-url") or options.get("base-url")
        if "--model" in options or "-m" in options:
            result.execution_options.model = options.get("--model") or options.get("-m")
        if "--max-steps" in options or "-n" in options:
            try:
                max_steps_val = options.get("--max-steps") or options.get("-n")
                if max_steps_val:
                    result.execution_options.max_steps = int(max_steps_val)
            except (ValueError, TypeError):
                pass
        if "--log-level" in options or "log-level" in options:
            result.execution_options.log_level = options.get("--log-level") or options.get(
                "log-level"
            )
        if "--save" in options or "save" in options:
            result.execution_options.save_session = True
        if "--benchmark" in options:
            result.execution_options.benchmark_mode = True
        if "--benchmark-output" in options:
            result.execution_options.benchmark_output = options.get("--benchmark-output")
        if "--debug-llm" in options:
            result.execution_options.debug_llm_file = options.get("--debug-llm")
        if "--debug-full" in options:
            result.execution_options.debug_full_dir = options.get("--debug-full")
        if "--api-key" in options:
            result.execution_options.api_key = options.get("--api-key")

        # Output style options
        if "--output-style" in options or "output-style" in options:
            style = options.get("--output-style") or options.get("output-style")
            if style and style in OUTPUT_STYLE_CHOICES:
                result.execution_options.output_style = style
        if "--no-color" in options or "no-color" in options:
            result.execution_options.no_color = True
        if "--no-banner" in options or "no-banner" in options:
            result.execution_options.no_banner = True
        if "--show-reasoning" in options or "show-reasoning" in options:
            result.execution_options.show_reasoning = True
        if "--hide-reasoning" in options or "hide-reasoning" in options:
            result.execution_options.show_reasoning = False
        if "--json" in options or "json" in options:
            result.execution_options.json_output = True
            # JSON implies minimal + no color
            result.execution_options.output_style = "minimal"
            result.execution_options.no_color = True

        # Working directory
        if "--workdir" in options or "-C" in options:
            workdir = options.get("--workdir") or options.get("-C")
            if workdir:
                result.execution_options.workdir = workdir

        # Wild mode
        if "--wild" in options or "-W" in options or "wild" in options:
            result.execution_options.wild_mode = True
            result.execution_options.wild_mode_explicit = True

        # Additional allow paths (-P/--allow-path)
        allow_paths: list[str] = []
        canonical_value = options.get("--allow-path")
        if isinstance(canonical_value, list):
            allow_paths.extend(canonical_value)
        elif isinstance(canonical_value, str):
            allow_paths.append(canonical_value)
        else:
            for key in ("-P", "allow-path"):
                value = options.get(key)
                if isinstance(value, list):
                    allow_paths.extend(value)
                elif isinstance(value, str):
                    allow_paths.append(value)
        if allow_paths:
            # Preserve order while de-duplicating
            seen: set[str] = set()
            ordered = [p for p in allow_paths if not (p in seen or seen.add(p))]
            result.execution_options.allow_paths = ordered
