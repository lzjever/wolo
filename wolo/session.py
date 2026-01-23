"""Session and message management for Wolo.

This module implements a layered storage architecture with immediate persistence:
- Session metadata stored in session.json
- Each message stored in separate files under messages/
- Todos stored in todos.json
- All writes are immediate to prevent data loss on crash
"""

import fcntl
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ==================== Data Classes ====================


@dataclass
class Part:
    id: str
    type: str


@dataclass
class TextPart(Part):
    text: str = ""

    def __init__(self, id: str = "", text: str = ""):
        self.id = id or str(uuid.uuid4())
        self.type = "text"
        self.text = text


@dataclass
class ToolPart(Part):
    tool: str
    input: dict[str, Any]
    output: str = ""
    status: str = "pending"
    start_time: float = 0.0
    end_time: float = 0.0

    def __init__(
        self,
        id: str = "",
        tool: str = "",
        input: dict | None = None,
        output: str = "",
        status: str = "pending",
    ):
        self.id = id if id else str(uuid.uuid4())
        self.type = "tool"
        self.tool = tool
        self.input = input or {}
        self.output = output
        self.status = status
        self.start_time = 0.0
        self.end_time = 0.0


@dataclass
class Message:
    id: str
    role: str
    parts: list[Part]
    timestamp: float
    finished: bool = False
    finish_reason: str = ""
    reasoning_content: str = ""  # GLM thinking mode
    metadata: dict[str, Any] = field(
        default_factory=dict
    )  # Extensible metadata (e.g., compaction info)

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
        self.metadata = metadata if metadata is not None else {}


