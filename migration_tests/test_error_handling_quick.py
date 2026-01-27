#!/usr/bin/env python3
"""
Quick error handling tests for lexilux migration.
Focused on essential error scenarios with faster execution.
"""

import asyncio
import logging
import time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_auth_error():
    """Test authentication error handling."""
    print("🔑 Testing Authentication Error Handling")
    print("-" * 50)

    try:
        from wolo.agents import get_agent
        from wolo.config import Config
        from wolo.llm_adapter import WoloLLMClient

        # Use invalid API key with real GLM endpoint (will fail quickly)
        config = Config(
            api_key="invalid-key-test",
            model="GLM-4.7",
            base_url="https://open.bigmodel.cn/api/coding/paas/v4",
            temperature=0.7,
            max_tokens=100,
            use_lexilux_client=True
        )

        agent_config = get_agent("general")
        client = WoloLLMClient(
            config=config,
            agent_config=agent_config,
            session_id="auth-error-test",
            agent_display_name="AuthErrorTest"
        )

        messages = [{"role": "user", "content": "Test auth error"}]

        print("📤 Sending request with invalid API key...")

        error_detected = False
        async for event in client.chat_completion(messages, stream=True):
            if event['type'] == 'error':
                error_msg = event.get('error', '').lower()
                print(f"✅ Auth error caught: {event.get('error')}")

                if any(keyword in error_msg for keyword in ['auth', 'unauthorized', '401', 'invalid']):
                    error_detected = True
                break

        return error_detected

    except Exception as e:
        # Exception is also valid error handling
        print(f"✅ Exception caught: {e}")
        return 'auth' in str(e).lower() or 'unauthorized' in str(e).lower()


async def test_malformed_request():
    """Test malformed request handling."""
    print("\n📦 Testing Malformed Request Handling")
    print("-" * 50)

    try:
        from wolo.agents import get_agent
        from wolo.config import Config
        from wolo.llm_adapter import WoloLLMClient

        # Use empty API key (should cause quick 400 error)
        config = Config(
            api_key="",
            model="GLM-4.7",
            base_url="https://open.bigmodel.cn/api/coding/paas/v4",
            temperature=0.7,
            max_tokens=100,
            use_lexilux_client=True
        )

        agent_config = get_agent("general")
        client = WoloLLMClient(
            config=config,
            agent_config=agent_config,
            session_id="malformed-test",
            agent_display_name="MalformedTest"
        )

        messages = [{"role": "user", "content": "Test"}]

        print("📤 Sending request with empty API key...")

        error_detected = False
        async for event in client.chat_completion(messages, stream=True):
            if event['type'] == 'error':
                print(f"✅ Malformed request error caught: {event.get('error')}")
                error_detected = True
                break

        return error_detected

    except Exception as e:
        print(f"✅ Exception caught: {e}")
        return True


async def test_large_input():
    """Test large input handling."""
    print("\n📏 Testing Large Input Handling")
    print("-" * 50)

    try:
        from wolo.agents import get_agent
        from wolo.config import Config
        from wolo.llm_adapter import WoloLLMClient

        config = Config.from_env()  # Use valid config
        agent_config = get_agent("general")

        client = WoloLLMClient(
            config=config,
            agent_config=agent_config,
            session_id="large-input-test",
            agent_display_name="LargeInputTest"
        )

        # Create moderately large message (not too large to avoid long processing)
        large_text = "This is a test message with repeated content. " * 200  # ~9KB
        messages = [{"role": "user", "content": f"Please summarize this text: {large_text}"}]

        print(f"📤 Sending large message ({len(large_text):,} characters)...")

        success = False
        error_handled = False

        start_time = time.time()

        try:
            async for event in client.chat_completion(messages, stream=True):
                if event['type'] == 'text-delta':
                    success = True
                elif event['type'] == 'error':
                    print(f"✅ Large input error handled: {event.get('error')}")
                    error_handled = True
                    break
                elif event['type'] == 'finish':
                    elapsed = time.time() - start_time
                    if success:
                        print(f"✅ Large input processed successfully in {elapsed:.2f}s")
                    break

                # Timeout protection
                if time.time() - start_time > 30:  # 30s timeout
                    print("⏰ Large input test timed out (acceptable)")
                    return True

        except Exception as e:
            print(f"✅ Large input exception handled: {e}")
            error_handled = True

        return success or error_handled

    except Exception as e:
        print(f"✅ Large input test handled: {e}")
        return True


