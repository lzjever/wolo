import pytest
from wolo.cli.commands.base import BaseCommand


def test_base_command_abstract():
    """BaseCommand should be abstract."""
    with pytest.raises(TypeError):
        BaseCommand()
