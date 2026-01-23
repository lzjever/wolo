"""
文件时间追踪系统

追踪文件的读取时间，在编辑前检测文件是否被外部修改。
防止覆盖用户或其他进程的修改。

Usage:
    from wolo.file_time import FileTime, FileModifiedError

    # 读取文件时记录时间
    FileTime.read(session_id, file_path)

    # 编辑前检查
    try:
        FileTime.assert_not_modified(session_id, file_path)
    except FileModifiedError:
        # 文件已被外部修改
        pass
"""

from pathlib import Path


class FileModifiedError(Exception):
    """文件已被外部修改"""

    def __init__(self, path: str, read_time: float, current_time: float):
        self.path = path
        self.read_time = read_time
        self.current_time = current_time
        super().__init__(
            f"File '{path}' has been modified since it was read. "
            f"Read at: {read_time}, Current mtime: {current_time}"
        )


class FileTime:
    """
    文件时间追踪器。

    使用类方法维护全局状态，按 session 隔离。
    """

    # session_id -> {file_path -> mtime}
    _read_times: dict[str, dict[str, float]] = {}

    @classmethod
    def read(cls, session_id: str, file_path: str) -> float | None:
        """
        记录文件读取时间。

        Args:
            session_id: 会话 ID
            file_path: 文件路径

        Returns:
            文件的修改时间，如果文件不存在返回 None
        """
        path = Path(file_path)

        if not path.exists():
            return None

        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None

        if session_id not in cls._read_times:
            cls._read_times[session_id] = {}

        cls._read_times[session_id][str(path.resolve())] = mtime
        return mtime

    @classmethod
    def assert_not_modified(cls, session_id: str, file_path: str) -> None:
        """
        断言文件自读取后未被修改。

        Args:
            session_id: 会话 ID
            file_path: 文件路径

        Raises:
            FileModifiedError: 文件已被修改
        """
        path = Path(file_path)
        resolved = str(path.resolve())

        # 获取记录的读取时间
        session_times = cls._read_times.get(session_id, {})
        read_time = session_times.get(resolved)

        if read_time is None:
            # 文件未被读取过，不检查
            return

        if not path.exists():
            # 文件已被删除
            raise FileModifiedError(file_path, read_time, 0)

        try:
            current_mtime = path.stat().st_mtime
        except OSError:
            return

        # 允许 0.001 秒的误差（文件系统精度）
        if current_mtime - read_time > 0.001:
            raise FileModifiedError(file_path, read_time, current_mtime)

    @classmethod
    def update(cls, session_id: str, file_path: str) -> float | None:
        """
        更新文件的记录时间（写入后调用）。

        Args:
            session_id: 会话 ID
            file_path: 文件路径

        Returns:
            新的修改时间
        """
        return cls.read(session_id, file_path)

    @classmethod
    def clear_session(cls, session_id: str) -> None:
        """
        清除会话的所有记录。
        """
        cls._read_times.pop(session_id, None)

    @classmethod
    def clear_file(cls, session_id: str, file_path: str) -> None:
        """
        清除特定文件的记录。
        """
        path = Path(file_path)
        resolved = str(path.resolve())

        session_times = cls._read_times.get(session_id)
        if session_times:
            session_times.pop(resolved, None)

    @classmethod
    def get_read_time(cls, session_id: str, file_path: str) -> float | None:
        """
        获取文件的记录读取时间。
        """
        path = Path(file_path)
        resolved = str(path.resolve())

        session_times = cls._read_times.get(session_id, {})
        return session_times.get(resolved)

    @classmethod
    def get_all_read_files(cls, session_id: str) -> list[str]:
        """
        获取会话中所有已读取的文件路径。
        """
        return list(cls._read_times.get(session_id, {}).keys())
