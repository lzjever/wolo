# Wolo → Lexilux 迁移技术方案

**项目**: 使用 lexilux 替换 wolo 自有 LLM 通讯实现
**日期**: 2026-01-24
**状态**: 详细实施方案
**目标**: 将 wolo/llm.py (565行) 替换为基于 lexilux 的通用 OpenAI 兼容适配层 (~200行)
**重要**: 去除所有 GLM 特定概念，支持所有 OpenAI 兼容模型服务

---

## 📢 重要说明：去除 GLM 特定概念

本次迁移的一个重要目标是**去除所有 GLM 特定概念**，使 wolo 真正成为支持所有 OpenAI 兼容模型的通用 AI 代理框架。

### 概念重构

| 旧概念 | 新概念 | 说明 |
|--------|--------|------|
| `GLMClient` | `WoloLLMClient` | 通用 LLM 客户端，支持所有 OpenAI 兼容模型 |
| GLM thinking mode | LLM reasoning mode | 支持推理模型 (OpenAI o1, DeepSeek R1, 等) |
| GLM 特定参数 | OpenAI 标准参数 | 使用标准 `top_p`, `max_tokens` 等 |
| GLM API | OpenAI 兼容 API | 支持任何 OpenAI 格式的模型服务 |

### 向后兼容性

为保持现有代码兼容，我们将：
- 在 `agent.py` 中保持 `GLMClient` 别名 → `WoloLLMClient`
- 配置和接口保持不变
- 逐步在文档中推广正确的通用概念

### 支持的模型服务

迁移后，wolo 将明确支持所有 OpenAI 兼容的模型服务：
- ✅ **OpenAI** (GPT-4, GPT-3.5, o1)
- ✅ **Anthropic** (Claude 3.5 Sonnet, Haiku)
- ✅ **DeepSeek** (DeepSeek-V2, DeepSeek-R1)
- ✅ **Zhipu** (GLM-4, ChatGLM)
- ✅ **任何其他 OpenAI 兼容服务**

---

## 一、现状分析

### 1.1 Wolo 当前 LLM 实现 (wolo/llm.py)

**核心功能**:
- `GLMClient` 类：565行自定义实现 (历史命名，实际支持所有 OpenAI 兼容模型)
- aiohttp 连接池管理 (66-134行)
- 自定义 SSE 解析 (336-473行) 
- 重试机制和错误处理 (154-186行)
- 工具调用 buffer 管理 (504-547行)
- opencode-style headers 构建 (198-206行)
- LLM reasoning mode 支持 (492-496行) - 支持推理模型
- 双层调试日志系统 (275-324行)

**事件格式**:
```python
{"type": "reasoning-delta", "text": "thinking content"}
{"type": "text-delta", "text": "response content"}  
{"type": "tool-call", "tool": "name", "input": {...}, "id": "id"}
{"type": "finish", "reason": "stop"}
```

**关键配置参数**:
```python
# wolo/llm.py:254-258 - 历史遗留的非标准参数
payload = {
    "topP": 0.9,              # ❌ 非标准参数 (应为 top_p)
    "topK": 40,               # ❌ 非标准参数 (非 OpenAI 标准)  
    "maxOutputTokens": ...,   # ❌ 非标准参数 (应为 max_tokens)
    "thinking": {...}         # ✅ 推理模式支持 (部分模型)
}
```

### 1.2 Lexilux 已实现的功能

**P0 功能** (✅ 已完成):
- `reasoning_content` 字段支持 (OpenAI o1/Claude 3.5/DeepSeek R1)
- 参数别名映射机制 (`param_aliases`)
- 完善的 `extra` 字段支持

**标准功能**:
- httpx HTTP 客户端 + 连接池
- 专用 SSE 解析器 (`SSEChatStreamParser`)
- 统一异常体系 (10+ 专用异常类)
- 重试机制 (`max_retries` 配置)
- 工具调用处理

---

## 二、迁移架构设计

### 2.1 分层架构

```
┌─────────────────────────────────────────┐
│     wolo/wolo/agent.py                  │ <- 无需修改
├─────────────────────────────────────────┤
│  wolo/wolo/llm_adapter.py (NEW)         │ <- 新建通用 LLM 适配层
│  - WoloLLMClient (~200 lines)          │
│  - 事件格式转换 (lexilux → wolo)       │
│  - opencode headers 构建               │
│  - 调试日志保留                        │
│  - OpenAI 标准参数处理                 │
├─────────────────────────────────────────┤
│  lexilux.chat.Chat                     │ <- 通用 OpenAI 兼容客户端
│  - HTTP 客户端 (httpx)                 │
│  - SSE 解析                           │
│  - 重试机制                           │
│  - 错误处理                           │
│  - reasoning_content 解析              │
└─────────────────────────────────────────┘
```

