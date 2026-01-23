import getpass
import os
import sys
import tempfile
from pathlib import Path

import yaml

from wolo.cli.commands.base import BaseCommand
from wolo.cli.exit_codes import ExitCode
from wolo.cli.parser import ParsedArgs


class ConfigCommandGroup(BaseCommand):
    """Configuration management command group."""

    @property
    def name(self) -> str:
        return "config"

    @property
    def description(self) -> str:
        return "Configuration management"

    def execute(self, args: ParsedArgs) -> int:
        """Route to subcommand."""
        subcommand = args.subcommand

        if subcommand == "init":
            return ConfigInitCommand().execute(args)
        elif subcommand == "list-endpoints":
            return ConfigListEndpointsCommand().execute(args)
        elif subcommand == "show":
            return ConfigShowCommand().execute(args)
        elif subcommand == "docs":
            return ConfigDocsCommand().execute(args)
        elif subcommand == "example":
            return ConfigExampleCommand().execute(args)
        else:
            print(f"Error: Unknown subcommand '{subcommand}'", file=sys.stderr)
            print(
                "Available subcommands: init, list-endpoints, show, docs, example", file=sys.stderr
            )
            return 1


class ConfigListEndpointsCommand(BaseCommand):
    """wolo config list-endpoints"""

    @property
    def name(self) -> str:
        return "config list-endpoints"

    @property
    def description(self) -> str:
        return "List configured endpoints"

    def execute(self, args: ParsedArgs) -> int:
        """Execute list-endpoints command."""
        from wolo.config import Config

        endpoints = Config._get_endpoints()
        if not endpoints:
            print("No endpoints configured in ~/.wolo/config.yaml")
        else:
            print(f"Found {len(endpoints)} configured endpoint(s):")
            print()
            config_data = Config._load_config_file()
            default_ep = config_data.get("default_endpoint", "")
            for ep in endpoints:
                marker = " (default)" if ep.name == default_ep else ""
                print(f"  Name: {ep.name}{marker}")
                print(f"    Model: {ep.model}")
                print(f"    API Base: {ep.api_base}")
                print(f"    Temperature: {ep.temperature}")
                print(f"    Max Tokens: {ep.max_tokens}")
                if ep.source_model:
                    print(f"    Source Model: {ep.source_model}")
                print()
        return 0


class ConfigShowCommand(BaseCommand):
    """wolo config show"""

    @property
    def name(self) -> str:
        return "config show"

    @property
    def description(self) -> str:
        return "Show current configuration"

    def execute(self, args: ParsedArgs) -> int:
        """Execute show command."""
        import yaml

        from wolo.config import Config

        try:
            config_data = Config._load_config_file()
            if not config_data:
                print("No configuration file found at ~/.wolo/config.yaml")
                print("Use 'wolo config example' to see an example configuration.")
                return 0

            print("Current configuration:")
            print()
            print(yaml.dump(config_data, default_flow_style=False, sort_keys=False))
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1


class ConfigExampleCommand(BaseCommand):
    """wolo config example"""

    @property
    def name(self) -> str:
        return "config example"

    @property
    def description(self) -> str:
        return "Show example configuration file"

    def execute(self, args: ParsedArgs) -> int:
        """Execute example command."""
        example_path = Path(__file__).parent.parent.parent.parent / "config.example.yaml"

        if not example_path.exists():
            print(f"Error: Example config file not found at {example_path}", file=sys.stderr)
            return 1

        print("Example configuration file (save to ~/.wolo/config.yaml):")
        print()
        print(example_path.read_text())
        return 0


class ConfigDocsCommand(BaseCommand):
    """wolo config docs"""

    @property
    def name(self) -> str:
        return "config docs"

    @property
    def description(self) -> str:
        return "Show configuration documentation"

    def execute(self, args: ParsedArgs) -> int:
        """Execute docs command."""
        docs_path = Path(__file__).parent.parent.parent.parent / "docs" / "CONFIGURATION.md"

        if not docs_path.exists():
            print(f"Error: Configuration docs not found at {docs_path}", file=sys.stderr)
            print("See https://github.com/your-repo/wolo/docs/CONFIGURATION.md", file=sys.stderr)
            return 1

        print(docs_path.read_text())
        return 0


class ConfigInitCommand(BaseCommand):
    """wolo config init"""

    @property
    def name(self) -> str:
        return "config init"

    @property
    def description(self) -> str:
        return "Initialize Wolo configuration (first-time setup)"

    def execute(self, args: ParsedArgs) -> int:
        """Execute init command."""
        # Step 1: Define Constants
        config_dir = Path.home() / ".wolo"
        config_file = config_dir / "config.yaml"

        # Step 2: Check if Config Already Exists
        from wolo.config import Config

        if not Config.is_first_run():
            # Config exists - show error and exit
            config_path = Path.home() / ".wolo" / "config.yaml"
            print(
                f"Error: Configuration file already exists at {config_path}",
                file=sys.stderr,
            )
            print(
                "If you want to reinitialize, please delete the current config file first.",
                file=sys.stderr,
            )
            print(f"  rm {config_path}", file=sys.stderr)
            return ExitCode.ERROR

        # Step 3: Get User Input (Interactive Mode)
        # Prompt for API endpoint URL
        api_base = input("API Endpoint URL: ").strip()
        if not api_base:
            print("Error: API endpoint URL is required", file=sys.stderr)
            return ExitCode.ERROR

        # Validate URL format
        if not (api_base.startswith("http://") or api_base.startswith("https://")):
            print(
                "Error: API endpoint URL must start with http:// or https://",
                file=sys.stderr,
            )
            return ExitCode.ERROR

        # Prompt for API key
        api_key = getpass.getpass("API Key: ").strip()
        if not api_key:
            print("Error: API key is required", file=sys.stderr)
            return ExitCode.ERROR

        # Prompt for model name
        model = input("Model name: ").strip()
        if not model:
            print("Error: Model name is required", file=sys.stderr)
            return ExitCode.ERROR

        # Step 4: Create Config Directory
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(
                f"Error: Failed to create config directory {config_dir}: {e}",
                file=sys.stderr,
            )
            return ExitCode.CONFIG_ERROR

        # Step 5: Create Config Data Structure
        config_data = {
            "endpoints": [
                {
                    "name": "default",
                    "model": model,
                    "api_base": api_base,
                    "api_key": api_key,
                    "temperature": 0.7,
                    "max_tokens": 16384,
                }
            ],
            "default_endpoint": "default",
        }

        # Step 6: Write Config File (Atomic)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=config_dir,
                delete=False,
                suffix=".yaml.tmp",
            ) as tmp_file:
                tmp_path = Path(tmp_file.name)
                yaml.dump(config_data, tmp_file, default_flow_style=False, sort_keys=False)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())

            # Atomic rename
            tmp_path.replace(config_file)
        except (OSError, yaml.YAMLError) as e:
            # Clean up temp file if it exists
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

            print(
                f"Error: Failed to write config file {config_file}: {e}",
                file=sys.stderr,
            )
            return ExitCode.CONFIG_ERROR

        # Step 7: Success Message
        print(f"Configuration initialized successfully at {config_file}")
        return ExitCode.SUCCESS
