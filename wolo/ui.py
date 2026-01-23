"""
基于 prompt_toolkit 的 UI 模块
提供状态栏、快捷键绑定、异步输入
"""

import asyncio
import logging
import os
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style

from wolo.control import ControlManager, ControlState
from wolo.terminal import TerminalManager, TerminalMode

logger = logging.getLogger(__name__)


# ==================== Output 配置 ====================


def _create_safe_output():
    """
    创建安全的 output，禁用 CPR 以避免兼容性问题。

    CPR (Cursor Position Request) 在某些终端环境下会导致：
    1. 警告信息：终端不支持 CPR
    2. CPR 响应被误读到 stdin，导致输入异常

    禁用 CPR 不会影响我们的功能，因为我们不使用需要光标位置的复杂 UI。
    """
    # from_pty 没有 enable_cpr 参数，需要先创建再设置
    output = Vt100_Output.from_pty(sys.stdout)
    output.enable_cpr = False  # 禁用 CPR 以避免兼容性问题
    return output


# ==================== 样式定义 ====================

UI_STYLE = Style.from_dict(
    {
        "status": "bg:#333333 #ffffff",
        "status.running": "bg:#333333 #00ff00 bold",
        "status.paused": "bg:#333333 #ffff00 bold",
        "status.waiting": "bg:#333333 #00ffff bold",
        "status.interrupt": "bg:#333333 #ff0000 bold",
        "status.idle": "bg:#333333 #888888",
        "status.shortcuts": "bg:#333333 #888888",
        "status.step": "bg:#333333 #aaaaaa",
        "prompt": "#00ff00 bold",
    }
)


# ==================== ANSI 颜色常量 ====================


class Colors:
    """ANSI 颜色代码"""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    BLACK = "\033[30m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


# ==================== SimpleUI ====================