### 2.2 迁移策略

**阶段 1**: 创建适配层 (保留旧实现)
**阶段 2**: 功能开关测试
**阶段 3**: 逐步切换和验证  
**阶段 4**: 移除旧实现

---

## 三、详细实施计划

### Phase 1: 创建 Lexilux 适配层 (2-3 天)

#### Step 1.1: 创建适配层文件

**文件**: `wolo/wolo/llm_adapter.py` (新建)

```python
"""
Wolo LLM Client Adapter using lexilux.

This adapter provides wolo-specific functionality while leveraging
lexilux's standard OpenAI-compatible client for HTTP/SSE/error handling.

Supports all OpenAI-compatible model services (OpenAI, Anthropic, DeepSeek, etc.)
"""

import json
import logging
import os
import platform
import time
from typing import Any, AsyncIterator

from lexilux.chat import Chat
from lexilux.chat.params import ChatParams
from lexilux.usage import Usage

from wolo.config import Config
from wolo.agents import AgentConfig
from wolo.events import bus

logger = logging.getLogger(__name__)

class WoloLLMClient:
    """
    Wolo LLM client adapter using lexilux.
    
    支持所有 OpenAI 兼容的模型服务 (OpenAI, Anthropic, DeepSeek, 等)
    
    职责：
    1. 使用 lexilux 作为底层 HTTP/SSE 客户端
    2. 转换 lexilux 事件格式为 wolo 事件格式
    3. 构建 opencode-style headers
    4. 保留产品级调试日志
    5. 处理推理模型的 reasoning 模式
    """
    
    def __init__(
        self,
        config: Config,
        agent_config: AgentConfig | None = None,
        session_id: str | None = None,
        agent_display_name: str | None = None,
    ):
        """初始化 Wolo LLM 适配器 (支持所有 OpenAI 兼容模型)."""
        # 构建 opencode headers
        headers = self._build_opencode_headers(session_id, agent_display_name)
        
        # ✅ 使用标准 OpenAI 参数 (修正历史遗留的非标准参数)
        params = ChatParams(
            temperature=config.temperature or 0.7,
            max_tokens=config.max_tokens,
            # ✅ 推理模式通过 extra 字段 (支持推理模型如 DeepSeek-R1)
            extra={
                "thinking": {
                    "type": "enabled",
                    "clear_thinking": False
                }
            } if config.enable_think else None
        )
        
        # 初始化 lexilux Chat 客户端
        self._lexilux_chat = Chat(
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            headers=headers,
        )
        
        # 存储默认参数
        self._default_params = params
        
        # Wolo 产品配置
        self._enable_think = config.enable_think
        self._debug_llm_file = config.debug_llm_file
        self._debug_full_dir = config.debug_full_dir
        self._request_count = 0
        self._finish_reason = None
        self._agent_display_name = agent_display_name
        self._session_id = session_id or "unknown"
    
    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        主要聊天完成方法 - 转换 lexilux 事件为 wolo 格式.
        
        Returns wolo 事件格式:
        - {"type": "reasoning-delta", "text": "..."}
        - {"type": "text-delta", "text": "..."}
        - {"type": "tool-call", "tool": "name", "input": {...}, "id": "..."}
        - {"type": "finish", "reason": "stop"}
        """
        # 1. 产品级调试日志
        self._log_request(messages)
        
        # 2. 格式转换
        lexilux_messages = self._to_lexilux_messages(messages)
        lexilux_tools = self._convert_tools(tools)
        
        try:
            # 3. ✅ 调用 lexilux 并启用 reasoning 解析
            lexilux_stream = self._lexilux_chat.astream(
                messages=lexilux_messages,
                tools=lexilux_tools,
                params=self._default_params,
                include_reasoning=self._enable_think,  # ✅ 使用 lexilux reasoning 功能
            )
            
            # 4. 事件格式转换：lexilux → wolo
            async for lexilux_chunk in lexilux_stream:
                # ✅ Reasoning content (推理模型支持)
                if lexilux_chunk.reasoning_content:
                    yield {
                        "type": "reasoning-delta", 
                        "text": lexilux_chunk.reasoning_content
                    }
                
                # 标准文本内容
                if lexilux_chunk.delta:
                    yield {
                        "type": "text-delta",
                        "text": lexilux_chunk.delta
                    }
                
                # 工具调用
                if lexilux_chunk.tool_calls:
                    for tc in lexilux_chunk.tool_calls:
                        yield {
                            "type": "tool-call",
                            "tool": tc.name,
                            "input": tc.get_arguments(),
                            "id": tc.id,
                        }
                
                # 完成
                if lexilux_chunk.done:
                    self._finish_reason = lexilux_chunk.finish_reason
                    yield {
                        "type": "finish", 
                        "reason": lexilux_chunk.finish_reason
                    }
        
        except Exception as e:
            # 转换异常为 wolo 格式
            logger.error(f"Chat completion failed: {e}")
            yield {
                "type": "error",
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    def _build_opencode_headers(
        self, 
        session_id: str | None, 
        agent_display_name: str | None
    ) -> dict[str, str]:
        """构建 opencode-style headers (wolo 产品特性)."""
        try:
            project_id = os.path.basename(os.getcwd())
        except OSError:
            project_id = "unknown"
        
        return {
            "User-Agent": f"opencode/1.0.0 ({platform.system()} {platform.release()}; {platform.machine()})",
            "x-opencode-project": project_id,
            "x-opencode-session": session_id or "unknown",
            "x-opencode-request": "user",
            "x-opencode-client": "cli",
        }
    
    def _log_request(self, messages: list[dict]) -> None:
        """Wolo 产品特定的调试日志."""
        if not self._debug_llm_file and not self._debug_full_dir:
            return
        
        self._request_count += 1
        
        try:
            # 增量调试日志
            if self._debug_llm_file:
                with open(self._debug_llm_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n{'=' * 60}\n")
                    f.write(f"[{time.strftime('%H:%M:%S')}] Request #{self._request_count}\n")
                    f.write(f"Model: {self._lexilux_chat.model}\n")
                    
                    # 显示最后一个用户消息以提供上下文
                    for msg in reversed(messages):
                        if msg.get("role") == "user":
                            content = str(msg.get("content", ""))[:100]
                            f.write(f"User: {content}{'...' if len(str(msg.get('content', ''))) > 100 else ''}\n")
                            break
                    f.write(f"{'=' * 60}\n")
                    f.flush()
            
            # 完整调试日志  
            if self._debug_full_dir:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                full_debug_file = os.path.join(self._debug_full_dir, f"req_{timestamp}.json")
                with open(full_debug_file, 'w', encoding='utf-8') as f:
                    f.write("---INPUT---\n")
                    f.write(json.dumps({
                        "model": self._lexilux_chat.model,
                        "messages": messages,
                        "timestamp": timestamp,
                    }, indent=2, ensure_ascii=False))
                    f.write("\n---OUTPUT---\n")
                    f.flush()
        
        except Exception as e:
            logger.error(f"Failed to write debug logs: {e}")
    
    def _to_lexilux_messages(self, messages: list[dict]) -> list[dict]:
        """转换 wolo 消息格式为 lexilux 格式."""
        formatted_messages = []
        
        for msg in messages:
            # 工具消息和带工具调用的消息保持原样
            if msg.get("role") == "tool" or "tool_calls" in msg:
                formatted_messages.append(msg)
            else:
                # 用户/助手/系统消息确保内容为字符串
                content = msg.get("content", "")
                if isinstance(content, list):
                    # 处理多模态内容
                    text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
                    content = "\n".join(text_parts)
                
                formatted_messages.append({
                    "role": msg.get("role", "user"), 
                    "content": content
                })
        
        return formatted_messages
    
    def _convert_tools(self, tools: list[dict] | None) -> list[dict] | None:
        """转换 wolo 工具格式为 lexilux 格式."""
        if not tools:
            return None
        # 通常格式兼容，直接返回
        return tools
    
    @property
    def finish_reason(self) -> str | None:
        """获取最后完成的原因."""
        return self._finish_reason


# ✅ 保持与原 GLMClient 兼容的函数
def get_token_usage() -> dict[str, int]:
    """Get token usage (compatibility function)."""
    # TODO: 从 lexilux Usage 获取 token 统计
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

def reset_token_usage() -> None:
    """Reset token usage (compatibility function)."""
    pass
```

