import sys
from wolo.cli.commands.base import BaseCommand
from wolo.cli.parser import ParsedArgs


class DebugCommandGroup(BaseCommand):
    """Debugging tools command group."""
    
    @property
    def name(self) -> str:
        return "debug"
    
    @property
    def description(self) -> str:
        return "Debugging tools"
    
    def execute(self, args: ParsedArgs) -> int:
        """Route to subcommand."""
        subcommand = args.subcommand
        
        if subcommand == "llm":
            return DebugLlmCommand().execute(args)
        elif subcommand == "full":
            return DebugFullCommand().execute(args)
        elif subcommand == "benchmark":
            return DebugBenchmarkCommand().execute(args)
        else:
            print(f"Error: Unknown subcommand '{subcommand}'", file=sys.stderr)
            print(f"Available subcommands: llm, full, benchmark", file=sys.stderr)
            return 1


class DebugLlmCommand(BaseCommand):
    """wolo debug llm <file>"""
    
    @property
    def name(self) -> str:
        return "debug llm"
    
    @property
    def description(self) -> str:
        return "Log LLM requests/responses to file"
    
    def validate_args(self, args: ParsedArgs) -> tuple[bool, str]:
        """Validate llm command arguments."""
        if not args.positional_args:
            return (False, "Error: debug llm requires a file path")
        return (True, "")
    
    def execute(self, args: ParsedArgs) -> int:
        """Execute llm command."""
        # This is handled by the execution options, not a standalone command
        # For now, just show usage
        print("Usage: wolo --debug-llm <file> <message>", file=sys.stderr)
        print("The --debug-llm option enables LLM request/response logging.", file=sys.stderr)
        return 1


class DebugFullCommand(BaseCommand):
    """wolo debug full <dir>"""
    
    @property
    def name(self) -> str:
        return "debug full"
    
    @property
    def description(self) -> str:
        return "Save full request/response JSON to directory"
    
    def validate_args(self, args: ParsedArgs) -> tuple[bool, str]:
        """Validate full command arguments."""
        if not args.positional_args:
            return (False, "Error: debug full requires a directory path")
        return (True, "")
    
    def execute(self, args: ParsedArgs) -> int:
        """Execute full command."""
        # This is handled by the execution options, not a standalone command
        # For now, just show usage
        print("Usage: wolo --debug-full <dir> <message>", file=sys.stderr)
        print("The --debug-full option saves full request/response JSON files.", file=sys.stderr)
        return 1


class DebugBenchmarkCommand(BaseCommand):
    """wolo debug benchmark [options] <message>"""
    
    @property
    def name(self) -> str:
        return "debug benchmark"
    
    @property
    def description(self) -> str:
        return "Export performance metrics after completion"
    
    def execute(self, args: ParsedArgs) -> int:
        """Execute benchmark command."""
        # This is handled by the execution options, not a standalone command
        # For now, just show usage
        print("Usage: wolo --benchmark [--benchmark-output <file>] <message>", file=sys.stderr)
        print("The --benchmark option exports performance metrics.", file=sys.stderr)
        return 1