class SimpleUI:
    """
    简化版 UI
    使用 prompt_toolkit 的 patch_stdout 和异步输入
    保持原生控制台风格
    """

    # 状态显示配置: (图标, 文本, 颜色)
    STATE_DISPLAY = {
        ControlState.IDLE: ("○", "空闲", Colors.GRAY),
        ControlState.RUNNING: ("▶", "运行中", Colors.GREEN),
        ControlState.INTERJECT_REQ: ("⏳", "等待步骤完成...", Colors.YELLOW),
        ControlState.INTERRUPT: ("⚡", "正在打断...", Colors.RED),
        ControlState.PAUSED: ("⏸", "已暂停", Colors.YELLOW),
        ControlState.WAIT_INPUT: ("✎", "等待输入", Colors.CYAN),
    }

    def __init__(self, manager: ControlManager, terminal: TerminalManager | None = None):
        """
        初始化 UI

        Args:
            manager: 控制管理器
            terminal: 终端管理器（可选，用于协调终端状态）
        """
        self.manager = manager
        self._terminal = terminal
        self._session: PromptSession | None = None
        self._last_notification: str = ""
        self._last_state: ControlState | None = None

        # 设置状态变化回调
        manager.set_state_callback(self._on_state_change)

    def _on_state_change(self, mgr: ControlManager):
        """状态变化回调"""
        state = mgr.state

        # 只在状态真正变化时才打印通知
        if state == self._last_state:
            return

        old_state = self._last_state
        self._last_state = state

        icon, text, color = self.STATE_DISPLAY.get(state, ("?", "未知", Colors.GRAY))

        # 根据状态打印通知
        if state == ControlState.INTERJECT_REQ:
            self._print_notification(f"{icon} 插话请求：等待当前步骤完成...", color)
        elif state == ControlState.INTERRUPT:
            self._print_notification(f"{icon} 打断请求：正在终止...", color)
        elif state == ControlState.PAUSED:
            self._print_notification(f"{icon} 已暂停 - Ctrl+P 恢复", color)
        elif state == ControlState.WAIT_INPUT:
            # 只在首次进入 WAIT_INPUT 时打印
            self._print_notification(f"{icon} 请输入补充信息:", color)
        elif state == ControlState.RUNNING:
            # 从暂停恢复时打印
            if old_state == ControlState.PAUSED:
                self._print_notification("▶ 已恢复", Colors.GREEN)

    def _print_notification(self, message: str, color: str = Colors.YELLOW):
        """打印通知消息"""
        self._last_notification = message
        print(f"\n{color}[{message}]{Colors.RESET}", flush=True)

    def print_shortcuts(self):
        """打印快捷键提示"""
        print(
            f"{Colors.DIM}[快捷键: ^A:插话 ^B:打断 ^P:暂停 ^S:Shell ^L:MCP ^H:帮助 ^C:退出]{Colors.RESET}",
            flush=True,
        )

    def print_status(self):
        """打印当前状态"""
        state = self.manager.state
        icon, text, color = self.STATE_DISPLAY.get(state, ("?", "未知", Colors.GRAY))
        step_info = f"Step: {self.manager.step}/{self.manager.max_steps}"
        print(
            f"{color}[{icon} {text}]{Colors.RESET} {Colors.DIM}{step_info}{Colors.RESET}",
            flush=True,
        )

    def _create_prompt_session(self) -> PromptSession:
        """创建 prompt session"""
        kb = KeyBindings()

        @kb.add("escape")
        def handle_escape(event):
            """Esc: 取消输入"""
            event.app.exit(result=None)

        @kb.add("c-c")
        def handle_ctrl_c(event):
            """Ctrl+C: 中断"""
            event.app.exit(exception=KeyboardInterrupt())

        @kb.add("enter")
        def handle_enter(event):
            """Enter: 提交输入（仅当输入不为空时）"""
            # 获取当前输入文本
            text = event.current_buffer.text
            # 如果输入为空（去除空白后），不提交
            if not text.strip():
                # 不调用 event.app.exit，继续等待输入
                # 可以给用户一个提示（可选）
                return
            # 输入不为空，正常提交
            event.app.exit(result=text)

        # 使用安全的 output（禁用 CPR）以避免兼容性问题
        output = _create_safe_output()

        return PromptSession(
            output=output,
            key_bindings=kb,
            style=UI_STYLE,
        )

    async def prompt_for_input(self, message: str = "") -> str | None:
        """
        提示用户输入

        Args:
            message: 可选的提示消息

        Returns:
            用户输入的文本，或 None（取消/中断）
        """
        if message:
            print(f"{Colors.CYAN}{message}{Colors.RESET}", flush=True)

        # prompt_toolkit 会自己管理终端设置
        # 但我们需要确保在完成后，如果 TerminalManager 可用，重新设置 cbreak 模式
        # 这样 KeyboardListener 才能继续工作
        if self._session is None:
            self._session = self._create_prompt_session()

        try:
            with patch_stdout():
                result = await self._session.prompt_async(
                    HTML("<prompt>> </prompt>"),
                )

            # prompt_toolkit 完成后，可能需要恢复终端状态
            # 如果 TerminalManager 可用，确保终端处于正确的状态
            # 注意：这里我们不能直接设置 cbreak，因为 KeyboardListener 的 context manager 会管理
            # 但我们可以确保 TerminalManager 知道当前状态
            if self._terminal and self._terminal.available:
                # 重新获取当前终端设置，因为 prompt_toolkit 可能改变了它们
                try:
                    import termios

                    fd = sys.stdin.fileno()
                    # 检查当前终端模式
                    termios.tcgetattr(fd)
                    # 如果 TerminalManager 认为应该在 cbreak 模式，但实际不是，则恢复
                    # 但这里我们不做强制设置，让 KeyboardListener 的 context manager 处理
                    # 只是确保 TerminalManager 知道当前状态可能被改变了
                    logger.debug("prompt_for_input completed, terminal state may have changed")
                except Exception:
                    pass

            return result.strip() if result else None

        except KeyboardInterrupt:
            logger.debug("Input interrupted by Ctrl+C")
            return None
        except EOFError:
            logger.debug("Input ended by EOF")
            return None
        except Exception as e:
            logger.error(f"Input error: {e}")
            return None

    async def wait_for_input_with_keyboard(self) -> str | None:
        """
        等待用户输入，支持 Esc 取消
        在 WAIT_INPUT 状态下使用

        Returns:
            用户输入的文本，或 None（取消）
        """
        print(f"{Colors.DIM}(输入后按回车继续，Esc 取消){Colors.RESET}", flush=True)

        result = await self.prompt_for_input()

        if result is None:
            # 用户取消
            print(f"{Colors.GRAY}[输入已取消]{Colors.RESET}", flush=True)

        return result


