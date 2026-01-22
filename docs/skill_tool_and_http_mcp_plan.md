# Wolo Skill Tool 与 HTTP MCP 支持规划文档

## 1. 问题分析

### 1.1 当前问题

用户反馈在 Claude CLI 中可以使用 `search-prime` 和 `web-reader` MCP 服务，但 Wolo 无法找到这些 MCP。

**根本原因：**

1. **MCP 配置位置不同**：Claude CLI 的 MCP 服务器不是通过 `claude_desktop_config.json` 配置的，而是通过 **HTTP Transport** 连接到 GLM 平台托管的 MCP 服务 (`https://open.bigmodel.cn/api/mcp/`)

2. **Wolo 只支持 Stdio Transport**：当前 Wolo 的 MCP 实现只支持本地进程通信（stdio），不支持 HTTP/SSE transport

3. **Skill 加载机制不同**：当前 Wolo 采用自动匹配注入，而 OpenCode 采用 Agent 主动调用 `skill` tool

### 1.2 Claude CLI MCP 架构

```
Claude CLI
    │
    ├── Stdio MCP (本地进程)
    │   └── 通过 claude_desktop_config.json 配置
    │   └── 例如: npx @upstash/context7-mcp
    │
    └── HTTP MCP (远程服务)
        └── 通过 GLM 平台提供
        └── URL: https://open.bigmodel.cn/api/mcp/{service_name}/mcp
        └── 例如: search-prime, web-reader
```

### 1.3 OpenCode MCP 架构

```typescript
// opencode/packages/opencode/src/mcp/index.ts
const transports = [
  {
    name: "StreamableHTTP",
    transport: new StreamableHTTPClientTransport(new URL(mcp.url), {
      authProvider,
      requestInit: mcp.headers ? { headers: mcp.headers } : undefined,
    }),
  },
  {
    name: "SSE",
    transport: new SSEClientTransport(new URL(mcp.url), {
      authProvider,
      requestInit: mcp.headers ? { headers: mcp.headers } : undefined,
    }),
  },
]
```

## 2. 需要实现的功能

### 2.1 Skill Tool（按需加载）

**目标**：让 Agent 能够自主探索和加载 Skills，而不是自动注入。

**OpenCode 实现参考**：

```typescript
// opencode/packages/opencode/src/tool/skill.ts
export const SkillTool = Tool.define("skill", async (ctx) => {
  const skills = await Skill.all()
  
  // Tool description 动态包含所有可用 skills
  const description = [
    "Load a skill to get detailed instructions for a specific task.",
    "<available_skills>",
    ...skills.flatMap((skill) => [
      `  <skill>`,
      `    <name>${skill.name}</name>`,
      `    <description>${skill.description}</description>`,
      `  </skill>`,
    ]),
    "</available_skills>",
  ].join(" ")

  return {
    description,
    parameters: { name: z.string() },
    async execute(params) {
      const skill = await Skill.get(params.name)
      return {
        title: `Loaded skill: ${skill.name}`,
        output: skill.content,
      }
    },
  }
})
```

### 2.2 HTTP MCP Transport

**目标**：支持通过 HTTP/SSE 连接远程 MCP 服务器。

**需要支持的 Transport 类型**：

| Transport | 协议 | 用途 |
|-----------|------|------|
| Stdio | 本地进程 stdin/stdout | 本地 MCP 服务器 |
| StreamableHTTP | HTTP POST/GET | 远程 MCP 服务器 |
| SSE | Server-Sent Events | 远程 MCP 服务器（流式） |

### 2.3 GLM 平台 MCP 集成

**目标**：自动发现和连接 GLM 平台提供的 MCP 服务。

**GLM MCP 服务列表**（已知）：
- `web-search-prime` - 网络搜索
- `web-reader` - 网页阅读

**连接方式**：
```
URL: https://open.bigmodel.cn/api/mcp/{service_name}/mcp
Headers:
  Authorization: Bearer {ANTHROPIC_AUTH_TOKEN}
  User-Agent: wolo/{version}
```

## 3. 详细设计

### 3.1 Skill Tool 设计

#### 3.1.1 新增文件：`wolo/skill_tool.py`

