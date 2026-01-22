"""Benchmark test suite for Wolo agent performance tracking."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# Add wolo to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from wolo.agent import agent_loop
from wolo.agents import get_agent
from wolo.cli import setup_logging
from wolo.config import Config
from wolo.metrics import MetricsCollector, generate_report
from wolo.session import add_user_message, create_session

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Run benchmark tests and collect metrics."""

    def __init__(self, config: Config):
        self.config = config
        self.results = []

    async def run_test(self, name: str, agent_type: str, message: str) -> dict[str, Any]:
        """
        Run a single benchmark test.

        Args:
            name: Test name for reporting
            agent_type: Type of agent to use (general, plan, explore)
            message: User message to send

        Returns:
            Metrics dictionary for this test
        """
        logger.info(f"Running benchmark test: {name}")

        # Clear any previous metrics
        collector = MetricsCollector()

        session_id = create_session()
        add_user_message(session_id, message)

        agent_config = get_agent(agent_type)
        await agent_loop(self.config, session_id, agent_config)

        # Collect metrics
        metrics = collector.export_session(session_id)
        if metrics:
            metrics["name"] = name
            metrics["test_message"] = message

        return metrics

    async def run_all_benchmarks(self) -> list[dict[str, Any]]:
        """
        Run all benchmark scenarios.

        Returns:
            List of metric dictionaries from all tests
        """
        logger.info("Starting benchmark suite...")

        # Test 1: Simple query (no tools expected)
        self.results.append(await self.run_test(
            "simple_math",
            "general",
            "What is 25 * 37? Just give me the number."
        ))

        # Test 2: File read operation
        self.results.append(await self.run_test(
            "file_read",
            "general",
            "Read the file /home/percy/works/mygithub/opencode/wolo/SUMMARY.md and summarize it in one sentence."
        ))

        # Test 3: Code search operation
        self.results.append(await self.run_test(
            "code_search",
            "general",
            "Use grep to find all files in wolo that contain 'async def' pattern. Count how many matches you find."
        ))

        # Test 4: Glob operation
        self.results.append(await self.run_test(
            "glob_search",
            "general",
            "Use glob to find all Python files in the wolo directory. How many files did you find?"
        ))

        # Test 5: Multi-step task with file write
        self.results.append(await self.run_test(
            "file_write",
            "general",
            "Create a file called /tmp/wolo_bench_test.txt with content 'Hello from Wolo Benchmark!'"
        ))

        # Test 6: Subagent delegation
        self.results.append(await self.run_test(
            "subagent_task",
            "general",
            "Use the task tool to spawn an explore agent to analyze the wolo directory structure."
        ))

        # Test 7: Plan mode
        self.results.append(await self.run_test(
            "plan_mode",
            "plan",
            "Create a plan for adding a new feature to wolo that tracks user preferences."
        ))

        # Test 8: Explore mode
        self.results.append(await self.run_test(
            "explore_mode",
            "explore",
            "Analyze the wolo tools implementation and explain how the shell tool works."
        ))

        # Clean up test file
        try:
            os.remove("/tmp/wolo_bench_test.txt")
        except FileNotFoundError:
            pass

        logger.info(f"Benchmark suite completed. Ran {len(self.results)} tests.")
        return self.results