# ==================== 键盘监听器 ====================


class KeyboardListener:
    """
    后台键盘监听器
    在 agent loop 运行时监听快捷键

    使用 TerminalManager 来管理终端状态，避免与其他组件冲突。
    """

    def __init__(self, manager: ControlManager, terminal: TerminalManager):
        """
        初始化监听器

        Args:
            manager: 控制管理器
            terminal: 终端管理器
        """
        self.manager = manager
        self.terminal = terminal
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self):
        """启动监听"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.debug("Keyboard listener started")

    def stop(self):
        """停止监听"""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        # TerminalManager 会在 context manager 退出时自动恢复
        logger.debug("Keyboard listener stopped")

    async def _listen_loop(self):
        """
        监听循环

        使用 TerminalManager 来管理终端状态，确保在需要时使用 cbreak 模式。
        当状态是 WAIT_INPUT 或 IDLE 时，不监听（让其他组件如 prompt_toolkit 处理输入）。
        """
        if not self.terminal.available:
            logger.debug("Terminal management not available, keyboard listener disabled")
            return

        try:
            import select
        except ImportError:
            logger.warning("select not available, keyboard listener disabled")
            return

        fd = sys.stdin.fileno()

        try:
            # 使用 TerminalManager 的 context manager 来管理终端模式
            # 注意：这个 context manager 会在整个循环期间保持 cbreak 模式
            async with self.terminal.enter_mode(TerminalMode.CBREAK):
                while self._running:
                    # 检查是否应该监听（不在 WAIT_INPUT 和 IDLE 状态）
                    # 在这些状态下，其他组件（如 prompt_toolkit）可能需要使用终端
                    if self.manager.state in (ControlState.IDLE, ControlState.WAIT_INPUT):
                        await asyncio.sleep(0.1)
                        continue

                    # 在非 WAIT_INPUT/IDLE 状态下，确保终端处于 cbreak 模式
                    # prompt_toolkit 可能改变了终端状态，我们需要强制重新设置
                    # 使用 force=True 确保即使 TerminalManager 认为已经是 CBREAK，也重新设置
                    try:
                        await self.terminal.set_mode(TerminalMode.CBREAK, force=True)
                    except Exception as e:
                        logger.warning(f"Failed to ensure cbreak mode: {e}")

                    # 非阻塞检查输入
                    rlist, _, _ = select.select([fd], [], [], 0.05)
                    if rlist:
                        try:
                            ch = os.read(fd, 1)
                            if ch:
                                await self._handle_key(ch[0])
                        except OSError:
                            pass

                    await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Keyboard listener error: {e}")

    async def _handle_key(self, byte: int):
        """处理按键"""
        # Ctrl+A (1)
        if byte == 1:
            self.manager.request_interject()
        # Ctrl+B (2)
        elif byte == 2:
            self.manager.request_interrupt()
        # Ctrl+H (8) - Show help
        elif byte == 8:
            self._show_help()
        # Ctrl+L (12) - Show MCP status
        elif byte == 12:
            self._show_mcp_status()
        # Ctrl+P (16)
        elif byte == 16:
            self.manager.toggle_pause()
        # Ctrl+S (19) - Show shell status
        elif byte == 19:
            self._show_shell_status()
        # Ctrl+C (3)
        elif byte == 3:
            logger.debug("Ctrl+C pressed")
            raise KeyboardInterrupt()

    def _show_help(self):
        """显示帮助信息"""
        print(f"\n{Colors.CYAN}{'─' * 60}{Colors.RESET}")
        print(f"{Colors.CYAN}│ 快捷键帮助 (Ctrl+H){Colors.RESET}")
        print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}")
        print(f"  {Colors.YELLOW}Ctrl+A{Colors.RESET}  插话 - 等待当前步骤完成后输入补充信息")
        print(f"  {Colors.YELLOW}Ctrl+B{Colors.RESET}  打断 - 立即终止当前操作")
        print(f"  {Colors.YELLOW}Ctrl+P{Colors.RESET}  暂停/恢复 - 暂停或恢复输出和执行")
        print(f"  {Colors.YELLOW}Ctrl+S{Colors.RESET}  Shell状态 - 查看运行中和最近的命令")
        print(f"  {Colors.YELLOW}Ctrl+L{Colors.RESET}  MCP列表 - 查看MCP服务器连接状态")
        print(f"  {Colors.YELLOW}Ctrl+H{Colors.RESET}  帮助 - 显示此帮助信息")
        print(f"  {Colors.YELLOW}Ctrl+C{Colors.RESET}  退出 - 终止程序")
        print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}\n", flush=True)

    def _show_mcp_status(self):
        """显示 MCP 服务器状态"""
        from wolo.mcp_integration import get_mcp_status

        status = get_mcp_status()

        print(f"\n{Colors.CYAN}{'─' * 60}{Colors.RESET}")
        print(f"{Colors.CYAN}│ MCP 服务器状态 (Ctrl+L){Colors.RESET}")
        print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}")

        if not status.get("enabled"):
            print(f"  {Colors.DIM}MCP 未启用{Colors.RESET}")
        else:
            # Show overall status
            if status.get("initializing"):
                print(f"  {Colors.YELLOW}◐ 正在初始化...{Colors.RESET}")
            elif status.get("initialized"):
                print(f"  {Colors.GREEN}✓ 初始化完成{Colors.RESET}")

            # Show server details
            servers = status.get("servers", {})
            if not servers:
                print(f"  {Colors.DIM}未配置 MCP 服务器{Colors.RESET}")
            else:
                print()
                for name, info in servers.items():
                    server_status = info.get("status", "unknown")
                    tools_count = info.get("tools", 0)
                    error = info.get("error", "")

                    if server_status == "running":
                        icon, color = "✓", Colors.GREEN
                        detail = f"{tools_count} tools"
                    elif server_status == "starting":
                        icon, color = "◐", Colors.YELLOW
                        detail = "connecting..."
                    elif server_status == "error":
                        icon, color = "✗", Colors.RED
                        detail = error[:40] if error else "failed"
                    elif server_status == "disabled":
                        icon, color = "○", Colors.GRAY
                        detail = "disabled"
                    elif server_status == "stopped":
                        icon, color = "○", Colors.GRAY
                        detail = "stopped"
                    else:
                        icon, color = "?", Colors.GRAY
                        detail = server_status

                    print(f"  {color}{icon} {name}{Colors.RESET}: {detail}")

            # Show skills count
            skills = status.get("skills_count", 0)
            if skills > 0:
                print(f"\n  {Colors.MAGENTA}📚 {skills} skills loaded{Colors.RESET}")

        print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}\n", flush=True)

    def _show_shell_status(self):
        """显示 shell 进程状态"""
        from wolo.tools import get_shell_status

        status = get_shell_status()
        running = status.get("running", [])
        history = status.get("history", [])

        print(f"\n{Colors.CYAN}{'─' * 60}{Colors.RESET}")
        print(f"{Colors.CYAN}│ Shell Status (Ctrl+S){Colors.RESET}")
        print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}")

        if running:
            print(f"{Colors.YELLOW}▶ Running:{Colors.RESET}")
            for shell in running:
                elapsed = __import__("time").time() - shell.get("start_time", 0)
                cmd = shell.get("command", "")[:50]
                print(
                    f"  {Colors.WHITE}$ {cmd}{Colors.RESET} {Colors.DIM}({elapsed:.1f}s){Colors.RESET}"
                )
        else:
            print(f"{Colors.DIM}  No running shells{Colors.RESET}")

        if history:
            print(f"\n{Colors.GREEN}✓ Recent:{Colors.RESET}")
            for shell in history[:3]:
                cmd = shell.get("command", "")[:50]
                duration = shell.get("duration", 0)
                exit_code = shell.get("exit_code", 0)
                status_icon = "✓" if exit_code == 0 else "✗"
                status_color = Colors.GREEN if exit_code == 0 else Colors.RED

                print(
                    f"  {status_color}{status_icon}{Colors.RESET} {Colors.DIM}$ {cmd}{Colors.RESET} {Colors.DIM}({duration:.1f}s){Colors.RESET}"
                )

                # Show last few lines of output
                output_lines = shell.get("output_lines", [])
                if output_lines:
                    # Show last 3 non-empty lines
                    recent = [ln for ln in output_lines[-5:] if ln.strip()][-3:]
                    for line in recent:
                        truncated = line[:70] + "..." if len(line) > 70 else line
                        print(f"    {Colors.DIM}{truncated}{Colors.RESET}")

        print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}\n", flush=True)


# ==================== 输出包装器 ====================


class OutputWrapper:
    """
    输出包装器
    在暂停状态下缓冲输出
    """

    def __init__(self, manager: ControlManager):
        self.manager = manager
        self._buffer: list[str] = []
        self._original_stdout = sys.stdout

    async def write(self, text: str):
        """
        写入文本，如果暂停则等待

        Args:
            text: 要输出的文本
        """
        # 等待暂停恢复
        await self.manager.wait_if_paused()

        # 检查打断
        if self.manager.should_interrupt():
            return

        # 输出
        print(text, end="", flush=True)

    def write_sync(self, text: str):
        """
        同步写入（不检查暂停）

        Args:
            text: 要输出的文本
        """
        print(text, end="", flush=True)


# ==================== 便捷函数 ====================


def create_ui(
    manager: ControlManager, terminal: TerminalManager | None = None
) -> tuple[SimpleUI, KeyboardListener]:
    """
    创建 UI 和键盘监听器

    Args:
        manager: 控制管理器
        terminal: 终端管理器（如果为 None，会创建新的）

    Returns:
        (UI 实例, 键盘监听器实例)
    """
    if terminal is None:
        from wolo.terminal import get_terminal_manager

        terminal = get_terminal_manager()

    ui = SimpleUI(manager, terminal)
    keyboard = KeyboardListener(manager, terminal)
    return ui, keyboard


# ==================== UI 实例注册 ====================

_current_ui: SimpleUI | None = None


def register_ui(ui: SimpleUI) -> None:
    """
    注册当前活动的UI实例。

    用于让其他模块（如question_ui）访问UI实例以使用统一的输入方法。

    Args:
        ui: UI实例
    """
    global _current_ui
    _current_ui = ui
    logger.debug("UI instance registered")


def get_current_ui() -> SimpleUI | None:
    """
    获取当前活动的UI实例。

    Returns:
        UI实例，如果未注册则返回None
    """
    return _current_ui


def unregister_ui() -> None:
    """
    取消注册UI实例。

    应在agent_loop结束时调用，确保UI实例生命周期正确管理。
    """
    global _current_ui
    _current_ui = None
    logger.debug("UI instance unregistered")
