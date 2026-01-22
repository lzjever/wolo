"""
输出截断系统

当工具输出过大时，截断输出并保存完整内容到文件，防止消耗过多token。

Usage:
    from wolo.truncate import truncate_output, init
    
    # 初始化（程序启动时调用）
    init()
    
    # 截断输出
    result = truncate_output(large_text)
    # result.content: 截断后的内容（含提示）
    # result.truncated: 是否被截断
    # result.saved_path: 完整内容保存路径（如果截断）
"""

import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ==================== 常量 ====================

MAX_LINES: int = 2000
"""最大行数限制"""

MAX_BYTES: int = 50 * 1024  # 50KB
"""最大字节数限制"""

OUTPUT_DIR: Path = Path.home() / ".wolo" / "tool-output"
"""截断输出保存目录"""

RETENTION_DAYS: int = 7
"""保留天数"""


# ==================== 数据类型 ====================

@dataclass
class TruncateResult:
    """截断结果"""
    content: str
    """处理后的内容（可能包含截断提示）"""
    
    truncated: bool
    """是否被截断"""
    
    saved_path: Optional[str] = None
    """完整内容保存路径（仅当truncated=True时有值）"""


# ==================== 公开接口 ====================

def init() -> None:
    """
    初始化截断系统。
    
    - 创建输出目录
    - 清理过期文件
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_old_outputs()


def cleanup_old_outputs() -> int:
    """
    清理过期的截断输出文件。
    
    Returns:
        删除的文件数量
    """
    if not OUTPUT_DIR.exists():
        return 0
    
    cutoff = time.time() - (RETENTION_DAYS * 24 * 60 * 60)
    count = 0
    
    for f in OUTPUT_DIR.iterdir():
        if f.is_file():
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    count += 1
            except OSError:
                pass
    
    return count


def truncate_output(
    text: str,
    *,
    max_lines: int = MAX_LINES,
    max_bytes: int = MAX_BYTES,
    direction: str = "head",
) -> TruncateResult:
    """
    截断过长的输出。
    
    Args:
        text: 原始文本
        max_lines: 最大行数
        max_bytes: 最大字节数
        direction: 截断方向
            - "head": 保留前面的内容（默认）
            - "tail": 保留后面的内容（适用于日志）
    
    Returns:
        TruncateResult 包含处理后的内容和元数据
    
    Example:
        >>> result = truncate_output("a\\n" * 3000)
        >>> result.truncated
        True
        >>> "truncated" in result.content
        True
    """
    if not text:
        return TruncateResult(content=text, truncated=False)
    
    lines = text.split("\n")
    total_bytes = len(text.encode("utf-8"))
    
    # 检查是否需要截断
    if len(lines) <= max_lines and total_bytes <= max_bytes:
        return TruncateResult(content=text, truncated=False)
    
    # 执行截断
    out_lines: list[str] = []
    current_bytes = 0
    hit_bytes = False
    
    if direction == "head":
        for i, line in enumerate(lines):
            if i >= max_lines:
                break
            line_bytes = len(line.encode("utf-8")) + (1 if out_lines else 0)
            if current_bytes + line_bytes > max_bytes:
                hit_bytes = True
                break
            out_lines.append(line)
            current_bytes += line_bytes
    else:  # tail
        for i in range(len(lines) - 1, -1, -1):
            if len(out_lines) >= max_lines:
                break
            line = lines[i]
            line_bytes = len(line.encode("utf-8")) + (1 if out_lines else 0)
            if current_bytes + line_bytes > max_bytes:
                hit_bytes = True
                break
            out_lines.insert(0, line)
            current_bytes += line_bytes
    
    # 计算截断量
    if hit_bytes:
        removed = total_bytes - current_bytes
        unit = "bytes"
    else:
        removed = len(lines) - len(out_lines)
        unit = "lines"
    
    # 保存完整内容
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_id = f"tool_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    saved_path = OUTPUT_DIR / file_id
    saved_path.write_text(text, encoding="utf-8")
    
    # 构建输出
    preview = "\n".join(out_lines)
    hint = (
        f"Output truncated. Full output saved to: {saved_path}\n"
        f"Use grep to search or read with offset/limit to view sections."
    )
    
    if direction == "head":
        content = f"{preview}\n\n...{removed} {unit} truncated...\n\n{hint}"
    else:
        content = f"...{removed} {unit} truncated...\n\n{hint}\n\n{preview}"
    
    return TruncateResult(
        content=content,
        truncated=True,
        saved_path=str(saved_path),
    )
