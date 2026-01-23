"""Metrics collection for benchmarking Wolo agent performance."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class StepMetrics:
    """Metrics collected during a single agent loop step."""

    step_number: int
    llm_latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    tool_calls: list[dict[str, Any]]
    tool_duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "step_number": self.step_number,
            "llm_latency_ms": self.llm_latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "tool_calls": self.tool_calls,
            "tool_count": len(self.tool_calls),
            "tool_duration_ms": self.tool_duration_ms,
        }


@dataclass
class SessionMetrics:
    """Metrics collected during an agent session."""

    session_id: str
    agent_type: str
    start_time: datetime
    end_time: datetime = None
    total_steps: int = 0
    llm_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    tool_calls: int = 0
    tool_errors: int = 0
    tools_by_name: dict[str, int] = field(default_factory=dict)
    errors_by_category: dict[str, int] = field(default_factory=dict)
    finish_reason: str = ""
    subagent_sessions: list[str] = field(default_factory=list)
    steps: list[StepMetrics] = field(default_factory=list)

    @property
    def total_duration_ms(self) -> float:
        """Total session duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0.0

    @property
    def total_tokens(self) -> int:
        """Total tokens used (prompt + completion)."""
        return self.total_prompt_tokens + self.total_completion_tokens

    @property
    def avg_llm_latency_ms(self) -> float:
        """Average LLM latency in milliseconds."""
        if self.llm_calls == 0:
            return 0.0
        return sum(s.llm_latency_ms for s in self.steps) / self.llm_calls

    @property
    def avg_step_duration_ms(self) -> float:
        """Average step duration in milliseconds."""
        if self.total_steps == 0:
            return 0.0
        return self.total_duration_ms / self.total_steps

    def record_step(self, step_metrics: StepMetrics) -> None:
        """Record a step's metrics."""
        self.steps.append(step_metrics)
        self.total_steps = step_metrics.step_number
        self.llm_calls += 1
        self.total_prompt_tokens += step_metrics.prompt_tokens
        self.total_completion_tokens += step_metrics.completion_tokens
        self.tool_calls += len(step_metrics.tool_calls)

        # Track tools by name
        for tc in step_metrics.tool_calls:
            tool_name = tc.get("tool", tc.get("function", {}).get("name", "unknown"))
            self.tools_by_name[tool_name] = self.tools_by_name.get(tool_name, 0) + 1

    def record_tool_error(self, tool_name: str, error_category: str) -> None:
        """Record a tool error."""
        self.tool_errors += 1
        self.errors_by_category[error_category] = self.errors_by_category.get(error_category, 0) + 1

    def record_subagent_session(self, subsession_id: str) -> None:
        """Record a spawned subagent session."""
        self.subagent_sessions.append(subsession_id)

    def finalize(self, finish_reason: str) -> None:
        """Finalize the session metrics."""
        self.end_time = datetime.now()
        self.finish_reason = finish_reason

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "agent_type": self.agent_type,
            "total_steps": self.total_steps,
            "total_duration_ms": self.total_duration_ms,
            "llm_calls": self.llm_calls,
            "avg_llm_latency_ms": self.avg_llm_latency_ms,
            "avg_step_duration_ms": self.avg_step_duration_ms,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "tool_calls": self.tool_calls,
            "tool_errors": self.tool_errors,
            "tools_by_name": self.tools_by_name,
            "errors_by_category": self.errors_by_category,
            "finish_reason": self.finish_reason,
            "subagent_count": len(self.subagent_sessions),
            "subagent_sessions": self.subagent_sessions,
            "steps": [s.to_dict() for s in self.steps],
        }


