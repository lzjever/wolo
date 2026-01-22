# Wolo 历史压缩功能优化计划

## 执行摘要

本计划旨在将 wolo 的历史压缩功能向 opencode 的实现对齐，优先实现**最容易实现且效果最显著**的改进。计划分为三个阶段，从最紧急的问题修复到高级功能增强。

---

## 一、现状分析

### 1.1 当前实现的关键问题

根据对比分析，wolo 的压缩实现存在以下关键问题：

1. **❌ 历史丢失（最严重）**
   - 压缩后原始消息被替换，无法恢复
   - 缺少审计追踪能力
   - 无法调试压缩问题

2. **❌ 配置硬编码**
   - `recent_exchanges = 6` 固定值
   - `RESERVED_TOKENS = 2000` 固定值
   - 检查间隔 `step % 5 == 0` 固定值
   - 无法根据场景调整

3. **❌ Token 估算不准确**
   - 字符估算（4字符=1token）误差大
   - 不区分代码、英文、中文的token密度
   - 可能导致过早或过晚压缩

4. **❌ 摘要质量受限**
   - 500字符硬限制可能截断重要信息
   - Prompt 过于简单
   - 无结构化输出

5. **❌ 触发机制不精确**
   - 每5步才检查一次，可能错过溢出
   - 基于估算而非实际token使用
   - 无手动触发机制

### 1.2 当前架构优势

✅ **消息持久化完善**
- 每个消息单独文件存储
- 支持原子写入和文件锁
- 已有完整的序列化/反序列化机制

✅ **代码结构清晰**
- `compaction.py` 模块化良好
- `session.py` 存储层完善
- `agent.py` 集成点明确

✅ **错误处理基础**
- 已有 try-catch 回退机制
- 日志记录完善

---

## 二、优化策略与优先级

### 2.1 优先级评估矩阵

| 改进项 | 实现难度 | 效果影响 | 优先级 | 预计工作量 |
|--------|---------|---------|--------|-----------|
| **保存压缩历史** | 低 | 极高 | 🔴 P0 | 2-3小时 |
| **配置化参数** | 低 | 高 | 🔴 P0 | 1-2小时 |
| **改进摘要质量** | 低 | 高 | 🟡 P1 | 1-2小时 |
| **改进触发机制** | 中 | 高 | 🟡 P1 | 3-4小时 |
| **Token估算改进** | 中 | 中 | 🟢 P2 | 4-6小时 |
| **工具输出修剪** | 高 | 中 | 🟢 P2 | 6-8小时 |
| **手动触发** | 低 | 中 | 🟢 P2 | 1-2小时 |

### 2.2 分阶段实施策略

**阶段一（P0 - 立即实施）**：修复关键问题，最小化改动
- 保存压缩历史
- 配置化参数
- 改进摘要质量

**阶段二（P1 - 短期优化）**：提升精确度和用户体验
- 改进触发机制
- Token估算改进

**阶段三（P2 - 长期增强）**：高级功能和完整对齐
- 工具输出修剪
- 手动触发
- 事件系统（可选）

---

## 三、详细实施计划

## 阶段一：关键问题修复（P0）

### 任务 1.1：保存压缩历史 ⭐⭐⭐

**目标**：保留原始消息，添加压缩元数据

**实现方案**：

#### 方案A：在消息中添加压缩标记（推荐）

**优点**：
- 最小改动
- 利用现有存储机制
- 无需额外存储空间

**实现步骤**：

1. **扩展 Message 类**（`session.py`）：
```python
@dataclass
class Message:
    id: str
    role: str
    parts: list[Part]
    timestamp: float
    finished: bool = False
    finish_reason: str = ""
    reasoning_content: str = ""
    # 新增字段
    metadata: dict = field(default_factory=dict)  # 存储压缩信息
```

