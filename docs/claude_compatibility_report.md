# Wolo 兼容 Claude 模式 - 可行性分析与实施方案

> 版本: 1.1  
> 日期: 2026-01-21  
> 状态: **已实现** ✅

---

## 1. 执行摘要

### 1.1 结论

**完全可行**，但需要注意以下几点：

1. **Claude Skills**: 可以完全兼容，格式是 Markdown + Shell 脚本
2. **Claude Plugins**: 可以部分兼容，需要适配 hooks 机制
3. **MCP**: Claude Desktop 使用标准 MCP 协议，可以复用配置
4. **Node/NPX 依赖**: 可以作为可选依赖处理

### 1.2 Claude 配置结构分析

```
~/.claude/
├── settings.json           # 全局设置（env, enabledPlugins）
├── skills/                 # 用户自定义 Skills
│   └── <skill-name>/
│       ├── SKILL.md        # Skill 定义（Markdown 格式）
│       ├── scripts/        # 脚本文件
│       └── data/           # 数据文件
├── plugins/
│   ├── installed_plugins.json  # 已安装插件列表
│   └── cache/              # 插件缓存
│       └── <marketplace>/<plugin-name>/<version>/
│           ├── .claude-plugin/  # 插件元数据
│           ├── commands/        # 命令定义（.md 文件）
│           ├── hooks/           # 生命周期钩子
│           └── scripts/         # 脚本文件
└── projects/               # 项目配置
    └── <project-hash>/
        └── CLAUDE.md       # 项目级指令
```

---

## 2. Claude Skills 格式详解

### 2.1 SKILL.md 结构

```markdown
---
name: skill-name
description: "Skill description for matching"
---

# Skill Title

## Prerequisites
（前置条件检查）

## How to Use This Skill
（使用说明，包含 bash 命令模板）

## Search Reference
（参考文档）
```

### 2.2 关键特点

1. **YAML Frontmatter**: `name` 和 `description` 用于匹配
2. **Markdown 正文**: 包含使用说明和命令模板
3. **脚本调用**: 使用 `python3 .claude/skills/<name>/scripts/xxx.py` 格式
4. **无 JSON Schema**: 不像 MCP 那样有严格的参数定义

### 2.3 兼容策略

```python
# wolo/skill/claude_loader.py

@dataclass
class ClaudeSkill:
    """Claude 格式的 Skill"""
    name: str
    description: str
    content: str  # Markdown 正文
    scripts_dir: Path
    data_dir: Path


def load_claude_skill(skill_dir: Path) -> ClaudeSkill:
    """加载 Claude 格式的 Skill"""
    skill_md = skill_dir / "SKILL.md"
    content = skill_md.read_text()
    
    # 解析 YAML frontmatter
    frontmatter, body = parse_frontmatter(content)
    
    return ClaudeSkill(
        name=frontmatter.get("name", skill_dir.name),
        description=frontmatter.get("description", ""),
        content=body,
        scripts_dir=skill_dir / "scripts",
        data_dir=skill_dir / "data",
    )
```

---

## 3. Claude Plugins 格式详解

### 3.1 目录结构

```
<plugin>/
├── .claude-plugin/
│   └── manifest.json       # 插件元数据（可选）
├── commands/
│   └── <command>.md        # 命令定义
├── hooks/
│   ├── hooks.json          # 钩子配置
│   └── <hook>.sh           # 钩子脚本
├── scripts/
│   └── <script>.sh         # 辅助脚本
└── README.md
```

### 3.2 命令定义格式 (commands/*.md)

```markdown
---
description: "Command description"
argument-hint: "PROMPT [--option VALUE]"
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/scripts/xxx.sh:*)"]
hide-from-slash-command-tool: "true"
---

# Command Title

（命令说明和执行模板）

```!
"${CLAUDE_PLUGIN_ROOT}/scripts/xxx.sh" $ARGUMENTS
```
```

### 3.3 Hooks 机制

```json
// hooks/hooks.json
{
  "description": "Hook description",
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/stop-hook.sh"
          }
        ]
      }
    ]
  }
}
```

**支持的 Hook 类型**:
- `Stop`: 会话结束前触发
- `PreToolCall`: 工具调用前触发
- `PostToolCall`: 工具调用后触发

### 3.4 兼容策略