@dataclass
class Session:
    id: str
    messages: list[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    parent_session_id: str | None = None
    agent_type: str | None = None
    title: str | None = None
    tags: list[str] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def add_message(self, message: Message) -> None:
        self.messages.append(message)
        self.updated_at = time.time()

    def get_messages(self) -> list[Message]:
        return self.messages


# ==================== Helper Functions ====================


def _generate_session_id(agent_name: str) -> str:
    """
    生成 session_id: {AgentName}_{YYMMDD}_{HHMMSS}

    Args:
        agent_name: Agent 显示名称（可能包含空格）

    Returns:
        session_id 字符串，格式：{SanitizedName}_{YYMMDD}_{HHMMSS}
    """
    # 去除 agent_name 中的所有空格
    sanitized_name = agent_name.replace(" ", "")

    # 获取当前时间
    now = datetime.now()

    # 格式化时间戳：YYMMDD_HHMMSS
    # 年份只取后2位，例如 2026 -> 26
    timestamp = now.strftime("%y%m%d_%H%M%S")

    # 组合：{sanitized_name}_{timestamp}
    session_id = f"{sanitized_name}_{timestamp}"

    return session_id


# ==================== Process Status Checking ====================


def _is_wolo_process_running(pid: int) -> bool:
    """
    检查指定 PID 是否是一个正在运行的 wolo 进程。

    这是统一的进程状态检查函数，处理：
    - PID 重用问题（排除当前进程）
    - 进程不存在的情况
    - 命令行检查确认是 wolo 进程

    Args:
        pid: 要检查的进程 ID

    Returns:
        True 如果是一个正在运行的 wolo 进程（且不是当前进程）
    """
    # 排除当前进程（避免 PID 重用导致把自己当作已运行的进程）
    if pid == os.getpid():
        return False

    try:
        import psutil

        try:
            process = psutil.Process(pid)
            cmdline = process.cmdline()
            is_wolo_process = any("wolo" in arg for arg in cmdline)
            return is_wolo_process and process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
    except ImportError:
        # psutil 不可用，无法检查
        return False


# ==================== Storage Layer ====================


class SessionStorage:
    """
    Layered storage for sessions with immediate persistence.

    Directory structure:
    ~/.wolo/sessions/{session_id}/
    ├── session.json       # Session metadata
    ├── messages/
    │   ├── {msg_id}.json  # Each message in separate file
    │   └── ...
    └── todos.json         # Todos state
    """

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or (Path.home() / ".wolo" / "sessions")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _session_dir(self, session_id: str) -> Path:
        """Get session directory path."""
        return self.base_dir / session_id

    def _session_file(self, session_id: str) -> Path:
        """Get session metadata file path."""
        return self._session_dir(session_id) / "session.json"

    def _messages_dir(self, session_id: str) -> Path:
        """Get messages directory path."""
        return self._session_dir(session_id) / "messages"

    def _message_file(self, session_id: str, message_id: str) -> Path:
        """Get message file path."""
        return self._messages_dir(session_id) / f"{message_id}.json"

    def _todos_file(self, session_id: str) -> Path:
        """Get todos file path."""
        return self._session_dir(session_id) / "todos.json"

    def _write_json(self, path: Path, data: dict) -> None:
        """Write JSON with file locking for safety."""
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file first, then rename (atomic)
        temp_path = path.with_suffix(".tmp")
        try:
            with open(temp_path, "w") as f:
                # Get exclusive lock
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Atomic rename
            temp_path.rename(path)
        except Exception as e:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise e

    def _read_json(self, path: Path) -> dict | None:
        """Read JSON with file locking."""
        if not path.exists():
            return None

        try:
            with open(path) as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to read {path}: {e}")
            return None

    # ==================== Session Operations ====================

    def create_session(self, session_id: str | None = None, agent_name: str | None = None) -> str:
        """
        Create a new session with immediate persistence.

        Args:
            session_id: 手动指定的 session_id，如果为 None 则自动生成
            agent_name: 用于生成 session_id 的 agent 名称，仅在 session_id 为 None 时使用

        Returns:
            session_id 字符串

        Raises:
            ValueError: 如果指定的 session_id 已存在
        """
        # 如果未指定 session_id，则自动生成
        if session_id is None:
            if agent_name is None:
                # 如果没有提供 agent_name，使用随机生成的名称
                from wolo.agent_names import get_random_agent_name

                agent_name = get_random_agent_name()
            session_id = _generate_session_id(agent_name)

        # 检查 session_id 是否已存在
        if self.session_exists(session_id):
            raise ValueError(f"Session '{session_id}' already exists. Please use a different name.")

        session_dir = self._session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        self._messages_dir(session_id).mkdir(exist_ok=True)

        # If agent_name was provided, use it; otherwise generate one
        if agent_name is None:
            from wolo.agent_names import get_random_agent_name

            agent_name = get_random_agent_name()

        metadata = {
            "id": session_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "parent_session_id": None,
            "agent_type": None,
            "title": None,
            "tags": [],
            "agent_display_name": agent_name,  # Store the agent name
            "pid": None,  # 新增：当前运行进程的 PID
            "pid_updated_at": None,  # 新增：PID 更新时间
        }
        self._write_json(self._session_file(session_id), metadata)
        logger.debug(f"Created session {session_id[:8]}...")
        return session_id

    def get_session_metadata(self, session_id: str) -> dict | None:
        """Get session metadata."""
        return self._read_json(self._session_file(session_id))

    def get_or_create_agent_display_name(self, session_id: str) -> str:
        """
        Get agent display name from session, or create a new one if not exists.

        Args:
            session_id: Session ID

        Returns:
            Agent display name
        """
        metadata = self.get_session_metadata(session_id)
        if metadata and metadata.get("agent_display_name"):
            return metadata["agent_display_name"]

        # Generate new name and save it
        from wolo.agent_names import get_random_agent_name

        agent_display_name = get_random_agent_name()
        self.update_session_metadata(session_id, agent_display_name=agent_display_name)
        logger.debug(
            f"Generated new agent display name: {agent_display_name} for session {session_id[:8]}..."
        )
        return agent_display_name

    def update_session_metadata(self, session_id: str, **kwargs) -> None:
        """Update session metadata fields."""
        metadata = self.get_session_metadata(session_id)
        if metadata:
            metadata.update(kwargs)
            metadata["updated_at"] = time.time()
            self._write_json(self._session_file(session_id), metadata)

    def session_exists(self, session_id: str) -> bool:
        """Check if session exists."""
        return self._session_file(session_id).exists()

    def delete_session(self, session_id: str) -> bool:
        """Delete session and all its data."""
        session_dir = self._session_dir(session_id)
        if not session_dir.exists():
            return False

        import shutil

        shutil.rmtree(session_dir)
        logger.debug(f"Deleted session {session_id[:8]}...")
        return True

    def check_and_set_pid(self, session_id: str) -> bool:
        """
        检查 session 是否已有运行中的进程，如果没有则设置当前 PID。

        Args:
            session_id: Session ID

        Returns:
            True 如果成功设置 PID（没有冲突），False 如果有运行中的进程

        Raises:
            FileNotFoundError: 如果 session 不存在
        """
        metadata = self.get_session_metadata(session_id)
        if not metadata:
            raise FileNotFoundError(f"Session not found: {session_id}")

        stored_pid = metadata.get("pid")
        current_pid = os.getpid()

        # 如果有存储的 PID 且进程正在运行，拒绝设置
        if stored_pid is not None and _is_wolo_process_running(stored_pid):
            return False

        # 设置当前 PID
        self.update_session_metadata(session_id, pid=current_pid, pid_updated_at=time.time())
        return True

    def clear_pid(self, session_id: str) -> None:
        """
        清除 session 的 PID（当进程退出时调用）。

        Args:
            session_id: Session ID
        """
        self.update_session_metadata(session_id, pid=None, pid_updated_at=None)

    def get_session_status(self, session_id: str) -> dict:
        """
        获取 session 的运行状态（统一检查进程和watch服务器）。

        Args:
            session_id: Session ID

        Returns:
            包含状态信息的字典：
            {
                "exists": bool,
                "pid": int | None,
                "is_running": bool,
                "watch_server_available": bool,
                "agent_name": str | None,
                "created_at": float | None,
                "message_count": int,
            }
        """
        metadata = self.get_session_metadata(session_id)
        if not metadata:
            return {"exists": False}

        # 使用统一的进程状态检查
        stored_pid = metadata.get("pid")
        is_running = stored_pid is not None and _is_wolo_process_running(stored_pid)

        # 检查watch服务器状态（socket文件）
        socket_path = self._session_dir(session_id) / "watch.sock"
        watch_server_available = socket_path.exists()

        # 计算消息数量
        messages_dir = self._messages_dir(session_id)
        message_count = len(list(messages_dir.glob("*.json"))) if messages_dir.exists() else 0

        return {
            "exists": True,
            "pid": stored_pid,
            "is_running": is_running,
            "watch_server_available": watch_server_available,
            "agent_name": metadata.get("agent_display_name"),
            "created_at": metadata.get("created_at"),
            "message_count": message_count,
        }

    def list_sessions(self) -> list[dict]:
        """List all sessions with metadata."""
        sessions = []
        for session_dir in self.base_dir.iterdir():
            if session_dir.is_dir():
                metadata = self.get_session_metadata(session_dir.name)
                if metadata:
                    # Count messages
                    messages_dir = self._messages_dir(session_dir.name)
                    message_count = (
                        len(list(messages_dir.glob("*.json"))) if messages_dir.exists() else 0
                    )
                    metadata["message_count"] = message_count

                    # 使用统一的进程状态检查
                    stored_pid = metadata.get("pid")
                    metadata["is_running"] = stored_pid is not None and _is_wolo_process_running(
                        stored_pid
                    )
                    sessions.append(metadata)

        return sorted(sessions, key=lambda x: x.get("updated_at", 0), reverse=True)

    # ==================== Message Operations ====================

    def save_message(self, session_id: str, message: Message) -> None:
        """Save a message immediately."""
        data = _serialize_message(message)
        self._write_json(self._message_file(session_id, message.id), data)
        self.update_session_metadata(session_id)  # Update timestamp
        logger.debug(f"Saved message {message.id[:8]}... to session {session_id[:8]}...")

    def get_message(self, session_id: str, message_id: str) -> Message | None:
        """Get a single message."""
        data = self._read_json(self._message_file(session_id, message_id))
        if data:
            return _deserialize_message(data)
        return None

    def get_all_messages(self, session_id: str) -> list[Message]:
        """Get all messages for a session, sorted by timestamp."""
        messages = []
        messages_dir = self._messages_dir(session_id)

        if not messages_dir.exists():
            return messages

        for msg_file in messages_dir.glob("*.json"):
            data = self._read_json(msg_file)
            if data:
                messages.append(_deserialize_message(data))

        # Sort by timestamp
        messages.sort(key=lambda m: m.timestamp)
        return messages

    def delete_message(self, session_id: str, message_id: str) -> bool:
        """Delete a message."""
        msg_file = self._message_file(session_id, message_id)
        if msg_file.exists():
            msg_file.unlink()
            return True
        return False

    # ==================== Todos Operations ====================

    def save_todos(self, session_id: str, todos: list[dict]) -> None:
        """Save todos for a session."""
        self._write_json(self._todos_file(session_id), {"todos": todos})

    def get_todos(self, session_id: str) -> list[dict]:
        """Get todos for a session."""
        data = self._read_json(self._todos_file(session_id))
        if data:
            return data.get("todos", [])
        return []

    # ==================== Full Session Load/Save ====================

    def load_full_session(self, session_id: str) -> Session | None:
        """Load a complete session with all messages."""
        metadata = self.get_session_metadata(session_id)
        if not metadata:
            return None

        session = Session(id=session_id)
        session.created_at = metadata.get("created_at", time.time())
        session.updated_at = metadata.get("updated_at", time.time())
        session.parent_session_id = metadata.get("parent_session_id")
        session.agent_type = metadata.get("agent_type")
        session.title = metadata.get("title")
        session.tags = metadata.get("tags", [])
        session.messages = self.get_all_messages(session_id)

        return session

    def save_full_session(self, session: Session) -> None:
        """Save a complete session (for migration/backup)."""
        # Ensure session directory exists
        self._session_dir(session.id).mkdir(parents=True, exist_ok=True)
        self._messages_dir(session.id).mkdir(exist_ok=True)

        # Get existing metadata to preserve agent_display_name
        existing_metadata = self.get_session_metadata(session.id) or {}

        # Save metadata
        metadata = {
            "id": session.id,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "parent_session_id": session.parent_session_id,
            "agent_type": session.agent_type,
            "title": session.title,
            "tags": session.tags,
            "agent_display_name": existing_metadata.get(
                "agent_display_name"
            ),  # Preserve agent_display_name
        }
        self._write_json(self._session_file(session.id), metadata)

        # Save all messages
        for message in session.messages:
            self.save_message(session.id, message)


# ==================== Session Saver with Debouncing ====================


class SessionSaver:
    """
    Debounced session saver for aggressive auto-save.

    This class provides debounced saving to avoid performance issues
    with frequent saves while ensuring data safety.

    Usage:
        saver = SessionSaver(session_id)

        # Regular save (debounced)
        saver.save()

        # Force save (ignores debounce)
        saver.save(force=True)

        # Flush pending saves (call in finally block)
        saver.flush()
    """

    MIN_SAVE_INTERVAL = 0.5  # seconds

    def __init__(self, session_id: str):
        """
        Initialize session saver.

        Args:
            session_id: Session ID to save
        """
        self.session_id = session_id
        self.last_save_time: float = 0
        self.pending_save: bool = False
        self._storage = get_storage()

    def save(self, force: bool = False) -> None:
        """
        Save session with debouncing.

        Args:
            force: If True, save immediately regardless of interval
        """
        now = time.time()

        if force or (now - self.last_save_time) >= self.MIN_SAVE_INTERVAL:
            self._do_save()
            self.last_save_time = now
            self.pending_save = False
        else:
            self.pending_save = True

    def flush(self) -> None:
        """Force save if there's a pending save."""
        if self.pending_save:
            self._do_save()
            self.pending_save = False

    def _do_save(self) -> None:
        """Perform the actual save."""
        session = get_session(self.session_id)
        if session:
            self._storage.save_full_session(session)
            logger.debug(f"Auto-saved session {self.session_id[:8]}...")


# ==================== Global Saver Registry ====================

_savers: dict[str, SessionSaver] = {}


def get_session_saver(session_id: str) -> SessionSaver:
    """
    Get or create a SessionSaver for the given session.

    Args:
        session_id: Session ID

    Returns:
        SessionSaver instance
    """
    if session_id not in _savers:
        _savers[session_id] = SessionSaver(session_id)
    return _savers[session_id]


def remove_session_saver(session_id: str) -> None:
    """
    Remove a SessionSaver when session is closed.

    Flushes any pending saves before removal.

    Args:
        session_id: Session ID
    """
    if session_id in _savers:
        _savers[session_id].flush()
        del _savers[session_id]


# ==================== Global Storage Instance ====================

_storage: SessionStorage | None = None


def get_storage() -> SessionStorage:
    """Get the global storage instance."""
    global _storage
    if _storage is None:
        _storage = SessionStorage()
    return _storage


def set_storage(storage: SessionStorage) -> None:
    """Set the global storage instance (for testing)."""
    global _storage
    _storage = storage


# ==================== In-Memory Cache ====================

_sessions: dict[str, Session] = {}


# ==================== Serialization ====================


def _serialize_part(part: Part) -> dict[str, Any]:
    """Serialize a Part to dict for JSON storage."""
    if isinstance(part, TextPart):
        return {"type": "text", "id": part.id, "text": part.text}
    elif isinstance(part, ToolPart):
        return {
            "type": "tool",
            "id": part.id,
            "tool": part.tool,
            "input": part.input,
            "output": part.output,
            "status": part.status,
            "start_time": part.start_time,
            "end_time": part.end_time,
        }
    else:
        return {"type": part.type, "id": part.id}


def _deserialize_part(data: dict[str, Any]) -> Part:
    """Deserialize a dict to a Part."""
    part_type = data.get("type", "text")
    if part_type == "text":
        return TextPart(id=data.get("id", ""), text=data.get("text", ""))
    elif part_type == "tool":
        part = ToolPart(
            id=data.get("id", ""),
            tool=data.get("tool", ""),
            input=data.get("input", {}),
            output=data.get("output", ""),  # ✅ Fixed: restore output
            status=data.get("status", "pending"),  # ✅ Fixed: restore status
        )
        part.start_time = data.get("start_time", 0.0)
        part.end_time = data.get("end_time", 0.0)
        return part
    else:
        return Part(id=data.get("id", ""), type=part_type)


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
        "metadata": message.metadata,  # Extensible metadata (e.g., compaction info)
    }