```python
"""Skill tool for on-demand skill loading."""

from typing import Optional
from wolo.mcp_integration import get_claude_skills
from wolo.claude.skill_loader import ClaudeSkill


def get_skill_tool_schema() -> dict:
    """
    Generate skill tool schema with available skills listed in description.
    
    Returns:
        Tool schema dict for LLM
    """
    skills = get_claude_skills()
    
    if not skills:
        description = (
            "Load a skill to get detailed instructions for a specific task. "
            "No skills are currently available."
        )
    else:
        skill_list = "\n".join([
            f'  <skill>\n'
            f'    <name>{s.name}</name>\n'
            f'    <description>{s.description}</description>\n'
            f'  </skill>'
            for s in skills
        ])
        description = (
            "Load a skill to get detailed instructions for a specific task. "
            "Skills provide specialized knowledge and step-by-step guidance. "
            "Use this when a task matches an available skill's description.\n"
            f"<available_skills>\n{skill_list}\n</available_skills>"
        )
    
    return {
        "type": "function",
        "function": {
            "name": "skill",
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The skill identifier from available_skills"
                    }
                },
                "required": ["name"]
            }
        }
    }


async def skill_execute(name: str) -> str:
    """
    Load and return skill content.
    
    Args:
        name: Skill name to load
    
    Returns:
        Skill content as formatted string
    """
    skills = get_claude_skills()
    skill = next((s for s in skills if s.name == name), None)
    
    if not skill:
        available = ", ".join(s.name for s in skills) or "none"
        return f'Skill "{name}" not found. Available skills: {available}'
    
    return f"""## Skill: {skill.name}

**Base directory**: {skill.skill_dir}

{skill.get_system_prompt()}
"""
```

#### 3.1.2 修改 `wolo/tool_registry.py`

添加 SKILL ToolSpec：

```python
SKILL = ToolSpec(
    name="skill",
    description="Load a skill for specialized instructions",
    parameters={"name": "Skill name to load"},
    required_params=["name"],
    category=ToolCategory.SYSTEM,
    icon="📚",
    show_output=True,
    brief_formatter=lambda args, result: f"Loaded skill: {args.get('name', 'unknown')}",
)
```

#### 3.1.3 修改 `wolo/tools.py`

在 `execute_tool` 中添加 skill 处理：

```python
elif tool_part.tool == "skill":
    from wolo.skill_tool import skill_execute
    result = await skill_execute(tool_part.input.get("name", ""))
    output = result
    status = "completed"
```

#### 3.1.4 移除自动注入逻辑

从 `wolo/llm.py` 中移除 `_add_skills_to_prompt` 方法及其调用。

### 3.2 HTTP MCP Transport 设计

#### 3.2.1 新增文件：`wolo/mcp/http_transport.py`

