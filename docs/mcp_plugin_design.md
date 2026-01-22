# Wolo MCP & Plugin 接入设计方案

> 版本: 1.0  
> 日期: 2026-01-21  
> 状态: 设计阶段

---

## 1. 概述

### 1.1 背景

当前 Wolo 的工具系统是内置的，扩展性有限。为了支持更丰富的功能（如网络搜索、数据库访问、第三方 API 等），需要设计一个灵活的扩展机制。

### 1.2 设计目标

1. **MCP (Model Context Protocol) 支持**: 兼容 Anthropic 的 MCP 协议，可接入现有 MCP Server
2. **Plugin 系统**: 支持本地 Python 插件，提供更灵活的扩展能力
3. **Skill 系统**: 支持可复用的技能定义，类似 OpenCode 的 skill 概念
4. **统一接口**: 无论是内置工具、MCP 工具还是 Plugin 工具，对 LLM 暴露统一的接口

### 1.3 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                         LLM                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Tool Registry                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐│
│  │ Built-in    │ │ MCP Tools   │ │ Plugin Tools            ││
│  │ Tools       │ │             │ │                         ││
│  └─────────────┘ └─────────────┘ └─────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
         │                 │                    │
         ▼                 ▼                    ▼
┌─────────────┐   ┌─────────────┐      ┌─────────────┐
│ Local       │   │ MCP Server  │      │ Plugin      │
│ Execution   │   │ (stdio/sse) │      │ Module      │
└─────────────┘   └─────────────┘      └─────────────┘
```

---

## 2. MCP 支持设计

### 2.1 MCP 协议简介

MCP (Model Context Protocol) 是 Anthropic 定义的协议，用于 LLM 与外部工具/资源的交互。

**核心概念**:
- **Server**: 提供工具和资源的服务端
- **Client**: 调用工具的客户端（Wolo）
- **Transport**: 通信方式（stdio, SSE, WebSocket）
- **Tools**: 可调用的函数
- **Resources**: 可读取的资源（文件、数据等）
- **Prompts**: 预定义的提示模板

### 2.2 MCP Client 实现

#### 2.2.1 文件结构

```
wolo/
├── mcp/
│   ├── __init__.py
│   ├── client.py          # MCP Client 实现
│   ├── transport.py       # 传输层（stdio, sse）
│   ├── protocol.py        # 协议消息定义
│   ├── server_manager.py  # Server 生命周期管理
│   └── types.py           # 类型定义
```

#### 2.2.2 核心接口

```python
# wolo/mcp/types.py

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class TransportType(Enum):
    STDIO = "stdio"
    SSE = "sse"
    WEBSOCKET = "websocket"


@dataclass
class MCPServerConfig:
    """MCP Server 配置"""
    name: str
    """服务器名称（唯一标识）"""
    
    command: str
    """启动命令（stdio 模式）"""
    
    args: list[str] = field(default_factory=list)
    """命令参数"""
    
    env: dict[str, str] = field(default_factory=dict)
    """环境变量"""
    
    transport: TransportType = TransportType.STDIO
    """传输类型"""
    
    url: Optional[str] = None
    """SSE/WebSocket URL（非 stdio 模式）"""
    
    enabled: bool = True
    """是否启用"""
    
    auto_start: bool = True
    """是否自动启动"""


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    """工具名称"""
    
    description: str
    """工具描述"""
    
    input_schema: dict
    """输入参数 JSON Schema"""
    
    server: str
    """所属服务器名称"""


@dataclass
class MCPResource:
    """MCP 资源定义"""
    uri: str
    """资源 URI"""
    
    name: str
    """资源名称"""
    
    description: str
    """资源描述"""
    
    mime_type: Optional[str] = None
    """MIME 类型"""
    
    server: str = ""
    """所属服务器名称"""
```

#### 2.2.3 MCP Client

```python
# wolo/mcp/client.py

import asyncio
from typing import Any, Optional
from wolo.mcp.types import MCPServerConfig, MCPTool, MCPResource
from wolo.mcp.transport import StdioTransport, SSETransport


