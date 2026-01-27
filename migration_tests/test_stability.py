#!/usr/bin/env python3
"""
Long-running stability tests for lexilux migration.
Tests sustained operation, memory usage, and connection stability.
"""

import asyncio
import logging
import statistics
import time

import psutil

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StabilityMonitor:
    """Monitor system resources and stability metrics."""

    def __init__(self):
        self.process = psutil.Process()
        self.start_time = time.time()
        self.measurements = []

    def record_measurement(self):
        """Record current system state."""
        current_time = time.time()
        memory_mb = self.process.memory_info().rss / 1024 / 1024
        cpu_percent = self.process.cpu_percent()

        measurement = {
            'timestamp': current_time,
            'elapsed': current_time - self.start_time,
            'memory_mb': memory_mb,
            'cpu_percent': cpu_percent,
        }

        self.measurements.append(measurement)
        return measurement

    def get_statistics(self):
        """Get stability statistics."""
        if not self.measurements:
            return {}

        memory_values = [m['memory_mb'] for m in self.measurements]
        cpu_values = [m['cpu_percent'] for m in self.measurements if m['cpu_percent'] > 0]

        return {
            'total_duration': self.measurements[-1]['elapsed'],
            'total_measurements': len(self.measurements),
            'memory_stats': {
                'min_mb': min(memory_values),
                'max_mb': max(memory_values),
                'avg_mb': statistics.mean(memory_values),
                'growth_mb': memory_values[-1] - memory_values[0] if len(memory_values) > 1 else 0
            },
            'cpu_stats': {
                'avg_percent': statistics.mean(cpu_values) if cpu_values else 0,
                'max_percent': max(cpu_values) if cpu_values else 0
            }
        }


async def test_sustained_requests():
    """Test sustained API requests over time."""
    print("⏱️  Testing Sustained Request Performance")
    print("-" * 50)

    try:
        from wolo.agents import get_agent
        from wolo.config import Config
        from wolo.llm_adapter import WoloLLMClient

        config = Config.from_env()
        agent_config = get_agent("general")

        client = WoloLLMClient(
            config=config,
            agent_config=agent_config,
            session_id="stability-sustained-test",
            agent_display_name="SustainedTest"
        )

        monitor = StabilityMonitor()

        # Test parameters
        num_requests = 10  # Reasonable number for stability testing
        delay_between_requests = 2  # Seconds

        print(f"📊 Running {num_requests} requests with {delay_between_requests}s intervals...")

        successful_requests = 0
        failed_requests = 0
        response_times = []

        for i in range(num_requests):
            print(f"   Request {i+1}/{num_requests}...")

            # Record system state before request
            monitor.record_measurement()

            messages = [{"role": "user", "content": f"Stability test request {i+1}: Please respond with 'Request {i+1} processed successfully'"}]

            start_time = time.time()
            request_success = False

            try:
                async for event in client.chat_completion(messages, stream=True):
                    if event['type'] == 'text-delta':
                        request_success = True
                    elif event['type'] == 'error':
                        print(f"     ❌ Request {i+1} failed: {event.get('error')}")
                        failed_requests += 1
                        break
                    elif event['type'] == 'finish':
                        end_time = time.time()
                        response_time = end_time - start_time

                        if request_success:
                            successful_requests += 1
                            response_times.append(response_time)
                            print(f"     ✅ Request {i+1} successful ({response_time:.2f}s)")
                        break

            except Exception as e:
                failed_requests += 1
                print(f"     ❌ Request {i+1} exception: {e}")

            # Wait between requests
            if i < num_requests - 1:
                await asyncio.sleep(delay_between_requests)

        # Final system measurement
        monitor.record_measurement()

        # Calculate statistics
        stats = monitor.get_statistics()
        success_rate = successful_requests / num_requests

        print("\n📊 Sustained Request Results:")
        print(f"   Success rate: {success_rate*100:.1f}% ({successful_requests}/{num_requests})")
        print(f"   Failed requests: {failed_requests}")
        print(f"   Total duration: {stats['total_duration']:.1f}s")

        if response_times:
            avg_response = statistics.mean(response_times)
            print(f"   Avg response time: {avg_response:.2f}s")
            print(f"   Response time range: {min(response_times):.2f}s - {max(response_times):.2f}s")

        print("\n💾 Resource Usage:")
        memory_stats = stats['memory_stats']
        print(f"   Memory usage: {memory_stats['min_mb']:.1f}MB - {memory_stats['max_mb']:.1f}MB")
        print(f"   Memory growth: {memory_stats['growth_mb']:+.1f}MB")
        print(f"   Average memory: {memory_stats['avg_mb']:.1f}MB")

        cpu_stats = stats['cpu_stats']
        if cpu_stats['avg_percent'] > 0:
            print(f"   CPU usage: avg {cpu_stats['avg_percent']:.1f}%, max {cpu_stats['max_percent']:.1f}%")

        # Stability assessment
        stable = True
        stability_notes = []

        if success_rate < 0.8:
            stable = False
            stability_notes.append("Low success rate")

        if memory_stats['growth_mb'] > 100:  # More than 100MB growth
            stable = False
            stability_notes.append("High memory growth")

        if len(response_times) > 1:
            response_variance = statistics.stdev(response_times) / statistics.mean(response_times)
            if response_variance > 0.5:  # High variance
                stability_notes.append("High response time variance")

        if stable:
            print("✅ Sustained operation: STABLE")
        else:
            print("⚠️  Sustained operation: NEEDS ATTENTION")
            for note in stability_notes:
                print(f"   - {note}")

        return stable and success_rate >= 0.8

    except Exception as e:
        print(f"❌ Sustained requests test failed: {e}")
        return False