def _deserialize_message(data: dict[str, Any]) -> Message:
    """Deserialize a dict to a Message."""
    message = Message(
        id=data.get("id", ""),
        role=data.get("role", ""),
        metadata=data.get("metadata", {}),
    )
    message.parts = [_deserialize_part(p) for p in data.get("parts", [])]
    message.timestamp = data.get("timestamp", time.time())
    message.finished = data.get("finished", False)
    message.finish_reason = data.get("finish_reason", "")
    message.reasoning_content = data.get("reasoning_content", "")
    return message


# ==================== Public API (Backward Compatible) ====================


def create_session(session_id: str | None = None, agent_name: str | None = None) -> str:
    """
    Create a new session.

    Args:
        session_id: 手动指定的 session_id，如果为 None 则自动生成
        agent_name: 用于生成 session_id 的 agent 名称，仅在 session_id 为 None 时使用

    Returns:
        session_id 字符串

    Raises:
        ValueError: 如果指定的 session_id 已存在
    """
    storage = get_storage()
    session_id = storage.create_session(session_id=session_id, agent_name=agent_name)

    # Also create in-memory
    _sessions[session_id] = Session(id=session_id)
    return session_id


def create_subsession(parent_session_id: str, agent_type: str) -> str:
    """Create a subsession for a subagent."""
    storage = get_storage()
    session_id = storage.create_session()
    storage.update_session_metadata(
        session_id, parent_session_id=parent_session_id, agent_type=agent_type
    )

    # Also create in-memory
    session = Session(id=session_id)
    session.parent_session_id = parent_session_id
    session.agent_type = agent_type
    _sessions[session_id] = session

    return session_id


