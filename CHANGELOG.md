# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Benchmark System
- **Comprehensive Metrics Collection**: Complete benchmark system for tracking agent performance
  - Session-level metrics: steps, duration, tokens, LLM calls, tool usage, errors
  - Step-level metrics: per-step latency, prompt/completion tokens, tool calls
  - Tool usage breakdown by name and error categorization
  - Subagent session tracking for nested agent calls
- **CLI Benchmark Flags**: `--benchmark` and `--benchmark-output` for easy benchmarking
  - Automatic JSON export of metrics data
  - Formatted terminal report with summary statistics
- **Benchmark Test Suite**: 8 comprehensive test scenarios
  - Simple math queries, file operations, code search, glob operations
  - Multi-step tasks, subagent delegation, plan/explore modes
- **MetricsCollector Singleton**: Thread-safe metrics collection across agent sessions
  - Session creation, tracking, finalization, and export
  - JSON serialization with datetime handling
- **Report Generation**: Comparison reports with aggregates and performance extremes

#### Tool Enhancements
- **multiedit Tool**: Edit multiple files at once with different changes
  - Atomic multi-file operations
  - Per-file success/failure tracking
  - Summary output with detailed results

#### Agent System
- **Multiple Agent Types**: Specialized agents for different use cases
  - `general` - Full access for coding tasks
  - `plan` - Read-only planning with structured workflow
  - `explore` - Codebase analysis and exploration
  - `compaction` - Context summarization for token efficiency
- **Permission Rulesets**: Fine-grained tool access control
  - Allow all, read-only, and ask-confirmation modes
  - Per-agent permission configuration

#### Session Management
- **Persistent Sessions**: Save and restore agent sessions
  - `--save` flag to persist sessions to disk
  - `--resume` flag to continue previous sessions
  - `--list-sessions` to browse saved sessions
- **Session Metadata**: Enhanced session tracking
  - Parent session ID for subagent relationships
  - Agent type tracking
  - Session titles and tags for organization
  - Update timestamps

#### Error Handling
- **Comprehensive Error Classification**: Detailed error categorization
  - Authentication errors (401, 403)
  - Rate limiting (429)
  - Server errors (5xx)
  - Network errors
  - Validation errors (400)
  - Not found (404)
- **User-Friendly Error Messages**: Clear error descriptions
- **Retry Strategy**: Automatic retry with exponential backoff for retryable errors

### Changed
- **LLM Client**: Enhanced with token usage extraction from GLM API
  - Captures actual prompt_tokens and completion_tokens from SSE responses
  - Per-request token tracking for accurate metrics
- **Agent Loop**: Integrated metrics collection throughout execution
  - Automatic timing of LLM calls and tool execution
  - Tool call tracking and error recording
  - Session finalization with finish reasons
- **Tool Execution**: Subagent spawning now tracked in parent metrics

### Fixed
- **Doom Loop Detection**: Prevent infinite loops from repeated tool calls
  - Detects when same tool+input is called 3+ times
  - Automatically stops with informative error message

## [0.2.0] - 2025-01-20

### Added
- **Streaming Support**: Real-time output from GLM API
- **Tool System**: Shell, read, write, edit, grep, glob tools
- **Web Integration**: Web search and page fetching
- **Event Bus**: Pub/sub system for UI updates
- **Session Management**: In-memory session storage with message history

## [0.1.0] - 2025-01-15

### Added
- Initial release
- Basic agent loop with GLM-4-Flash integration
- Shell tool for command execution
- CLI interface with argument parsing