#### Step 1.2: 修改 agent.py 导入

**文件**: `wolo/wolo/agent.py`

```python
# 第 13 行，修改导入 (重要：保持 GLMClient 别名以维持向后兼容)
# OLD:
from wolo.llm import GLMClient, get_token_usage, reset_token_usage

# NEW:
from wolo.llm_adapter import WoloLLMClient as GLMClient, get_token_usage, reset_token_usage
```

#### Step 1.3: 添加功能开关

**文件**: `wolo/wolo/config.py`

```python
@dataclass  
class Config:
    # ... 现有字段 ...
    
    # ✅ 新增：lexilux 迁移开关
    use_lexilux_client: bool = False  # 默认 False 使用旧实现
```

**文件**: `wolo/wolo/agent.py` (第 364 行附近)

```python
# OLD:
client = GLMClient(config, agent_config, session_id, agent_display_name=agent_display_name)

# NEW:
if config.use_lexilux_client:
    from wolo.llm_adapter import WoloLLMClient
    client = WoloLLMClient(config, agent_config, session_id, agent_display_name=agent_display_name)
else:
    from wolo.llm import GLMClient  # 保持历史兼容性
    client = GLMClient(config, agent_config, session_id, agent_display_name=agent_display_name)
```

---

### Phase 2: 测试和验证 (2-3 天)

