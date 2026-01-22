"""Main entry point for running wolo as a module."""

from wolo.cli import main_async
import sys

if __name__ == "__main__":
    sys.exit(main_async())
