"""Watch server for broadcasting session events to observers."""

import asyncio
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class WatchServer:
    """
    Unix Domain Socket 服务器，用于向观察者广播 session 事件。

    重要：这个服务器只负责发送事件，不修改任何 session 数据。
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.socket_path = self._get_socket_path(session_id)
        self.server: asyncio.Server | None = None
        self.observers: set[asyncio.StreamWriter] = set()
        self._lock = asyncio.Lock()

    def _get_socket_path(self, session_id: str) -> Path:
        """获取 socket 文件路径."""
        sessions_dir = Path.home() / ".wolo" / "sessions" / session_id
        sessions_dir.mkdir(parents=True, exist_ok=True)
        return sessions_dir / "watch.sock"

    async def start(self) -> None:
        """启动 watch 服务器."""
        # 清理旧的 socket 文件（如果存在）
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass

        # 创建 Unix Domain Socket 服务器
        self.server = await asyncio.start_unix_server(self._handle_client, str(self.socket_path))

        # 设置 socket 文件权限（仅用户可读写）
        os.chmod(self.socket_path, 0o600)

        logger.info(
            f"Watch server started for session {self.session_id[:8]}... at {self.socket_path}"
        )

    async def stop(self) -> None:
        """停止 watch 服务器并清理."""
        # 关闭所有观察者连接
        async with self._lock:
            for writer in list(self.observers):
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
            self.observers.clear()

        # 关闭服务器
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # 清理 socket 文件
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass

        logger.info(f"Watch server stopped for session {self.session_id[:8]}...")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """处理新的观察者连接."""
        async with self._lock:
            self.observers.add(writer)

        logger.info(f"Observer connected to session {self.session_id[:8]}...")

        try:
            # 发送欢迎消息和初始 session 信息
            await self._send_event(
                writer,
                {
                    "type": "connected",
                    "session_id": self.session_id,
                    "message": "Connected to watch server",
                },
            )

            # 保持连接，等待客户端断开
            while True:
                # 简单的 keepalive：读取任何数据（观察者可能发送心跳）
                try:
                    data = await asyncio.wait_for(reader.read(1024), timeout=30.0)
                    if not data:
                        break
                except TimeoutError:
                    # 超时是正常的，继续等待
                    continue
                except Exception:
                    break
        except Exception as e:
            logger.debug(f"Observer connection error: {e}")
        finally:
            # 移除观察者
            async with self._lock:
                self.observers.discard(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.info(f"Observer disconnected from session {self.session_id[:8]}...")

    async def broadcast_event(self, event: dict) -> None:
        """
        向所有观察者广播事件。

        重要：这个方法只发送事件，不修改任何数据。

        Args:
            event: 事件字典，必须包含 "type" 字段
        """
        if not self.observers:
            return

        # 添加时间戳
        import time

        event_with_timestamp = {**event, "timestamp": time.time()}

        # 序列化为 JSON
        try:
            event_json = json.dumps(event_with_timestamp, ensure_ascii=False) + "\n"
            event_bytes = event_json.encode("utf-8")
        except Exception as e:
            logger.error(f"Failed to serialize event: {e}")
            return

        # 向所有观察者发送
        async with self._lock:
            disconnected = set()
            for writer in self.observers:
                try:
                    writer.write(event_bytes)
                    await writer.drain()
                except Exception as e:
                    logger.debug(f"Failed to send event to observer: {e}")
                    disconnected.add(writer)

            # 移除断开的观察者
            for writer in disconnected:
                self.observers.discard(writer)
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    async def _send_event(self, writer: asyncio.StreamWriter, event: dict) -> None:
        """向单个观察者发送事件."""
        import time

        event_with_timestamp = {**event, "timestamp": time.time()}
        try:
            event_json = json.dumps(event_with_timestamp, ensure_ascii=False) + "\n"
            writer.write(event_json.encode("utf-8"))
            await writer.drain()
        except Exception:
            pass


# 全局 watch 服务器实例（每个 session 一个）
_watch_servers: dict[str, WatchServer] = {}


def get_watch_server(session_id: str) -> WatchServer:
    """获取或创建 watch 服务器实例."""
    if session_id not in _watch_servers:
        _watch_servers[session_id] = WatchServer(session_id)
    return _watch_servers[session_id]


async def start_watch_server(session_id: str) -> WatchServer:
    """启动 watch 服务器."""
    server = get_watch_server(session_id)
    await server.start()
    return server


async def stop_watch_server(session_id: str) -> None:
    """停止 watch 服务器."""
    if session_id in _watch_servers:
        await _watch_servers[session_id].stop()
        del _watch_servers[session_id]
