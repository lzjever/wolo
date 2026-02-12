# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.13.1] - 2026-02-13

### Added

- **CLI version flag**: Add `-V/--version` to display wolo version (required for install script verification)

### Fixed

- **Install script verification**: Use venv Python for verification when installing via uv method

### Changed

- **Repo URL**: Updated all references from `mbos-agent/wolo` to `lzjever/wolo`

### Removed

- **Legacy memory tools**: Removed `memory_list`, `memory_recall`, `memory_delete` functions and `/recall`, `/memories`, `/forget` slash commands (users manage memories via filesystem)

## [0.13.0] - 2026-02-13

### Added

- **Project-local configuration priority**: `.wolo/config.yaml` now takes precedence over `~/.wolo/config.yaml` for complete project isolation
- **Session resume enhancement**: `-r/--resume` now creates a new session if the ID doesn't exist instead of erroring
- **Markdown-based memory system**: Memories now stored as `.md` files with YAML frontmatter instead of JSON
  - New `wolo/memory/markdown_model.py` - Markdown memory data model
  - New `wolo/memory/markdown_storage.py` - Storage with mtime-based caching
  - New `wolo/memory/scanner.py` - Memory scanner for LLM context injection
  - New `wolo/memory/migrate.py` - JSON to Markdown migration tool
- **Session ID security validation**: Prevents path traversal attacks in session IDs
- **Security documentation**: Comprehensive `docs/SECURITY.md` documenting all security mechanisms
- **E2E test suite**: 17 end-to-end tests covering file operations, shell commands, multi-step tasks, and session continuity
- **Homebrew formula**: `homebrew/wolo.rb` for macOS native installation
- **Universal installer**: Enhanced `install.sh` supporting uv/pipx/pip methods

### Changed

- Memory context now automatically injected before each LLM call when LTM is enabled
- Removed `memory_list`, `memory_recall`, `memory_delete` tools (users manage memories via filesystem)
- Updated `docs/INSTALLATION.md` with comprehensive installation options
- Sessions and memories now follow config directory (project `.wolo/` or home `~/.wolo/`)

### Security

- Added `SessionStorage._validate_session_id()` to prevent path traversal attacks
- Added validation in all public session API functions (`load_session`, `delete_session`, etc.)
- Memory file names sanitized via `_slugify()` to prevent path injection

### Fixed

- Code analysis e2e test now accepts 2 or 3 methods (LLM may count `__init__`)

## [0.3.0] - 2026-02-06

### Added

- Wild-mode behavior updates for SOLO execution, including automatic wild-mode enablement in SOLO when not explicitly set.
- Session-focused SOLO console framing (`[session_id]` at start/end) and streamlined SOLO output behavior.
- Improved path confirmation UX using the shared UI input flow plus safer terminal-mode fallback handling.
- Development workflow improvements in `Makefile` (`sync` target, corrected benchmark target, and more reliable dev dependency installation).

### Changed

- API-key and provider-facing language to be provider-neutral (`WOLO_API_KEY` only in runtime messaging).
- Config defaults for generic OpenAI-compatible endpoints and model names in examples.
- Requirements entry to align with project-managed dependency installation (`-e .`).

### Fixed

- Full repository lint/format pass and cleanup.
- Path confirmation prompt clarity with resolved-path display.
- Missing `clean-docs` make target and mismatched benchmark module path.

## [0.2.0]

### Added

- Lexilux-based LLM client (`WoloLLMClient`) supporting OpenAI-compatible models (OpenAI, Anthropic, DeepSeek, etc.)
- Output formatting system with minimal, default, and verbose modes
- Subprocess manager for background process handling
- Comprehensive migration test suite for lexilux integration

### Changed

- Lexilux client is now the default (use `WOLO_USE_LEXILUX_CLIENT=false` to revert)
- Improved agent loop with better client selection logic

### Removed

- Legacy GLM client (deprecated, use lexilux client instead)

## [0.1.1]

### Fixed

- Resolved lint errors
- Improved code quality and formatting

## [0.1.0]

### Added

- CLI: `run`, `repl`, `session`, `config`, `debug` subcommands.
- MCP (Model Context Protocol) integration and skill tool for external tools.
- History compaction (summary/pruning policies, token estimation).
- Question UI for interactive LLM–user prompts.
- Tools: read, write, edit, grep, glob, shell, batch, skill, and related helpers.
- LLM integration, config/schema, and event bus.