```python
# wolo/plugin/claude_loader.py

@dataclass
class ClaudePlugin:
    """Claude 格式的 Plugin"""
    name: str
    version: str
    install_path: Path
    commands: dict[str, ClaudeCommand]
    hooks: dict[str, list[ClaudeHook]]
    enabled: bool


@dataclass
class ClaudeCommand:
    """Claude Plugin 命令"""
    name: str
    description: str
    argument_hint: str
    allowed_tools: list[str]
    content: str


def load_claude_plugin(plugin_dir: Path) -> ClaudePlugin:
    """加载 Claude 格式的 Plugin"""
    commands = {}
    for cmd_file in (plugin_dir / "commands").glob("*.md"):
        cmd = parse_command_md(cmd_file)
        commands[cmd.name] = cmd
    
    hooks = {}
    hooks_json = plugin_dir / "hooks" / "hooks.json"
    if hooks_json.exists():
        hooks = parse_hooks_json(hooks_json)
    
    return ClaudePlugin(
        name=plugin_dir.name,
        version="unknown",
        install_path=plugin_dir,
        commands=commands,
        hooks=hooks,
        enabled=True,
    )
```

---

## 4. MCP 配置兼容

### 4.1 Claude Desktop MCP 配置

Claude Desktop 的 MCP 配置通常在：
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "web-search": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-web-search"],
      "env": {
        "BRAVE_API_KEY": "xxx"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-filesystem", "/path/to/dir"]
    }
  }
}
```

### 4.2 兼容策略

```python
# wolo/mcp/claude_config.py

def load_claude_mcp_config() -> dict[str, MCPServerConfig]:
    """加载 Claude Desktop 的 MCP 配置"""
    config_paths = [
        Path.home() / ".config" / "claude" / "claude_desktop_config.json",
        Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
    ]
    
    for path in config_paths:
        if path.exists():
            config = json.loads(path.read_text())
            return parse_mcp_servers(config.get("mcpServers", {}))
    
    return {}


def parse_mcp_servers(servers: dict) -> dict[str, MCPServerConfig]:
    """解析 MCP Server 配置"""
    result = {}
    for name, config in servers.items():
        result[name] = MCPServerConfig(
            name=name,
            command=config.get("command", ""),
            args=config.get("args", []),
            env=config.get("env", {}),
            transport=TransportType.STDIO,
            enabled=True,
        )
    return result
```

---

## 5. Wolo 配置设计

### 5.1 统一配置文件

```yaml
# ~/.wolo/config.yaml 或 .wolo/config.yaml

# Claude 兼容模式
claude:
  enabled: true                    # 启用 Claude 兼容
  config_dir: ~/.claude            # Claude 配置目录
  
  # 加载 Claude Skills
  skills:
    enabled: true
    load_from_claude: true         # 从 ~/.claude/skills 加载
  
  # 加载 Claude Plugins
  plugins:
    enabled: true
    load_from_claude: true         # 从 ~/.claude/plugins 加载
    enabled_plugins: []            # 留空则使用 settings.json 中的配置
  
  # 加载 Claude MCP 配置
  mcp:
    enabled: true
    load_from_claude_desktop: true # 从 claude_desktop_config.json 加载

# Wolo 原生 MCP 配置（优先级高于 Claude）
mcp:
  enabled: true
  servers:
    # 可以覆盖或添加新的 MCP Server
    custom-server:
      command: "python"
      args: ["-m", "my_mcp_server"]

# Wolo 原生 Plugin 配置
plugins:
  enabled: true
  directories:
    - ~/.wolo/plugins
    - ./.wolo/plugins

# Wolo 原生 Skill 配置
skills:
  enabled: true
  directories:
    - ~/.wolo/skills
    - ./.wolo/skills