class MCPClient:
    """
    MCP Client 实现。
    
    负责与单个 MCP Server 通信。
    
    Usage:
        client = MCPClient(config)
        await client.connect()
        
        tools = await client.list_tools()
        result = await client.call_tool("web_search", {"query": "python"})
        
        await client.disconnect()
    """
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._transport: Optional[Transport] = None
        self._tools: list[MCPTool] = []
        self._resources: list[MCPResource] = []
        self._connected = False
    
    async def connect(self) -> None:
        """连接到 MCP Server"""
        pass
    
    async def disconnect(self) -> None:
        """断开连接"""
        pass
    
    async def list_tools(self) -> list[MCPTool]:
        """获取可用工具列表"""
        pass
    
    async def list_resources(self) -> list[MCPResource]:
        """获取可用资源列表"""
        pass
    
    async def call_tool(self, name: str, arguments: dict) -> Any:
        """调用工具"""
        pass
    
    async def read_resource(self, uri: str) -> Any:
        """读取资源"""
        pass
    
    @property
    def is_connected(self) -> bool:
        return self._connected
```

#### 2.2.4 Server Manager

```python
# wolo/mcp/server_manager.py

from typing import Optional
from wolo.mcp.client import MCPClient
from wolo.mcp.types import MCPServerConfig, MCPTool


class MCPServerManager:
    """
    MCP Server 生命周期管理器。
    
    负责管理多个 MCP Server 的启动、停止和工具注册。
    
    Usage:
        manager = MCPServerManager()
        
        # 从配置加载
        manager.load_config(config_path)
        
        # 启动所有服务器
        await manager.start_all()
        
        # 获取所有工具
        tools = manager.get_all_tools()
        
        # 调用工具
        result = await manager.call_tool("web_search", {"query": "test"})
        
        # 停止所有服务器
        await manager.stop_all()
    """
    
    def __init__(self):
        self._servers: dict[str, MCPServerConfig] = {}
        self._clients: dict[str, MCPClient] = {}
        self._tool_map: dict[str, str] = {}  # tool_name -> server_name
    
    def load_config(self, config_path: str) -> None:
        """从配置文件加载 Server 配置"""
        pass
    
    def add_server(self, config: MCPServerConfig) -> None:
        """添加 Server 配置"""
        pass
    
    def remove_server(self, name: str) -> None:
        """移除 Server"""
        pass
    
    async def start_server(self, name: str) -> None:
        """启动指定 Server"""
        pass
    
    async def stop_server(self, name: str) -> None:
        """停止指定 Server"""
        pass
    
    async def start_all(self) -> None:
        """启动所有启用的 Server"""
        pass
    
    async def stop_all(self) -> None:
        """停止所有 Server"""
        pass
    
    def get_all_tools(self) -> list[MCPTool]:
        """获取所有可用工具"""
        pass
    
    async def call_tool(self, name: str, arguments: dict) -> Any:
        """调用工具（自动路由到对应 Server）"""
        pass
    
    def get_server_status(self) -> dict[str, bool]:
        """获取所有 Server 状态"""
        pass
```

### 2.3 MCP 配置文件

```yaml
# ~/.wolo/mcp.yaml 或 .wolo/mcp.yaml

servers:
  # 网络搜索 MCP Server
  web-search:
    command: "npx"
    args: ["-y", "@anthropic/mcp-server-web-search"]
    env:
      BRAVE_API_KEY: "${BRAVE_API_KEY}"
    enabled: true
    auto_start: true
  
  # 文件系统 MCP Server
  filesystem:
    command: "npx"
    args: ["-y", "@anthropic/mcp-server-filesystem", "/home/user/projects"]
    enabled: true
  
  # 数据库 MCP Server
  postgres:
    command: "npx"
    args: ["-y", "@anthropic/mcp-server-postgres"]
    env:
      DATABASE_URL: "${DATABASE_URL}"
    enabled: false
  
  # 自定义 Python MCP Server
  custom-tools:
    command: "python"
    args: ["-m", "my_mcp_server"]
    enabled: true
  
  # SSE 模式的远程 Server
  remote-api:
    transport: sse
    url: "https://api.example.com/mcp"
    enabled: false
