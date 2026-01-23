"""
控制状态管理模块
管理插话、打断、暂停等状态
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto

logger = logging.getLogger(__name__)


class ControlState(Enum):
    """控制状态枚举"""

    IDLE = auto()  # 空闲
    RUNNING = auto()  # 正常运行
    INTERJECT_REQ = auto()  # 请求插话（等待步骤完成）
    INTERRUPT = auto()  # 请求打断（立即终止）
    PAUSED = auto()  # 已暂停
    WAIT_INPUT = auto()  # 等待用户输入


@dataclass
class ControlManager:
    """
    控制管理器

    管理 agent loop 的控制状态，支持：
    - 插话 (Ctrl+A): 等待当前步骤完成后让用户输入
    - 打断 (Ctrl+B): 立即终止当前操作，让用户输入
    - 暂停 (Ctrl+P): 暂停/恢复输出
    """

    state: ControlState = ControlState.IDLE
    pending_input: str | None = None
    step: int = 0
    max_steps: int = 100

    # 内部事件
    _pause_event: asyncio.Event = field(default_factory=asyncio.Event)
    _input_event: asyncio.Event = field(default_factory=asyncio.Event)
    _input_ready: asyncio.Event = field(default_factory=asyncio.Event)

    # 回调
    _on_state_change: Callable[["ControlManager"], None] | None = None

    def __post_init__(self):
        self._pause_event.set()  # 初始未暂停

    def set_state_callback(self, callback: Callable[["ControlManager"], None]):
        """设置状态变化回调"""
        self._on_state_change = callback

    def _set_state(self, new_state: ControlState):
        """设置状态并触发回调"""
        old_state = self.state
        if old_state == new_state:
            return
        self.state = new_state
        logger.debug(f"Control state: {old_state.name} -> {new_state.name}")
        if self._on_state_change:
            try:
                self._on_state_change(self)
            except Exception as e:
                logger.error(f"State callback error: {e}")

    # ==================== 用户操作 ====================

    def request_interject(self) -> bool:
        """
        请求插话 (Ctrl+A)
        等待当前步骤完成后让用户输入

        Returns:
            是否成功请求
        """
        if self.state == ControlState.RUNNING:
            self._set_state(ControlState.INTERJECT_REQ)
            logger.info("Interject requested")
            return True
        logger.debug(f"Cannot interject in state {self.state.name}")
        return False

    def request_interrupt(self) -> bool:
        """
        请求打断 (Ctrl+B)
        立即终止当前操作

        Returns:
            是否成功请求
        """
        if self.state in (ControlState.RUNNING, ControlState.INTERJECT_REQ, ControlState.PAUSED):
            self._set_state(ControlState.INTERRUPT)
            # 如果在暂停状态，也要恢复 pause_event 让循环继续
            self._pause_event.set()
            logger.info("Interrupt requested")
            return True
        logger.debug(f"Cannot interrupt in state {self.state.name}")
        return False

    def toggle_pause(self) -> bool:
        """
        切换暂停状态 (Ctrl+P)

        Returns:
            当前是否暂停
        """
        if self.state == ControlState.RUNNING:
            self._set_state(ControlState.PAUSED)
            self._pause_event.clear()
            logger.info("Paused")
            return True
        elif self.state == ControlState.PAUSED:
            self._set_state(ControlState.RUNNING)
            self._pause_event.set()
            logger.info("Resumed")
            return False
        logger.debug(f"Cannot toggle pause in state {self.state.name}")
        return self.state == ControlState.PAUSED

    def submit_input(self, text: str) -> bool:
        """
        提交用户输入

        Args:
            text: 用户输入的文本

        Returns:
            是否成功提交
        """
        if self.state == ControlState.WAIT_INPUT:
            self.pending_input = text
            self._input_event.set()
            logger.info(f"Input submitted: {text[:50]}...")
            return True
        logger.debug(f"Cannot submit input in state {self.state.name}")
        return False

    def cancel_input(self) -> bool:
        """
        取消输入（Esc）

        Returns:
            是否成功取消
        """
        if self.state == ControlState.WAIT_INPUT:
            self.pending_input = None
            self._set_state(ControlState.RUNNING)
            self._input_event.set()
            logger.info("Input cancelled")
            return True
        return False

    # ==================== Agent Loop 调用 ====================

    def start_running(self):
        """开始运行（agent loop 开始时调用）"""
        self._set_state(ControlState.RUNNING)
        self._pause_event.set()
        self.step = 0
        self.pending_input = None
        logger.debug("Control started")

    def set_step(self, step: int, max_steps: int = None):
        """
        更新步骤信息

        Args:
            step: 当前步骤
            max_steps: 最大步骤数（可选）
        """
        self.step = step
        if max_steps is not None:
            self.max_steps = max_steps
        # 触发回调更新 UI
        if self._on_state_change:
            try:
                self._on_state_change(self)
            except Exception as e:
                logger.error(f"State callback error: {e}")

    def check_step_boundary(self) -> str | None:
        """
        在步骤边界检查状态

        调用时机：每个 agent loop 步骤开始时

        Returns:
            None: 继续执行
            "WAIT": 需要等待用户输入
        """
        if self.state == ControlState.INTERJECT_REQ:
            # 插话请求：进入等待输入状态
            self._set_state(ControlState.WAIT_INPUT)
            logger.debug("Step boundary: entering WAIT_INPUT for interject")
            return "WAIT"

        if self.state == ControlState.INTERRUPT:
            # 打断请求：进入等待输入状态
            self._set_state(ControlState.WAIT_INPUT)
            logger.debug("Step boundary: entering WAIT_INPUT for interrupt")
            return "WAIT"

        return None

    def should_interrupt(self) -> bool:
        """
        检查是否应该立即中断

        调用时机：LLM 流式输出时、工具执行时

        Returns:
            是否应该中断
        """
        return self.state == ControlState.INTERRUPT

    async def wait_if_paused(self):
        """
        如果暂停则等待

        调用时机：输出前、循环迭代时
        """
        await self._pause_event.wait()

    async def wait_for_input(self) -> str | None:
        """
        等待用户输入

        Returns:
            用户输入的文本，或 None（取消）
        """
        if self.state != ControlState.WAIT_INPUT:
            return None

        self._input_event.clear()
        self._input_ready.set()  # 通知 UI 可以接收输入了

        logger.debug("Waiting for user input...")
        await self._input_event.wait()

        self._input_ready.clear()

        result = self.pending_input
        self.pending_input = None

        if result:
            self._set_state(ControlState.RUNNING)

        return result

    def is_input_ready(self) -> bool:
        """检查是否准备好接收输入"""
        return self._input_ready.is_set()

    def finish(self):
        """完成运行"""
        self._set_state(ControlState.IDLE)
        self._pause_event.set()
        self._input_event.set()  # 释放可能的等待
        logger.debug("Control finished")

    def reset(self):
        """重置状态"""
        self.state = ControlState.IDLE
        self.pending_input = None
        self.step = 0
        self._pause_event.set()
        self._input_event.clear()
        self._input_ready.clear()


# ==================== 全局管理器 ====================

_managers: dict[str, ControlManager] = {}


def get_manager(session_id: str) -> ControlManager:
    """
    获取或创建控制管理器

    Args:
        session_id: 会话 ID

    Returns:
        控制管理器实例
    """
    if session_id not in _managers:
        _managers[session_id] = ControlManager()
        logger.debug(f"Created control manager for session {session_id[:8]}...")
    return _managers[session_id]


def remove_manager(session_id: str):
    """
    移除控制管理器

    Args:
        session_id: 会话 ID
    """
    if session_id in _managers:
        _managers[session_id].finish()
        del _managers[session_id]
        logger.debug(f"Removed control manager for session {session_id[:8]}...")


def get_all_managers() -> dict[str, ControlManager]:
    """获取所有管理器（用于调试）"""
    return _managers.copy()
