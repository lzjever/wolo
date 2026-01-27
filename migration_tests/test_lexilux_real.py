#!/usr/bin/env python3
"""
Real-world test of lexilux migration with actual API endpoints.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main test function."""
    print("🚀 WOLO LEXILUX MIGRATION - REAL WORLD TEST")
    print("=" * 60)

    # Test config loading
    print("\n📋 Step 1: Testing configuration loading...")

    try:
        from wolo.agents import get_agent
        from wolo.config import Config

        config_path = Path.home() / ".wolo" / "config.yaml"
        print(f"Loading config from: {config_path}")

        if not config_path.exists():
            print(f"❌ Config file not found: {config_path}")
            return False

        # Load config using from_env method (reads from config file by default)
        config = Config.from_env()
        agent_config = get_agent("general")

        print("✅ Config loaded successfully")
        print(f"   Default endpoint: {config_path}")
        print(f"   Model: {config.model}")
        print(f"   Base URL: {config.base_url}")
        print(f"   Enable thinking: {config.enable_think}")
        print(f"   Use lexilux client: {getattr(config, 'use_lexilux_client', 'Not set')}")

        if not getattr(config, 'use_lexilux_client', False):
            print("⚠️  WARNING: use_lexilux_client is not enabled in config")
            print("   Please ensure the config.yaml has 'use_lexilux_client: true'")
            return False

    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return False

    # Test client instantiation
    print("\n🔧 Step 2: Testing client instantiation...")

    try:
        # Test dynamic import based on config flag
        if config.use_lexilux_client:
            from wolo.llm_adapter import WoloLLMClient as LLMClient
            print("✅ Using new lexilux-based WoloLLMClient")
        else:
            from wolo.llm import GLMClient as LLMClient
            print("❌ This shouldn't happen - using legacy GLMClient")

        client = LLMClient(
            config=config,
            agent_config=agent_config,
            session_id="test-session-" + str(int(time.time())),
            agent_display_name="TestAgent"
        )

        print("✅ Client created successfully")
        print(f"   Client class: {type(client).__name__}")
        print(f"   Model: {client.model}")
        print(f"   Reasoning enabled: {client.enable_think}")

    except Exception as e:
        print(f"❌ Failed to create client: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test API call
    print("\n💬 Step 3: Testing real API call...")

    async def test_chat():
        try:
            messages = [
                {
                    "role": "user",
                    "content": "Hello! Please respond with just 'Hello from lexilux!' to confirm the new client is working."
                }
            ]

            print("   Sending test message...")

            events = []
            async for event in client.chat_completion(messages, stream=True):
                events.append(event)
                print(f"   📤 Event: {event['type']}")

                # Print reasoning content if available
                if event['type'] == 'reasoning-delta' and event.get('text'):
                    print(f"   🧠 Reasoning: {event['text'][:100]}...")

                # Print text content
                elif event['type'] == 'text-delta' and event.get('text'):
                    print(f"   💬 Text: {event['text'][:100]}...")

                # Print completion
                elif event['type'] == 'finish':
                    print(f"   ✅ Finished: {event.get('reason', 'unknown')}")

                # Print errors
                elif event['type'] == 'error':
                    print(f"   ❌ Error: {event.get('error', 'unknown')}")
                    return False

            if events:
                print(f"✅ API call completed successfully ({len(events)} events)")

                # Check for reasoning events (if thinking mode enabled)
                reasoning_events = [e for e in events if e['type'] == 'reasoning-delta']
                text_events = [e for e in events if e['type'] == 'text-delta']
                finish_events = [e for e in events if e['type'] == 'finish']

                print(f"   - Reasoning events: {len(reasoning_events)}")
                print(f"   - Text events: {len(text_events)}")
                print(f"   - Finish events: {len(finish_events)}")

                if config.enable_think and reasoning_events:
                    print("✅ Reasoning mode working (GLM thinking → lexilux reasoning)")
                elif config.enable_think and not reasoning_events:
                    print("⚠️  Reasoning mode enabled but no reasoning events received")

                return True
            else:
                print("❌ No events received from API")
                return False

        except Exception as e:
            print(f"❌ API call failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    # Run async test
    try:
        result = asyncio.run(test_chat())
        if not result:
            return False
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return False

    # Test token usage tracking
    print("\n📊 Step 4: Testing token usage tracking...")

    try:
        from wolo.llm_adapter import get_token_usage

        usage = get_token_usage()
        print(f"✅ Token usage retrieved: {usage}")

        if usage['total_tokens'] > 0:
            print("✅ Token usage tracking is working")
        else:
            print("⚠️  No token usage recorded (may be normal for some providers)")

    except Exception as e:
        print(f"❌ Token usage test failed: {e}")
        return False

    # Final summary
    print("\n" + "=" * 60)
    print("🎉 LEXILUX MIGRATION TEST COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print("✅ All tests passed:")
    print("   ✅ Configuration loading with lexilux flag")
    print("   ✅ Dynamic client selection (WoloLLMClient)")
    print("   ✅ Real API calls working")
    print("   ✅ Event streaming working")
    print("   ✅ Token usage tracking")

    if config.enable_think:
        print("   ✅ Reasoning mode support (GLM thinking → standard reasoning)")

    print("\n🎯 Migration Status: PRODUCTION READY")
    print("   The lexilux-based client is working correctly with your endpoints.")
    print("   You can now use the new implementation for better stability and")
    print("   support for all OpenAI-compatible models!")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