```python
"""HTTP/SSE transport for MCP."""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

import aiohttp

from .transport import Transport, JSONRPCMessage

logger = logging.getLogger(__name__)


@dataclass
class HTTPTransportConfig:
    """Configuration for HTTP transport."""
    url: str
    headers: dict[str, str] = None
    timeout: int = 60000  # ms
    auth_token: Optional[str] = None


class HTTPTransport(Transport):
    """
    HTTP transport for MCP using Streamable HTTP protocol.
    
    Implements the MCP Streamable HTTP transport spec:
    - POST for requests
    - GET for server-initiated messages (SSE)
    """
    
    def __init__(self, config: HTTPTransportConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._connected = False
        self._session_id: Optional[str] = None
    
    async def connect(self) -> None:
        """Establish HTTP connection."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.config.headers:
            headers.update(self.config.headers)
        if self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
        
        timeout = aiohttp.ClientTimeout(
            total=self.config.timeout / 1000,
            connect=10,
        )
        
        self._session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
        )
        self._connected = True
        logger.info(f"HTTP transport connected to {self.config.url}")
    
    async def send(self, message: JSONRPCMessage) -> None:
        """Send JSON-RPC message via HTTP POST."""
        if not self._session:
            raise RuntimeError("Transport not connected")
        
        async with self._session.post(
            self.config.url,
            json=message.to_dict(),
        ) as response:
            if response.status != 200:
                text = await response.text()
                raise RuntimeError(f"HTTP {response.status}: {text}")
    
    async def receive(self) -> AsyncIterator[JSONRPCMessage]:
        """Receive messages via SSE stream."""
        if not self._session:
            raise RuntimeError("Transport not connected")
        
        async with self._session.get(self.config.url) as response:
            if response.status != 200:
                text = await response.text()
                raise RuntimeError(f"HTTP {response.status}: {text}")
            
            async for line in response.content:
                line = line.decode().strip()
                if line.startswith("data: "):
                    data = line[6:]
                    if data:
                        try:
                            msg_dict = json.loads(data)
                            yield JSONRPCMessage.from_dict(msg_dict)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in SSE: {data}")
    
    async def close(self) -> None:
        """Close HTTP connection."""
        if self._session:
            await self._session.close()
            self._session = None
        self._connected = False
    
    @property
    def is_connected(self) -> bool:
        return self._connected


class SSETransport(HTTPTransport):
    """
    SSE (Server-Sent Events) transport for MCP.
    
    Similar to HTTP transport but uses SSE for bidirectional communication.
    """
    
    async def send(self, message: JSONRPCMessage) -> None:
        """Send message and handle SSE response."""
        if not self._session:
            raise RuntimeError("Transport not connected")
        
        async with self._session.post(
            self.config.url,
            json=message.to_dict(),
            headers={"Accept": "text/event-stream"},
        ) as response:
            if response.status != 200:
                text = await response.text()
                raise RuntimeError(f"HTTP {response.status}: {text}")
            
            # For SSE, response might be streamed
            content_type = response.headers.get("Content-Type", "")
            if "text/event-stream" in content_type:
                # Handle SSE response
                async for line in response.content:
                    line = line.decode().strip()
                    if line.startswith("data: "):
                        data = line[6:]
                        if data:
                            # Process SSE data
                            pass
```

#### 3.2.2 修改 `wolo/mcp/server_manager.py`

添加 HTTP transport 支持：

```python
from .http_transport import HTTPTransport, SSETransport, HTTPTransportConfig

class MCPServerManager:
    async def _start_http_server(
        self, 
        name: str, 
        config: MCPServerConfig
    ) -> bool:
        """Start an HTTP-based MCP server."""
        try:
            http_config = HTTPTransportConfig(
                url=config.url,
                headers=config.headers,
                auth_token=config.auth_token,
                timeout=config.timeout or 60000,
            )
            
            # Try StreamableHTTP first, then SSE
            transports = [
                ("StreamableHTTP", HTTPTransport(http_config)),
                ("SSE", SSETransport(http_config)),
            ]
            
            for transport_name, transport in transports:
                try:
                    await transport.connect()
                    client = MCPClient(transport)
                    await asyncio.wait_for(
                        client.initialize(),
                        timeout=30.0
                    )
                    
                    self._states[name] = ServerState(
                        config=config,
                        status=ServerStatus.RUNNING,
                        client=client,
                        transport=transport,
                    )
                    logger.info(f"Connected to HTTP MCP: {name} via {transport_name}")
                    return True
                    
                except Exception as e:
                    logger.debug(f"Failed {transport_name} for {name}: {e}")
                    await transport.close()
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to start HTTP MCP {name}: {e}")
            return False
```

### 3.3 GLM 平台 MCP 集成设计

#### 3.3.1 新增文件：`wolo/glm/mcp_discovery.py`

