#!/usr/bin/env python3
"""
Multi-endpoint testing for lexilux migration.
Tests both GLM and DeepSeek endpoints to ensure compatibility.
"""

import asyncio
import logging
import time
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_endpoint(endpoint_name: str):
    """Test a specific endpoint from config."""
    print(f"\n🔍 Testing endpoint: {endpoint_name}")
    print("-" * 50)
    
    try:
        from wolo.config import Config
        from wolo.agents import get_agent
        
        # Load config for specific endpoint
        import yaml
        config_path = Path.home() / ".wolo" / "config.yaml"
        with open(config_path) as f:
            config_data = yaml.safe_load(f)
        
        # Find endpoint config
        endpoint_config = None
        for ep in config_data.get('endpoints', []):
            if ep.get('name') == endpoint_name:
                endpoint_config = ep
                break
                
        if not endpoint_config:
            print(f"❌ Endpoint '{endpoint_name}' not found in config")
            return False
            
        print(f"✅ Found endpoint config:")
        print(f"   Model: {endpoint_config.get('model')}")
        print(f"   Base URL: {endpoint_config.get('api_base')}")
        print(f"   Thinking enabled: {endpoint_config.get('enable_think', False)}")
        
        # Create config for this endpoint
        config = Config(
            api_key=endpoint_config.get('api_key'),
            model=endpoint_config.get('model'),
            base_url=endpoint_config.get('api_base'),
            temperature=endpoint_config.get('temperature', 0.7),
            max_tokens=endpoint_config.get('max_tokens', 1000),
            enable_think=endpoint_config.get('enable_think', False),
            use_lexilux_client=True,  # Force new client
        )
        
        agent_config = get_agent("general")
        
        # Import new client
        from wolo.llm_adapter import WoloLLMClient
        
        client = WoloLLMClient(
            config=config,
            agent_config=agent_config,
            session_id=f"test-{endpoint_name}-{int(time.time())}",
            agent_display_name=f"TestAgent-{endpoint_name}"
        )
        
        print(f"✅ Client created for {endpoint_name}")
        
        # Test basic chat
        messages = [
            {
                "role": "user",
                "content": f"Hello! This is a test message for {endpoint_name}. Please respond with 'Hello from {endpoint_name}!' to confirm connectivity."
            }
        ]
        
        print("📤 Sending test message...")
        start_time = time.time()
        
        events = []
        text_content = ""
        reasoning_content = ""
        
        async for event in client.chat_completion(messages, stream=True):
            events.append(event)
            
            if event['type'] == 'text-delta':
                text_content += event.get('text', '')
                
            elif event['type'] == 'reasoning-delta':
                reasoning_content += event.get('text', '')
                
            elif event['type'] == 'error':
                print(f"❌ API Error: {event.get('error')}")
                return False
                
        end_time = time.time()
        response_time = end_time - start_time
        
        # Analyze results
        text_events = [e for e in events if e['type'] == 'text-delta']
        reasoning_events = [e for e in events if e['type'] == 'reasoning-delta']
        finish_events = [e for e in events if e['type'] == 'finish']
        
        print(f"✅ {endpoint_name} test completed successfully!")
        print(f"📊 Results:")
        print(f"   Response time: {response_time:.2f}s")
        print(f"   Total events: {len(events)}")
        print(f"   Text events: {len(text_events)}")
        print(f"   Reasoning events: {len(reasoning_events)}")
        print(f"   Finish events: {len(finish_events)}")
        print(f"   Response content: {text_content[:100]}{'...' if len(text_content) > 100 else ''}")
        
        if reasoning_events:
            print(f"   Reasoning content: {reasoning_content[:100]}{'...' if len(reasoning_content) > 100 else ''}")
            
        # Verify expected content
        expected_text = f"Hello from {endpoint_name}"
        if expected_text.lower() in text_content.lower():
            print(f"✅ Response contains expected content")
        else:
            print(f"⚠️  Response doesn't contain expected content '{expected_text}'")
            
        return True
        
    except Exception as e:
        print(f"❌ Test failed for {endpoint_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_all_endpoints():
    """Test all configured endpoints."""
    print("🌐 MULTI-ENDPOINT COMPATIBILITY TEST")
    print("=" * 60)
    print("Testing all configured endpoints with lexilux client...")
    
    # Load endpoint names from config
    try:
        import yaml
        config_path = Path.home() / ".wolo" / "config.yaml"
        with open(config_path) as f:
            config_data = yaml.safe_load(f)
            
        endpoints = [ep.get('name') for ep in config_data.get('endpoints', [])]
        
        if not endpoints:
            print("❌ No endpoints found in config")
            return False
            
        print(f"📋 Found {len(endpoints)} endpoints: {', '.join(endpoints)}")
        
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return False
    
    # Test each endpoint
    results = {}
    for endpoint_name in endpoints:
        results[endpoint_name] = await test_endpoint(endpoint_name)
        
        # Small delay between tests
        await asyncio.sleep(2)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 MULTI-ENDPOINT TEST SUMMARY")
    print("=" * 60)
    
    successful = sum(1 for success in results.values() if success)
    total = len(results)
    
    for endpoint_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {endpoint_name}: {status}")
    
    print(f"\n🎯 Overall Result: {successful}/{total} endpoints successful")
    
    if successful == total:
        print("🎉 All endpoints working perfectly with lexilux!")
        print("✅ Multi-endpoint compatibility verified")
    else:
        print("⚠️  Some endpoints need attention")
        print("   Check API keys, network connectivity, or endpoint configurations")
    
    return successful == total


async def main():
    """Main test function."""
    success = await test_all_endpoints()
    
    if success:
        print(f"\n🚀 Next Steps:")
        print(f"   1. ✅ Multi-endpoint testing completed")
        print(f"   2. 🔄 Ready for tool calling compatibility tests")
        print(f"   3. 📊 Ready for performance benchmarking")
        print(f"\n   Run: python test_tool_calling.py")
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)