class MetricsCollector:
    """Singleton collector for session metrics."""

    _instance: "MetricsCollector | None" = None
    _sessions: dict[str, SessionMetrics] = {}

    def __new__(cls) -> "MetricsCollector":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def create_session(self, session_id: str, agent_type: str) -> SessionMetrics:
        """Create a new metrics session."""
        metrics = SessionMetrics(
            session_id=session_id, agent_type=agent_type, start_time=datetime.now()
        )
        self._sessions[session_id] = metrics
        return metrics

    def get_session(self, session_id: str) -> SessionMetrics | None:
        """Get metrics for a session."""
        return self._sessions.get(session_id)

    def finalize_session(self, session_id: str, finish_reason: str) -> None:
        """Finalize a session's metrics."""
        metrics = self.get_session(session_id)
        if metrics:
            metrics.finalize(finish_reason)

    def export_session(self, session_id: str) -> dict[str, Any] | None:
        """Export a session's metrics as a dictionary."""
        metrics = self.get_session(session_id)
        if metrics:
            return metrics.to_dict()
        return None

    def export_all(self) -> list[dict[str, Any]]:
        """Export all session metrics as a list of dictionaries."""
        return [m.to_dict() for m in self._sessions.values()]

    def clear(self) -> None:
        """Clear all collected metrics."""
        self._sessions.clear()

    def save_to_file(self, file_path: str) -> None:
        """Save all metrics to a JSON file."""
        with open(file_path, "w") as f:
            json.dump(self.export_all(), f, indent=2, default=str)


def generate_report(results: list[dict[str, Any]]) -> str:
    """
    Generate a formatted benchmark report from metrics results.

    Args:
        results: List of session metric dictionaries

    Returns:
        Formatted report string
    """
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("WOLO BENCHMARK RESULTS")
    report_lines.append("=" * 80)
    report_lines.append("")

    if not results:
        report_lines.append("No benchmark results available.")
        return "\n".join(report_lines)

    # Summary table
    report_lines.append(f"{'Test':<25} {'Steps':<8} {'Tokens':<10} {'Tools':<8} {'Duration':<12}")
    report_lines.append("-" * 80)

    for r in results:
        name = r.get("name", r.get("session_id", "unknown")[:25])
        steps = r.get("total_steps", 0)
        tokens = r.get("total_tokens", 0)
        tools = r.get("tool_calls", 0)
        duration = f"{r.get('total_duration_ms', 0):.0f}ms"
        report_lines.append(f"{name:<25} {steps:<8} {tokens:<10} {tools:<8} {duration:<12}")

    report_lines.append("")
    report_lines.append("DETAILED METRICS:")
    report_lines.append("-" * 80)

    for r in results:
        name = r.get("name", r.get("session_id", "unknown"))
        report_lines.append(f"\n{name}:")
        report_lines.append(f"  Agent: {r.get('agent_type', 'unknown')}")
        report_lines.append(f"  Finish Reason: {r.get('finish_reason', 'unknown')}")
        report_lines.append(f"  LLM Calls: {r.get('llm_calls', 0)}")
        report_lines.append(f"  Avg LLM Latency: {r.get('avg_llm_latency_ms', 0):.0f}ms")
        report_lines.append(f"  Avg Step Duration: {r.get('avg_step_duration_ms', 0):.0f}ms")
        report_lines.append(f"  Prompt Tokens: {r.get('total_prompt_tokens', 0)}")
        report_lines.append(f"  Completion Tokens: {r.get('total_completion_tokens', 0)}")
        report_lines.append(f"  Total Tokens: {r.get('total_tokens', 0)}")
        report_lines.append(f"  Tool Calls: {r.get('tool_calls', 0)}")
        report_lines.append(f"  Tool Errors: {r.get('tool_errors', 0)}")
        report_lines.append(f"  Subagent Sessions: {r.get('subagent_count', 0)}")

        tools_by_name = r.get("tools_by_name", {})
        if tools_by_name:
            report_lines.append(f"  Tools Used: {tools_by_name}")

        errors_by_category = r.get("errors_by_category", {})
        if errors_by_category:
            report_lines.append(f"  Errors by Category: {errors_by_category}")

    report_lines.append("")
    report_lines.append("=" * 80)
    return "\n".join(report_lines)