2. **修改 `compact_messages` 函数**（`compaction.py`）：
```python
async def compact_messages(
    messages: list[Message],
    config: Config,
    max_tokens: int | None = None,
    session_id: str | None = None  # 新增参数
) -> list[Message]:
    # ... 现有逻辑 ...
    
    # 创建压缩摘要消息
    summary_msg = Message(role="user")
    summary_msg.parts.append(TextPart(
        text=f"[Previous conversation summary: {summary}]"
    ))
    
    # 添加压缩元数据
    summary_msg.metadata = {
        "compaction": True,
        "compacted_at": time.time(),
        "original_message_count": len(messages),
        "preserved_message_count": len(recent_messages),
        "compacted_message_ids": [msg.id for msg in to_summarize],
        "preserved_message_ids": [msg.id for msg in recent_messages]
    }
    
    compacted.append(summary_msg)
    compacted.extend(recent_messages)
    
    # 标记被压缩的消息（不删除，只标记）
    if session_id:
        storage = get_storage()
        for msg in to_summarize:
            if not msg.metadata.get("compacted"):
                msg.metadata["compacted"] = True
                msg.metadata["compacted_at"] = time.time()
                msg.metadata["compaction_summary_id"] = summary_msg.id
                storage.save_message(session_id, msg)  # 更新消息元数据
    
    return compacted
```

3. **修改调用点**（`agent.py`）：
```python
# 在 _call_llm 中传递 session_id
messages_to_use = await compact_messages(
    messages, config, limit, session_id=session_id
)
```

4. **添加查询函数**（`session.py`）：
```python
def get_compaction_history(session_id: str) -> list[dict]:
    """获取压缩历史记录"""
    messages = get_session_messages(session_id)
    compactions = []
    for msg in messages:
        if msg.metadata.get("compaction"):
            compactions.append({
                "summary_message_id": msg.id,
                "compacted_at": msg.metadata.get("compacted_at"),
                "original_count": msg.metadata.get("original_message_count"),
                "preserved_count": msg.metadata.get("preserved_message_count"),
                "compacted_ids": msg.metadata.get("compacted_message_ids", []),
            })
    return compactions

def get_original_messages(session_id: str, summary_message_id: str) -> list[Message]:
    """根据压缩摘要消息ID获取原始消息"""
    summary_msg = get_message(session_id, summary_message_id)
    if not summary_msg or not summary_msg.metadata.get("compaction"):
        return []
    
    compacted_ids = summary_msg.metadata.get("compacted_message_ids", [])
    all_messages = get_session_messages(session_id)
    return [msg for msg in all_messages if msg.id in compacted_ids]
```

**测试要点**：
- 压缩后原始消息仍然存在
- 元数据正确保存
- 可以查询压缩历史
- 可以恢复原始消息

**预计工作量**：2-3小时

---

### 任务 1.2：配置化参数 ⭐⭐

**目标**：将硬编码值改为可配置参数

**实现步骤**：

1. **扩展 Config 类**（`config.py`）：
```python
@dataclass
class CompactionConfig:
    """压缩配置"""
    enabled: bool = True
    check_interval: int = 5  # 每N步检查一次
    recent_exchanges: int = 6  # 保留最近N轮对话
    reserved_tokens: int = 2000  # 保留的token数
    summary_max_length: int | None = None  # None表示不限制
    auto_compact: bool = True  # 是否自动压缩

@dataclass
class Config:
    # ... 现有字段 ...
    compaction: CompactionConfig = field(default_factory=CompactionConfig)
```

2. **从配置文件加载**（`config.py`）：
```python
@classmethod
def from_env(cls, ...) -> "Config":
    # ... 现有逻辑 ...
    
    # 加载压缩配置
    compaction_data = config_data.get("compaction", {})
    compaction_config = CompactionConfig(
        enabled=compaction_data.get("enabled", True),
        check_interval=compaction_data.get("check_interval", 5),
        recent_exchanges=compaction_data.get("recent_exchanges", 6),
        reserved_tokens=compaction_data.get("reserved_tokens", 2000),
        summary_max_length=compaction_data.get("summary_max_length"),
        auto_compact=compaction_data.get("auto_compact", True),
    )
    
    return cls(
        # ... 现有参数 ...
        compaction=compaction_config,
    )
```

3. **更新 `compaction.py`**：
```python
# 移除硬编码常量
# recent_exchanges = 6  # 删除
# RESERVED_TOKENS = 2000  # 删除

async def compact_messages(
    messages: list[Message],
    config: Config,
    max_tokens: int | None = None,
    session_id: str | None = None
) -> list[Message]:
    # 使用配置值
    if max_tokens is None:
        max_tokens = config.max_tokens - config.compaction.reserved_tokens
    
    # ... 其他逻辑 ...
    
    recent_exchanges = config.compaction.recent_exchanges
    # ... 使用 recent_exchanges ...
```