```python
"""GLM platform MCP service discovery."""

import os
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Known GLM MCP services
GLM_MCP_SERVICES = {
    "web-search-prime": {
        "description": "Web search powered by GLM",
        "endpoint": "web_search_prime",
    },
    "web-reader": {
        "description": "Web page reader powered by GLM", 
        "endpoint": "web_reader",
    },
}


@dataclass
class GLMMCPConfig:
    """Configuration for GLM MCP service."""
    name: str
    url: str
    description: str
    auth_token: str


def get_glm_base_url() -> Optional[str]:
    """
    Get GLM API base URL from environment.
    
    Checks ANTHROPIC_BASE_URL for GLM platform URLs.
    """
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "")
    
    if "open.bigmodel.cn" in base_url or "dev.bigmodel.cn" in base_url:
        # Extract base domain
        if "open.bigmodel.cn" in base_url:
            return "https://open.bigmodel.cn"
        elif "dev.bigmodel.cn" in base_url:
            return "https://dev.bigmodel.cn"
    
    return None


def get_glm_auth_token() -> Optional[str]:
    """Get GLM auth token from environment."""
    return os.environ.get("ANTHROPIC_AUTH_TOKEN")


def discover_glm_mcp_services() -> list[GLMMCPConfig]:
    """
    Discover available GLM MCP services.
    
    Returns:
        List of GLM MCP configurations
    """
    base_url = get_glm_base_url()
    auth_token = get_glm_auth_token()
    
    if not base_url or not auth_token:
        logger.debug("GLM MCP not available: missing base URL or auth token")
        return []
    
    services = []
    for name, info in GLM_MCP_SERVICES.items():
        config = GLMMCPConfig(
            name=name,
            url=f"{base_url}/api/mcp/{info['endpoint']}/mcp",
            description=info["description"],
            auth_token=auth_token,
        )
        services.append(config)
        logger.info(f"Discovered GLM MCP service: {name}")
    
    return services
```

#### 3.3.2 修改 `wolo/mcp_integration.py`

集成 GLM MCP 发现：

```python
from wolo.glm.mcp_discovery import discover_glm_mcp_services

async def initialize_mcp(config: Config) -> MCPServerManager:
    # ... existing code ...
    
    # Discover GLM platform MCP services
    if config.glm_mcp_enabled:  # New config option
        glm_services = discover_glm_mcp_services()
        for service in glm_services:
            _mcp_manager.add_http_server(
                name=service.name,
                url=service.url,
                auth_token=service.auth_token,
                description=service.description,
            )
    
    # ... rest of initialization ...
```

### 3.4 配置更新

#### 3.4.1 修改 `wolo/config.py`

```python
@dataclass
class MCPConfig:
    """MCP configuration."""
    enabled: bool = True
    node_strategy: str = "warn"
    servers: dict = field(default_factory=dict)
    glm_enabled: bool = True  # Enable GLM platform MCP services


@dataclass  
class ClaudeCompatConfig:
    """Claude compatibility configuration."""
    enabled: bool = False
    config_dir: Optional[Path] = None
    load_skills: bool = True
    load_mcp: bool = True
    node_strategy: str = "warn"
```

#### 3.4.2 配置文件示例

```yaml
# ~/.wolo/config.yaml

# MCP configuration
mcp:
  enabled: true
  glm_enabled: true  # Auto-discover GLM platform MCP services
  
  # Custom MCP servers
  servers:
    my-custom-server:
      type: stdio
      command: npx
      args: ["-y", "@my/mcp-server"]
    
    remote-server:
      type: http
      url: https://example.com/mcp
      headers:
        Authorization: "Bearer xxx"

# Claude compatibility
claude:
  enabled: true
  load_skills: true
  load_mcp: true
```

## 4. 实施计划

### Phase 1: Skill Tool（优先级：高）

| 任务 | 描述 | 预计工作量 |
|------|------|-----------|
| 1.1 | 创建 `wolo/skill_tool.py` | 1h |
| 1.2 | 添加 SKILL ToolSpec | 0.5h |
| 1.3 | 在 `tools.py` 中添加 skill 执行逻辑 | 0.5h |
| 1.4 | 移除 `llm.py` 中的自动注入逻辑 | 0.5h |
| 1.5 | 编写单元测试 | 1h |
| 1.6 | 集成测试 | 0.5h |

**验收标准**：
- [ ] Agent 可以在 tool description 中看到可用 skills 列表
- [ ] Agent 可以调用 `skill({ name: "xxx" })` 加载 skill
- [ ] Skill 内容正确返回给 Agent
- [ ] 所有测试通过

### Phase 2: HTTP MCP Transport（优先级：高）