```

### 2.4 与 Tool Registry 集成

```python
# wolo/tool_registry.py 修改

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}
        self._mcp_tools: dict[str, MCPTool] = {}  # MCP 工具
        self._plugin_tools: dict[str, PluginTool] = {}  # Plugin 工具
        self._register_defaults()
    
    def register_mcp_tool(self, tool: MCPTool) -> None:
        """注册 MCP 工具"""
        # 转换为 ToolSpec 格式
        spec = ToolSpec(
            name=f"mcp:{tool.server}:{tool.name}",  # 命名空间
            description=tool.description,
            parameters=tool.input_schema.get("properties", {}),
            required_params=tool.input_schema.get("required", []),
            category=ToolCategory.MCP,
            icon="🔌",
            show_output=True,
        )
        self._tools[spec.name] = spec
        self._mcp_tools[spec.name] = tool
    
    def get_llm_schemas(self, include_mcp: bool = True) -> list[dict]:
        """获取所有工具的 LLM Schema"""
        schemas = [spec.to_llm_schema() for spec in self._tools.values()]
        return schemas
```

---

## 3. Plugin 系统设计

### 3.1 设计原则

1. **简单易用**: 最小化样板代码
2. **类型安全**: 使用 dataclass 和类型注解
3. **隔离性**: 每个 Plugin 独立运行
4. **热加载**: 支持运行时加载/卸载

### 3.2 文件结构

```
wolo/
├── plugin/
│   ├── __init__.py
│   ├── base.py            # Plugin 基类
│   ├── loader.py          # Plugin 加载器
│   ├── manager.py         # Plugin 管理器
│   └── types.py           # 类型定义

# 用户 Plugin 目录
~/.wolo/plugins/
├── my_plugin/
│   ├── __init__.py
│   ├── plugin.yaml        # Plugin 元数据
│   └── tools.py           # 工具实现
```

### 3.3 Plugin 定义

#### 3.3.1 Plugin 基类

```python
# wolo/plugin/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class PluginMeta:
    """Plugin 元数据"""
    name: str
    """Plugin 名称"""
    
    version: str
    """版本号"""
    
    description: str
    """描述"""
    
    author: str = ""
    """作者"""
    
    homepage: str = ""
    """主页"""
    
    dependencies: list[str] = None
    """依赖的 Python 包"""


class Plugin(ABC):
    """
    Plugin 基类。
    
    所有 Plugin 必须继承此类。
    
    Example:
        class MyPlugin(Plugin):
            @property
            def meta(self) -> PluginMeta:
                return PluginMeta(
                    name="my-plugin",
                    version="1.0.0",
                    description="My awesome plugin",
                )
            
            def get_tools(self) -> list[PluginTool]:
                return [
                    PluginTool(
                        name="my_tool",
                        description="Does something",
                        parameters={...},
                        handler=self.my_tool_handler,
                    )
                ]
            
            async def my_tool_handler(self, **kwargs) -> str:
                return "result"
    """
    
    @property
    @abstractmethod
    def meta(self) -> PluginMeta:
        """返回 Plugin 元数据"""
        pass
    
    @abstractmethod
    def get_tools(self) -> list["PluginTool"]:
        """返回 Plugin 提供的工具列表"""
        pass
    
    async def on_load(self) -> None:
        """Plugin 加载时调用"""
        pass
    
    async def on_unload(self) -> None:
        """Plugin 卸载时调用"""
        pass


@dataclass
class PluginTool:
    """Plugin 工具定义"""
    name: str
    """工具名称"""
    
    description: str
    """工具描述"""
    
    parameters: dict
    """参数定义（JSON Schema 格式）"""
    
    handler: callable
    """处理函数"""
    
    required_params: list[str] = None
    """必需参数"""
    
    category: str = "plugin"
    """分类"""
    
    icon: str = "🔧"
    """图标"""
```

#### 3.3.2 Plugin 示例

```python
# ~/.wolo/plugins/web_tools/tools.py

from wolo.plugin import Plugin, PluginMeta, PluginTool
import aiohttp


class WebToolsPlugin(Plugin):
    """网络工具 Plugin"""
    
    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="web-tools",
            version="1.0.0",
            description="Web search and fetch tools",
            author="Wolo Team",
            dependencies=["aiohttp", "beautifulsoup4"],
        )
    
    def get_tools(self) -> list[PluginTool]:
        return [
            PluginTool(
                name="web_search",
                description="Search the web using DuckDuckGo",
                parameters={
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results"},
                },
                required_params=["query"],
                handler=self.web_search,
                icon="🔍",
            ),
            PluginTool(
                name="web_fetch",
                description="Fetch content from a URL",
                parameters={
                    "url": {"type": "string", "description": "URL to fetch"},
                    "format": {"type": "string", "enum": ["text", "html", "markdown"]},
                },
                required_params=["url"],
                handler=self.web_fetch,
                icon="🌐",
            ),
        ]
    
    async def web_search(self, query: str, max_results: int = 5) -> str:
        """执行网络搜索"""
        # 实现搜索逻辑
        pass
    
    async def web_fetch(self, url: str, format: str = "text") -> str:
        """获取网页内容"""
        # 实现获取逻辑
        pass