4. **更新 `agent.py`**：
```python
async def _call_llm(...):
    # 检查压缩配置
    if not config.compaction.enabled or not config.compaction.auto_compact:
        messages_to_use = messages
    elif step > 0 and step % config.compaction.check_interval == 0:
        # ... 压缩逻辑 ...
```

5. **配置文件示例**（`~/.wolo/config.yaml`）：
```yaml
compaction:
  enabled: true
  check_interval: 3  # 每3步检查一次（更频繁）
  recent_exchanges: 8  # 保留8轮对话
  reserved_tokens: 3000  # 保留更多token
  summary_max_length: null  # 不限制摘要长度
  auto_compact: true
```

**测试要点**：
- 配置正确加载
- 默认值生效
- 配置文件覆盖默认值
- 禁用压缩时正常工作

**预计工作量**：1-2小时

---

### 任务 1.3：改进摘要质量 ⭐⭐

**目标**：提升摘要质量，移除硬限制

**实现步骤**：

1. **改进 Prompt**（`compaction.py`）：
```python
async def _summarize_messages(messages: list[Message], config: Config) -> str:
    # ... 提取对话文本 ...
    
    # 改进的prompt（参考opencode）
    prompt_text = (
        "请详细总结以下对话，重点关注对继续对话有帮助的信息。\n\n"
        "请包含以下内容：\n"
        "1. 我们做了什么（已完成的任务和操作）\n"
        "2. 我们正在做什么（当前进行中的工作）\n"
        "3. 我们正在处理哪些文件\n"
        "4. 接下来要做什么（考虑到新会话无法访问我们的对话历史）\n\n"
        "请保留关键决策、重要上下文和必要的技术细节。\n\n"
        "对话内容：\n"
        + "\n".join(conversation)
    )
```

2. **移除长度限制**：
```python
# 删除或改为配置控制
# if len(summary) > 500:
#     summary = summary[:500] + "..."

summary = "".join(summary_parts).strip()

# 如果配置了最大长度，才限制
if config.compaction.summary_max_length:
    if len(summary) > config.compaction.summary_max_length:
        summary = summary[:config.compaction.summary_max_length] + "..."
```

3. **改进摘要格式**（可选）：
```python
# 可以尝试结构化输出
prompt_text = (
    "请用以下格式总结对话：\n\n"
    "## 已完成的工作\n"
    "[总结已完成的任务]\n\n"
    "## 当前状态\n"
    "[总结当前进行的工作和文件]\n\n"
    "## 下一步计划\n"
    "[总结接下来要做的事情]\n\n"
    "对话内容：\n"
    + "\n".join(conversation)
)
```

**测试要点**：
- 摘要质量提升
- 无长度限制时完整输出
- 有长度限制时正确截断
- 错误处理正常

**预计工作量**：1-2小时

---

## 阶段二：精确度提升（P1）

### 任务 2.1：改进触发机制 ⭐⭐⭐

**目标**：更精确的触发时机，基于实际token使用

**实现步骤**：

1. **添加token使用追踪**（`agent.py`）：
```python
# 在 agent_loop 或 _call_llm 中追踪实际token使用
# 从 LLM 响应中获取实际token数

async def _call_llm(...):
    # ... 调用LLM ...
    
    # 获取实际token使用（如果LLM客户端支持）
    actual_tokens = get_token_usage()  # 假设已有此函数
    if actual_tokens:
        # 更新消息的token信息
        assistant_msg.metadata["tokens"] = {
            "input": actual_tokens.get("input", 0),
            "output": actual_tokens.get("output", 0),
            "total": actual_tokens.get("total", 0),
        }
```

2. **改进触发逻辑**（`agent.py`）：
```python
async def _call_llm(...):
    # 方案A：每次调用后检查（更精确）
    if step > 0:
        # 计算累计token
        total_tokens = sum(
            msg.metadata.get("tokens", {}).get("total", 0) 
            for msg in messages
        )
        # 加上当前估算
        current_estimate = estimate_session_tokens(messages)
        
        limit = config.max_tokens - config.compaction.reserved_tokens
        if total_tokens > limit * 0.8 or current_estimate > limit:
            # 接近或超过限制，触发压缩
            logger.info(f"Token usage high ({total_tokens}/{limit}), compacting...")
            try:
                messages_to_use = await compact_messages(
                    messages, config, limit, session_id
                )
            except Exception as e:
                logger.warning(f"Compaction failed: {e}")
                messages_to_use = messages
    else:
        messages_to_use = messages
```

