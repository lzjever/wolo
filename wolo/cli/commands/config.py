import sys
from pathlib import Path
from wolo.cli.commands.base import BaseCommand
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
        
        if subcommand == "list-endpoints":
            return ConfigListEndpointsCommand().execute(args)
        elif subcommand == "show":
            return ConfigShowCommand().execute(args)
        elif subcommand == "docs":
            return ConfigDocsCommand().execute(args)
        elif subcommand == "example":
            return ConfigExampleCommand().execute(args)
        else:
            print(f"Error: Unknown subcommand '{subcommand}'", file=sys.stderr)
            print(f"Available subcommands: list-endpoints, show, docs, example", file=sys.stderr)
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
        from wolo.config import Config, EndpointConfig
        
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
        from wolo.config import Config
        import yaml
        
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
        
        print(f"Example configuration file (save to ~/.wolo/config.yaml):")
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