#### Step 2.1: 创建单元测试

**文件**: `wolo/wolo/tests/test_llm_adapter.py` (新建)

```python
"""Tests for lexilux adapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from wolo.config import Config
from wolo.llm_adapter import WoloLLMClient


@pytest.fixture
def mock_config():
    """Create mock config."""
    config = MagicMock(spec=Config)
    config.base_url = "https://api.test.com/v1"
    config.api_key = "test-key"
    config.model = "test-model"  # 可以是任何 OpenAI 兼容模型
    config.temperature = 0.7
    config.max_tokens = 1000
    config.enable_think = True  # 推理模式
    config.debug_llm_file = None
    config.debug_full_dir = None
    return config


@pytest.mark.asyncio
async def test_wolo_llm_client_initialization(mock_config):
    """Test WoloLLMClient initialization."""
    client = WoloLLMClient(
        config=mock_config,
        session_id="test-session",
        agent_display_name="TestAgent"
    )
    
    assert client._enable_think is True
    assert client._session_id == "test-session"


@pytest.mark.asyncio  
async def test_opencode_headers_building(mock_config):
    """Test opencode headers construction."""
    client = WoloLLMClient(config=mock_config, session_id="test-session")
    
    headers = client._build_opencode_headers("test-session", "TestAgent")
    
    assert "x-opencode-session" in headers
    assert headers["x-opencode-session"] == "test-session"
    assert "x-opencode-client" in headers
    assert headers["x-opencode-client"] == "cli"


@pytest.mark.asyncio
async def test_message_format_conversion(mock_config):
    """Test wolo → lexilux message format conversion.""" 
    client = WoloLLMClient(config=mock_config)
    
    wolo_messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": ["text part"]},
    ]
    
    lexilux_messages = client._to_lexilux_messages(wolo_messages)
    
    assert len(lexilux_messages) == 2
    assert lexilux_messages[0]["role"] == "user"
    assert lexilux_messages[0]["content"] == "Hello"
```

#### Step 2.2: 集成测试

**文件**: `wolo/wolo/tests/test_integration_lexilux.py` (新建)

```python
"""Integration tests for lexilux adapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from wolo.config import Config  
from wolo.llm_adapter import WoloLLMClient


@pytest.mark.asyncio
async def test_event_format_conversion():
    """Test lexilux → wolo event format conversion."""
    # 模拟 lexilux 的 ChatStreamChunk
    lexilux_chunk = MagicMock()
    lexilux_chunk.reasoning_content = "thinking..."
    lexilux_chunk.delta = "response text"
    lexilux_chunk.tool_calls = []
    lexilux_chunk.done = False
    
    # 验证事件转换逻辑
    # (实际测试需要 mock lexilux.chat.Chat.astream)
    pass


@pytest.mark.asyncio
async def test_debugging_logs():
    """Test debugging log functionality.""" 
    import tempfile
    import os
    
    config = MagicMock(spec=Config)
    config.debug_llm_file = tempfile.mktemp()
    config.debug_full_dir = tempfile.mkdtemp()
    # ... other config setup
    
    client = WoloLLMClient(config=config)
    
    messages = [{"role": "user", "content": "test message"}]
    client._log_request(messages)
    
    # 验证调试文件被创建
    assert os.path.exists(config.debug_llm_file)
    
    # 清理
    os.unlink(config.debug_llm_file)
    os.rmdir(config.debug_full_dir)
```