3. **添加溢出检测函数**（`compaction.py`）：
```python
def is_overflow(
    messages: list[Message],
    config: Config,
    model_limit: int | None = None
) -> bool:
    """
    检查是否溢出context限制
    
    Args:
        messages: 消息列表
        config: 配置
        model_limit: 模型限制（如果为None，使用config.max_tokens）
    
    Returns:
        是否溢出
    """
    limit = (model_limit or config.max_tokens) - config.compaction.reserved_tokens
    
    # 优先使用实际token数
    total_actual = sum(
        msg.metadata.get("tokens", {}).get("total", 0)
        for msg in messages
    )
    
    if total_actual > 0:
        return total_actual > limit
    
    # 回退到估算
    estimated = estimate_session_tokens(messages)
    return estimated > limit
```

4. **更新调用点**：
```python
# 在 _call_llm 中使用
if step > 0 and is_overflow(messages, config):
    messages_to_use = await compact_messages(...)
```

**测试要点**：
- 基于实际token触发
- 估算回退正常
- 阈值设置合理
- 不会过早或过晚触发

**预计工作量**：3-4小时

---

### 任务 2.2：Token估算改进 ⭐⭐

**目标**：提高token估算准确性

**实现步骤**：

1. **添加tiktoken支持**（可选，如果可用）：
```python
# compaction.py
try:
    import tiktoken
    _has_tiktoken = True
except ImportError:
    _has_tiktoken = False
    logger.debug("tiktoken not available, using character-based estimation")

def estimate_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """估算token数，优先使用tiktoken"""
    if not text:
        return 0
    
    if _has_tiktoken:
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception:
            # 回退到字符估算
            pass
    
    # 字符估算（改进版）
    # 中文字符通常1字符=1token，英文4字符=1token
    chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
    other_chars = len(text) - chinese_chars
    return chinese_chars + int(other_chars * 0.25) + 1
```

2. **改进消息token估算**：
```python
def estimate_message_tokens(message: Message, model: str = "gpt-3.5-turbo") -> int:
    """估算消息token数"""
    total = 0
    for part in message.parts:
        if isinstance(part, TextPart):
            total += estimate_tokens(part.text, model)
        elif isinstance(part, ToolPart):
            # 工具调用：名称 + 参数 + 输出
            total += 20  # 基础开销
            if hasattr(part, "input"):
                import json
                total += estimate_tokens(json.dumps(part.input), model)
            if hasattr(part, "output"):
                total += estimate_tokens(part.output, model)
    
    # 消息开销：role + 格式
    total += 10
    return total
```

3. **从配置获取模型名**：
```python
def estimate_session_tokens(
    messages: list[Message],
    model: str | None = None
) -> int:
    """估算会话token数"""
    model = model or "gpt-3.5-turbo"  # 默认值
    return sum(estimate_message_tokens(m, model) for m in messages)

# 在 compact_messages 中使用
async def compact_messages(..., config: Config, ...):
    # 使用配置的模型名
    model_name = config.model  # 或从config获取
    current_tokens = estimate_session_tokens(messages, model_name)
```

**测试要点**：
- tiktoken可用时使用
- 回退机制正常
- 中英文混合文本估算准确
- 与API实际token数接近

**预计工作量**：4-6小时（包含tiktoken集成和测试）

---

## 阶段三：高级功能（P2）

### 任务 3.1：工具输出修剪 ⭐⭐⭐

**目标**：选择性修剪旧工具输出，类似opencode的prune功能

**实现步骤**：

