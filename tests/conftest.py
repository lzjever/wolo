"""Pytest configuration for tests at repo root.

Ensures the project root is on sys.path so that `import wolo` works when
collecting tests from tests/ (e.g. tests/compaction/).
"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if _root not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(_root))
