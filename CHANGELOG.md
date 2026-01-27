# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