def get_session(session_id: str) -> Session | None:
    """Get a session (from memory or disk)."""
    if session_id in _sessions:
        return _sessions[session_id]

    # Try to load from disk
    storage = get_storage()
    session = storage.load_full_session(session_id)
    if session:
        _sessions[session_id] = session
    return session


def add_user_message(session_id: str, text: str) -> Message:
    """Add a user message and persist immediately."""
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    message = Message(role="user")
    message.parts.append(TextPart(text=text))
    message.finished = True
    session.add_message(message)

    # Persist immediately
    storage = get_storage()
    storage.save_message(session_id, message)

    return message


def add_assistant_message(session_id: str) -> Message:
    """Add an assistant message and persist immediately."""
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    message = Message(role="assistant")
    session.add_message(message)

    # Persist immediately
    storage = get_storage()
    storage.save_message(session_id, message)

    return message


def update_message(session_id: str, message: Message) -> None:
    """Update a message and persist immediately."""
    storage = get_storage()
    storage.save_message(session_id, message)


def get_session_messages(session_id: str) -> list[Message]:
    """Get all messages for a session."""
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")
    return session.get_messages()


def find_last_user_message(messages: list[Message]) -> Message | None:
    """Find the last user message."""
    for message in reversed(messages):
        if message.role == "user":
            return message
    return None