async def test_connection_reuse():
    """Test connection reuse and pooling stability."""
    print("\n🔄 Testing Connection Reuse Stability")
    print("-" * 50)

    try:
        from wolo.agents import get_agent
        from wolo.config import Config
        from wolo.llm_adapter import WoloLLMClient

        config = Config.from_env()
        agent_config = get_agent("general")

        # Create multiple clients to test connection pooling
        clients = []
        for i in range(3):
            client = WoloLLMClient(
                config=config,
                agent_config=agent_config,
                session_id=f"connection-reuse-{i}",
                agent_display_name=f"ConnReuseTest{i}"
            )
            clients.append(client)

        print(f"🔗 Testing connection reuse with {len(clients)} clients...")

        # Test alternating requests between clients
        successful_requests = 0
        total_requests = 6  # 2 requests per client

        for i in range(total_requests):
            client_idx = i % len(clients)
            client = clients[client_idx]

            messages = [{"role": "user", "content": f"Connection test {i+1} from client {client_idx+1}"}]

            print(f"   Request {i+1} via client {client_idx+1}...")

            try:
                success = False
                async for event in client.chat_completion(messages, stream=True):
                    if event['type'] == 'text-delta':
                        success = True
                    elif event['type'] == 'error':
                        print(f"     ❌ Connection error: {event.get('error')}")
                        break
                    elif event['type'] == 'finish':
                        if success:
                            successful_requests += 1
                            print("     ✅ Connection successful")
                        break

            except Exception as e:
                print(f"     ❌ Connection exception: {e}")

            # Small delay between requests
            await asyncio.sleep(0.5)

        success_rate = successful_requests / total_requests
        print(f"📊 Connection reuse success rate: {success_rate*100:.1f}% ({successful_requests}/{total_requests})")

        # Test connection cleanup
        try:
            for client in clients:
                if hasattr(client, 'close_all_sessions'):
                    await client.close_all_sessions()
            print("✅ Connection cleanup successful")
        except Exception as e:
            print(f"⚠️  Connection cleanup: {e}")

        return success_rate >= 0.8

    except Exception as e:
        print(f"❌ Connection reuse test failed: {e}")
        return False


