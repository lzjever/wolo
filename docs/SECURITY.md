# Wolo 安全策略

本文档详细说明 Wolo 采取的安全机制以及用户可配置的安全选项。

---

## 目录

1. [安全架构概述](#1-安全架构概述)
2. [文件路径保护 (PathGuard)](#2-文件路径保护-pathguard)
3. [Shell 命令风险检测](#3-shell-命令风险检测)
4. [Session ID 安全](#4-session-id-安全)
5. [内存数据安全](#5-内存数据安全)
6. [Wild 模式](#6-wild-模式)
7. [用户配置选项](#7-用户配置选项)
8. [最佳实践建议](#8-最佳实践建议)

---

## 1. 安全架构概述

Wolo 采用**多层防御**策略：

```
┌─────────────────────────────────────────────────────────────┐
│                      用户/CLI 输入                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  第一层: Session ID 验证                                     │
│  - 防止路径遍历攻击                                          │
│  - 禁止 / \ .. 等特殊字符                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  第二层: PathGuard 路径保护                                  │
│  - 写入操作需要路径白名单验证                                │
│  - 读取操作默认允许                                          │
│  - 支持用户确认机制                                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  第三层: Shell 高风险命令检测                                │
│  - 检测 rm -rf /、mkfs、dd 等危险命令                        │
│  - 需要用户确认才能执行                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  第四层: 文件修改检测 (FileTime)                             │
│  - 检测外部修改冲突                                          │
│  - 防止覆盖他人更改                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 文件路径保护 (PathGuard)

### 2.1 核心原则

- **读取操作**：默认允许，无需确认
- **写入操作**：需要路径白名单验证或用户确认

### 2.2 路径白名单优先级

从高到低：

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 | workdir (`-C/--workdir`) | 工作目录及其子目录 |
| 2 | `/tmp` | 默认安全目录 |
| 3 | CLI 路径 (`-P/--allow-path`) | 命令行指定的路径 |
| 4 | 配置文件路径 | `path_safety.allowed_write_paths` |
| 5 | 会话确认目录 | 当前会话中用户已确认的目录 |

### 2.3 工作流程

```
写入请求 → 检查白名单 → 在白名单内? → 是 → 允许执行
                           │
                           否
                           │
                           ▼
                    需要用户确认 → 用户同意? → 是 → 添加到确认目录 → 允许执行
                                        │
                                        否
                                        │
                                        ▼
                                    拒绝执行
```

### 2.4 确认限制

- 每个会话最多确认 `max_confirmations_per_session` 个目录（默认 10）
- 达到限制后，新的写入请求将被自动拒绝

### 2.5 审计日志

启用 `audit_denied: true` 时，所有被拒绝的操作会记录到审计日志：

```yaml
path_safety:
  audit_denied: true
  audit_log_file: ~/.wolo/path_audit.log
```

---

## 3. Shell 命令风险检测

### 3.1 高风险命令模式

以下命令模式被识别为高风险，需要额外确认：

| ID | 模式 | 说明 |
|----|------|------|
| `rm_root_like` | `rm -rf /` | 根目录递归删除 |
| `mkfs_disk` | `mkfs` | 磁盘格式化 |
| `dd_to_block_device` | `dd ... of=/dev/` | 块设备原始写入 |
| `shutdown_or_reboot` | `shutdown`, `reboot`, `halt` | 系统关机/重启 |
| `curl_pipe_shell` | `curl ... \| sh` | 远程脚本管道执行 |
| `git_reset_hard` | `git reset --hard` | 破坏性 Git 重置 |

### 3.2 确认机制

- 高风险命令在执行前会显示警告并要求用户确认
- 同一会话内，相同类型的风险命令只需确认一次
- Wild 模式下跳过所有确认

---

## 4. Session ID 安全

### 4.1 验证规则

Session ID 必须满足以下条件：

```python
# 禁止的字符/模式：
- '/' 或 '\\'     # 路径分隔符
- '..'            # 路径遍历
- 以 '.' 开头      # 隐藏文件
- 空字符串
```

### 4.2 示例

```bash
# 有效
wolo -r "MySession_260213_123456" "prompt"
wolo -s "project-alpha" "prompt"

# 无效 - 会被拒绝
wolo -r "../../../etc/passwd"      # 路径遍历
wolo -s "/tmp/malicious"           # 路径分隔符
wolo -s ".hidden_session"          # 隐藏文件
```

### 4.3 自动生成的 Session ID

自动生成的 Session ID 格式：`{AgentName}_{YYMMDD}_{HHMMSS}`

- AgentName 来自预定义列表，不包含特殊字符
- 时间戳格式固定，无路径遍历风险

---

## 5. 内存数据安全

### 5.1 Memory 文件名安全

Memory 文件名通过 `_slugify()` 函数处理，过滤所有危险字符：

```python
# 被替换为 '-' 的字符：
/ \ : * ? " < > | . 空格

# 示例：
"../../../etc/passwd" → "etc-passwd"
"/tmp/malicious"      → "tmp-malicious"
```

### 5.2 文件写入安全

- 使用临时文件 + 原子重命名模式
- 防止写入中断导致的数据损坏

```python
temp_path = path.with_suffix(".tmp")
# 写入到临时文件...
temp_path.rename(path)  # 原子操作
```

### 5.3 LTM (长期记忆) 配置

```yaml
ltm:
  enabled: true              # 是否启用长期记忆
  storage_dir: ~/.wolo/memories  # 存储目录
  max_memories: 1000         # 最大记忆数量
  max_ltm_size: 12000        # 单条记忆最大字符数
```

---

## 6. Wild 模式

### 6.1 说明

Wild 模式**绕过所有安全检查**：

- 跳过 PathGuard 路径验证
- 跳过 Shell 高风险命令确认
- 跳过文件修改检测 (FileTime)
- 跳过工具权限检查

### 6.2 启用方式

```bash
# 方式 1: 命令行参数
wolo --wild "your prompt"
wolo -W "your prompt"

# 方式 2: 环境变量
WOLO_WILD_MODE=1 wolo "your prompt"

# 方式 3: 配置文件
path_safety:
  wild_mode: true
```

### 6.3 SOLO 模式自动 Wild

SOLO 模式（默认）会自动启用 Wild 模式：

```bash
wolo "prompt"  # SOLO 模式，自动启用 --wild
```

这是为了支持自动化脚本场景。如果需要安全检查，请使用：

```bash
wolo --coop "prompt"   # COOP 模式，保留安全检查
wolo --repl "prompt"   # REPL 模式，保留安全检查
```

### 6.4 ⚠️ 警告

> **Wild 模式仅应在可信环境中使用！**
>
> 在 Wild 模式下，AI 可以执行任意文件操作和 Shell 命令，可能导致数据丢失或系统损坏。

---

## 7. 用户配置选项

### 7.1 配置文件位置

配置文件按以下顺序查找（优先级从高到低）：

1. `{当前目录}/.wolo/config.yaml` - 项目本地配置
2. `~/.wolo/config.yaml` - 用户全局配置

当项目本地配置存在时，会话和记忆数据也会存储在 `.wolo/` 目录中，实现完全隔离。

### 7.2 完整安全配置示例

```yaml
# ~/.wolo/config.yaml 或 .wolo/config.yaml

# 路径安全配置
path_safety:
  # 允许无需确认即可写入的路径
  allowed_write_paths:
    - ~/projects
    - ~/workspace
    - /data/shared

  # 每个会话最大确认次数
  max_confirmations_per_session: 10

  # 是否记录被拒绝的操作
  audit_denied: true

  # 审计日志文件路径
  audit_log_file: ~/.wolo/path_audit.log

  # Wild 模式（绕过所有安全检查）
  wild_mode: false

# 长期记忆配置
ltm:
  enabled: true
  storage_dir: ~/.wolo/memories
  max_memories: 1000
  max_ltm_size: 12000
```

### 7.3 命令行安全选项

```bash
# 添加临时允许路径
wolo -P ~/temp_project "prompt"
wolo --allow-path /data/workspace "prompt"

# 设置工作目录（自动添加到白名单）
wolo -C ~/myproject "prompt"
wolo --workdir ~/myproject "prompt"

# 启用 Wild 模式
wolo -W "prompt"
wolo --wild "prompt"
```

---

## 8. 最佳实践建议

### 8.1 生产环境

```yaml
path_safety:
  allowed_write_paths:
    - /var/www/html
    - /opt/myapp
  max_confirmations_per_session: 5
  audit_denied: true
  wild_mode: false
```

### 8.2 开发环境

```yaml
path_safety:
  allowed_write_paths:
    - ~/projects
    - ~/code
  max_confirmations_per_session: 20
  audit_denied: false
  wild_mode: false
```

### 8.3 CI/CD 环境

```bash
# 使用 Wild 模式 + 受限环境
wolo --wild --workdir /workspace "automated task"
```

### 8.4 项目隔离

对于需要完全隔离的项目：

```bash
# 在项目目录创建 .wolo/config.yaml
mkdir -p .wolo
cat > .wolo/config.yaml << 'EOF'
endpoints:
  - name: default
    model: gpt-4
    api_base: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}

path_safety:
  allowed_write_paths:
    - .  # 当前项目目录
EOF

# 所有数据将存储在 .wolo/ 中，与 ~/.wolo/ 完全隔离
wolo "your prompt"
```

---

## 附录：安全检查清单

在部署 Wolo 之前，建议检查以下项目：

- [ ] 已配置 `allowed_write_paths` 限制写入范围
- [ ] 已设置合理的 `max_confirmations_per_session`
- [ ] 已启用 `audit_denied` 用于安全审计
- [ ] 仅在可信环境中使用 `wild_mode: true`
- [ ] 已审查 LTM 存储目录的权限
- [ ] 已了解 SOLO 模式会自动启用 Wild 模式