#### Step 2.3: 端到端测试

**文件**: `wolo/wolo/tests/test_e2e_lexilux.py` (新建)

```python
"""End-to-end tests with lexilux adapter."""

import pytest
import asyncio
from unittest.mock import patch

from wolo.config import Config
from wolo.agent import agent_loop
from wolo.agents import AgentConfig


@pytest.mark.asyncio 
@patch('wolo.llm_adapter.Chat')  # Mock lexilux Chat
async def test_agent_loop_with_lexilux(mock_chat):
    """Test complete agent loop with lexilux adapter."""
    
    # 配置使用 lexilux
    config = Config(
        api_key="test-key",
        base_url="https://api.test.com/v1", 
        model="test-model",
        temperature=0.7,
        max_tokens=1000,
        use_lexilux_client=True,  # ✅ 启用 lexilux
        enable_think=True
    )
    
    agent_config = AgentConfig(
        name="test-agent",
        system_prompt="You are a test agent"
    )
    
    # Mock lexilux 响应
    mock_stream = AsyncMock()
    mock_stream.__aiter__ = AsyncMock(return_value=iter([
        # 模拟 lexilux ChatStreamChunk 对象
        # ...
    ]))
    mock_chat.return_value.astream.return_value = mock_stream
    
    # 测试 agent loop
    result = await agent_loop(
        config=config,
        session_id="test-session", 
        agent_config=agent_config,
        max_steps=2,
        initial_message="Hello, test the lexilux integration"
    )
    
    # 验证结果
    assert result is not None
    # 验证 lexilux Chat 被正确调用
    mock_chat.assert_called_once()
```

---

### Phase 3: 逐步切换和优化 (3-4 天)

#### Step 3.1: 添加性能监控

**文件**: `wolo/wolo/llm_adapter.py`

```python
# 在 WoloGLMClient 中添加性能监控

import time
from wolo.metrics import MetricsCollector

class WoloGLMClient:
    def __init__(self, ...):
        # ... 现有代码 ...
        self._metrics = MetricsCollector()
    
    async def chat_completion(self, ...):
        start_time = time.time()
        
        try:
            # ... 现有逻辑 ...
            async for event in lexilux_stream:
                # ... event processing ...
                yield event
        finally:
            # 记录性能指标
            duration = time.time() - start_time
            self._metrics.record_llm_call(duration, len(messages))
```

#### Step 3.2: 错误处理增强

**文件**: `wolo/wolo/llm_adapter.py`

```python
from lexilux.exceptions import (
    AuthenticationError,
    RateLimitError,
    TimeoutError as LexiluxTimeoutError,
    APIError
)
from wolo.errors import WoloAPIError

class WoloGLMClient:
    async def chat_completion(self, ...):
        try:
            # ... lexilux 调用 ...
        except AuthenticationError as e:
            raise WoloAPIError(f"Authentication failed: {e}", 401)
        except RateLimitError as e:
            raise WoloAPIError(f"Rate limit exceeded: {e}", 429)  
        except LexiluxTimeoutError as e:
            raise WoloAPIError(f"Request timeout: {e}", 408)
        except APIError as e:
            raise WoloAPIError(f"API error: {e}", getattr(e, 'status_code', 500))
        except Exception as e:
            raise WoloAPIError(f"Unexpected error: {e}", 500)
```

#### Step 3.3: Token 使用统计

**文件**: `wolo/wolo/llm_adapter.py`

```python
# 全局 token 使用跟踪（与原实现兼容）
_api_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

class WoloGLMClient:
    async def chat_completion(self, ...):
        global _api_token_usage
        
        async for lexilux_chunk in lexilux_stream:
            # 提取 token 使用信息
            if lexilux_chunk.usage:
                _api_token_usage.update({
                    "prompt_tokens": lexilux_chunk.usage.input_tokens or 0,
                    "completion_tokens": lexilux_chunk.usage.output_tokens or 0, 
                    "total_tokens": lexilux_chunk.usage.total_tokens or 0,
                })
            
            # ... 事件处理 ...

def get_token_usage() -> dict[str, int]:
    """Get token usage from last API call."""
    return _api_token_usage.copy()

def reset_token_usage() -> None:
    """Reset token usage tracking."""
    global _api_token_usage
    _api_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
```