# 导出 Plugin 实例
plugin = WebToolsPlugin()
```

#### 3.3.3 Plugin 配置文件

```yaml
# ~/.wolo/plugins/web_tools/plugin.yaml

name: web-tools
version: 1.0.0
description: Web search and fetch tools
author: Wolo Team

# Python 依赖
dependencies:
  - aiohttp>=3.8.0
  - beautifulsoup4>=4.12.0

# 入口点
entry_point: tools:plugin

# 配置项
config:
  search_engine:
    type: string
    default: duckduckgo
    description: Search engine to use
  
  timeout:
    type: integer
    default: 30000
    description: Request timeout in ms

# 权限声明
permissions:
  - network  # 需要网络访问
```

### 3.4 Plugin Manager

```python
# wolo/plugin/manager.py

from pathlib import Path
from typing import Optional
from wolo.plugin.base import Plugin, PluginTool


class PluginManager:
    """
    Plugin 管理器。
    
    负责 Plugin 的加载、卸载和管理。
    
    Usage:
        manager = PluginManager()
        
        # 加载所有 Plugin
        await manager.load_all()
        
        # 加载单个 Plugin
        await manager.load_plugin("web-tools")
        
        # 获取所有工具
        tools = manager.get_all_tools()
        
        # 调用工具
        result = await manager.call_tool("web_search", {"query": "test"})
        
        # 卸载 Plugin
        await manager.unload_plugin("web-tools")
    """
    
    def __init__(self, plugin_dirs: list[Path] = None):
        self._plugin_dirs = plugin_dirs or [
            Path.home() / ".wolo" / "plugins",
            Path.cwd() / ".wolo" / "plugins",
        ]
        self._plugins: dict[str, Plugin] = {}
        self._tools: dict[str, PluginTool] = {}
    
    async def load_all(self) -> None:
        """加载所有 Plugin"""
        pass
    
    async def load_plugin(self, name: str) -> None:
        """加载指定 Plugin"""
        pass
    
    async def unload_plugin(self, name: str) -> None:
        """卸载指定 Plugin"""
        pass
    
    async def reload_plugin(self, name: str) -> None:
        """重新加载 Plugin"""
        pass
    
    def get_all_tools(self) -> list[PluginTool]:
        """获取所有可用工具"""
        pass
    
    async def call_tool(self, name: str, arguments: dict) -> Any:
        """调用工具"""
        pass
    
    def get_plugin_status(self) -> dict[str, dict]:
        """获取所有 Plugin 状态"""
        pass
```

---

## 4. Skill 系统设计

### 4.1 概念

Skill 是一组预定义的工具使用模式，可以被 LLM 复用。类似于 OpenCode 的 skill 概念。

### 4.2 Skill 定义

```yaml
# ~/.wolo/skills/code_review.yaml

name: code-review
description: Review code changes and provide feedback
version: 1.0.0

# 触发条件
triggers:
  - pattern: "review (this|the) (code|changes|PR)"
  - pattern: "code review"
  - intent: code_review

# 工具序列
steps:
  - name: get_diff
    tool: shell
    input:
      command: "git diff HEAD~1"
    output_var: diff_content
  
  - name: analyze_changes
    tool: read
    input:
      file_path: "${changed_files}"
    loop: true
    output_var: file_contents
  
  - name: check_tests
    tool: shell
    input:
      command: "make test"
    optional: true

# 输出模板
output_template: |
  ## Code Review Summary
  
  ### Changes
  ${diff_content}
  
  ### Analysis
  ${analysis}
  
  ### Recommendations
  ${recommendations}

# 配置
config:
  max_files: 10
  include_tests: true
```

### 4.3 Skill Manager

```python
# wolo/skill/manager.py

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SkillStep:
    """Skill 步骤"""
    name: str
    tool: str
    input: dict
    output_var: str = ""
    loop: bool = False
    optional: bool = False
    condition: str = ""


@dataclass
class Skill:
    """Skill 定义"""
    name: str
    description: str
    version: str
    triggers: list[dict]
    steps: list[SkillStep]
    output_template: str
    config: dict


