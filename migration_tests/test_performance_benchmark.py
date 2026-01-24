#!/usr/bin/env python3
"""
Performance benchmark test comparing old vs new lexilux client.
Tests response time, memory usage, and connection stability.
"""

import asyncio
import logging
import psutil
import statistics
import time
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor performance metrics during tests."""
    
    def __init__(self):
        self.process = psutil.Process()
        self.start_memory = None
        self.peak_memory = 0
        self.start_time = None
    
    def start(self):
        """Start monitoring."""
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.peak_memory = self.start_memory
        self.start_time = time.time()
    
    def update(self):
        """Update peak memory usage."""
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.peak_memory = max(self.peak_memory, current_memory)
    
    def get_stats(self):
        """Get performance statistics."""
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        duration = time.time() - self.start_time if self.start_time else 0
        
        return {
            "duration": duration,
            "start_memory_mb": self.start_memory,
            "current_memory_mb": current_memory,
            "peak_memory_mb": self.peak_memory,
            "memory_delta_mb": current_memory - self.start_memory if self.start_memory else 0
        }


async def test_client_performance(client_type: str, use_lexilux: bool, num_requests: int = 5):
    """Test performance of a specific client type."""
    print(f"\n🚀 Testing {client_type.upper()} Client Performance")
    print("-" * 50)
    
    monitor = PerformanceMonitor()
    monitor.start()
    
    try:
        from wolo.config import Config
        from wolo.agents import get_agent
        
        # Setup config
        config = Config.from_env()
        config.use_lexilux_client = use_lexilux
        agent_config = get_agent("general")
        
        # Import appropriate client
        if use_lexilux:
            from wolo.llm_adapter import WoloLLMClient as LLMClient
            print("✅ Using lexilux-based WoloLLMClient")
        else:
            from wolo.llm import GLMClient as LLMClient
            print("✅ Using legacy GLMClient")
        
        client = LLMClient(
            config=config,
            agent_config=agent_config,
            session_id=f"perf-test-{client_type}-{int(time.time())}",
            agent_display_name=f"PerfTestAgent-{client_type}"
        )
        
        print(f"📊 Running {num_requests} requests for performance testing...")
        
        # Test messages of varying complexity
        test_messages = [
            [{"role": "user", "content": "Hello! Please say 'Hello World' to test basic connectivity."}],
            [{"role": "user", "content": "Count from 1 to 5 in your response."}],
            [{"role": "user", "content": "What is 12 + 34? Please show the calculation step by step."}],
            [{"role": "user", "content": "List 3 colors and briefly describe each one."}],
            [{"role": "user", "content": "Write a short sentence about the weather."}],
        ]
        
        response_times = []
        successful_requests = 0
        total_events = 0
        total_tokens = 0
        
        for i in range(min(num_requests, len(test_messages))):
            messages = test_messages[i]
            
            print(f"   Request {i+1}/{num_requests}: {messages[0]['content'][:50]}...")
            
            start_time = time.time()
            events = []
            
            try:
                async for event in client.chat_completion(messages, stream=True):
                    events.append(event)
                    monitor.update()  # Track memory during streaming
                    
                    if event['type'] == 'error':
                        print(f"     ❌ Error in request {i+1}: {event.get('error')}")
                        break
                
                end_time = time.time()
                request_time = end_time - start_time
                response_times.append(request_time)
                successful_requests += 1
                total_events += len(events)
                
                print(f"     ✅ Completed in {request_time:.2f}s ({len(events)} events)")
                
                # Small delay between requests
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"     ❌ Request {i+1} failed: {e}")
                continue
        
        # Get final performance stats
        perf_stats = monitor.get_stats()
        
        # Calculate statistics
        if response_times:
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            median_response_time = statistics.median(response_times)
            
            # Calculate requests per second
            total_request_time = sum(response_times)
            requests_per_second = successful_requests / total_request_time if total_request_time > 0 else 0
        else:
            avg_response_time = 0
            min_response_time = 0 
            max_response_time = 0
            median_response_time = 0
            requests_per_second = 0
        
        # Get token usage if available
        try:
            if use_lexilux:
                from wolo.llm_adapter import get_token_usage
            else:
                from wolo.llm import get_token_usage
            
            token_usage = get_token_usage()
            total_tokens = token_usage.get('total_tokens', 0)
        except:
            total_tokens = 0
        
        results = {
            "client_type": client_type,
            "successful_requests": successful_requests,
            "total_requests": num_requests,
            "success_rate": successful_requests / num_requests if num_requests > 0 else 0,
            "avg_response_time": avg_response_time,
            "min_response_time": min_response_time,
            "max_response_time": max_response_time,
            "median_response_time": median_response_time,
            "requests_per_second": requests_per_second,
            "total_events": total_events,
            "total_tokens": total_tokens,
            "memory_stats": perf_stats
        }
        
        print(f"\n📊 {client_type.upper()} Performance Results:")
        print(f"   Success rate: {results['success_rate']*100:.1f}% ({successful_requests}/{num_requests})")
        print(f"   Avg response time: {avg_response_time:.2f}s")
        print(f"   Min/Max response time: {min_response_time:.2f}s / {max_response_time:.2f}s") 
        print(f"   Median response time: {median_response_time:.2f}s")
        print(f"   Requests per second: {requests_per_second:.2f}")
        print(f"   Total events: {total_events}")
        print(f"   Total tokens: {total_tokens}")
        print(f"   Memory usage: {perf_stats['memory_delta_mb']:.1f}MB delta (peak: {perf_stats['peak_memory_mb']:.1f}MB)")
        
        return results
        
    except Exception as e:
        print(f"❌ Performance test failed for {client_type}: {e}")
        return None


async def run_benchmark_comparison():
    """Run comparative benchmark between old and new clients."""
    print("⚡ PERFORMANCE BENCHMARK COMPARISON")
    print("=" * 60)
    print("Comparing legacy GLMClient vs lexilux WoloLLMClient...")
    
    # Test parameters
    num_requests = 3  # Keep small for quick testing
    
    # Run tests for both clients
    print("\n🔄 Running performance tests (this may take a few minutes)...")
    
    # Test legacy client
    legacy_results = await test_client_performance("Legacy", use_lexilux=False, num_requests=num_requests)
    
    # Small break between tests
    await asyncio.sleep(2)
    
    # Test new lexilux client  
    lexilux_results = await test_client_performance("Lexilux", use_lexilux=True, num_requests=num_requests)
    
    # Compare results
    if legacy_results and lexilux_results:
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE COMPARISON")
        print("=" * 60)
        
        # Response time comparison
        legacy_avg = legacy_results['avg_response_time']
        lexilux_avg = lexilux_results['avg_response_time']
        
        if lexilux_avg > 0 and legacy_avg > 0:
            time_improvement = ((legacy_avg - lexilux_avg) / legacy_avg) * 100
            time_status = "🚀 FASTER" if time_improvement > 0 else "🐌 SLOWER"
            print(f"Average Response Time:")
            print(f"   Legacy:  {legacy_avg:.2f}s")
            print(f"   Lexilux: {lexilux_avg:.2f}s")
            print(f"   Change:  {time_improvement:+.1f}% {time_status}")
        
        # Success rate comparison
        legacy_success = legacy_results['success_rate'] * 100
        lexilux_success = lexilux_results['success_rate'] * 100
        success_improvement = lexilux_success - legacy_success
        
        print(f"\nSuccess Rate:")
        print(f"   Legacy:  {legacy_success:.1f}%")
        print(f"   Lexilux: {lexilux_success:.1f}%")
        print(f"   Change:  {success_improvement:+.1f}%")
        
        # Memory usage comparison
        legacy_memory = legacy_results['memory_stats']['memory_delta_mb']
        lexilux_memory = lexilux_results['memory_stats']['memory_delta_mb']
        
        print(f"\nMemory Usage Delta:")
        print(f"   Legacy:  {legacy_memory:.1f}MB")
        print(f"   Lexilux: {lexilux_memory:.1f}MB")
        print(f"   Change:  {lexilux_memory - legacy_memory:+.1f}MB")
        
        # Events and tokens comparison
        print(f"\nThroughput:")
        print(f"   Legacy Events:  {legacy_results['total_events']}")
        print(f"   Lexilux Events: {lexilux_results['total_events']}")
        print(f"   Legacy Tokens:  {legacy_results['total_tokens']}")
        print(f"   Lexilux Tokens: {lexilux_results['total_tokens']}")
        
        # Overall assessment
        improvements = []
        if success_improvement >= 0:
            improvements.append("✅ Success rate maintained/improved")
        if time_improvement > -10:  # Within 10% is acceptable
            improvements.append("✅ Response time competitive")
        if lexilux_memory < legacy_memory + 50:  # Within 50MB is acceptable
            improvements.append("✅ Memory usage reasonable")
            
        print(f"\n🎯 Overall Assessment:")
        for improvement in improvements:
            print(f"   {improvement}")
        
        if len(improvements) >= 2:
            print(f"\n🎉 Performance benchmark: PASSED")
            print(f"   Lexilux client performs competitively with legacy client!")
            return True
        else:
            print(f"\n⚠️  Performance benchmark: NEEDS ATTENTION") 
            print(f"   Some metrics show significant regression")
            return False
    else:
        print(f"\n❌ Performance benchmark: FAILED")
        print(f"   Could not complete tests for comparison")
        return False


async def main():
    """Run performance benchmark tests."""
    success = await run_benchmark_comparison()
    
    if success:
        print(f"\n🚀 Next Steps:")
        print(f"   1. ✅ Performance benchmarking completed")
        print(f"   2. 🔄 Ready for error handling tests")
        print(f"   3. 📊 Ready for stability testing")
        print(f"\n   Run: python test_error_handling.py")
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)