---

### Phase 4: 部署和清理 (1-2 天)

#### Step 4.1: 配置默认切换

**文件**: `wolo/wolo/config.py`

```python
@dataclass
class Config:
    # ... 现有字段 ...
    
    # ✅ 修改：默认启用 lexilux
    use_lexilux_client: bool = True  # 改为 True
```

#### Step 4.2: 添加弃用警告

**文件**: `wolo/wolo/llm.py`

```python
"""GLM API client for Wolo - DEPRECATED."""

import warnings

# 在文件顶部添加弃用警告
warnings.warn(
    "wolo.llm.GLMClient is deprecated and will be removed in v2.0. "
    "The new lexilux-based implementation is now used by default. "
    "Set use_lexilux_client=False in config to use the legacy client.",
    DeprecationWarning,
    stacklevel=2
)

# ... 现有代码 ...
```

#### Step 4.3: 更新文档

**文件**: `wolo/AGENTS.md`

```markdown
# LLM 客户端迁移

Wolo 现在使用 [lexilux](https://github.com/lexilux/lexilux) 作为底层 LLM 客户端。

## 新功能

- ✅ 支持推理模型 (OpenAI o1, Claude 3.5, DeepSeek R1)
- ✅ 更稳定的 HTTP 连接池 (httpx)
- ✅ 统一的错误处理
- ✅ 更快的 SSE 解析

## 配置

默认启用 lexilux 客户端。如需使用旧客户端：

```yaml
# ~/.wolo/config.yaml
use_lexilux_client: false  # 使用旧实现
```

## 迁移指南

所有现有功能保持兼容：
- opencode-style headers ✅
- GLM thinking mode ✅  
- 调试日志 ✅
- 工具调用 ✅
```

#### Step 4.4: 性能基准对比

**文件**: `wolo/wolo/tests/benchmark_lexilux.py` (新建)

```python
"""Benchmark lexilux vs original implementation."""

import asyncio
import time
from unittest.mock import MagicMock

from wolo.config import Config
from wolo.llm import GLMClient as OriginalLLMClient
from wolo.llm_adapter import WoloLLMClient as LexiluxLLMClient


async def benchmark_implementation(client_class, config, messages, iterations=10):
    """Benchmark a client implementation."""
    times = []
    
    for _ in range(iterations):
        client = client_class(config)
        start_time = time.time()
        
        try:
            # Mock the actual API call
            events = []
            async for event in client.chat_completion(messages):
                events.append(event)
                if event.get("type") == "finish":
                    break
        except Exception:
            pass  # Ignore errors for benchmark
        
        end_time = time.time()
        times.append(end_time - start_time)
    
    return {
        "avg_time": sum(times) / len(times),
        "min_time": min(times),
        "max_time": max(times)
    }


async def main():
    """Run benchmark comparison."""
    config = MagicMock(spec=Config)
    # ... setup config ...
    
    messages = [{"role": "user", "content": "Hello, world!"}]
    
    print("Benchmarking original implementation...")
    original_results = await benchmark_implementation(
        OriginalLLMClient, config, messages
    )
    
    print("Benchmarking lexilux implementation...")
    lexilux_results = await benchmark_implementation(
        LexiluxLLMClient, config, messages
    )
    
    print("\nResults:")
    print(f"Original: {original_results}")
    print(f"Lexilux: {lexilux_results}")
    
    improvement = (original_results["avg_time"] - lexilux_results["avg_time"]) / original_results["avg_time"]
    print(f"Performance change: {improvement:.2%}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 四、验收标准

### 4.1 功能性要求

- ✅ **事件兼容性**: 所有现有事件格式 (reasoning-delta, text-delta, tool-call, finish) 正常工作
- ✅ **调试功能**: debug_llm_file 和 debug_full_dir 保持相同行为
- ✅ **opencode headers**: x-opencode-* headers 正确构建和发送
- ✅ **推理模式**: enable_think 配置正确启用推理模型的 reasoning 功能
- ✅ **工具调用**: 工具调用检测和执行保持不变
- ✅ **错误处理**: 错误分类和重试逻辑保持一致

### 4.2 性能要求

- ✅ **响应时间**: 不超过原实现 110%
- ✅ **内存使用**: 不超过原实现 120%  
- ✅ **连接稳定性**: 长时间运行无连接泄漏

### 4.3 质量要求

- ✅ **测试覆盖**: 新适配层测试覆盖率 > 80%
- ✅ **错误率**: 线上错误率不增加
- ✅ **监控兼容**: 现有监控和指标保持正常

---

## 五、风险与缓解

### 5.1 主要风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| **事件格式不兼容** | 中 | 高 | 详细测试事件转换逻辑 |
| **性能回退** | 低 | 中 | 基准测试和性能监控 |
| **调试功能丢失** | 低 | 高 | 完整保留调试逻辑在适配层 |
| **工具调用问题** | 中 | 高 | E2E 测试覆盖所有工具类型 |

### 5.2 回滚计划

```python
# 快速回滚：修改配置
Config.use_lexilux_client = False  # 立即回到旧实现