def find_last_assistant_message(messages: list[Message]) -> Message | None:
    """Find the last assistant message."""
    for message in reversed(messages):
        if message.role == "assistant":
            return message
    return None


def has_pending_tool_calls(message: Message) -> bool:
    """Check if message has pending tool calls."""
    for part in message.parts:
        if isinstance(part, ToolPart) and part.status == "pending":
            return True
    return False


def get_pending_tool_calls(message: Message) -> list[ToolPart]:
    """Get all pending tool calls from a message."""
    return [p for p in message.parts if isinstance(p, ToolPart) and p.status == "pending"]


def get_all_tool_calls(message: Message) -> list[ToolPart]:
    """Get all tool calls from a message."""
    return [p for p in message.parts if isinstance(p, ToolPart)]


def to_llm_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert messages to GLM API format."""
    result = []

    for message in messages:
        text_parts = [p for p in message.parts if isinstance(p, TextPart)]
        tool_parts = [p for p in message.parts if isinstance(p, ToolPart)]
        text_content = "\n".join(p.text for p in text_parts)

        if message.role == "assistant":
            tool_calls = []
            for part in tool_parts:
                if part.status in ("pending", "running", "completed"):
                    tool_calls.append(
                        {
                            "id": part.id,
                            "type": "function",
                            "function": {"name": part.tool, "arguments": json.dumps(part.input)},
                        }
                    )

            msg_data = {"role": "assistant"}
            if text_content:
                msg_data["content"] = text_content
            if tool_calls:
                msg_data["tool_calls"] = tool_calls
            if message.reasoning_content:
                msg_data["reasoning_content"] = message.reasoning_content

            if text_content or tool_calls:
                result.append(msg_data)

            for part in tool_parts:
                if part.status == "completed":
                    result.append(
                        {
                            "role": "tool",
                            "tool_call_id": part.id,
                            "content": part.output or "Tool completed",
                        }
                    )

        elif message.role == "user":
            if text_content:
                result.append({"role": "user", "content": text_content})

    return result


# ==================== Session Persistence (Backward Compatible) ====================


def get_sessions_dir() -> Path:
    """Get the directory where sessions are stored."""
    return get_storage().base_dir


def save_session(session_id: str, sessions_dir: Path | None = None) -> None:
    """Save a session to disk (full save for backward compatibility)."""
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    storage = get_storage()
    storage.save_full_session(session)
    logger.info(f"Session saved: {session_id[:8]}...")


def load_session(session_id: str, sessions_dir: Path | None = None) -> Session:
    """Load a session from disk."""
    storage = get_storage()

    # Check new format first
    session = storage.load_full_session(session_id)
    if session:
        _sessions[session_id] = session
        return session

    # Try old format (single JSON file)
    old_file = storage.base_dir / f"{session_id}.json"
    if old_file.exists():
        with open(old_file) as f:
            data = json.load(f)
        session = _deserialize_session_legacy(data)
        _sessions[session_id] = session

        # Migrate to new format
        storage.save_full_session(session)
        old_file.unlink()  # Remove old file
        logger.info(f"Migrated session {session_id[:8]}... to new format")

        return session

    raise FileNotFoundError(f"Session not found: {session_id}")


def _deserialize_session_legacy(data: dict[str, Any]) -> Session:
    """Deserialize old format session."""
    session = Session(id=data.get("id", ""))
    session.messages = [_deserialize_message(m) for m in data.get("messages", [])]
    session.created_at = data.get("created_at", time.time())
    session.parent_session_id = data.get("parent_session_id")
    session.agent_type = data.get("agent_type")
    session.title = data.get("title")
    session.tags = data.get("tags", [])
    session.updated_at = data.get("updated_at", data.get("created_at", time.time()))
    return session


def list_sessions(sessions_dir: Path | None = None) -> list[dict[str, Any]]:
    """List all saved sessions."""
    storage = get_storage()
    sessions = storage.list_sessions()

    # 不再支持旧格式，只返回新格式
    return sessions


def check_and_set_session_pid(session_id: str) -> bool:
    """
    检查并设置 session PID（公共 API）。

    Returns:
        True 如果成功，False 如果有运行中的进程
    """
    storage = get_storage()
    return storage.check_and_set_pid(session_id)


def clear_session_pid(session_id: str) -> None:
    """清除 session PID（公共 API）。"""
    storage = get_storage()
    storage.clear_pid(session_id)


def get_session_status(session_id: str) -> dict:
    """获取 session 状态（公共 API）。"""
    storage = get_storage()
    return storage.get_session_status(session_id)


def delete_session(session_id: str, sessions_dir: Path | None = None) -> bool:
    """Delete a session from disk."""
    storage = get_storage()

    # Try new format
    if storage.delete_session(session_id):
        if session_id in _sessions:
            del _sessions[session_id]
        return True

    # Try old format
    old_file = storage.base_dir / f"{session_id}.json"
    if old_file.exists():
        old_file.unlink()
        if session_id in _sessions:
            del _sessions[session_id]
        return True

    return False


def search_sessions(query: str, sessions_dir: Path | None = None) -> list[dict[str, Any]]:
    """Search for sessions by title or tags."""
    all_sessions = list_sessions(sessions_dir)
    query_lower = query.lower()

    results = []
    for session in all_sessions:
        title = session.get("title", "") or ""
        tags = session.get("tags", []) or []

        if query_lower in title.lower() or any(query_lower in tag.lower() for tag in tags):
            results.append(session)

    return results


def delete_old_sessions(days: int = 30, sessions_dir: Path | None = None) -> int:
    """Delete sessions older than the specified number of days."""
    cutoff_time = time.time() - (days * 24 * 60 * 60)
    all_sessions = list_sessions(sessions_dir)
    deleted_count = 0

    for session in all_sessions:
        if session.get("updated_at", 0) < cutoff_time:
            if delete_session(session["id"]):
                deleted_count += 1

    return deleted_count


def set_session_title(session_id: str, title: str) -> None:
    """Set the title of a session."""
    session = get_session(session_id)
    if session:
        session.title = title
        session.updated_at = time.time()
        get_storage().update_session_metadata(session_id, title=title)


def add_session_tag(session_id: str, tag: str) -> None:
    """Add a tag to a session."""
    session = get_session(session_id)
    if session and tag not in session.tags:
        session.tags.append(tag)
        session.updated_at = time.time()
        get_storage().update_session_metadata(session_id, tags=session.tags)


# ==================== Todos Persistence ====================


def save_session_todos(session_id: str, todos: list[dict]) -> None:
    """Save todos for a session."""
    get_storage().save_todos(session_id, todos)


def load_session_todos(session_id: str) -> list[dict]:
    """Load todos for a session."""
    return get_storage().get_todos(session_id)


def get_or_create_agent_display_name(session_id: str) -> str:
    """
    Get agent display name from session, or create a new one if not exists.

    Args:
        session_id: Session ID

    Returns:
        Agent display name
    """
    storage = get_storage()
    return storage.get_or_create_agent_display_name(session_id)