```

### 5.2 配置加载优先级

```
1. 命令行参数 (最高)
2. 项目级配置 (.wolo/config.yaml)
3. 用户级配置 (~/.wolo/config.yaml)
4. Claude 配置 (~/.claude/*, claude_desktop_config.json)
5. 默认值 (最低)
```

---

## 6. Node/NPX 依赖处理

### 6.1 问题分析

MCP Server 通常使用 Node.js 实现，通过 `npx` 启动：

```bash
npx -y @anthropic/mcp-server-web-search
```

这对纯 Python 项目带来挑战：
1. 用户可能没有安装 Node.js
2. Python 包管理器无法管理 Node 依赖
3. 跨平台兼容性问题

### 6.2 解决方案

#### 方案 A: 运行时检测 + 优雅降级

```python
# wolo/mcp/node_check.py

import shutil
import subprocess
from typing import Optional


def check_node_available() -> bool:
    """检查 Node.js 是否可用"""
    return shutil.which("node") is not None


def check_npx_available() -> bool:
    """检查 npx 是否可用"""
    return shutil.which("npx") is not None


def get_node_version() -> Optional[str]:
    """获取 Node.js 版本"""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def ensure_node_available() -> bool:
    """
    确保 Node.js 可用。
    
    如果不可用，打印友好的安装提示。
    """
    if check_npx_available():
        return True
    
    print("⚠️  Node.js/npx not found")
    print("")
    print("Some MCP servers require Node.js. To install:")
    print("")
    print("  # macOS (Homebrew)")
    print("  brew install node")
    print("")
    print("  # Ubuntu/Debian")
    print("  curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -")
    print("  sudo apt-get install -y nodejs")
    print("")
    print("  # Arch/Manjaro")
    print("  sudo pacman -S nodejs npm")
    print("")
    print("  # Windows")
    print("  winget install OpenJS.NodeJS.LTS")
    print("")
    
    return False
```

#### 方案 B: 纯 Python MCP Server 替代

对于常用功能，提供纯 Python 实现的 MCP Server：

```python
# wolo/mcp/builtin_servers/web_search.py

"""
纯 Python 实现的 Web Search MCP Server。
作为 @anthropic/mcp-server-web-search 的替代。
"""

from mcp.server import Server
from mcp.types import Tool, TextContent
import aiohttp


async def create_web_search_server() -> Server:
    """创建 Web Search MCP Server"""
    server = Server("wolo-web-search")
    
    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name="web_search",
                description="Search the web",
                inputSchema={...},
            ),
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name == "web_search":
            return await do_search(arguments["query"])
    
    return server
```

#### 方案 C: 混合策略（推荐）

```yaml
# ~/.wolo/config.yaml

mcp:
  # Node.js 依赖处理策略
  node_strategy: "auto"  # auto | require | skip | python_fallback
  
  # auto: 有 Node 就用，没有就跳过需要 Node 的 Server
  # require: 必须有 Node，否则报错
  # skip: 跳过所有需要 Node 的 Server
  # python_fallback: 尝试使用 Python 替代实现
  
  servers:
    web-search:
      # 优先使用 Node 版本
      command: "npx"
      args: ["-y", "@anthropic/mcp-server-web-search"]
      
      # Python 备选（当 Node 不可用时）
      python_fallback:
        module: "wolo.mcp.builtin_servers.web_search"
```

### 6.3 Python 包发布策略

```toml
# pyproject.toml

[project]
name = "wolo"
dependencies = [
    # 核心依赖
    "aiohttp>=3.8.0",
    "pyyaml>=6.0",
    # ...
]

[project.optional-dependencies]
# MCP 支持（包含纯 Python MCP Server）
mcp = [
    "mcp>=0.1.0",  # MCP Python SDK
]

# 完整功能（包含所有可选功能）
full = [
    "wolo[mcp]",
    "pillow>=12.0.0",
    "pymupdf>=1.26.0",
]
```

安装方式：

```bash
# 基础安装
pip install wolo

# 包含 MCP 支持
pip install wolo[mcp]

# 完整安装
pip install wolo[full]
```

### 6.4 文档说明

```markdown
# README.md

## MCP Server 支持

Wolo 支持 MCP (Model Context Protocol) 扩展。

### Node.js MCP Servers

许多 MCP Server 使用 Node.js 实现。如果你想使用这些 Server：

1. 安装 Node.js (推荐 LTS 版本)
2. 配置 MCP Server

```yaml
# ~/.wolo/config.yaml
mcp:
  servers:
    web-search:
      command: "npx"
      args: ["-y", "@anthropic/mcp-server-web-search"]
```

### 纯 Python 替代

对于没有 Node.js 的环境，Wolo 提供部分功能的纯 Python 实现：

```yaml
mcp:
  node_strategy: "python_fallback"
```

支持的 Python 替代：
- `web_search` - 网络搜索
- `web_fetch` - 网页获取
```

---

## 7. 实现计划

### 7.1 第一阶段: Claude 配置读取

| 任务 | 优先级 | 预计工时 |
|------|--------|----------|
| Claude settings.json 解析 | P0 | 2h |
| Claude Skills 加载器 | P0 | 4h |
| Claude Plugins 加载器 | P1 | 6h |
| Claude MCP 配置加载 | P0 | 2h |
| 配置合并逻辑 | P0 | 4h |
| 测试 | P0 | 4h |

### 7.2 第二阶段: MCP 客户端

| 任务 | 优先级 | 预计工时 |
|------|--------|----------|
| MCP 协议实现 | P0 | 8h |
| Stdio Transport | P0 | 4h |
| Node.js 检测 | P0 | 2h |
| Server Manager | P0 | 4h |
| 测试 | P0 | 4h |

### 7.3 第三阶段: Python 备选实现

| 任务 | 优先级 | 预计工时 |
|------|--------|----------|
| Web Search Server | P1 | 4h |
| Web Fetch Server | P1 | 4h |
| Filesystem Server | P2 | 4h |
| 测试 | P1 | 4h |

### 7.4 第四阶段: 集成与文档

| 任务 | 优先级 | 预计工时 |
|------|--------|----------|
| Tool Registry 集成 | P0 | 4h |
| Agent 集成 | P0 | 4h |
| UI 集成 | P1 | 4h |
| 文档编写 | P1 | 4h |

---

## 8. 文件结构

```
wolo/
├── claude/                     # Claude 兼容层
│   ├── __init__.py
│   ├── config.py              # Claude 配置读取
│   ├── skill_loader.py        # Claude Skill 加载
│   ├── plugin_loader.py       # Claude Plugin 加载
│   └── mcp_config.py          # Claude MCP 配置
├── mcp/
│   ├── __init__.py
│   ├── client.py              # MCP Client
│   ├── transport.py           # 传输层
│   ├── server_manager.py      # Server 管理
│   ├── node_check.py          # Node.js 检测
│   └── builtin_servers/       # 纯 Python MCP Server
│       ├── __init__.py
│       ├── web_search.py
│       └── web_fetch.py
├── skill/
│   ├── __init__.py
│   ├── manager.py             # Skill 管理
│   └── executor.py            # Skill 执行
└── config.py                  # 统一配置管理
```

---

## 9. 配置示例

### 9.1 最简配置（使用 Claude 配置）

```yaml
# ~/.wolo/config.yaml

claude:
  enabled: true
```

这将自动：
- 加载 `~/.claude/skills/` 中的 Skills
- 加载 `~/.claude/plugins/` 中已启用的 Plugins
- 加载 Claude Desktop 的 MCP 配置

### 9.2 混合配置

```yaml
# ~/.wolo/config.yaml

claude:
  enabled: true
  skills:
    enabled: true
  plugins:
    enabled: false  # 不使用 Claude Plugins
  mcp:
    enabled: true

# 添加 Wolo 自己的 MCP Server
mcp:
  servers:
    my-custom-server:
      command: "python"
      args: ["-m", "my_server"]
```

### 9.3 纯 Wolo 配置（不使用 Claude）

```yaml
# ~/.wolo/config.yaml

claude:
  enabled: false

mcp:
  enabled: true
  node_strategy: "python_fallback"
  servers:
    web-search:
      python_fallback:
        module: "wolo.mcp.builtin_servers.web_search"

skills:
  directories:
    - ~/.wolo/skills
```

---

## 10. 总结

### 10.1 可行性

| 功能 | 兼容性 | 说明 |
|------|--------|------|
| Claude Skills | ✅ 完全兼容 | Markdown + Shell 格式，易于解析 |
| Claude Plugins | ⚠️ 部分兼容 | Commands 可兼容，Hooks 需要适配 |
| Claude MCP | ✅ 完全兼容 | 标准 MCP 协议 |
| Node.js 依赖 | ⚠️ 可选 | 提供 Python 备选方案 |

### 10.2 优势

1. **用户体验**: 已有 Claude 用户无需重新配置
2. **生态复用**: 可以使用 Claude 生态的 Skills 和 Plugins
3. **灵活性**: 可以混合使用 Claude 和 Wolo 原生配置
4. **渐进式**: Node.js 是可选的，纯 Python 环境也能工作

### 10.3 风险

1. **Claude 格式变更**: Claude 可能更新配置格式
2. **Plugin Hooks**: 复杂的 Hooks 可能难以完全兼容
3. **Node.js 依赖**: 部分用户可能不愿安装 Node.js

### 10.4 建议

1. **优先实现 Skills 和 MCP**: 这两个格式稳定且实用
2. **Plugins 作为可选**: 复杂度较高，可以后续支持
3. **提供 Python 备选**: 确保纯 Python 环境可用
4. **文档清晰**: 说明各种配置方式的优缺点
