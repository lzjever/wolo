# Wolo 历史压缩功能重构开发规格说明书

**版本**: 1.0  
**状态**: 待开发  
**最后更新**: 2025-01-27

---

## 目录

1. [项目概述](#1-项目概述)
2. [架构设计](#2-架构设计)
3. [数据结构定义](#3-数据结构定义)
4. [接口规格](#4-接口规格)
5. [实现规格](#5-实现规格)
6. [配置规格](#6-配置规格)
7. [测试规格](#7-测试规格)
8. [验收标准](#8-验收标准)

---

## 1. 项目概述

### 1.1 目标

重构 Wolo 的历史压缩功能，实现：
1. **策略模式架构**：支持多种压缩策略，可扩展
2. **历史保留**：压缩后保留原始消息引用
3. **可配置化**：所有参数可通过配置文件调整
4. **高质量摘要**：改进摘要生成
5. **工具输出修剪**：选择性修剪旧工具输出

### 1.2 设计原则

1. **单一职责原则**：每个类/函数只做一件事
2. **开闭原则**：对扩展开放，对修改关闭
3. **依赖倒置**：依赖抽象而非具体实现
4. **策略模式**：压缩策略可插拔
5. **不可变优先**：数据结构尽量不可变

### 1.3 文件结构

```
wolo/
├── compaction/
│   ├── __init__.py           # 模块导出
│   ├── types.py              # 类型定义和数据结构
│   ├── config.py             # 压缩配置
│   ├── token.py              # Token 估算
│   ├── policy/               # 压缩策略
│   │   ├── __init__.py
│   │   ├── base.py           # 策略基类
│   │   ├── summary.py        # 摘要压缩策略
│   │   └── pruning.py        # 工具输出修剪策略
│   ├── manager.py            # 压缩管理器
│   └── history.py            # 压缩历史记录
├── config.py                 # 修改：添加 CompactionConfig
└── session.py                # 修改：添加 metadata 字段
```

---

## 2. 架构设计

### 2.1 类图

```
┌─────────────────────────────────────────────────────────────────┐
│                      CompactionManager                           │
│  ─────────────────────────────────────────────────────────────  │
│  - config: CompactionConfig                                      │
│  - policies: list[CompactionPolicy]                              │
│  - history: CompactionHistory                                    │
│  ─────────────────────────────────────────────────────────────  │
│  + should_compact(messages, session_id) -> CompactionDecision   │
│  + compact(messages, session_id) -> CompactionResult            │
│  + get_history(session_id) -> list[CompactionRecord]            │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 │ uses
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   <<abstract>> CompactionPolicy                  │
│  ─────────────────────────────────────────────────────────────  │
│  + name: str                                                     │
│  + priority: int                                                 │
│  ─────────────────────────────────────────────────────────────  │
│  + should_apply(context: CompactionContext) -> bool             │
│  + apply(context: CompactionContext) -> PolicyResult            │
│  + estimate_savings(context: CompactionContext) -> int          │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 │                               │
                 ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────────┐
│    SummaryCompactionPolicy│   │   ToolOutputPruningPolicy     │
│  ───────────────────────  │   │  ───────────────────────────  │
│  name = "summary"         │   │  name = "tool_pruning"        │
│  priority = 100           │   │  priority = 50                │
│  ───────────────────────  │   │  ───────────────────────────  │
│  + should_apply(...)      │   │  + should_apply(...)          │
│  + apply(...)             │   │  + apply(...)                 │
│  + estimate_savings(...)  │   │  + estimate_savings(...)      │
└───────────────────────────┘   └───────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      CompactionHistory                           │
│  ─────────────────────────────────────────────────────────────  │
│  - storage: SessionStorage                                       │
│  ─────────────────────────────────────────────────────────────  │
│  + add_record(session_id, record: CompactionRecord) -> None     │
│  + get_records(session_id) -> list[CompactionRecord]            │
│  + get_original_messages(session_id, record_id) -> list[Message]│
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       TokenEstimator                             │
│  ─────────────────────────────────────────────────────────────  │
│  + estimate_text(text: str, model: str) -> int                  │
│  + estimate_message(message: Message, model: str) -> int        │
│  + estimate_messages(messages: list[Message], model: str) -> int│
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
Input Messages
      │
      ▼
┌─────────────────┐
│ should_compact  │──── No ────▶ Return Original Messages
└────────┬────────┘
         │ Yes
         ▼
┌─────────────────┐
│ Sort Policies   │ (by priority, descending)
│ by Priority     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ For each Policy │◀─────────────┐
└────────┬────────┘              │
         │                       │
         ▼                       │
┌─────────────────┐              │
│ should_apply?   │── No ────────┤
└────────┬────────┘              │
         │ Yes                   │
         ▼                       │
┌─────────────────┐              │
│ Apply Policy    │              │
└────────┬────────┘              │
         │                       │
         ▼                       │
┌─────────────────┐              │
│ Record History  │              │
└────────┬────────┘              │
         │                       │
         ▼                       │
┌─────────────────┐              │
│ Still Overflow? │── Yes ───────┘
└────────┬────────┘
         │ No
         ▼
   Return Result
```

---

## 3. 数据结构定义

### 3.1 文件: `wolo/compaction/types.py`

```python
"""压缩模块类型定义。

本模块定义所有压缩相关的数据结构。所有数据类均为不可变。
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class CompactionStatus(Enum):
    """压缩操作状态。"""
    NOT_NEEDED = auto()      # 不需要压缩
    APPLIED = auto()         # 已应用压缩
    FAILED = auto()          # 压缩失败
    SKIPPED = auto()         # 跳过（如禁用）


class PolicyType(Enum):
    """压缩策略类型。"""
    SUMMARY = "summary"              # 摘要压缩
    TOOL_PRUNING = "tool_pruning"    # 工具输出修剪
    # 预留扩展
    # EMBEDDING = "embedding"        # 基于embedding的压缩（未来）
    # IMPORTANCE = "importance"      # 基于重要性的压缩（未来）


@dataclass(frozen=True)
class TokenStats:
    """Token 统计信息。
    
    Attributes:
        estimated: 估算的 token 数
        actual: 实际的 token 数（如果可用，否则为 None）
        model: 估算使用的模型名称
    """
    estimated: int
    actual: int | None = None
    model: str = "default"


@dataclass(frozen=True)
class MessageRef:
    """消息引用。
    
    用于在压缩记录中引用原始消息，不包含完整内容。
    
    Attributes:
        id: 消息 ID
        role: 消息角色 ("user" | "assistant")
        timestamp: 消息时间戳
        token_count: 消息的 token 数
    """
    id: str
    role: str
    timestamp: float
    token_count: int


@dataclass(frozen=True)
class CompactionRecord:
    """压缩历史记录。
    
    记录一次压缩操作的完整信息。
    
    Attributes:
        id: 记录唯一 ID（UUID）
        session_id: 会话 ID
        policy: 使用的策略类型
        created_at: 压缩时间戳
        
        # 压缩前后统计
        original_token_count: 原始 token 数
        result_token_count: 压缩后 token 数
        original_message_count: 原始消息数
        result_message_count: 压缩后消息数
        
        # 消息引用
        compacted_message_ids: 被压缩的消息 ID 列表
        preserved_message_ids: 保留的消息 ID 列表
        summary_message_id: 摘要消息 ID（如果创建了摘要）
        
        # 摘要内容
        summary_text: 生成的摘要文本
        
        # 元信息
        config_snapshot: 压缩时的配置快照
    """
    id: str
    session_id: str
    policy: PolicyType
    created_at: float
    
    original_token_count: int
    result_token_count: int
    original_message_count: int
    result_message_count: int
    
    compacted_message_ids: tuple[str, ...]
    preserved_message_ids: tuple[str, ...]
    summary_message_id: str | None
    
    summary_text: str
    
    config_snapshot: dict[str, Any]


@dataclass(frozen=True)
class CompactionContext:
    """压缩上下文。
    
    传递给策略的上下文信息。
    
    Attributes:
        session_id: 会话 ID
        messages: 当前消息列表（只读）
        token_count: 当前 token 数
        token_limit: token 上限
        model: 模型名称
        config: 压缩配置
    """
    session_id: str
    messages: tuple  # tuple[Message, ...]
    token_count: int
    token_limit: int
    model: str
    config: "CompactionConfig"  # forward reference


@dataclass(frozen=True)
class PolicyResult:
    """策略执行结果。
    
    Attributes:
        status: 执行状态
        messages: 处理后的消息列表（如果成功）
        record: 压缩记录（如果成功）
        error: 错误信息（如果失败）
    """
    status: CompactionStatus
    messages: tuple | None = None  # tuple[Message, ...] | None
    record: CompactionRecord | None = None
    error: str | None = None


@dataclass(frozen=True)
class CompactionDecision:
    """压缩决策。
    
    should_compact 方法的返回值。
    
    Attributes:
        should_compact: 是否需要压缩
        reason: 决策原因
        current_tokens: 当前 token 数
        limit_tokens: token 上限
        overflow_ratio: 溢出比例（current / limit）
        applicable_policies: 可应用的策略列表
    """
    should_compact: bool
    reason: str
    current_tokens: int
    limit_tokens: int
    overflow_ratio: float
    applicable_policies: tuple[PolicyType, ...]


@dataclass(frozen=True)
class CompactionResult:
    """压缩总结果。
    
    compact 方法的返回值。
    
    Attributes:
        status: 最终状态
        original_messages: 原始消息数
        result_messages: 结果消息列表
        records: 生成的压缩记录列表（可能多次压缩）
        total_tokens_saved: 总共节省的 token 数
        policies_applied: 应用的策略列表
        error: 错误信息（如果有）
    """
    status: CompactionStatus
    original_messages: tuple  # tuple[Message, ...]
    result_messages: tuple    # tuple[Message, ...]
    records: tuple[CompactionRecord, ...]
    total_tokens_saved: int
    policies_applied: tuple[PolicyType, ...]
    error: str | None = None
```

### 3.2 文件: `wolo/compaction/config.py`

```python
"""压缩配置定义。

所有压缩相关的配置项。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SummaryPolicyConfig:
    """摘要策略配置。
    
    Attributes:
        enabled: 是否启用
        recent_exchanges_to_keep: 保留最近的对话轮数
        summary_max_tokens: 摘要最大 token 数（None 表示不限制）
        summary_prompt_template: 摘要生成的 prompt 模板
        include_tool_calls_in_summary: 摘要中是否包含工具调用信息
    """
    enabled: bool = True
    recent_exchanges_to_keep: int = 6
    summary_max_tokens: int | None = None
    summary_prompt_template: str = ""  # 空字符串使用默认模板
    include_tool_calls_in_summary: bool = True


@dataclass
class ToolPruningPolicyConfig:
    """工具输出修剪策略配置。
    
    Attributes:
        enabled: 是否启用
        protect_recent_turns: 保护最近 N 轮的工具输出
        protect_token_threshold: 保护最近 N tokens 的工具输出
        minimum_prune_tokens: 最小修剪量（低于此值不执行）
        protected_tools: 受保护的工具列表（永不修剪）
        replacement_text: 修剪后的替换文本
    """
    enabled: bool = True
    protect_recent_turns: int = 2
    protect_token_threshold: int = 40000
    minimum_prune_tokens: int = 20000
    protected_tools: tuple[str, ...] = ()
    replacement_text: str = "[Output pruned to save context space]"


@dataclass
class CompactionConfig:
    """压缩总配置。
    
    Attributes:
        enabled: 是否启用压缩功能
        auto_compact: 是否自动压缩（vs 手动触发）
        check_interval_steps: 自动检查间隔（每 N 步检查一次）
        overflow_threshold: 溢出阈值（0.0-1.0，超过此比例触发压缩）
        reserved_tokens: 保留 token 数（给 system prompt 和新消息）
        
        # 策略配置
        summary_policy: 摘要策略配置
        tool_pruning_policy: 工具修剪策略配置
        
        # 策略执行顺序（priority 高的先执行）
        policy_priority: 策略优先级映射
    """
    enabled: bool = True
    auto_compact: bool = True
    check_interval_steps: int = 3
    overflow_threshold: float = 0.9
    reserved_tokens: int = 2000
    
    summary_policy: SummaryPolicyConfig = field(default_factory=SummaryPolicyConfig)
    tool_pruning_policy: ToolPruningPolicyConfig = field(default_factory=ToolPruningPolicyConfig)
    
    policy_priority: dict[str, int] = field(default_factory=lambda: {
        "tool_pruning": 50,   # 先尝试修剪工具输出
        "summary": 100,       # 再进行摘要压缩
    })


# 默认摘要 Prompt 模板
DEFAULT_SUMMARY_PROMPT_TEMPLATE = """请详细总结以下对话历史，生成一个用于继续对话的上下文摘要。

## 要求

1. **包含关键信息**：
   - 已完成的任务和操作
   - 当前正在进行的工作
   - 涉及的文件和代码
   - 关键决策和原因

2. **保持连贯性**：
   - 摘要应该让新的对话能够无缝继续
   - 保留重要的技术细节
   - 记录未完成的待办事项

3. **格式**：
   - 使用简洁的 Markdown 格式
   - 按主题组织信息
   - 突出关键信息

## 对话历史

{conversation}

## 请生成摘要
"""


def get_default_config() -> CompactionConfig:
    """获取默认配置。"""
    return CompactionConfig()


def load_compaction_config(config_data: dict[str, Any]) -> CompactionConfig:
    """从配置字典加载压缩配置。
    
    Args:
        config_data: 配置字典，来自 config.yaml 的 compaction 部分
        
    Returns:
        CompactionConfig 实例
    """
    if not config_data:
        return get_default_config()
    
    # 加载摘要策略配置
    summary_data = config_data.get("summary_policy", {})
    summary_config = SummaryPolicyConfig(
        enabled=summary_data.get("enabled", True),
        recent_exchanges_to_keep=summary_data.get("recent_exchanges_to_keep", 6),
        summary_max_tokens=summary_data.get("summary_max_tokens"),
        summary_prompt_template=summary_data.get("summary_prompt_template", ""),
        include_tool_calls_in_summary=summary_data.get("include_tool_calls_in_summary", True),
    )
    
    # 加载工具修剪策略配置
    pruning_data = config_data.get("tool_pruning_policy", {})
    pruning_config = ToolPruningPolicyConfig(
        enabled=pruning_data.get("enabled", True),
        protect_recent_turns=pruning_data.get("protect_recent_turns", 2),
        protect_token_threshold=pruning_data.get("protect_token_threshold", 40000),
        minimum_prune_tokens=pruning_data.get("minimum_prune_tokens", 20000),
        protected_tools=tuple(pruning_data.get("protected_tools", [])),
        replacement_text=pruning_data.get(
            "replacement_text", 
            "[Output pruned to save context space]"
        ),
    )
    
    return CompactionConfig(
        enabled=config_data.get("enabled", True),
        auto_compact=config_data.get("auto_compact", True),
        check_interval_steps=config_data.get("check_interval_steps", 3),
        overflow_threshold=config_data.get("overflow_threshold", 0.9),
        reserved_tokens=config_data.get("reserved_tokens", 2000),
        summary_policy=summary_config,
        tool_pruning_policy=pruning_config,
        policy_priority=config_data.get("policy_priority", {
            "tool_pruning": 50,
            "summary": 100,
        }),
    )
```

---

## 4. 接口规格

### 4.1 文件: `wolo/compaction/policy/base.py`

```python
"""压缩策略基类。

定义所有压缩策略必须实现的接口。
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wolo.compaction.types import CompactionContext, PolicyResult, PolicyType


class CompactionPolicy(ABC):
    """压缩策略抽象基类。
    
    所有具体策略必须继承此类并实现所有抽象方法。
    
    Attributes:
        name (str): 策略名称，必须唯一
        priority (int): 策略优先级，数值越高越先执行
    
    Class Invariants:
        - name 必须是非空字符串
        - priority 必须是正整数
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称。
        
        Returns:
            非空字符串，在所有策略中唯一
        """
        ...
    
    @property
    @abstractmethod
    def policy_type(self) -> "PolicyType":
        """策略类型枚举。
        
        Returns:
            PolicyType 枚举值
        """
        ...
    
    @property
    @abstractmethod
    def priority(self) -> int:
        """策略优先级。
        
        优先级高的策略先执行。建议值：
        - 10-49: 轻量级预处理
        - 50-99: 选择性修剪
        - 100-199: 完整压缩
        - 200+: 后处理
        
        Returns:
            正整数
        """
        ...
    
    @abstractmethod
    def should_apply(self, context: "CompactionContext") -> bool:
        """判断是否应该应用此策略。
        
        此方法必须是幂等的，不能有副作用。
        
        Args:
            context: 压缩上下文，包含消息和配置
            
        Returns:
            True 如果应该应用此策略，False 否则
            
        Preconditions:
            - context 不为 None
            - context.messages 不为空
            
        Postconditions:
            - 不修改任何状态
        """
        ...
    
    @abstractmethod
    async def apply(self, context: "CompactionContext") -> "PolicyResult":
        """应用压缩策略。
        
        执行实际的压缩操作。此方法可能调用 LLM。
        
        Args:
            context: 压缩上下文
            
        Returns:
            PolicyResult 包含压缩结果
            
        Preconditions:
            - should_apply(context) 返回 True
            - context 不为 None
            
        Postconditions:
            - 如果成功，result.messages 包含压缩后的消息
            - 如果成功，result.record 包含压缩记录
            - 原始消息不被修改（返回新列表）
            
        Raises:
            此方法不应抛出异常，错误通过 PolicyResult.error 返回
        """
        ...
    
    @abstractmethod
    def estimate_savings(self, context: "CompactionContext") -> int:
        """估算压缩可节省的 token 数。
        
        用于决定策略选择和效果预测。
        
        Args:
            context: 压缩上下文
            
        Returns:
            预估节省的 token 数，如果无法估算返回 0
            
        Preconditions:
            - context 不为 None
            
        Postconditions:
            - 返回值 >= 0
            - 不修改任何状态
        """
        ...
```

### 4.2 文件: `wolo/compaction/manager.py`

```python
"""压缩管理器。

协调压缩策略的执行。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wolo.compaction.config import CompactionConfig
    from wolo.compaction.types import (
        CompactionDecision,
        CompactionResult,
        CompactionRecord,
    )
    from wolo.compaction.policy.base import CompactionPolicy
    from wolo.compaction.history import CompactionHistory
    from wolo.session import Message


class CompactionManager:
    """压缩管理器。
    
    负责协调压缩策略的执行，管理压缩历史。
    
    使用示例:
        ```python
        config = CompactionConfig()
        manager = CompactionManager(config)
        
        # 检查是否需要压缩
        decision = manager.should_compact(messages, session_id)
        if decision.should_compact:
            result = await manager.compact(messages, session_id)
        ```
    
    Thread Safety:
        此类非线程安全。每个 session 应使用独立实例或加锁。
    """
    
    def __init__(
        self,
        config: "CompactionConfig",
        llm_config: "Config",  # wolo.config.Config
    ) -> None:
        """初始化压缩管理器。
        
        Args:
            config: 压缩配置
            llm_config: LLM 配置（用于摘要生成）
            
        Postconditions:
            - self.config == config
            - self.policies 包含所有启用的策略，按优先级降序排列
            - self.history 已初始化
        """
        ...
    
    def should_compact(
        self,
        messages: list["Message"],
        session_id: str,
    ) -> "CompactionDecision":
        """判断是否需要压缩。
        
        检查当前 token 使用量，判断是否超过阈值。
        
        Args:
            messages: 当前消息列表
            session_id: 会话 ID
            
        Returns:
            CompactionDecision 包含决策信息
            
        Preconditions:
            - messages 不为 None（可以为空）
            - session_id 非空字符串
            
        Algorithm:
            1. 如果 config.enabled == False，返回不需要压缩
            2. 计算当前 token 数
            3. 计算有效上限（max_tokens - reserved_tokens）
            4. 如果 current / limit > overflow_threshold，返回需要压缩
            5. 返回不需要压缩
        """
        ...
    
    async def compact(
        self,
        messages: list["Message"],
        session_id: str,
    ) -> "CompactionResult":
        """执行压缩。
        
        按优先级顺序尝试各策略，直到不再溢出或所有策略尝试完毕。
        
        Args:
            messages: 当前消息列表
            session_id: 会话 ID
            
        Returns:
            CompactionResult 包含压缩结果
            
        Preconditions:
            - messages 不为 None 且不为空
            - session_id 非空字符串
            
        Algorithm:
            1. 创建 CompactionContext
            2. 按优先级排序策略（降序）
            3. 对于每个策略:
               a. 检查 should_apply
               b. 如果是，执行 apply
               c. 更新 context.messages
               d. 检查是否仍然溢出
               e. 如果不溢出，停止
            4. 保存所有压缩记录到历史
            5. 返回最终结果
            
        Postconditions:
            - 如果成功，result.result_messages 包含压缩后的消息
            - 压缩记录已保存到历史
            - 原始消息未被修改
        """
        ...
    
    def get_history(
        self,
        session_id: str,
    ) -> list["CompactionRecord"]:
        """获取压缩历史。
        
        Args:
            session_id: 会话 ID
            
        Returns:
            压缩记录列表，按时间降序排列
        """
        ...
    
    def get_original_messages(
        self,
        session_id: str,
        record_id: str,
    ) -> list["Message"]:
        """根据压缩记录获取原始消息。
        
        Args:
            session_id: 会话 ID
            record_id: 压缩记录 ID
            
        Returns:
            原始消息列表，如果找不到返回空列表
        """
        ...
```

### 4.3 文件: `wolo/compaction/token.py`

```python
"""Token 估算模块。

提供 token 数量估算功能。
"""


class TokenEstimator:
    """Token 估算器。
    
    提供多种 token 估算方法，支持不同模型。
    
    估算精度说明：
        - 字符估算：误差 ±30%
        - 中英混合优化：误差 ±20%
        - tiktoken（未来）：误差 ±5%
    """
    
    # 常量定义
    CHARS_PER_TOKEN_ENGLISH: float = 4.0
    CHARS_PER_TOKEN_CHINESE: float = 1.5
    MESSAGE_OVERHEAD_TOKENS: int = 10
    TOOL_CALL_BASE_OVERHEAD: int = 20
    
    @staticmethod
    def estimate_text(text: str, model: str = "default") -> int:
        """估算文本的 token 数。
        
        Args:
            text: 要估算的文本
            model: 模型名称（用于选择估算方法）
            
        Returns:
            估算的 token 数
            
        Algorithm:
            1. 如果 text 为空或 None，返回 0
            2. 统计中文字符数（Unicode 范围 \\u4e00-\\u9fff）
            3. 统计其他字符数
            4. 中文字符数 / CHARS_PER_TOKEN_CHINESE
            5. 其他字符数 / CHARS_PER_TOKEN_ENGLISH
            6. 返回两者之和，最小为 1
            
        Postconditions:
            - 返回值 >= 0
            - 如果 text 非空，返回值 >= 1
        """
        ...
    
    @staticmethod
    def estimate_message(message: "Message", model: str = "default") -> int:
        """估算消息的 token 数。
        
        Args:
            message: 消息对象
            model: 模型名称
            
        Returns:
            估算的 token 数
            
        Algorithm:
            1. 初始化 total = MESSAGE_OVERHEAD_TOKENS
            2. 对于每个 TextPart:
               total += estimate_text(part.text, model)
            3. 对于每个 ToolPart:
               total += TOOL_CALL_BASE_OVERHEAD
               total += estimate_text(json.dumps(part.input), model)
               total += estimate_text(part.output, model)
            4. 返回 total
        """
        ...
    
    @staticmethod
    def estimate_messages(
        messages: list["Message"],
        model: str = "default",
    ) -> int:
        """估算消息列表的 token 数。
        
        Args:
            messages: 消息列表
            model: 模型名称
            
        Returns:
            估算的总 token 数
        """
        ...
    
    @staticmethod
    def is_chinese_char(char: str) -> bool:
        """判断是否为中文字符。
        
        Args:
            char: 单个字符
            
        Returns:
            True 如果是中文字符
        """
        ...
```

---

## 5. 实现规格

### 5.1 文件: `wolo/compaction/policy/summary.py`

```python
"""摘要压缩策略。

通过 LLM 生成对话摘要，替换旧消息。
"""

import time
import uuid
from typing import TYPE_CHECKING

from wolo.compaction.policy.base import CompactionPolicy
from wolo.compaction.types import (
    CompactionRecord,
    CompactionStatus,
    PolicyResult,
    PolicyType,
)
from wolo.compaction.config import DEFAULT_SUMMARY_PROMPT_TEMPLATE
from wolo.compaction.token import TokenEstimator
from wolo.session import Message, TextPart

if TYPE_CHECKING:
    from wolo.compaction.types import CompactionContext
    from wolo.config import Config


class SummaryCompactionPolicy(CompactionPolicy):
    """摘要压缩策略。
    
    将旧消息压缩为摘要，保留最近的消息。
    
    Attributes:
        llm_config: LLM 配置，用于生成摘要
    """
    
    def __init__(self, llm_config: "Config") -> None:
        """初始化摘要策略。
        
        Args:
            llm_config: LLM 配置
        """
        self._llm_config = llm_config
    
    @property
    def name(self) -> str:
        return "summary"
    
    @property
    def policy_type(self) -> PolicyType:
        return PolicyType.SUMMARY
    
    @property
    def priority(self) -> int:
        return 100
    
    def should_apply(self, context: "CompactionContext") -> bool:
        """判断是否应该应用摘要压缩。
        
        Conditions:
            1. 策略在配置中启用
            2. 消息数 > recent_exchanges_to_keep * 2（至少有消息可压缩）
            3. 当前 token 数 > token_limit
            
        Returns:
            True 如果满足所有条件
        """
        if not context.config.summary_policy.enabled:
            return False
        
        min_messages = context.config.summary_policy.recent_exchanges_to_keep * 2
        if len(context.messages) <= min_messages:
            return False
        
        return context.token_count > context.token_limit
    
    async def apply(self, context: "CompactionContext") -> PolicyResult:
        """执行摘要压缩。
        
        Algorithm:
            1. 确定保留的最近消息（last N exchanges）
            2. 确定要压缩的消息（其余部分）
            3. 如果没有要压缩的消息，返回 SKIPPED
            4. 调用 LLM 生成摘要
            5. 创建摘要消息（role="user"）
            6. 组合：[摘要消息] + [保留的消息]
            7. 标记原始消息（添加 metadata）
            8. 创建 CompactionRecord
            9. 返回 PolicyResult
            
        摘要消息格式:
            Message(
                id=uuid,
                role="user",
                parts=[TextPart(text="[对话历史摘要]\n\n{summary}")],
                metadata={
                    "compaction": {
                        "is_summary": True,
                        "record_id": record.id,
                        "compacted_message_ids": [...],
                        "created_at": timestamp,
                    }
                }
            )
            
        被压缩消息的标记:
            message.metadata = {
                "compaction": {
                    "is_compacted": True,
                    "compacted_by_record": record.id,
                    "compacted_at": timestamp,
                }
            }
        """
        ...
    
    def estimate_savings(self, context: "CompactionContext") -> int:
        """估算压缩可节省的 token 数。
        
        Algorithm:
            1. 计算要压缩的消息的 token 总数
            2. 估算摘要的 token 数（约为原始的 20%）
            3. 返回差值
        """
        ...
    
    async def _generate_summary(
        self,
        messages: tuple,
        context: "CompactionContext",
    ) -> str:
        """生成摘要。
        
        Args:
            messages: 要压缩的消息
            context: 压缩上下文
            
        Returns:
            摘要文本
            
        Error Handling:
            如果 LLM 调用失败，生成简单的回退摘要:
            "之前的对话包含 {user_count} 条用户消息和 {assistant_count} 条助手回复。"
        """
        ...
    
    def _split_messages(
        self,
        messages: tuple,
        keep_exchanges: int,
    ) -> tuple[tuple, tuple]:
        """分割消息为要压缩和保留的部分。
        
        Args:
            messages: 所有消息
            keep_exchanges: 保留的对话轮数
            
        Returns:
            (to_compact, to_keep) 元组
            
        Algorithm:
            1. 从后往前遍历消息
            2. 计数 user 消息数
            3. 当计数达到 keep_exchanges 时停止
            4. 之前的消息为 to_compact
            5. 之后的消息为 to_keep
        """
        ...
```

### 5.2 文件: `wolo/compaction/policy/pruning.py`

```python
"""工具输出修剪策略。

选择性移除旧的工具输出，保留工具调用记录。
"""

import time
from typing import TYPE_CHECKING

from wolo.compaction.policy.base import CompactionPolicy
from wolo.compaction.types import (
    CompactionRecord,
    CompactionStatus,
    PolicyResult,
    PolicyType,
)
from wolo.compaction.token import TokenEstimator
from wolo.session import Message, ToolPart

if TYPE_CHECKING:
    from wolo.compaction.types import CompactionContext


class ToolOutputPruningPolicy(CompactionPolicy):
    """工具输出修剪策略。
    
    移除旧的工具输出，保留工具调用信息。
    比完整压缩更轻量，适合作为第一道防线。
    """
    
    @property
    def name(self) -> str:
        return "tool_pruning"
    
    @property
    def policy_type(self) -> PolicyType:
        return PolicyType.TOOL_PRUNING
    
    @property
    def priority(self) -> int:
        return 50
    
    def should_apply(self, context: "CompactionContext") -> bool:
        """判断是否应该应用工具修剪。
        
        Conditions:
            1. 策略在配置中启用
            2. 消息中有已完成的工具调用
            3. 工具输出 token 数 > protect_token_threshold
            4. 当前 token 数 > token_limit
            
        Returns:
            True 如果满足所有条件
        """
        ...
    
    async def apply(self, context: "CompactionContext") -> PolicyResult:
        """执行工具输出修剪。
        
        Algorithm:
            1. 收集所有工具输出及其 token 数
            2. 从后往前遍历，累计保护的 token 数
            3. 当累计超过 protect_token_threshold 后，标记为待修剪
            4. 如果待修剪 token 数 < minimum_prune_tokens，返回 SKIPPED
            5. 创建消息副本，修剪工具输出
            6. 创建 CompactionRecord
            7. 返回 PolicyResult
            
        修剪后的 ToolPart:
            ToolPart(
                ...original fields...,
                output=replacement_text,
                metadata={
                    "pruned": True,
                    "pruned_at": timestamp,
                    "original_output_tokens": token_count,
                }
            )
            
        注意:
            - 保护最近 protect_recent_turns 轮的所有工具
            - protected_tools 列表中的工具永不修剪
            - 如果遇到摘要消息（is_summary=True），停止遍历
        """
        ...
    
    def estimate_savings(self, context: "CompactionContext") -> int:
        """估算修剪可节省的 token 数。"""
        ...
    
    def _find_prunable_outputs(
        self,
        messages: tuple,
        config: "ToolPruningPolicyConfig",
    ) -> list[tuple["Message", "ToolPart", int]]:
        """找出可修剪的工具输出。
        
        Args:
            messages: 消息列表
            config: 修剪配置
            
        Returns:
            列表，每项为 (message, tool_part, token_count)
        """
        ...
```

### 5.3 文件: `wolo/compaction/history.py`

```python
"""压缩历史管理。

存储和查询压缩记录。
"""

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wolo.compaction.types import CompactionRecord
    from wolo.session import Message, SessionStorage


class CompactionHistory:
    """压缩历史管理器。
    
    负责存储和查询压缩记录。
    
    存储格式:
        ~/.wolo/sessions/{session_id}/compaction/
        ├── records.json          # 压缩记录索引
        └── {record_id}.json      # 每个压缩记录的详细信息
        
    records.json 格式:
        {
            "records": [
                {"id": "xxx", "created_at": 12345, "policy": "summary"},
                ...
            ]
        }
    """
    
    def __init__(self, storage: "SessionStorage") -> None:
        """初始化压缩历史。
        
        Args:
            storage: 会话存储实例
        """
        self._storage = storage
    
    def add_record(
        self,
        session_id: str,
        record: "CompactionRecord",
    ) -> None:
        """添加压缩记录。
        
        Args:
            session_id: 会话 ID
            record: 压缩记录
            
        Postconditions:
            - 记录已保存到文件
            - 索引已更新
        """
        ...
    
    def get_records(
        self,
        session_id: str,
    ) -> list["CompactionRecord"]:
        """获取所有压缩记录。
        
        Args:
            session_id: 会话 ID
            
        Returns:
            压缩记录列表，按时间降序排列
        """
        ...
    
    def get_record(
        self,
        session_id: str,
        record_id: str,
    ) -> "CompactionRecord | None":
        """获取单个压缩记录。
        
        Args:
            session_id: 会话 ID
            record_id: 记录 ID
            
        Returns:
            压缩记录，如果不存在返回 None
        """
        ...
    
    def get_original_messages(
        self,
        session_id: str,
        record_id: str,
    ) -> list["Message"]:
        """根据压缩记录获取原始消息。
        
        Args:
            session_id: 会话 ID
            record_id: 压缩记录 ID
            
        Returns:
            原始消息列表（从存储中读取）
            
        Algorithm:
            1. 获取压缩记录
            2. 从 compacted_message_ids 获取消息 ID 列表
            3. 从存储中读取每个消息
            4. 返回消息列表
        """
        ...
    
    def _compaction_dir(self, session_id: str) -> Path:
        """获取压缩目录路径。"""
        ...
    
    def _records_file(self, session_id: str) -> Path:
        """获取记录索引文件路径。"""
        ...
    
    def _record_file(self, session_id: str, record_id: str) -> Path:
        """获取单个记录文件路径。"""
        ...
```

---

## 6. 配置规格

### 6.1 配置文件格式: `~/.wolo/config.yaml`

```yaml
# 压缩配置
compaction:
  # 是否启用压缩功能（默认: true）
  enabled: true
  
  # 是否自动压缩（默认: true）
  auto_compact: true
  
  # 自动检查间隔，每 N 步检查一次（默认: 3）
  check_interval_steps: 3
  
  # 溢出阈值，超过此比例触发压缩（默认: 0.9）
  overflow_threshold: 0.9
  
  # 保留 token 数，给 system prompt 和新消息（默认: 2000）
  reserved_tokens: 2000
  
  # 摘要策略配置
  summary_policy:
    # 是否启用（默认: true）
    enabled: true
    
    # 保留最近的对话轮数（默认: 6）
    recent_exchanges_to_keep: 6
    
    # 摘要最大 token 数，null 表示不限制（默认: null）
    summary_max_tokens: null
    
    # 摘要 prompt 模板，空字符串使用默认（默认: ""）
    summary_prompt_template: ""
    
    # 摘要中是否包含工具调用信息（默认: true）
    include_tool_calls_in_summary: true
  
  # 工具输出修剪策略配置
  tool_pruning_policy:
    # 是否启用（默认: true）
    enabled: true
    
    # 保护最近 N 轮的工具输出（默认: 2）
    protect_recent_turns: 2
    
    # 保护最近 N tokens 的工具输出（默认: 40000）
    protect_token_threshold: 40000
    
    # 最小修剪量，低于此值不执行（默认: 20000）
    minimum_prune_tokens: 20000
    
    # 受保护的工具列表（默认: []）
    protected_tools: []
    
    # 修剪后的替换文本
    replacement_text: "[Output pruned to save context space]"
  
  # 策略优先级（数值越高越先执行）
  policy_priority:
    tool_pruning: 50
    summary: 100
```

### 6.2 修改 `wolo/config.py`

**添加内容**:

```python
# 在 Config 类中添加字段
@dataclass
class Config:
    # ... 现有字段 ...
    
    # 压缩配置
    compaction: "CompactionConfig" = field(default_factory=lambda: None)
    
# 在 from_env 方法中添加加载逻辑
@classmethod
def from_env(cls, ...) -> "Config":
    # ... 现有逻辑 ...
    
    # 加载压缩配置
    from wolo.compaction.config import load_compaction_config
    compaction_data = config_data.get("compaction", {})
    compaction_config = load_compaction_config(compaction_data)
    
    return cls(
        # ... 现有参数 ...
        compaction=compaction_config,
    )
```

---

## 7. 测试规格

### 7.1 单元测试: `tests/compaction/test_token.py`

```python
"""Token 估算测试。"""

import pytest
from wolo.compaction.token import TokenEstimator
from wolo.session import Message, TextPart, ToolPart


class TestEstimateText:
    """estimate_text 方法测试。"""
    
    def test_empty_string_returns_zero(self):
        """空字符串返回 0。"""
        assert TokenEstimator.estimate_text("") == 0
    
    def test_none_returns_zero(self):
        """None 返回 0。"""
        assert TokenEstimator.estimate_text(None) == 0
    
    def test_english_text_4_chars_per_token(self):
        """英文文本约 4 字符/token。
        
        输入: "hello world" (11 字符)
        预期: 11 / 4 = 2.75 -> 3
        """
        result = TokenEstimator.estimate_text("hello world")
        assert result == 3
    
    def test_chinese_text_1_5_chars_per_token(self):
        """中文文本约 1.5 字符/token。
        
        输入: "你好世界" (4 字符)
        预期: 4 / 1.5 = 2.67 -> 3
        """
        result = TokenEstimator.estimate_text("你好世界")
        assert result == 3
    
    def test_mixed_text(self):
        """中英混合文本。
        
        输入: "hello你好" (7 字符 = 5 英文 + 2 中文)
        预期: 5/4 + 2/1.5 = 1.25 + 1.33 = 2.58 -> 3
        """
        result = TokenEstimator.estimate_text("hello你好")
        assert result == 3
    
    def test_minimum_one_token_for_non_empty(self):
        """非空文本至少返回 1。
        
        输入: "a" (1 字符)
        预期: >= 1
        """
        result = TokenEstimator.estimate_text("a")
        assert result >= 1
    
    def test_long_text(self):
        """长文本测试。
        
        输入: 4000 个英文字符
        预期: 4000 / 4 = 1000
        """
        text = "a" * 4000
        result = TokenEstimator.estimate_text(text)
        assert result == 1000
    
    def test_code_text(self):
        """代码文本测试。
        
        输入: Python 代码片段
        预期: 合理的 token 数
        """
        code = """def hello():
    print("Hello, World!")
    return True
"""
        result = TokenEstimator.estimate_text(code)
        # 约 50 字符 -> 约 12-15 tokens
        assert 10 <= result <= 20


class TestEstimateMessage:
    """estimate_message 方法测试。"""
    
    def test_text_only_message(self):
        """纯文本消息。
        
        输入: Message with "hello" (5 字符)
        预期: MESSAGE_OVERHEAD (10) + 5/4 = 10 + 2 = 12
        """
        msg = Message(role="user", parts=[TextPart(text="hello")])
        result = TokenEstimator.estimate_message(msg)
        assert result == 12
    
    def test_tool_call_message(self):
        """工具调用消息。
        
        输入: Message with ToolPart
        预期: MESSAGE_OVERHEAD + TOOL_OVERHEAD + input + output
        """
        msg = Message(
            role="assistant",
            parts=[
                ToolPart(
                    tool="read",
                    input={"path": "/test.py"},
                    output="file content here",
                )
            ]
        )
        result = TokenEstimator.estimate_message(msg)
        # 10 (overhead) + 20 (tool) + input_tokens + output_tokens
        assert result > 30
    
    def test_mixed_parts_message(self):
        """混合部件消息。"""
        msg = Message(
            role="assistant",
            parts=[
                TextPart(text="Let me read the file"),
                ToolPart(tool="read", input={"path": "/test.py"}, output="content"),
            ]
        )
        result = TokenEstimator.estimate_message(msg)
        # 应该累加所有部件
        text_only = TokenEstimator.estimate_message(
            Message(role="assistant", parts=[TextPart(text="Let me read the file")])
        )
        assert result > text_only


class TestEstimateMessages:
    """estimate_messages 方法测试。"""
    
    def test_empty_list_returns_zero(self):
        """空列表返回 0。"""
        assert TokenEstimator.estimate_messages([]) == 0
    
    def test_single_message(self):
        """单条消息。"""
        msg = Message(role="user", parts=[TextPart(text="hello")])
        result = TokenEstimator.estimate_messages([msg])
        assert result == TokenEstimator.estimate_message(msg)
    
    def test_multiple_messages_sum(self):
        """多条消息求和。"""
        msg1 = Message(role="user", parts=[TextPart(text="hello")])
        msg2 = Message(role="assistant", parts=[TextPart(text="hi")])
        
        result = TokenEstimator.estimate_messages([msg1, msg2])
        expected = (
            TokenEstimator.estimate_message(msg1) +
            TokenEstimator.estimate_message(msg2)
        )
        assert result == expected
```

### 7.2 单元测试: `tests/compaction/test_config.py`

```python
"""压缩配置测试。"""

import pytest
from wolo.compaction.config import (
    CompactionConfig,
    SummaryPolicyConfig,
    ToolPruningPolicyConfig,
    get_default_config,
    load_compaction_config,
)


class TestGetDefaultConfig:
    """get_default_config 测试。"""
    
    def test_returns_compaction_config(self):
        """返回 CompactionConfig 实例。"""
        config = get_default_config()
        assert isinstance(config, CompactionConfig)
    
    def test_default_enabled_true(self):
        """默认启用压缩。"""
        config = get_default_config()
        assert config.enabled is True
    
    def test_default_auto_compact_true(self):
        """默认自动压缩。"""
        config = get_default_config()
        assert config.auto_compact is True
    
    def test_default_check_interval_3(self):
        """默认检查间隔 3。"""
        config = get_default_config()
        assert config.check_interval_steps == 3
    
    def test_default_overflow_threshold_0_9(self):
        """默认溢出阈值 0.9。"""
        config = get_default_config()
        assert config.overflow_threshold == 0.9
    
    def test_default_reserved_tokens_2000(self):
        """默认保留 2000 tokens。"""
        config = get_default_config()
        assert config.reserved_tokens == 2000
    
    def test_default_summary_policy(self):
        """默认摘要策略配置。"""
        config = get_default_config()
        assert config.summary_policy.enabled is True
        assert config.summary_policy.recent_exchanges_to_keep == 6
        assert config.summary_policy.summary_max_tokens is None
    
    def test_default_pruning_policy(self):
        """默认修剪策略配置。"""
        config = get_default_config()
        assert config.tool_pruning_policy.enabled is True
        assert config.tool_pruning_policy.protect_recent_turns == 2
        assert config.tool_pruning_policy.protect_token_threshold == 40000
        assert config.tool_pruning_policy.minimum_prune_tokens == 20000


class TestLoadCompactionConfig:
    """load_compaction_config 测试。"""
    
    def test_empty_dict_returns_defaults(self):
        """空字典返回默认配置。"""
        config = load_compaction_config({})
        default = get_default_config()
        assert config.enabled == default.enabled
    
    def test_none_returns_defaults(self):
        """None 返回默认配置。"""
        config = load_compaction_config(None)
        assert isinstance(config, CompactionConfig)
    
    def test_override_enabled(self):
        """覆盖 enabled。"""
        config = load_compaction_config({"enabled": False})
        assert config.enabled is False
    
    def test_override_check_interval(self):
        """覆盖检查间隔。"""
        config = load_compaction_config({"check_interval_steps": 5})
        assert config.check_interval_steps == 5
    
    def test_override_summary_policy(self):
        """覆盖摘要策略。"""
        config = load_compaction_config({
            "summary_policy": {
                "enabled": False,
                "recent_exchanges_to_keep": 10,
            }
        })
        assert config.summary_policy.enabled is False
        assert config.summary_policy.recent_exchanges_to_keep == 10
    
    def test_override_pruning_policy(self):
        """覆盖修剪策略。"""
        config = load_compaction_config({
            "tool_pruning_policy": {
                "protected_tools": ["read", "write"],
                "minimum_prune_tokens": 30000,
            }
        })
        assert config.tool_pruning_policy.protected_tools == ("read", "write")
        assert config.tool_pruning_policy.minimum_prune_tokens == 30000
    
    def test_partial_override_preserves_defaults(self):
        """部分覆盖保留默认值。"""
        config = load_compaction_config({
            "summary_policy": {
                "enabled": False,
            }
        })
        # enabled 被覆盖
        assert config.summary_policy.enabled is False
        # 其他保持默认
        assert config.summary_policy.recent_exchanges_to_keep == 6
```

### 7.3 单元测试: `tests/compaction/test_summary_policy.py`

```python
"""摘要压缩策略测试。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from wolo.compaction.policy.summary import SummaryCompactionPolicy
from wolo.compaction.types import (
    CompactionContext,
    CompactionStatus,
    PolicyType,
)
from wolo.compaction.config import CompactionConfig
from wolo.session import Message, TextPart


def create_messages(count: int) -> tuple:
    """创建测试消息。"""
    messages = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        messages.append(
            Message(role=role, parts=[TextPart(text=f"Message {i}")])
        )
    return tuple(messages)


def create_context(
    messages: tuple,
    token_count: int = 10000,
    token_limit: int = 8000,
    config: CompactionConfig = None,
) -> CompactionContext:
    """创建测试上下文。"""
    return CompactionContext(
        session_id="test-session",
        messages=messages,
        token_count=token_count,
        token_limit=token_limit,
        model="test-model",
        config=config or CompactionConfig(),
    )


class TestSummaryPolicyProperties:
    """策略属性测试。"""
    
    def test_name_is_summary(self):
        """名称为 'summary'。"""
        policy = SummaryCompactionPolicy(MagicMock())
        assert policy.name == "summary"
    
    def test_policy_type_is_summary(self):
        """类型为 SUMMARY。"""
        policy = SummaryCompactionPolicy(MagicMock())
        assert policy.policy_type == PolicyType.SUMMARY
    
    def test_priority_is_100(self):
        """优先级为 100。"""
        policy = SummaryCompactionPolicy(MagicMock())
        assert policy.priority == 100


class TestSummaryPolicyShouldApply:
    """should_apply 方法测试。"""
    
    def test_returns_false_when_disabled(self):
        """禁用时返回 False。"""
        policy = SummaryCompactionPolicy(MagicMock())
        config = CompactionConfig()
        config.summary_policy.enabled = False
        context = create_context(create_messages(20), config=config)
        
        assert policy.should_apply(context) is False
    
    def test_returns_false_when_not_enough_messages(self):
        """消息不足时返回 False。
        
        recent_exchanges_to_keep = 6，需要至少 12 条消息
        """
        policy = SummaryCompactionPolicy(MagicMock())
        context = create_context(create_messages(10))
        
        assert policy.should_apply(context) is False
    
    def test_returns_false_when_under_limit(self):
        """未超限时返回 False。"""
        policy = SummaryCompactionPolicy(MagicMock())
        context = create_context(
            create_messages(20),
            token_count=5000,
            token_limit=8000,
        )
        
        assert policy.should_apply(context) is False
    
    def test_returns_true_when_all_conditions_met(self):
        """所有条件满足时返回 True。"""
        policy = SummaryCompactionPolicy(MagicMock())
        context = create_context(
            create_messages(20),
            token_count=10000,
            token_limit=8000,
        )
        
        assert policy.should_apply(context) is True


class TestSummaryPolicyApply:
    """apply 方法测试。"""
    
    @pytest.mark.asyncio
    async def test_returns_skipped_when_no_messages_to_compact(self):
        """无可压缩消息时返回 SKIPPED。"""
        policy = SummaryCompactionPolicy(MagicMock())
        # 刚好等于保留数
        context = create_context(create_messages(12))
        
        result = await policy.apply(context)
        
        assert result.status == CompactionStatus.SKIPPED
    
    @pytest.mark.asyncio
    async def test_creates_summary_message(self):
        """创建摘要消息。"""
        llm_config = MagicMock()
        policy = SummaryCompactionPolicy(llm_config)
        
        with patch.object(
            policy, '_generate_summary',
            new_callable=AsyncMock,
            return_value="This is a summary"
        ):
            context = create_context(create_messages(20))
            result = await policy.apply(context)
        
        assert result.status == CompactionStatus.APPLIED
        assert result.messages is not None
        # 第一条应该是摘要消息
        first_msg = result.messages[0]
        assert first_msg.role == "user"
        assert "摘要" in first_msg.parts[0].text or "summary" in first_msg.parts[0].text.lower()
    
    @pytest.mark.asyncio
    async def test_preserves_recent_messages(self):
        """保留最近的消息。"""
        policy = SummaryCompactionPolicy(MagicMock())
        messages = create_messages(20)
        
        with patch.object(
            policy, '_generate_summary',
            new_callable=AsyncMock,
            return_value="Summary"
        ):
            context = create_context(messages)
            result = await policy.apply(context)
        
        # 保留最近 6 轮 = 12 条消息 + 1 条摘要
        assert len(result.messages) == 13
        # 最后一条应该是原来的最后一条
        assert result.messages[-1].id == messages[-1].id
    
    @pytest.mark.asyncio
    async def test_creates_compaction_record(self):
        """创建压缩记录。"""
        policy = SummaryCompactionPolicy(MagicMock())
        
        with patch.object(
            policy, '_generate_summary',
            new_callable=AsyncMock,
            return_value="Summary"
        ):
            context = create_context(create_messages(20))
            result = await policy.apply(context)
        
        assert result.record is not None
        assert result.record.policy == PolicyType.SUMMARY
        assert result.record.session_id == "test-session"
        assert len(result.record.compacted_message_ids) == 8  # 20 - 12 = 8
    
    @pytest.mark.asyncio
    async def test_summary_message_has_metadata(self):
        """摘要消息包含元数据。"""
        policy = SummaryCompactionPolicy(MagicMock())
        
        with patch.object(
            policy, '_generate_summary',
            new_callable=AsyncMock,
            return_value="Summary"
        ):
            context = create_context(create_messages(20))
            result = await policy.apply(context)
        
        first_msg = result.messages[0]
        assert hasattr(first_msg, 'metadata')
        assert first_msg.metadata.get("compaction", {}).get("is_summary") is True


class TestSummaryPolicyEstimateSavings:
    """estimate_savings 方法测试。"""
    
    def test_returns_positive_when_can_compact(self):
        """可压缩时返回正数。"""
        policy = SummaryCompactionPolicy(MagicMock())
        context = create_context(
            create_messages(20),
            token_count=10000,
        )
        
        savings = policy.estimate_savings(context)
        
        assert savings > 0
    
    def test_returns_zero_when_cannot_compact(self):
        """无法压缩时返回 0。"""
        policy = SummaryCompactionPolicy(MagicMock())
        context = create_context(create_messages(10))
        
        savings = policy.estimate_savings(context)
        
        assert savings == 0
```

### 7.4 单元测试: `tests/compaction/test_pruning_policy.py`

```python
"""工具输出修剪策略测试。"""

import pytest
from unittest.mock import MagicMock

from wolo.compaction.policy.pruning import ToolOutputPruningPolicy
from wolo.compaction.types import (
    CompactionContext,
    CompactionStatus,
    PolicyType,
)
from wolo.compaction.config import CompactionConfig
from wolo.session import Message, TextPart, ToolPart


def create_tool_message(output_size: int = 1000) -> Message:
    """创建包含工具调用的消息。"""
    return Message(
        role="assistant",
        parts=[
            ToolPart(
                tool="read",
                input={"path": "/test.py"},
                output="x" * output_size,
                status="completed",
            )
        ]
    )


def create_context_with_tools(
    tool_messages: int = 10,
    output_size: int = 5000,
    config: CompactionConfig = None,
) -> CompactionContext:
    """创建包含工具调用的上下文。"""
    messages = []
    for i in range(tool_messages):
        messages.append(Message(role="user", parts=[TextPart(text=f"Request {i}")]))
        messages.append(create_tool_message(output_size))
    
    return CompactionContext(
        session_id="test-session",
        messages=tuple(messages),
        token_count=100000,
        token_limit=50000,
        model="test-model",
        config=config or CompactionConfig(),
    )


class TestPruningPolicyProperties:
    """策略属性测试。"""
    
    def test_name_is_tool_pruning(self):
        """名称为 'tool_pruning'。"""
        policy = ToolOutputPruningPolicy()
        assert policy.name == "tool_pruning"
    
    def test_policy_type_is_tool_pruning(self):
        """类型为 TOOL_PRUNING。"""
        policy = ToolOutputPruningPolicy()
        assert policy.policy_type == PolicyType.TOOL_PRUNING
    
    def test_priority_is_50(self):
        """优先级为 50。"""
        policy = ToolOutputPruningPolicy()
        assert policy.priority == 50


class TestPruningPolicyShouldApply:
    """should_apply 方法测试。"""
    
    def test_returns_false_when_disabled(self):
        """禁用时返回 False。"""
        policy = ToolOutputPruningPolicy()
        config = CompactionConfig()
        config.tool_pruning_policy.enabled = False
        context = create_context_with_tools(config=config)
        
        assert policy.should_apply(context) is False
    
    def test_returns_false_when_no_tool_calls(self):
        """无工具调用时返回 False。"""
        policy = ToolOutputPruningPolicy()
        messages = tuple([
            Message(role="user", parts=[TextPart(text="Hello")]),
            Message(role="assistant", parts=[TextPart(text="Hi")]),
        ])
        context = CompactionContext(
            session_id="test",
            messages=messages,
            token_count=100000,
            token_limit=50000,
            model="test",
            config=CompactionConfig(),
        )
        
        assert policy.should_apply(context) is False
    
    def test_returns_true_when_conditions_met(self):
        """条件满足时返回 True。"""
        policy = ToolOutputPruningPolicy()
        context = create_context_with_tools()
        
        assert policy.should_apply(context) is True


class TestPruningPolicyApply:
    """apply 方法测试。"""
    
    @pytest.mark.asyncio
    async def test_skips_when_not_enough_to_prune(self):
        """修剪量不足时跳过。"""
        policy = ToolOutputPruningPolicy()
        context = create_context_with_tools(
            tool_messages=3,
            output_size=100,
        )
        
        result = await policy.apply(context)
        
        assert result.status == CompactionStatus.SKIPPED
    
    @pytest.mark.asyncio
    async def test_prunes_old_tool_outputs(self):
        """修剪旧的工具输出。"""
        policy = ToolOutputPruningPolicy()
        context = create_context_with_tools(
            tool_messages=20,
            output_size=5000,
        )
        
        result = await policy.apply(context)
        
        assert result.status == CompactionStatus.APPLIED
        # 检查旧消息的输出被修剪
        for msg in result.messages[:10]:  # 前面的消息
            for part in msg.parts:
                if isinstance(part, ToolPart):
                    assert "[pruned]" in part.output.lower() or len(part.output) < 100
    
    @pytest.mark.asyncio
    async def test_protects_recent_turns(self):
        """保护最近的轮次。"""
        policy = ToolOutputPruningPolicy()
        context = create_context_with_tools(
            tool_messages=20,
            output_size=5000,
        )
        
        result = await policy.apply(context)
        
        # 最后 2 轮（4 条消息）应该保持不变
        original_last = context.messages[-4:]
        result_last = result.messages[-4:]
        for orig, res in zip(original_last, result_last):
            for op, rp in zip(orig.parts, res.parts):
                if isinstance(op, ToolPart):
                    assert op.output == rp.output
    
    @pytest.mark.asyncio
    async def test_protects_specified_tools(self):
        """保护指定的工具。"""
        policy = ToolOutputPruningPolicy()
        config = CompactionConfig()
        config.tool_pruning_policy.protected_tools = ("read",)
        
        # 创建包含 protected tool 的上下文
        messages = []
        for i in range(20):
            messages.append(Message(role="user", parts=[TextPart(text=f"Request {i}")]))
            messages.append(Message(
                role="assistant",
                parts=[ToolPart(
                    tool="read",
                    input={"path": f"/test{i}.py"},
                    output="x" * 5000,
                    status="completed",
                )]
            ))
        
        context = CompactionContext(
            session_id="test",
            messages=tuple(messages),
            token_count=100000,
            token_limit=50000,
            model="test",
            config=config,
        )
        
        result = await policy.apply(context)
        
        # read 工具的输出不应该被修剪
        assert result.status == CompactionStatus.SKIPPED
```

### 7.5 集成测试: `tests/compaction/test_manager_integration.py`

```python
"""压缩管理器集成测试。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from wolo.compaction.manager import CompactionManager
from wolo.compaction.config import CompactionConfig
from wolo.compaction.types import CompactionStatus
from wolo.session import Message, TextPart, ToolPart


def create_large_session(messages_count: int = 50) -> list[Message]:
    """创建大型会话。"""
    messages = []
    for i in range(messages_count):
        role = "user" if i % 2 == 0 else "assistant"
        if role == "assistant" and i % 4 == 1:
            # 每隔一个 assistant 消息添加工具调用
            messages.append(Message(
                role=role,
                parts=[
                    TextPart(text=f"Let me check {i}"),
                    ToolPart(
                        tool="read",
                        input={"path": f"/file{i}.py"},
                        output="x" * 2000,
                        status="completed",
                    )
                ]
            ))
        else:
            messages.append(
                Message(role=role, parts=[TextPart(text=f"Message {i} " * 100)])
            )
    return messages


class TestCompactionManagerShouldCompact:
    """should_compact 方法集成测试。"""
    
    def test_returns_not_needed_when_disabled(self):
        """禁用时返回不需要压缩。"""
        config = CompactionConfig(enabled=False)
        llm_config = MagicMock()
        manager = CompactionManager(config, llm_config)
        
        decision = manager.should_compact(
            create_large_session(),
            "test-session"
        )
        
        assert decision.should_compact is False
        assert "disabled" in decision.reason.lower()
    
    def test_returns_not_needed_when_under_threshold(self):
        """未超阈值时返回不需要压缩。"""
        config = CompactionConfig()
        llm_config = MagicMock()
        llm_config.max_tokens = 1000000  # 很大的限制
        manager = CompactionManager(config, llm_config)
        
        decision = manager.should_compact(
            create_large_session(10),
            "test-session"
        )
        
        assert decision.should_compact is False
    
    def test_returns_needed_when_over_threshold(self):
        """超阈值时返回需要压缩。"""
        config = CompactionConfig()
        llm_config = MagicMock()
        llm_config.max_tokens = 1000  # 很小的限制
        manager = CompactionManager(config, llm_config)
        
        decision = manager.should_compact(
            create_large_session(50),
            "test-session"
        )
        
        assert decision.should_compact is True
        assert decision.overflow_ratio > config.overflow_threshold


class TestCompactionManagerCompact:
    """compact 方法集成测试。"""
    
    @pytest.mark.asyncio
    async def test_applies_pruning_first(self):
        """先应用修剪策略。"""
        config = CompactionConfig()
        llm_config = MagicMock()
        llm_config.max_tokens = 10000
        manager = CompactionManager(config, llm_config)
        
        messages = create_large_session(30)
        
        with patch.object(
            manager._policies[0],  # 修剪策略（priority 50）
            'apply',
            new_callable=AsyncMock,
        ) as mock_pruning:
            mock_pruning.return_value = MagicMock(
                status=CompactionStatus.APPLIED,
                messages=tuple(messages[10:]),  # 模拟修剪
            )
            
            result = await manager.compact(messages, "test-session")
        
        mock_pruning.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_applies_summary_if_still_overflow(self):
        """如果仍然溢出，应用摘要策略。"""
        config = CompactionConfig()
        llm_config = MagicMock()
        llm_config.max_tokens = 1000
        manager = CompactionManager(config, llm_config)
        
        # 模拟 LLM 调用
        with patch(
            'wolo.compaction.policy.summary.GLMClient',
        ) as mock_client:
            mock_client.return_value.chat_completion = AsyncMock(
                return_value=iter([
                    {"type": "text-delta", "text": "Summary"},
                    {"type": "finish"},
                ])
            )
            
            result = await manager.compact(
                create_large_session(50),
                "test-session"
            )
        
        assert result.status == CompactionStatus.APPLIED
        assert len(result.records) >= 1
    
    @pytest.mark.asyncio
    async def test_preserves_original_messages(self):
        """保留原始消息。"""
        config = CompactionConfig()
        llm_config = MagicMock()
        llm_config.max_tokens = 1000
        manager = CompactionManager(config, llm_config)
        
        original = create_large_session(30)
        original_ids = [m.id for m in original]
        
        with patch(
            'wolo.compaction.policy.summary.GLMClient',
        ):
            result = await manager.compact(original, "test-session")
        
        # 原始消息不应被修改
        assert [m.id for m in original] == original_ids
    
    @pytest.mark.asyncio
    async def test_records_compaction_history(self):
        """记录压缩历史。"""
        config = CompactionConfig()
        llm_config = MagicMock()
        llm_config.max_tokens = 1000
        manager = CompactionManager(config, llm_config)
        
        with patch(
            'wolo.compaction.policy.summary.GLMClient',
        ), patch.object(
            manager._history,
            'add_record',
        ) as mock_add:
            await manager.compact(
                create_large_session(50),
                "test-session"
            )
        
        assert mock_add.called


class TestCompactionManagerHistory:
    """历史相关方法测试。"""
    
    def test_get_history_returns_records(self):
        """获取历史记录。"""
        config = CompactionConfig()
        llm_config = MagicMock()
        manager = CompactionManager(config, llm_config)
        
        with patch.object(
            manager._history,
            'get_records',
            return_value=[MagicMock(), MagicMock()],
        ):
            records = manager.get_history("test-session")
        
        assert len(records) == 2
    
    def test_get_original_messages(self):
        """获取原始消息。"""
        config = CompactionConfig()
        llm_config = MagicMock()
        manager = CompactionManager(config, llm_config)
        
        mock_messages = [MagicMock(), MagicMock()]
        with patch.object(
            manager._history,
            'get_original_messages',
            return_value=mock_messages,
        ):
            messages = manager.get_original_messages("test-session", "record-1")
        
        assert messages == mock_messages
```

---

## 8. 验收标准

### 8.1 功能验收标准

| ID | 功能 | 验收标准 | 测试方法 |
|----|------|----------|----------|
| F1 | 策略模式架构 | 新增策略只需实现 CompactionPolicy 接口，无需修改其他代码 | 添加一个 mock 策略验证 |
| F2 | 摘要压缩 | 50条消息压缩后不超过 15 条（含摘要） | 单元测试 |
| F3 | 工具修剪 | 旧工具输出被替换为占位符，保留最近 2 轮 | 单元测试 |
| F4 | 配置加载 | 从 config.yaml 正确加载所有配置项 | 配置测试 |
| F5 | 历史保留 | 可通过记录 ID 查询原始消息 | 集成测试 |
| F6 | 自动触发 | 超过阈值时自动触发压缩 | 集成测试 |
| F7 | 禁用功能 | enabled=false 时完全跳过压缩 | 单元测试 |

### 8.2 非功能验收标准

| ID | 要求 | 验收标准 | 测试方法 |
|----|------|----------|----------|
| NF1 | 不可变性 | 原始消息列表在压缩后不被修改 | 对比压缩前后消息 ID |
| NF2 | Token 估算 | 估算误差不超过 30% | 与实际 API 返回对比 |
| NF3 | 代码覆盖 | 核心模块覆盖率 > 90% | pytest-cov |
| NF4 | 类型安全 | 通过 mypy 严格模式检查 | mypy --strict |
| NF5 | 文档完整 | 所有公开 API 有 docstring | pydocstyle |

### 8.3 代码质量标准

```python
# 所有文件必须通过以下检查：

# 1. 类型检查
# mypy --strict wolo/compaction/

# 2. 代码风格
# ruff check wolo/compaction/

# 3. 文档检查
# pydocstyle wolo/compaction/

# 4. 测试覆盖率
# pytest tests/compaction/ --cov=wolo/compaction --cov-report=term-missing
# 要求: 覆盖率 > 90%
```

### 8.4 交付物清单

| 序号 | 交付物 | 描述 |
|------|--------|------|
| 1 | `wolo/compaction/` | 完整的压缩模块 |
| 2 | `tests/compaction/` | 完整的测试套件 |
| 3 | 修改后的 `wolo/config.py` | 添加压缩配置 |
| 4 | 修改后的 `wolo/session.py` | Message 添加 metadata |
| 5 | 修改后的 `wolo/agent.py` | 集成 CompactionManager |
| 6 | 配置示例 | `config.yaml` 示例 |
| 7 | 测试报告 | pytest 输出 |
| 8 | 覆盖率报告 | pytest-cov 输出 |

---

## 附录 A: 消息数据结构修改

### A.1 修改 `wolo/session.py` 中的 Message 类

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
    metadata: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str = "",
        role: str = "",
        parts: list[Part] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.id = id or str(uuid.uuid4())
        self.role = role
        self.parts = parts or []
        self.timestamp = time.time()
        self.finished = False
        self.finish_reason = ""
        self.reasoning_content = ""
        self.metadata = metadata or {}
```

### A.2 修改序列化函数

```python
def _serialize_message(message: Message) -> dict[str, Any]:
    """Serialize a Message to dict for JSON storage."""
    return {
        "id": message.id,
        "role": message.role,
        "parts": [_serialize_part(p) for p in message.parts],
        "timestamp": message.timestamp,
        "finished": message.finished,
        "finish_reason": message.finish_reason,
        "reasoning_content": message.reasoning_content,
        "metadata": message.metadata,  # 新增
    }


def _deserialize_message(data: dict[str, Any]) -> Message:
    """Deserialize a dict to Message."""
    msg = Message(
        id=data["id"],
        role=data["role"],
        parts=[_deserialize_part(p) for p in data.get("parts", [])],
        metadata=data.get("metadata", {}),  # 新增
    )
    msg.timestamp = data.get("timestamp", time.time())
    msg.finished = data.get("finished", False)
    msg.finish_reason = data.get("finish_reason", "")
    msg.reasoning_content = data.get("reasoning_content", "")
    return msg
```

---

## 附录 B: agent.py 集成示例

```python
# 在 agent.py 中修改 _call_llm 函数

from wolo.compaction.manager import CompactionManager
from wolo.compaction.config import load_compaction_config

async def _call_llm(
    client: GLMClient,
    messages: list[Message],
    config: Config,
    session_id: str,  # 新增参数
    step: int,
    max_steps: int,
    control: Optional["ControlManager"],
    assistant_msg: Message,
    excluded_tools: set[str] = None,
) -> tuple[Message, list[dict], bool, float]:
    """Call LLM and handle streaming."""
    
    # 使用新的压缩管理器
    compaction_manager = CompactionManager(
        config.compaction,
        config,
    )
    
    messages_to_use = list(messages)
    
    # 检查是否需要压缩
    if step > 0 and step % config.compaction.check_interval_steps == 0:
        decision = compaction_manager.should_compact(messages, session_id)
        if decision.should_compact:
            logger.info(
                f"Compaction triggered: {decision.current_tokens} tokens "
                f"(threshold: {decision.limit_tokens})"
            )
            try:
                result = await compaction_manager.compact(messages, session_id)
                if result.status == CompactionStatus.APPLIED:
                    messages_to_use = list(result.result_messages)
                    logger.info(
                        f"Compacted: saved {result.total_tokens_saved} tokens, "
                        f"policies: {[p.value for p in result.policies_applied]}"
                    )
            except Exception as e:
                logger.warning(f"Compaction failed: {e}")
    
    # 继续原有逻辑...
    llm_messages = to_llm_messages(messages_to_use)
    # ...
```

---

**文档版本**: 1.0  
**创建日期**: 2025-01-27  
**最后更新**: 2025-01-27  
**状态**: 待开发