1. **添加修剪函数**（`compaction.py`）：
```python
# 配置常量
PRUNE_PROTECT_TOKENS = 40_000  # 保护最近N tokens的工具输出
PRUNE_MINIMUM_TOKENS = 20_000  # 最小修剪量
PRUNE_PROTECTED_TOOLS = []  # 受保护的工具列表（可配置）

async def prune_tool_outputs(
    messages: list[Message],
    session_id: str,
    config: Config
) -> int:
    """
    修剪旧工具输出，保留最近的重要输出
    
    Returns:
        修剪的token数
    """
    if not config.compaction.enabled:
        return 0
    
    storage = get_storage()
    total_tokens = 0
    pruned_tokens = 0
    to_prune = []
    turns = 0
    
    # 从后往前遍历
    for msg in reversed(messages):
        if msg.role == "user":
            turns += 1
        if turns < 2:  # 保护最近2轮
            continue
        
        # 检查是否已有压缩标记
        if msg.metadata.get("compaction"):
            break
        
        # 检查工具输出
        for part in msg.parts:
            if isinstance(part, ToolPart):
                if part.status == "completed" and part.output:
                    # 检查是否受保护
                    if part.tool in PRUNE_PROTECTED_TOOLS:
                        continue
                    
                    # 检查是否已修剪
                    if part.metadata.get("pruned"):
                        break
                    
                    # 估算token
                    tokens = estimate_tokens(part.output)
                    total_tokens += tokens
                    
                    if total_tokens > PRUNE_PROTECT_TOKENS:
                        pruned_tokens += tokens
                        to_prune.append((msg, part))
    
    # 如果修剪量足够，执行修剪
    if pruned_tokens > PRUNE_MINIMUM_TOKENS:
        for msg, part in to_prune:
            # 标记为已修剪，清空输出
            if not hasattr(part, "metadata"):
                part.metadata = {}
            part.metadata["pruned"] = True
            part.metadata["pruned_at"] = time.time()
            original_output = part.output
            part.output = "[Output pruned to save tokens]"
            
            # 保存更新
            storage.save_message(session_id, msg)
            logger.debug(f"Pruned tool output: {part.tool} ({len(original_output)} chars)")
        
        logger.info(f"Pruned {pruned_tokens} tokens from {len(to_prune)} tool outputs")
        return pruned_tokens
    
    return 0
```

2. **在压缩后调用**（`agent.py`）：
```python
# 在压缩后，尝试修剪
if messages_to_use != messages:
    # 压缩已完成，尝试修剪工具输出
    await prune_tool_outputs(messages_to_use, session_id, config)
```

**测试要点**：
- 保护最近2轮
- 正确修剪旧工具输出
- 受保护工具不被修剪
- 修剪量达到阈值才执行

**预计工作量**：6-8小时

---

### 任务 3.2：手动触发压缩 ⭐

**目标**：添加CLI命令手动触发压缩

**实现步骤**：

1. **添加CLI命令**（`cli.py` 或新建 `cli/commands/compact.py`）：
```python
class CompactCommand(BaseCommand):
    """手动压缩会话历史"""
    
    def setup(self, parser):
        parser.add_argument("session_id", help="会话ID")
        parser.add_argument(
            "--force",
            action="store_true",
            help="强制压缩，即使未超过限制"
        )
    
    async def run(self, args):
        session_id = args.session_id
        config = Config.from_env()
        
        # 获取会话消息
        messages = get_session_messages(session_id)
        if not messages:
            print(f"Session {session_id} has no messages")
            return 1
        
        # 检查是否需要压缩
        if not args.force:
            limit = config.max_tokens - config.compaction.reserved_tokens
            current = estimate_session_tokens(messages)
            if current <= limit:
                print(f"Session size ({current} tokens) within limit ({limit}), no compaction needed")
                print("Use --force to compact anyway")
                return 0
        
        # 执行压缩
        print(f"Compacting session {session_id}...")
        try:
            compacted = await compact_messages(
                messages, config, session_id=session_id
            )
            
            # 更新会话消息
            storage = get_storage()
            session = storage.load_full_session(session_id)
            if session:
                session.messages = compacted
                storage.save_full_session(session)
            
            print(f"Compaction completed: {len(messages)} -> {len(compacted)} messages")
            return 0
        except Exception as e:
            print(f"Compaction failed: {e}")
            return 1
```

2. **注册命令**：
```python
# 在 cli.py 的 main 函数中
subparsers.add_parser("compact", parents=[...]).set_defaults(
    handler=CompactCommand().run
)
```

**测试要点**：
- 命令正确执行
- 强制模式工作
- 错误处理正常
- 消息正确更新

**预计工作量**：1-2小时

---

## 四、实施时间表

### 第一周：阶段一（关键修复）

**Day 1-2**：任务1.1 - 保存压缩历史
- 扩展Message类
- 修改压缩函数
- 添加查询函数
- 编写测试

**Day 3**：任务1.2 - 配置化参数
- 扩展Config类
- 更新压缩逻辑
- 更新配置文件
- 测试配置加载

