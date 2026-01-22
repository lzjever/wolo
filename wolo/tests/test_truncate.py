"""截断系统测试"""
import os
import time
from pathlib import Path

import pytest

from wolo.truncate import (
    MAX_BYTES,
    MAX_LINES,
    OUTPUT_DIR,
    TruncateResult,
    cleanup_old_outputs,
    init,
    truncate_output,
)


class TestTruncateOutput:
    """truncate_output 函数测试"""

    def test_no_truncation_small_text(self):
        """小文本不截断"""
        text = "line1\nline2\nline3"
        result = truncate_output(text)

        assert result.truncated is False
        assert result.content == text
        assert result.saved_path is None

    def test_no_truncation_empty_text(self):
        """空文本不截断"""
        result = truncate_output("")
        assert result.truncated is False
        assert result.content == ""
        assert result.saved_path is None

    def test_truncate_by_lines(self):
        """按行数截断"""
        text = "\n".join(f"line{i}" for i in range(3000))
        result = truncate_output(text, max_lines=100)

        assert result.truncated is True
        assert result.saved_path is not None
        assert "truncated" in result.content.lower()
        # 截断后行数应该少很多（100行内容 + 提示信息）
        assert result.content.count("\n") < 150

    def test_truncate_by_bytes(self):
        """按字节数截断"""
        text = "x" * 100000  # 100KB
        result = truncate_output(text, max_bytes=1024)

        assert result.truncated is True
        # 截断后应该小于原始大小
        assert len(result.content.encode()) < 10000

    def test_truncate_direction_head(self):
        """head方向截断保留前面内容"""
        text = "\n".join(f"line{i}" for i in range(100))
        result = truncate_output(text, max_lines=10, direction="head")

        assert result.truncated is True
        assert "line0" in result.content
        assert "line99" not in result.content

    def test_truncate_direction_tail(self):
        """tail方向截断保留后面内容"""
        text = "\n".join(f"line{i}" for i in range(100))
        result = truncate_output(text, max_lines=10, direction="tail")

        assert result.truncated is True
        assert "line99" in result.content
        assert "line0" not in result.content

    def test_saved_file_contains_full_content(self):
        """保存的文件包含完整内容"""
        text = "\n".join(f"line{i}" for i in range(3000))
        result = truncate_output(text, max_lines=100)

        assert result.saved_path is not None
        saved = Path(result.saved_path).read_text()
        assert saved == text

    def test_truncate_hint_message(self):
        """截断提示信息正确"""
        text = "\n".join(f"line{i}" for i in range(3000))
        result = truncate_output(text, max_lines=100)

        assert "Output truncated" in result.content
        assert "Full output saved to" in result.content
        assert "grep" in result.content.lower() or "read" in result.content.lower()

    def test_truncate_by_lines_shows_line_count(self):
        """按行截断时显示行数"""
        text = "\n".join(f"line{i}" for i in range(200))
        result = truncate_output(text, max_lines=50)

        assert result.truncated is True
        assert "lines" in result.content.lower()

    def test_truncate_by_bytes_shows_byte_count(self):
        """按字节截断时显示字节数"""
        text = "x" * 10000
        result = truncate_output(text, max_bytes=500, max_lines=10000)

        assert result.truncated is True
        assert "bytes" in result.content.lower()

    def test_exact_limit_no_truncation(self):
        """刚好在限制内不截断"""
        text = "\n".join(f"line{i}" for i in range(MAX_LINES))
        # 如果字节数也在限制内
        if len(text.encode()) <= MAX_BYTES:
            result = truncate_output(text)
            assert result.truncated is False

    def test_unicode_content(self):
        """Unicode 内容处理"""
        text = "\n".join(f"行{i}：中文内容测试" for i in range(100))
        result = truncate_output(text, max_lines=10)

        assert result.truncated is True
        assert "行0" in result.content
        assert result.saved_path is not None

        # 验证保存的文件
        saved = Path(result.saved_path).read_text(encoding="utf-8")
        assert saved == text


class TestCleanup:
    """清理功能测试"""

    def test_cleanup_old_files(self, tmp_path, monkeypatch):
        """清理过期文件"""
        # 使用临时目录
        monkeypatch.setattr("wolo.truncate.OUTPUT_DIR", tmp_path)

        # 创建旧文件
        old_file = tmp_path / "old_file"
        old_file.write_text("old")
        # 修改时间为8天前
        old_time = time.time() - (8 * 24 * 60 * 60)
        os.utime(old_file, (old_time, old_time))

        # 创建新文件
        new_file = tmp_path / "new_file"
        new_file.write_text("new")

        # 执行清理
        count = cleanup_old_outputs()

        assert count == 1
        assert not old_file.exists()
        assert new_file.exists()

    def test_cleanup_empty_dir(self, tmp_path, monkeypatch):
        """清理空目录"""
        monkeypatch.setattr("wolo.truncate.OUTPUT_DIR", tmp_path)
        count = cleanup_old_outputs()
        assert count == 0

    def test_cleanup_nonexistent_dir(self, tmp_path, monkeypatch):
        """清理不存在的目录"""
        nonexistent = tmp_path / "nonexistent"
        monkeypatch.setattr("wolo.truncate.OUTPUT_DIR", nonexistent)
        count = cleanup_old_outputs()
        assert count == 0


class TestInit:
    """初始化测试"""

    def test_creates_output_dir(self, tmp_path, monkeypatch):
        """初始化创建输出目录"""
        test_dir = tmp_path / "test_output"
        monkeypatch.setattr("wolo.truncate.OUTPUT_DIR", test_dir)

        assert not test_dir.exists()
        init()
        assert test_dir.exists()

    def test_init_idempotent(self, tmp_path, monkeypatch):
        """初始化是幂等的"""
        test_dir = tmp_path / "test_output"
        monkeypatch.setattr("wolo.truncate.OUTPUT_DIR", test_dir)

        init()
        init()  # 第二次调用不应报错
        assert test_dir.exists()


class TestTruncateResult:
    """TruncateResult 数据类测试"""

    def test_dataclass_fields(self):
        """数据类字段正确"""
        result = TruncateResult(content="test", truncated=True, saved_path="/tmp/test")
        assert result.content == "test"
        assert result.truncated is True
        assert result.saved_path == "/tmp/test"

    def test_default_saved_path(self):
        """saved_path 默认值"""
        result = TruncateResult(content="test", truncated=False)
        assert result.saved_path is None