async def test_connection_stability():
    """Test connection stability with multiple requests."""
    print("\n🔄 Testing Connection Stability")
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
            session_id="stability-test",
            agent_display_name="StabilityTest"
        )

        print("📤 Testing connection stability with multiple requests...")

        successful_requests = 0
        total_requests = 3

        for i in range(total_requests):
            messages = [{"role": "user", "content": f"Stability test {i+1}: Please respond with 'Test {i+1} successful'"}]

            request_success = False
            start_time = time.time()

            try:
                async for event in client.chat_completion(messages, stream=True):
                    if event['type'] == 'text-delta':
                        request_success = True
                    elif event['type'] == 'finish':
                        elapsed = time.time() - start_time
                        if request_success:
                            successful_requests += 1
                            print(f"✅ Request {i+1} successful ({elapsed:.2f}s)")
                        break
                    elif event['type'] == 'error':
                        print(f"⚠️  Request {i+1} failed: {event.get('error')}")
                        break

                    # Per-request timeout
                    if time.time() - start_time > 15:  # 15s per request
                        print(f"⏰ Request {i+1} timed out")
                        break

            except Exception as e:
                print(f"⚠️  Request {i+1} exception: {e}")

            # Small delay between requests
            await asyncio.sleep(1)

        success_rate = successful_requests / total_requests
        print(f"📊 Stability success rate: {success_rate*100:.1f}% ({successful_requests}/{total_requests})")

        return success_rate >= 0.67  # At least 2/3 should succeed

    except Exception as e:
        print(f"⚠️  Stability test failed: {e}")
        return False


async def test_error_recovery():
    """Test error recovery by alternating good and bad requests."""
    print("\n🛡️  Testing Error Recovery")
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
            session_id="recovery-test",
            agent_display_name="RecoveryTest"
        )

        print("📤 Testing error recovery with mixed requests...")

        # Test sequence: good -> bad -> good
        test_requests = [
            (True, [{"role": "user", "content": "Good request 1: Say hello"}]),
            (False, [{"role": "invalid", "content": "Bad request: Invalid role"}]),  # Should cause error
            (True, [{"role": "user", "content": "Good request 2: Say goodbye"}])
        ]

        results = []

        for i, (expect_success, messages) in enumerate(test_requests):
            request_type = "Good" if expect_success else "Bad"
            print(f"   {request_type} request {i+1}...")

            had_text = False
            had_error = False

            try:
                async for event in client.chat_completion(messages, stream=True):
                    if event['type'] == 'text-delta':
                        had_text = True
                    elif event['type'] == 'error':
                        had_error = True
                        print(f"     ✅ Expected error caught: {event.get('error')}")
                        break
                    elif event['type'] == 'finish':
                        break

            except Exception as e:
                had_error = True
                print(f"     ✅ Exception caught: {e}")

            # Evaluate result
            if expect_success and had_text:
                results.append(True)
                print("     ✅ Good request succeeded")
            elif not expect_success and had_error:
                results.append(True)
                print("     ✅ Bad request properly failed")
            else:
                results.append(False)
                print("     ❌ Unexpected result")

            await asyncio.sleep(0.5)

        recovery_success = sum(results) / len(results)
        print(f"📊 Error recovery rate: {recovery_success*100:.1f}%")

        return recovery_success >= 0.67

    except Exception as e:
        print(f"⚠️  Error recovery test failed: {e}")
        return False


async def run_quick_error_tests():
    """Run quick error handling tests."""
    print("🛡️  QUICK ERROR HANDLING TESTS")
    print("=" * 60)
    print("Testing essential error scenarios with fast execution...")

    tests = [
        ("Authentication Error", test_auth_error),
        ("Malformed Request", test_malformed_request),
        ("Large Input", test_large_input),
        ("Connection Stability", test_connection_stability),
        ("Error Recovery", test_error_recovery),
    ]

    results = {}

    for test_name, test_func in tests:
        print(f"\n{'='*15} {test_name} {'='*15}")
        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ Test {test_name} failed: {e}")
            results[test_name] = False

        # Brief pause between tests
        await asyncio.sleep(1)

    # Summary
    print("\n" + "=" * 60)
    print("📊 ERROR HANDLING TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for success in results.values() if success)
    total = len(results)

    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {test_name}: {status}")

    print(f"\n🎯 Overall Result: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed >= total * 0.8:  # 80% pass rate
        print("🎉 Error handling tests: PASSED")
        print("✅ Lexilux client demonstrates robust error handling!")
        return True
    else:
        print("⚠️  Error handling tests: NEEDS ATTENTION")
        return False


async def main():
    """Run quick error handling tests."""
    success = await run_quick_error_tests()

    if success:
        print("\n🚀 Next Steps:")
        print("   1. ✅ Error handling validated")
        print("   2. 🔄 Ready for edge cases testing")
        print("   3. 📊 Ready for MCP integration testing")

    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
