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

from dataclasses import dataclass, field
from typing import Optional
import sys
import select

from wolo.modes import ExecutionMode

# Short to long option mapping
SHORT_OPTIONS = {
    "-s": "--session",
    "-r": "--resume",
    "-l": "--list",
    "-w": "--watch",
    "-S": "--save",
    "-h": "--help",
    "-a": "--agent",
    "-e": "--endpoint",
    "-m": "--model",
    "-L": "--log-level",
    "-n": "--max-steps",
}

# Options that require values
OPTIONS_NEEDING_VALUE = {
    "--session", "-s",
    "--resume", "-r",
    "--watch", "-w",
    "--agent", "-a",
    "--endpoint", "-e",
    "--model", "-m",
    "--log-level", "-L",
    "--max-steps", "-n",
    "--api-key",
    "--debug-llm",
    "--debug-full",
    "--benchmark-output",
}

# Mutually exclusive option groups
MUTUALLY_EXCLUSIVE_GROUPS = [
    # Execution modes (only one allowed)
    {"--solo", "--coop"},
    # Session creation vs resume (can't do both)
    {"--session", "-s", "--resume", "-r"},
]

# Deprecated options with migration hints
DEPRECATED_OPTIONS = {
    "--silent": ("--solo", "Use --solo instead of --silent"),
    "--interactive": ("--coop", "Use --coop instead of --interactive"),
    "--prompt-file": (None, "Use 'cat FILE | wolo' instead of --prompt-file"),
}

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
    endpoint_name: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    max_steps: int = 100
    log_level: Optional[str] = None
    save_session: bool = False
    benchmark_mode: bool = False
    benchmark_output: str = "benchmark_results.json"
    debug_llm_file: Optional[str] = None
    debug_full_dir: Optional[str] = None


@dataclass
class SessionOptions:
    """Session-related quick options."""
    session_name: Optional[str] = None  # -s, --session
    resume_id: Optional[str] = None     # -r, --resume
    watch_id: Optional[str] = None      # -w, --watch


@dataclass
class ParsedArgs:
    """Parsed command-line arguments."""
    command_type: str = "default"
    subcommand: Optional[str] = None
    execution_options: ExecutionOptions = field(default_factory=ExecutionOptions)
    session_options: SessionOptions = field(default_factory=SessionOptions)
    # Combined message (after dual input processing)
    message: str = ""
    message_from_stdin: bool = False
    # Separate tracking for dual input
    pipe_input: Optional[str] = None
    cli_prompt: Optional[str] = None
    positional_args: list[str] = field(default_factory=list)


def combine_inputs(pipe_input: Optional[str], cli_prompt: Optional[str]) -> tuple[str, bool]:
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
        message = DUAL_INPUT_TEMPLATE.format(
            pipe_input=pipe_input,
            user_prompt=cli_prompt
        )
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


def check_deprecated_options(options: dict) -> list[str]:
    """
    Check for deprecated options and return warning messages.
    
    Args:
        options: Parsed options dictionary
    
    Returns:
        List of deprecation warning messages
    """
    warnings = []
    for opt, (replacement, message) in DEPRECATED_OPTIONS.items():
        key_with_prefix = opt
        key_without_prefix = opt.lstrip("-")
        if key_with_prefix in options or key_without_prefix in options:
            warnings.append(f"Warning: {message}")
    return warnings


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
                positional.extend(args[i+1:])
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
                                options[opt] = args[i+1] if i+1 < len(args) else None
                                if i+1 < len(args):
                                    i += 1
                                break
            else:
                # Positional argument or option value
                if option_expecting_value:
                    options[option_expecting_value] = arg
                    option_expecting_value = None
                else:
                    positional.append(arg)
            
            i += 1
        
        # Handle last option expecting value
        if option_expecting_value:
            options[option_expecting_value] = None
        
        # Check for deprecated options and print warnings
        deprecation_warnings = check_deprecated_options(options)
        for warning in deprecation_warnings:
            print(warning, file=sys.stderr)
        
        # Apply options to result
        self._apply_options(result, options)
        
        # Set positional arguments and CLI prompt
        result.positional_args = positional
        result.cli_prompt = " ".join(positional) if positional else None
        
        # Combine inputs using dual input handling
        result.message, _ = combine_inputs(result.pipe_input, result.cli_prompt)
        
        return result
    
    def _read_stdin_if_available(self) -> Optional[str]:
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
                if hasattr(select, 'select'):
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
        
        # Execution mode: --solo / --coop (new), with backward compatibility
        if "--solo" in options or "solo" in options:
            result.execution_options.mode = ExecutionMode.SOLO
        elif "--coop" in options or "coop" in options:
            result.execution_options.mode = ExecutionMode.COOP
        # Backward compatibility: map old options to new
        elif "--silent" in options or "silent" in options:
            result.execution_options.mode = ExecutionMode.SOLO
        elif "--interactive" in options or "interactive" in options:
            result.execution_options.mode = ExecutionMode.COOP
        # Default is SOLO (set in ExecutionOptions dataclass)
        
        if "--agent" in options or "-a" in options:
            result.execution_options.agent_type = options.get("--agent") or options.get("-a") or "general"
        if "--endpoint" in options or "-e" in options:
            result.execution_options.endpoint_name = options.get("--endpoint") or options.get("-e")
        if "--model" in options or "-m" in options:
            result.execution_options.model = options.get("--model") or options.get("-m")
        if "--max-steps" in options or "-n" in options:
            try:
                max_steps_val = options.get("--max-steps") or options.get("-n")
                if max_steps_val:
                    result.execution_options.max_steps = int(max_steps_val)
            except (ValueError, TypeError):
                pass
        if "--log-level" in options or "-L" in options:
            result.execution_options.log_level = options.get("--log-level") or options.get("-L")
        if "--save" in options or "-S" in options:
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
