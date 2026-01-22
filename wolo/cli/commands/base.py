from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wolo.cli.parser import ParsedArgs

class BaseCommand(ABC):
    """Base class for all CLI commands."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Command name (e.g., 'run', 'session')."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Command description for help text."""
        pass
    
    @abstractmethod
    def execute(self, args: "ParsedArgs") -> int:
        """
        Execute the command.
        
        Args:
            args: Parsed command arguments
            
        Returns:
            Exit code (0 = success, non-zero = failure)
        """
        pass
    
    def validate_args(self, args: "ParsedArgs") -> tuple[bool, str]:
        """
        Validate command arguments.
        
        Args:
            args: Parsed arguments
            
        Returns:
            (is_valid, error_message) tuple
        """
        return (True, "")
    
    def get_help(self) -> str:
        """Get help text for this command."""
        return f"{self.name}: {self.description}"