class SkillManager:
    """
    Skill 管理器。
    
    Usage:
        manager = SkillManager()
        manager.load_skills()
        
        # 检查是否匹配 Skill
        skill = manager.match_skill("review this code")
        
        # 执行 Skill
        result = await manager.execute_skill(skill, context)
    """
    
    def __init__(self):
        self._skills: dict[str, Skill] = {}
    
    def load_skills(self, skill_dirs: list[Path] = None) -> None:
        """加载所有 Skill"""
        pass
    
    def match_skill(self, user_input: str) -> Optional[Skill]:
        """匹配用户输入到 Skill"""
        pass
    
    async def execute_skill(self, skill: Skill, context: dict) -> str:
        """执行 Skill"""
        pass
    
    def get_all_skills(self) -> list[Skill]:
        """获取所有 Skill"""
        pass
```

---

## 5. 统一执行层

### 5.1 Tool Executor

```python
# wolo/executor.py

from typing import Any, Optional
from wolo.tool_registry import ToolRegistry, get_registry
from wolo.mcp.server_manager import MCPServerManager
from wolo.plugin.manager import PluginManager
from wolo.session import ToolPart


class ToolExecutor:
    """
    统一工具执行器。
    
    负责路由和执行来自不同来源的工具调用。
    
    Usage:
        executor = ToolExecutor()
        await executor.initialize()
        
        # 执行工具
        result = await executor.execute(tool_part, session_id)
    """
    
    def __init__(self):
        self._registry = get_registry()
        self._mcp_manager: Optional[MCPServerManager] = None
        self._plugin_manager: Optional[PluginManager] = None
    
    async def initialize(self) -> None:
        """初始化执行器"""
        # 加载 MCP Servers
        self._mcp_manager = MCPServerManager()
        self._mcp_manager.load_config()
        await self._mcp_manager.start_all()
        
        # 加载 Plugins
        self._plugin_manager = PluginManager()
        await self._plugin_manager.load_all()
        
        # 注册工具到 Registry
        self._register_external_tools()
    
    async def shutdown(self) -> None:
        """关闭执行器"""
        if self._mcp_manager:
            await self._mcp_manager.stop_all()
    
    async def execute(
        self,
        tool_part: ToolPart,
        session_id: str = None,
        config: Any = None,
    ) -> None:
        """
        执行工具调用。
        
        根据工具名称前缀路由到对应的执行器：
        - 无前缀: 内置工具
        - mcp:server:tool: MCP 工具
        - plugin:name:tool: Plugin 工具
        """
        tool_name = tool_part.tool
        
        if tool_name.startswith("mcp:"):
            # MCP 工具
            await self._execute_mcp_tool(tool_part)
        elif tool_name.startswith("plugin:"):
            # Plugin 工具
            await self._execute_plugin_tool(tool_part)
        else:
            # 内置工具
            await self._execute_builtin_tool(tool_part, session_id, config)
    
    async def _execute_mcp_tool(self, tool_part: ToolPart) -> None:
        """执行 MCP 工具"""
        pass
    
    async def _execute_plugin_tool(self, tool_part: ToolPart) -> None:
        """执行 Plugin 工具"""
        pass
    
    async def _execute_builtin_tool(
        self,
        tool_part: ToolPart,
        session_id: str,
        config: Any,
    ) -> None:
        """执行内置工具"""
        from wolo.tools import execute_tool
        await execute_tool(tool_part, session_id, config)
    
    def _register_external_tools(self) -> None:
        """注册外部工具到 Registry"""
        # 注册 MCP 工具
        for tool in self._mcp_manager.get_all_tools():
            self._registry.register_mcp_tool(tool)
        
        # 注册 Plugin 工具
        for tool in self._plugin_manager.get_all_tools():
            self._registry.register_plugin_tool(tool)
    
    def get_all_tool_schemas(self) -> list[dict]:
        """获取所有工具的 LLM Schema"""
        return self._registry.get_llm_schemas()
```

---

## 6. 配置系统

### 6.1 统一配置

```yaml
# ~/.wolo/config.yaml

# MCP 配置
mcp:
  enabled: true
  config_file: ~/.wolo/mcp.yaml
  auto_start: true

# Plugin 配置
plugins:
  enabled: true
  directories:
    - ~/.wolo/plugins
    - ./.wolo/plugins
  auto_load: true

