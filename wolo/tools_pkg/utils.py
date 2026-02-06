"""Utility functions for the tools system."""

from pathlib import Path

from wolo.tools_pkg.constants import BINARY_EXTENSIONS


def _is_binary_file(path: Path) -> bool:
    """Check if a file is binary."""
    # Check extension
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True

    # Check content
    try:
        with open(path, "rb") as f:
            chunk = f.read(4096)

        if not chunk:
            return False

        # Check for NULL bytes
        if b"\x00" in chunk:
            return True

        # Check non-printable character ratio
        non_printable = sum(
            1
            for byte in chunk
            if byte < 32 and byte not in (9, 10, 13)  # tab, newline, carriage return
        )
        ratio = non_printable / len(chunk)
        return ratio > 0.1  # More than 10% non-printable suggests binary

    except OSError:
        return False


def _suggest_similar_files(path: Path) -> list[str]:
    """Suggest similar files based on the given path."""
    suggestions = []
    parent = path.parent
    base = path.stem

    try:
        if parent.exists():
            for f in parent.iterdir():
                if f.is_file():
                    # Check if names are similar
                    if base.lower() in f.stem.lower() or f.stem.lower() in base.lower():
                        suggestions.append(str(f))
                        if len(suggestions) >= 5:
                            break
    except OSError:
        pass

    return suggestions
