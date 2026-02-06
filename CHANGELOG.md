# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