| 任务 | 描述 | 预计工作量 |
|------|------|-----------|
| 2.1 | 创建 `wolo/mcp/http_transport.py` | 2h |
| 2.2 | 修改 `MCPServerManager` 支持 HTTP | 1h |
| 2.3 | 更新 `MCPServerConfig` 数据结构 | 0.5h |
| 2.4 | 编写单元测试 | 1.5h |
| 2.5 | 集成测试 | 1h |

**验收标准**：
- [ ] 可以连接 HTTP MCP 服务器
- [ ] 可以连接 SSE MCP 服务器
- [ ] 支持自定义 headers 和 auth token
- [ ] 正确处理连接超时和错误
- [ ] 所有测试通过

### Phase 3: GLM 平台 MCP 集成（优先级：高）

| 任务 | 描述 | 预计工作量 |
|------|------|-----------|
| 3.1 | 创建 `wolo/glm/mcp_discovery.py` | 1h |
| 3.2 | 修改 `mcp_integration.py` 集成 GLM | 1h |
| 3.3 | 更新配置结构 | 0.5h |
| 3.4 | 编写测试 | 1h |
| 3.5 | 端到端测试 | 1h |

**验收标准**：
- [ ] 自动检测 GLM 平台环境变量
- [ ] 自动发现并连接 GLM MCP 服务
- [ ] `search-prime` 和 `web-reader` 可用
- [ ] Agent 可以调用 GLM MCP tools
- [ ] 所有测试通过

### Phase 4: 文档和清理（优先级：中）

| 任务 | 描述 | 预计工作量 |
|------|------|-----------|
| 4.1 | 更新 README | 0.5h |
| 4.2 | 更新 mcp_plugin_design.md | 0.5h |
| 4.3 | 添加配置示例 | 0.5h |
| 4.4 | 代码清理和优化 | 1h |

## 5. 测试计划

### 5.1 单元测试

```python
# wolo/tests/test_skill_tool.py

class TestSkillTool:
    def test_get_skill_tool_schema_no_skills(self):
        """Test schema generation with no skills."""
        
    def test_get_skill_tool_schema_with_skills(self):
        """Test schema includes skill list in description."""
        
    async def test_skill_execute_found(self):
        """Test loading existing skill."""
        
    async def test_skill_execute_not_found(self):
        """Test error when skill not found."""


# wolo/tests/test_http_transport.py

class TestHTTPTransport:
    async def test_connect(self):
        """Test HTTP connection."""
        
    async def test_send_receive(self):
        """Test message send/receive."""
        
    async def test_auth_header(self):
        """Test authorization header."""
        
    async def test_timeout(self):
        """Test connection timeout."""


# wolo/tests/test_glm_mcp.py

class TestGLMMCPDiscovery:
    def test_discover_with_env(self):
        """Test discovery with GLM env vars."""
        
    def test_discover_without_env(self):
        """Test discovery without GLM env vars."""
        
    def test_get_glm_base_url(self):
        """Test base URL extraction."""
```

### 5.2 集成测试

```python
# wolo/tests/test_mcp_integration.py

class TestMCPIntegration:
    async def test_initialize_with_glm(self):
        """Test MCP initialization with GLM services."""
        
    async def test_call_glm_tool(self):
        """Test calling GLM MCP tool."""
        
    async def test_skill_tool_in_agent(self):
        """Test skill tool works in agent loop."""
```

## 6. 风险和缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| GLM MCP 服务不稳定 | 工具调用失败 | 添加重试逻辑，优雅降级 |
| HTTP transport 兼容性 | 某些服务器不支持 | 支持多种 transport，自动回退 |
| Auth token 泄露 | 安全风险 | 不在日志中打印 token |
| 网络延迟 | 用户体验差 | 添加超时配置，显示进度 |

## 7. 总结

本规划文档涵盖了三个主要功能的实现：

1. **Skill Tool**：让 Agent 能够自主探索和加载 Skills
2. **HTTP MCP Transport**：支持远程 MCP 服务器连接
3. **GLM 平台 MCP 集成**：自动发现和使用 GLM 提供的 MCP 服务

实施这些功能后，Wolo 将能够：
- 与 OpenCode 的 Skill 机制保持一致
- 支持 GLM 平台的 `search-prime` 和 `web-reader` MCP 服务
- 支持任意 HTTP/SSE MCP 服务器

是否开始实施？
