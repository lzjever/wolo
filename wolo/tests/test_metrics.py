"""Unit tests for the metrics module."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from wolo.metrics import (
    StepMetrics,
    SessionMetrics,
    MetricsCollector,
    generate_report,
)


class TestStepMetrics:
    """Tests for StepMetrics dataclass."""

    def test_create_step_metrics(self):
        """Test creating a StepMetrics instance."""
        step = StepMetrics(
            step_number=1,
            llm_latency_ms=1234.5,
            prompt_tokens=100,
            completion_tokens=50,
            tool_calls=[{"tool": "read", "input": {"file_path": "test.txt"}}],
            tool_duration_ms=100.0
        )
        assert step.step_number == 1
        assert step.llm_latency_ms == 1234.5
        assert step.prompt_tokens == 100
        assert step.completion_tokens == 50
        assert len(step.tool_calls) == 1

    def test_step_metrics_to_dict(self):
        """Test converting StepMetrics to dictionary."""
        step = StepMetrics(
            step_number=1,
            llm_latency_ms=1234.5,
            prompt_tokens=100,
            completion_tokens=50,
            tool_calls=[{"tool": "read"}],
            tool_duration_ms=100.0
        )
        result = step.to_dict()
        assert result["step_number"] == 1
        assert result["llm_latency_ms"] == 1234.5
        assert result["total_tokens"] == 150
        assert result["tool_count"] == 1


class TestSessionMetrics:
    """Tests for SessionMetrics dataclass."""

    def test_create_session_metrics(self):
        """Test creating a SessionMetrics instance."""
        session = SessionMetrics(
            session_id="test-session-123",
            agent_type="general",
            start_time=datetime.now()
        )
        assert session.session_id == "test-session-123"
        assert session.agent_type == "general"
        assert session.total_steps == 0
        assert session.llm_calls == 0

    def test_session_properties_empty(self):
        """Test session properties when empty."""
        session = SessionMetrics(
            session_id="test",
            agent_type="general",
            start_time=datetime.now()
        )
        assert session.total_tokens == 0
        assert session.total_duration_ms == 0
        assert session.avg_llm_latency_ms == 0

    def test_session_properties_with_data(self):
        """Test session properties with data."""
        now = datetime.now()
        later = now + timedelta(seconds=5)
        session = SessionMetrics(
            session_id="test",
            agent_type="general",
            start_time=now,
            end_time=later
        )
        session.total_prompt_tokens = 1000
        session.total_completion_tokens = 500
        session.llm_calls = 2

        assert session.total_duration_ms == 5000
        assert session.total_tokens == 1500
        assert session.avg_llm_latency_ms == 0  # No steps recorded

    def test_record_step(self):
        """Test recording a step."""
        session = SessionMetrics(
            session_id="test",
            agent_type="general",
            start_time=datetime.now()
        )
        step = StepMetrics(
            step_number=1,
            llm_latency_ms=1000,
            prompt_tokens=100,
            completion_tokens=50,
            tool_calls=[{"tool": "read"}],
            tool_duration_ms=100
        )
        session.record_step(step)

        assert session.total_steps == 1
        assert session.llm_calls == 1
        assert session.total_prompt_tokens == 100
        assert session.total_completion_tokens == 50
        assert session.tool_calls == 1
        assert session.tools_by_name == {"read": 1}

    def test_record_multiple_steps_same_tool(self):
        """Test recording multiple steps with same tool."""
        session = SessionMetrics(
            session_id="test",
            agent_type="general",
            start_time=datetime.now()
        )
        step1 = StepMetrics(
            step_number=1,
            llm_latency_ms=1000,
            prompt_tokens=100,
            completion_tokens=50,
            tool_calls=[{"tool": "read"}],
            tool_duration_ms=100
        )
        step2 = StepMetrics(
            step_number=2,
            llm_latency_ms=1200,
            prompt_tokens=200,
            completion_tokens=80,
            tool_calls=[{"tool": "read"}, {"tool": "grep"}],
            tool_duration_ms=200
        )
        session.record_step(step1)
        session.record_step(step2)

        assert session.total_steps == 2
        assert session.llm_calls == 2
        assert session.total_prompt_tokens == 300
        assert session.total_completion_tokens == 130
        assert session.tool_calls == 3
        assert session.tools_by_name == {"read": 2, "grep": 1}

    def test_record_tool_error(self):
        """Test recording a tool error."""
        session = SessionMetrics(
            session_id="test",
            agent_type="general",
            start_time=datetime.now()
        )
        session.record_tool_error("read", "file_not_found")
        session.record_tool_error("write", "permission_denied")

        assert session.tool_errors == 2
        assert session.errors_by_category == {
            "file_not_found": 1,
            "permission_denied": 1
        }

    def test_record_subagent_session(self):
        """Test recording subagent sessions."""
        session = SessionMetrics(
            session_id="test",
            agent_type="general",
            start_time=datetime.now()
        )
        session.record_subagent_session("sub-1")
        session.record_subagent_session("sub-2")

        assert session.subagent_sessions == ["sub-1", "sub-2"]

    def test_finalize(self):
        """Test finalizing a session."""
        session = SessionMetrics(
            session_id="test",
            agent_type="general",
            start_time=datetime.now()
        )
        session.finalize("stop")

        assert session.end_time is not None
        assert session.finish_reason == "stop"

    def test_to_dict(self):
        """Test converting session to dictionary."""
        now = datetime.now()
        session = SessionMetrics(
            session_id="test-123",
            agent_type="general",
            start_time=now
        )
        session.finalize("stop")

        result = session.to_dict()
        assert result["session_id"] == "test-123"
        assert result["agent_type"] == "general"
        assert result["finish_reason"] == "stop"
        assert "subagent_count" in result


class TestMetricsCollector:
    """Tests for MetricsCollector singleton."""

    def test_singleton(self):
        """Test that MetricsCollector is a singleton."""
        collector1 = MetricsCollector()
        collector2 = MetricsCollector()
        assert collector1 is collector2

    def test_create_session(self):
        """Test creating a metrics session."""
        collector = MetricsCollector()
        collector.clear()  # Clear any previous state

        metrics = collector.create_session("test-id", "general")
        assert metrics.session_id == "test-id"
        assert metrics.agent_type == "general"

    def test_get_session(self):
        """Test getting a session."""
        collector = MetricsCollector()
        collector.clear()

        collector.create_session("test-id", "general")
        metrics = collector.get_session("test-id")
        assert metrics is not None
        assert metrics.session_id == "test-id"

    def test_get_nonexistent_session(self):
        """Test getting a nonexistent session."""
        collector = MetricsCollector()
        collector.clear()

        metrics = collector.get_session("nonexistent")
        assert metrics is None

    def test_finalize_session(self):
        """Test finalizing a session."""
        collector = MetricsCollector()
        collector.clear()

        collector.create_session("test-id", "general")
        collector.finalize_session("test-id", "stop")

        metrics = collector.get_session("test-id")
        assert metrics is not None
        assert metrics.finish_reason == "stop"
        assert metrics.end_time is not None

    def test_export_session(self):
        """Test exporting a session."""
        collector = MetricsCollector()
        collector.clear()

        collector.create_session("test-id", "general")
        collector.finalize_session("test-id", "stop")

        result = collector.export_session("test-id")
        assert result is not None
        assert result["session_id"] == "test-id"

    def test_export_all(self):
        """Test exporting all sessions."""
        collector = MetricsCollector()
        collector.clear()

        collector.create_session("test-1", "general")
        collector.create_session("test-2", "plan")

        results = collector.export_all()
        assert len(results) == 2
        session_ids = {r["session_id"] for r in results}
        assert session_ids == {"test-1", "test-2"}

    def test_clear(self):
        """Test clearing all sessions."""
        collector = MetricsCollector()

        collector.create_session("test-1", "general")
        collector.create_session("test-2", "plan")
        assert len(collector.export_all()) >= 2

        collector.clear()
        assert len(collector.export_all()) == 0

    def test_save_to_file(self, tmp_path):
        """Test saving metrics to a JSON file."""
        collector = MetricsCollector()
        collector.clear()

        collector.create_session("test-id", "general")
        collector.finalize_session("test-id", "stop")

        output_file = tmp_path / "metrics.json"
        collector.save_to_file(str(output_file))

        assert output_file.exists()
        with open(output_file) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["session_id"] == "test-id"


class TestGenerateReport:
    """Tests for the generate_report function."""

    def test_empty_results(self):
        """Test report with empty results."""
        report = generate_report([])
        assert "No benchmark results available" in report

    def test_single_result(self):
        """Test report with a single result."""
        results = [{
            "name": "test",
            "agent_type": "general",
            "total_steps": 5,
            "total_tokens": 1000,
            "tool_calls": 3,
            "total_duration_ms": 5000,
            "finish_reason": "stop",
            "llm_calls": 5,
            "avg_llm_latency_ms": 800,
            "total_prompt_tokens": 700,
            "total_completion_tokens": 300,
            "tool_errors": 0,
            "subagent_count": 0,
            "tools_by_name": {"read": 2, "grep": 1},
            "errors_by_category": {}
        }]
        report = generate_report(results)
        assert "test" in report
        assert "WOLO BENCHMARK RESULTS" in report
        assert "5" in report  # steps
        assert "1000" in report  # tokens

    def test_multiple_results(self):
        """Test report with multiple results."""
        results = [
            {
                "name": "test1",
                "agent_type": "general",
                "total_steps": 3,
                "total_tokens": 500,
                "tool_calls": 1,
                "total_duration_ms": 2000,
                "finish_reason": "stop",
                "llm_calls": 3,
                "avg_llm_latency_ms": 600,
                "total_prompt_tokens": 300,
                "total_completion_tokens": 200,
                "tool_errors": 0,
                "subagent_count": 0,
                "tools_by_name": {"read": 1},
                "errors_by_category": {}
            },
            {
                "name": "test2",
                "agent_type": "plan",
                "total_steps": 7,
                "total_tokens": 1500,
                "tool_calls": 5,
                "total_duration_ms": 8000,
                "finish_reason": "stop",
                "llm_calls": 7,
                "avg_llm_latency_ms": 1000,
                "total_prompt_tokens": 1000,
                "total_completion_tokens": 500,
                "tool_errors": 1,
                "subagent_count": 0,
                "tools_by_name": {"read": 3, "grep": 2},
                "errors_by_category": {"file_not_found": 1}
            }
        ]
        report = generate_report(results)
        assert "test1" in report
        assert "test2" in report
        assert "WOLO BENCHMARK RESULTS" in report