def generate_comparison_report(results: list[dict[str, Any]]) -> str:
    """
    Generate a comparison report showing relative performance.

    Args:
        results: List of metric dictionaries

    Returns:
        Formatted comparison report string
    """
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("WOLO BENCHMARK COMPARISON REPORT")
    report_lines.append("=" * 80)
    report_lines.append("")

    if not results:
        report_lines.append("No benchmark results to compare.")
        return "\n".join(report_lines)

    # Calculate aggregates
    total_tokens = sum(r.get("total_tokens", 0) for r in results)
    total_duration = sum(r.get("total_duration_ms", 0) for r in results)
    total_steps = sum(r.get("total_steps", 0) for r in results)
    total_tools = sum(r.get("tool_calls", 0) for r in results)
    total_llm_calls = sum(r.get("llm_calls", 0) for r in results)

    avg_tokens = total_tokens / len(results) if results else 0
    avg_duration = total_duration / len(results) if results else 0
    avg_steps = total_steps / len(results) if results else 0

    report_lines.append("AGGREGATE STATISTICS:")
    report_lines.append("-" * 80)
    report_lines.append(f"Total Tests: {len(results)}")
    report_lines.append(f"Total Tokens: {total_tokens}")
    report_lines.append(f"Total Duration: {total_duration:.0f}ms ({total_duration/1000:.1f}s)")
    report_lines.append(f"Total Steps: {total_steps}")
    report_lines.append(f"Total LLM Calls: {total_llm_calls}")
    report_lines.append(f"Total Tool Calls: {total_tools}")
    report_lines.append("")
    report_lines.append(f"Avg Tokens per Test: {avg_tokens:.0f}")
    report_lines.append(f"Avg Duration per Test: {avg_duration:.0f}ms")
    report_lines.append(f"Avg Steps per Test: {avg_steps:.1f}")
    report_lines.append("")

    # Find fastest/slowest tests
    valid_results = [r for r in results if r.get("total_duration_ms", 0) > 0]
    if valid_results:
        fastest = min(valid_results, key=lambda x: x.get("total_duration_ms", float("inf")))
        slowest = max(valid_results, key=lambda x: x.get("total_duration_ms", 0))
        most_tokens = max(results, key=lambda x: x.get("total_tokens", 0))
        fewest_tokens = min(results, key=lambda x: x.get("total_tokens", float("inf")))

        report_lines.append("PERFORMANCE EXTREMES:")
        report_lines.append("-" * 80)
        report_lines.append(f"Fastest: {fastest.get('name', 'unknown')} ({fastest.get('total_duration_ms', 0):.0f}ms)")
        report_lines.append(f"Slowest: {slowest.get('name', 'unknown')} ({slowest.get('total_duration_ms', 0):.0f}ms)")
        report_lines.append(f"Most Tokens: {most_tokens.get('name', 'unknown')} ({most_tokens.get('total_tokens', 0)} tokens)")
        report_lines.append(f"Fewest Tokens: {fewest_tokens.get('name', 'unknown')} ({fewest_tokens.get('total_tokens', 0)} tokens)")
        report_lines.append("")

    # Agent type breakdown
    by_agent: dict[str, list[dict]] = {}
    for r in results:
        agent = r.get("agent_type", "unknown")
        if agent not in by_agent:
            by_agent[agent] = []
        by_agent[agent].append(r)

    if len(by_agent) > 1:
        report_lines.append("BREAKDOWN BY AGENT TYPE:")
        report_lines.append("-" * 80)
        for agent_type, agent_results in by_agent.items():
            avg_dur = sum(r.get("total_duration_ms", 0) for r in agent_results) / len(agent_results)
            avg_tok = sum(r.get("total_tokens", 0) for r in agent_results) / len(agent_results)
            report_lines.append(f"{agent_type:12s} - {len(agent_results)} tests, avg {avg_dur:.0f}ms, avg {avg_tok:.0f} tokens")
        report_lines.append("")

    # Most used tools across all tests
    all_tools: dict[str, int] = {}
    for r in results:
        for tool, count in r.get("tools_by_name", {}).items():
            all_tools[tool] = all_tools.get(tool, 0) + count

    if all_tools:
        report_lines.append("MOST USED TOOLS:")
        report_lines.append("-" * 80)
        sorted_tools = sorted(all_tools.items(), key=lambda x: x[1], reverse=True)
        for tool, count in sorted_tools[:10]:
            report_lines.append(f"  {tool:20s}: {count} calls")
        report_lines.append("")

    report_lines.append("=" * 80)
    return "\n".join(report_lines)


async def main_benchmark() -> int:
    """Main entry point for benchmark suite."""
    # Setup logging
    setup_logging("INFO")

    print("=" * 80)
    print("WOLO BENCHMARK SUITE")
    print("=" * 80)
    print()

    # Check for API key
    if not os.getenv("GLM_API_KEY"):
        print("Error: GLM_API_KEY environment variable is not set.")
        print("Please set it with: export GLM_API_KEY=your_api_key")
        return 1

    try:
        config = Config.from_env()
    except ValueError as e:
        print(f"Configuration error: {e}")
        return 1

    # Run benchmarks
    runner = BenchmarkRunner(config)
    results = await runner.run_all_benchmarks()

    # Save JSON
    output_file = "benchmark_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nBenchmark results saved to: {output_file}")

    # Print individual test report
    print("\n" + generate_report(results))

    # Print comparison report
    print("\n" + generate_comparison_report(results))

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main_benchmark()))
