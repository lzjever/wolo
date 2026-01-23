"""Main entry point for running wolo as a module."""

import sys

from wolo.cli import main_async

if __name__ == "__main__":
    sys.exit(main_async())
