"""Constants for the tools system."""

# Shell process tracking constants
MAX_SHELL_HISTORY = 10
MAX_OUTPUT_LINES = 500

# Binary file extensions
BINARY_EXTENSIONS = {
    ".zip",
    ".tar",
    ".gz",
    ".exe",
    ".dll",
    ".so",
    ".class",
    ".jar",
    ".war",
    ".7z",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".bin",
    ".dat",
    ".obj",
    ".o",
    ".a",
    ".lib",
    ".wasm",
    ".pyc",
    ".pyo",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".webp",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wav",
    ".flac",
    ".pdf",
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
}

# Backward compatibility aliases
_BINARY_EXTENSIONS = BINARY_EXTENSIONS
_MAX_SHELL_HISTORY = MAX_SHELL_HISTORY
_MAX_OUTPUT_LINES = MAX_OUTPUT_LINES