# Skill 配置
skills:
  enabled: true
  directories:
    - ~/.wolo/skills
    - ./.wolo/skills

# 工具配置
tools:
  # 禁用特定工具
  disabled:
    - shell  # 如果需要禁用
  
  # 工具别名
  aliases:
    search: mcp:web-search:search
    fetch: plugin:web-tools:web_fetch
  
  # 权限控制
  permissions:
    shell:
      require_confirmation: true
    write:
      require_confirmation: false
```

---

## 7. 实现计划

### 7.1 第一阶段: MCP 基础支持

| 任务 | 优先级 | 预计工时 |
|------|--------|----------|
| MCP 协议消息定义 | P0 | 2h |
| Stdio Transport 实现 | P0 | 4h |
| MCP Client 实现 | P0 | 6h |
| Server Manager 实现 | P0 | 4h |
| 配置文件解析 | P1 | 2h |
| 与 Tool Registry 集成 | P0 | 4h |
| 测试 | P0 | 4h |

### 7.2 第二阶段: Plugin 系统

| 任务 | 优先级 | 预计工时 |
|------|--------|----------|
| Plugin 基类定义 | P0 | 2h |
| Plugin Loader 实现 | P0 | 4h |
| Plugin Manager 实现 | P0 | 4h |
| 热加载支持 | P1 | 4h |
| 示例 Plugin (web-tools) | P1 | 4h |
| 测试 | P0 | 4h |

### 7.3 第三阶段: Skill 系统

| 任务 | 优先级 | 预计工时 |
|------|--------|----------|
| Skill 定义格式 | P1 | 2h |
| Skill Loader | P1 | 2h |
| Skill Manager | P1 | 4h |
| 触发匹配 | P1 | 4h |
| 示例 Skill | P2 | 2h |
| 测试 | P1 | 2h |

### 7.4 第四阶段: 统一执行层

| 任务 | 优先级 | 预计工时 |
|------|--------|----------|
| Tool Executor 实现 | P0 | 4h |
| 路由逻辑 | P0 | 2h |
| 错误处理 | P0 | 2h |
| UI 集成 | P1 | 4h |
| 文档 | P1 | 4h |

---

## 8. 安全考虑

### 8.1 MCP 安全

1. **Server 验证**: 只允许配置文件中定义的 Server
2. **环境变量**: 敏感信息通过环境变量传递
3. **沙箱**: 考虑使用容器隔离 MCP Server

### 8.2 Plugin 安全

1. **权限声明**: Plugin 必须声明所需权限
2. **代码审查**: 建议只使用可信来源的 Plugin
3. **依赖检查**: 检查 Plugin 依赖的安全性

### 8.3 Skill 安全

1. **工具限制**: Skill 只能使用已注册的工具
2. **输入验证**: 验证 Skill 参数
3. **执行限制**: 限制 Skill 的执行时间和资源

---

## 9. 示例：迁移 Web 工具到 MCP

### 9.1 创建 MCP Server

```python
# mcp_servers/web_search/server.py

from mcp.server import Server
from mcp.types import Tool, TextContent
import aiohttp

server = Server("web-search")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="web_search",
            description="Search the web using DuckDuckGo",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="web_fetch",
            description="Fetch content from a URL",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                    "format": {"type": "string", "enum": ["text", "html", "markdown"]},
                },
                "required": ["url"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "web_search":
        return await do_web_search(arguments["query"], arguments.get("max_results", 5))
    elif name == "web_fetch":
        return await do_web_fetch(arguments["url"], arguments.get("format", "text"))


async def do_web_search(query: str, max_results: int) -> list[TextContent]:
    # 实现搜索逻辑
    pass


async def do_web_fetch(url: str, format: str) -> list[TextContent]:
    # 实现获取逻辑
    pass


if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    
    asyncio.run(stdio_server(server))
```

### 9.2 配置 MCP Server

```yaml
# ~/.wolo/mcp.yaml

servers:
  web-search:
    command: "python"
    args: ["-m", "mcp_servers.web_search.server"]
    enabled: true
```

---

## 10. 总结

本设计方案提供了三层扩展机制：

1. **MCP**: 标准化协议，可接入现有生态
2. **Plugin**: 灵活的本地扩展，适合定制需求
3. **Skill**: 高级抽象，可复用的工具组合

这三层机制相互补充，共同构成了 Wolo 的扩展体系。