# 或环境变量
export WOLO_USE_LEXILUX_CLIENT=false
```

---

## 六、时间表

| 阶段 | 任务 | 预计时间 | 负责人 |
|------|------|----------|--------|
| **Phase 1** | 创建适配层 + 功能开关 | 2-3 天 | 开发者 |
| **Phase 2** | 测试和验证 | 2-3 天 | 开发者 + QA |
| **Phase 3** | 逐步切换和优化 | 3-4 天 | 开发者 |
| **Phase 4** | 部署和清理 | 1-2 天 | 开发者 + 运维 |
| **总计** | | **8-12 天** | |

---

## 七、检查清单

### 开发阶段
- [ ] 创建 `wolo/wolo/llm_adapter.py`
- [ ] 实现 `WoloLLMClient` 类 (支持所有 OpenAI 兼容模型)
- [ ] 实现事件格式转换 (lexilux → wolo)
- [ ] 实现 opencode headers 构建
- [ ] 保留调试日志功能
- [ ] 添加功能开关到 `config.py`
- [ ] 修改 `agent.py` 支持两种实现

### 测试阶段
- [ ] 创建单元测试 `test_llm_adapter.py`
- [ ] 创建集成测试 `test_integration_lexilux.py` 
- [ ] 创建 E2E 测试 `test_e2e_lexilux.py`
- [ ] 运行性能基准测试
- [ ] 验证所有现有测试通过

### 部署阶段
- [ ] 修改默认配置启用 lexilux
- [ ] 添加弃用警告到旧实现
- [ ] 更新文档 `AGENTS.md`
- [ ] 监控线上指标
- [ ] 收集用户反馈

### 清理阶段 (1-2 个版本后)
- [ ] 移除 `use_lexilux_client` 功能开关
- [ ] 删除 `wolo/llm.py` 旧实现
- [ ] 清理相关测试和文档

---

## 附录：命名规范重构

### A.1 类名和文件重构

| 组件 | 旧名称 | 新名称 | 重构原因 |
|------|--------|--------|----------|
| **主客户端类** | `GLMClient` | `WoloLLMClient` | 去除特定模型绑定，支持所有 OpenAI 兼容模型 |
| **文件命名** | `glm_*.py` | `llm_*.py` | 使用通用 LLM 概念 |
| **配置字段** | `glm_*` | `llm_*` | 统一配置命名 |
| **日志消息** | "GLM API error" | "LLM API error" | 通用错误消息 |

### A.2 向后兼容策略

```python
# wolo/wolo/agent.py - 保持兼容性
from wolo.llm_adapter import WoloLLMClient as GLMClient  # 别名保持兼容

# 长期目标 (v2.0)：完全移除 GLM 概念
# from wolo.llm_adapter import WoloLLMClient
```

### A.3 文档更新优先级

| 优先级 | 更新内容 | 时间 |
|--------|----------|------|
| **P0** | 代码注释和类文档 | Phase 1 |
| **P1** | README 和 AGENTS.md | Phase 4 |
| **P2** | 示例代码和教程 | 后续版本 |

---

**迁移完成标志**: 所有检查清单项目完成，线上运行稳定 1 周无问题，GLM 特定概念基本清理完成。

**下一步**: 开始Phase 1实施，创建`wolo/wolo/llm_adapter.py`通用 LLM 适配层文件。