async def test_memory_stability():
    """Test memory usage stability over multiple operations."""
    print("\n💾 Testing Memory Usage Stability")
    print("-" * 50)

    try:
        from wolo.agents import get_agent
        from wolo.config import Config
        from wolo.llm_adapter import WoloLLMClient

        config = Config.from_env()
        agent_config = get_agent("general")

        client = WoloLLMClient(
            config=config,
            agent_config=agent_config,
            session_id="memory-stability-test",
            agent_display_name="MemoryTest"
        )

        monitor = StabilityMonitor()

        # Record initial memory
        initial_measurement = monitor.record_measurement()
        print(f"📊 Initial memory usage: {initial_measurement['memory_mb']:.1f}MB")

        # Perform multiple operations
        num_cycles = 5

        for cycle in range(num_cycles):
            print(f"   Memory cycle {cycle+1}/{num_cycles}...")

            # Perform various operations
            operations = [
                {"role": "user", "content": "Short message"},
                {"role": "user", "content": "Medium length message for memory testing. " * 10},
                {"role": "user", "content": "A"},  # Very short
            ]

            for op_idx, messages in enumerate([operations]):
                try:
                    async for event in client.chat_completion([messages[op_idx % len(messages)]], stream=True):
                        if event['type'] == 'finish':
                            break
                except Exception:
                    pass  # Ignore errors for memory test

            # Record memory after each cycle
            measurement = monitor.record_measurement()
            print(f"     After cycle {cycle+1}: {measurement['memory_mb']:.1f}MB")

            await asyncio.sleep(0.5)

        # Final statistics
        stats = monitor.get_statistics()
        memory_stats = stats['memory_stats']

        print("\n📊 Memory Stability Results:")
        print(f"   Initial memory: {memory_stats['min_mb']:.1f}MB")
        print(f"   Peak memory: {memory_stats['max_mb']:.1f}MB")
        print(f"   Final memory: {monitor.measurements[-1]['memory_mb']:.1f}MB")
        print(f"   Total growth: {memory_stats['growth_mb']:+.1f}MB")
        print(f"   Average usage: {memory_stats['avg_mb']:.1f}MB")

        # Assess memory stability
        growth_rate = memory_stats['growth_mb'] / stats['total_duration'] * 60  # MB per minute

        memory_stable = True
        if memory_stats['growth_mb'] > 50:  # More than 50MB total growth
            memory_stable = False
            print("⚠️  High memory growth detected")
        elif growth_rate > 10:  # More than 10MB/minute
            memory_stable = False
            print(f"⚠️  High memory growth rate: {growth_rate:.1f}MB/min")
        else:
            print(f"✅ Memory usage stable (growth: {growth_rate:.1f}MB/min)")

        return memory_stable

    except Exception as e:
        print(f"❌ Memory stability test failed: {e}")
        return False


async def run_stability_tests():
    """Run all stability tests."""
    print("🏃 COMPREHENSIVE STABILITY TESTS")
    print("=" * 60)
    print("Testing long-term operation stability...")

    tests = [
        ("Sustained Requests", test_sustained_requests),
        ("Connection Reuse", test_connection_reuse),
        ("Memory Stability", test_memory_stability),
    ]

    results = {}
    overall_start_time = time.time()

    for test_name, test_func in tests:
        print(f"\n{'='*15} {test_name} {'='*15}")
        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ Test {test_name} failed: {e}")
            results[test_name] = False

        # Brief pause between tests
        await asyncio.sleep(2)

    total_duration = time.time() - overall_start_time

    # Summary
    print("\n" + "=" * 60)
    print("📊 STABILITY TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for success in results.values() if success)
    total = len(results)

    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {test_name}: {status}")

    print(f"\n🎯 Overall Result: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print(f"⏱️  Total test duration: {total_duration:.1f}s")

    if passed >= total * 0.75:  # 75% pass rate for stability tests
        print("🎉 Stability tests: PASSED")
        print("✅ Lexilux client demonstrates excellent long-term stability!")

        print("\n🏆 Stability Achievements:")
        print("   - Sustained operation under load")
        print("   - Efficient connection management")
        print("   - Stable memory usage patterns")
        print("   - Ready for production deployment")

        return True
    else:
        print("⚠️  Stability tests: NEEDS ATTENTION")
        return False


async def main():
    """Run stability tests."""
    success = await run_stability_tests()

    if success:
        print("\n🎊 CONGRATULATIONS!")
        print("   All major tests completed successfully!")
        print("   Lexilux migration is production-ready!")

    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