**Day 4**：任务1.3 - 改进摘要质量
- 改进prompt
- 移除硬限制
- 测试摘要质量

**Day 5**：集成测试和文档
- 端到端测试
- 更新文档
- 代码审查

### 第二周：阶段二（精确度提升）

**Day 1-2**：任务2.1 - 改进触发机制
- 添加token追踪
- 改进触发逻辑
- 测试触发时机

**Day 3-4**：任务2.2 - Token估算改进
- 集成tiktoken（可选）
- 改进估算算法
- 测试准确性

**Day 5**：优化和测试
- 性能测试
- 准确性验证
- 文档更新

### 第三周：阶段三（高级功能，可选）

**Day 1-3**：任务3.1 - 工具输出修剪
- 实现修剪逻辑
- 集成到压缩流程
- 测试修剪效果

**Day 4**：任务3.2 - 手动触发
- 实现CLI命令
- 测试命令功能

**Day 5**：最终测试和文档
- 完整功能测试
- 性能评估
- 文档完善

---

## 五、风险评估与缓解

### 5.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 消息元数据不兼容 | 高 | 低 | 向后兼容设计，旧消息无metadata时使用默认值 |
| 配置加载失败 | 中 | 低 | 提供默认值，优雅降级 |
| Token估算误差大 | 中 | 中 | 使用实际token优先，估算作为回退 |
| 压缩后性能下降 | 低 | 低 | 压缩是异步操作，不影响主流程 |

### 5.2 数据风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 压缩后数据丢失 | 极高 | 低 | 保留原始消息，只添加标记 |
| 元数据损坏 | 中 | 低 | 使用JSON格式，验证数据完整性 |
| 存储空间增加 | 低 | 中 | 可选：压缩后归档旧消息 |

### 5.3 实施风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 开发时间超期 | 中 | 中 | 分阶段实施，优先关键功能 |
| 测试不充分 | 高 | 中 | 每个任务完成后立即测试 |
| 向后兼容问题 | 高 | 低 | 保持API兼容，添加新字段时使用默认值 |

---

## 六、成功指标

### 6.1 功能指标

- ✅ 压缩后原始消息100%保留
- ✅ 可以查询所有压缩历史
- ✅ 配置参数100%可配置
- ✅ 摘要质量提升（人工评估）
- ✅ Token估算误差 < 20%（与API实际值对比）

### 6.2 性能指标

- ✅ 压缩操作不影响主流程性能
- ✅ 压缩后token减少 > 50%
- ✅ 触发时机准确（不早不晚）

### 6.3 质量指标

- ✅ 所有新功能有单元测试
- ✅ 集成测试覆盖主要场景
- ✅ 代码覆盖率 > 80%
- ✅ 文档完整更新

---

## 七、后续优化方向

### 7.1 高级功能（未来考虑）

1. **重要性评估**
   - 基于消息重要性选择保留/压缩
   - 使用embedding计算相似度
   - 保留关键决策点

2. **增量压缩**
   - 不总是全量压缩
   - 只压缩最旧的部分
   - 保留更多中间历史

3. **压缩策略选择**
   - 根据会话类型选择策略
   - 代码会话 vs 对话会话
   - 自适应参数调整

4. **事件系统**
   - 发布压缩事件
   - 允许插件监听
   - 支持自定义压缩逻辑

### 7.2 性能优化

1. **异步压缩**
   - 后台压缩
   - 不阻塞主流程
   - 渐进式压缩

2. **缓存优化**
   - 缓存token估算结果
   - 缓存压缩历史查询
   - 减少重复计算

3. **存储优化**
   - 压缩后归档旧消息
   - 可选：删除已压缩消息（用户确认）
   - 压缩存储格式

---

## 八、总结

本优化计划采用**渐进式改进**策略，优先解决最关键的问题（历史丢失），然后逐步提升精确度和用户体验。三个阶段的设计确保了：

1. **快速见效**：阶段一解决核心问题，立即带来价值
2. **风险可控**：每个阶段独立，可以随时停止
3. **向后兼容**：所有改动保持API兼容
4. **易于测试**：每个任务都有明确的测试要点

**建议**：立即开始阶段一的实施，预计一周内可以完成关键修复，显著提升压缩功能的可靠性和可用性。

---

**文档版本**：1.0  
**创建日期**：2025-01-27  
**最后更新**：2025-01-27
