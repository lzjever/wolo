"""
Output rendering module for Wolo CLI.

Provides different output styles for various use cases:
- minimal: Script-friendly, no colors, structured summary
- default: Standard interactive output with colors and icons
- verbose: Detailed output with diffs, full command output, etc.
"""

from wolo.cli.output.base import OutputConfig, OutputRenderer, OutputStyle
from wolo.cli.output.default import DefaultRenderer
from wolo.cli.output.minimal import MinimalRenderer
from wolo.cli.output.verbose import VerboseRenderer

__all__ = [
    "OutputConfig",
    "OutputRenderer",
    "OutputStyle",
    "DefaultRenderer",
    "MinimalRenderer",
    "VerboseRenderer",
    "get_renderer",
]


def get_renderer(config: OutputConfig) -> OutputRenderer:
    """
    Get the appropriate renderer based on configuration.

    Args:
        config: Output configuration

    Returns:
        OutputRenderer instance for the specified style
    """
    renderers = {
        OutputStyle.MINIMAL: MinimalRenderer,
        OutputStyle.DEFAULT: DefaultRenderer,
        OutputStyle.VERBOSE: VerboseRenderer,
    }

    renderer_class = renderers.get(config.style, DefaultRenderer)
    return renderer_class(config)
