"""智能替换测试"""

import pytest

from wolo.smart_replace import (
    REPLACERS,
    block_anchor_replacer,
    context_aware_replacer,
    escape_normalized_replacer,
    find_match,
    indentation_flexible_replacer,
    line_trimmed_replacer,
    simple_replacer,
    smart_replace,
    trimmed_boundary_replacer,
    whitespace_normalized_replacer,
)


class TestSimpleReplacer:
    """精确匹配测试"""

    def test_exact_match(self):
        """精确匹配"""
        content = "hello world"
        result = list(simple_replacer(content, "world"))
        assert result == ["world"]

    def test_no_match(self):
        """无匹配"""
        content = "hello world"
        result = list(simple_replacer(content, "foo"))
        assert result == []

    def test_multiline_match(self):
        """多行匹配"""
        content = "line1\nline2\nline3"
        result = list(simple_replacer(content, "line2\nline3"))
        assert result == ["line2\nline3"]


class TestLineTrimmedReplacer:
    """行trim匹配测试"""

    def test_leading_whitespace(self):
        """行首空白"""
        content = "  def foo():\n    pass"
        find = "def foo():\npass"
        result = list(line_trimmed_replacer(content, find))
        assert len(result) == 1
        assert "def foo():" in result[0]

    def test_trailing_whitespace(self):
        """行尾空白"""
        content = "def foo():  \n  pass  "
        find = "def foo():\npass"
        result = list(line_trimmed_replacer(content, find))
        assert len(result) == 1

    def test_both_whitespace(self):
        """首尾都有空白"""
        content = "  hello  \n  world  "
        find = "hello\nworld"
        result = list(line_trimmed_replacer(content, find))
        assert len(result) == 1

    def test_no_match_different_content(self):
        """内容不同无匹配"""
        content = "hello\nworld"
        find = "hello\nfoo"
        result = list(line_trimmed_replacer(content, find))
        assert len(result) == 0

    def test_trailing_empty_lines_in_find(self):
        """find末尾有空行"""
        content = "hello\nworld"
        find = "hello\nworld\n\n"
        result = list(line_trimmed_replacer(content, find))
        assert len(result) == 1


class TestIndentationFlexibleReplacer:
    """缩进灵活匹配测试"""

    def test_different_indent_level(self):
        """不同缩进级别"""
        content = "    def foo():\n        pass"
        find = "def foo():\n    pass"
        result = list(indentation_flexible_replacer(content, find))
        assert len(result) == 1
        assert "    def foo():" in result[0]

    def test_same_indent(self):
        """相同缩进"""
        content = "def foo():\n    pass"
        find = "def foo():\n    pass"
        result = list(indentation_flexible_replacer(content, find))
        assert len(result) == 1

    def test_no_indent_to_indent(self):
        """无缩进到有缩进"""
        content = "class Foo:\n    def bar():\n        pass"
        find = "def bar():\n    pass"
        result = list(indentation_flexible_replacer(content, find))
        assert len(result) == 1


class TestWhitespaceNormalizedReplacer:
    """空白归一化测试"""

    def test_multiple_spaces(self):
        """多空格"""
        content = "hello    world"
        find = "hello world"
        result = list(whitespace_normalized_replacer(content, find))
        assert len(result) >= 1

    def test_tabs_and_spaces(self):
        """tab和空格混合"""
        content = "hello\t\tworld"
        find = "hello world"
        result = list(whitespace_normalized_replacer(content, find))
        assert len(result) >= 1

    def test_multiline_whitespace(self):
        """多行空白"""
        content = "hello   world\nfoo    bar"
        find = "hello world\nfoo bar"
        result = list(whitespace_normalized_replacer(content, find))
        assert len(result) >= 1


class TestBlockAnchorReplacer:
    """块锚定匹配测试"""

    def test_anchor_match_same_lines(self):
        """锚定匹配 - 行数相同"""
        content = """def foo():
    x = 1
    return x"""
        find = """def foo():
    y = 2
    return x"""
        result = list(block_anchor_replacer(content, find))
        assert len(result) >= 1

    def test_short_block_ignored(self):
        """短块不处理"""
        content = "a\nb"
        find = "a\nb"
        result = list(block_anchor_replacer(content, find))
        assert len(result) == 0  # 少于3行不处理

    def test_exact_anchors_same_structure(self):
        """精确锚点 - 相同结构"""
        content = """start
middle1
end"""
        find = """start
different
end"""
        result = list(block_anchor_replacer(content, find))
        assert len(result) >= 1


class TestTrimmedBoundaryReplacer:
    """边界trim测试"""

    def test_leading_trailing_newlines(self):
        """首尾换行"""
        content = "hello\nworld"
        find = "\nhello\nworld\n"
        result = list(trimmed_boundary_replacer(content, find))
        assert len(result) >= 1

    def test_leading_trailing_spaces(self):
        """首尾空格"""
        content = "hello world"
        find = "  hello world  "
        result = list(trimmed_boundary_replacer(content, find))
        assert len(result) >= 1

    def test_already_trimmed(self):
        """已经trim过"""
        content = "hello"
        find = "hello"
        result = list(trimmed_boundary_replacer(content, find))
        assert len(result) == 0  # 不需要这个替换器


class TestEscapeNormalizedReplacer:
    """转义归一化测试"""

    def test_escaped_newline(self):
        """转义换行"""
        content = "hello\nworld"
        find = "hello\\nworld"
        result = list(escape_normalized_replacer(content, find))
        assert len(result) >= 1

    def test_escaped_tab(self):
        """转义tab"""
        content = "hello\tworld"
        find = "hello\\tworld"
        result = list(escape_normalized_replacer(content, find))
        assert len(result) >= 1

    def test_no_escapes(self):
        """无转义"""
        content = "hello world"
        find = "hello world"
        result = list(escape_normalized_replacer(content, find))
        assert len(result) == 0  # 不需要这个替换器


class TestContextAwareReplacer:
    """上下文感知测试"""

    def test_context_match_exact_middle(self):
        """上下文匹配 - 中间行精确匹配"""
        content = """def foo():
    x = 1
    return x"""
        find = """def foo():
    x = 1
    return x"""
        result = list(context_aware_replacer(content, find))
        # 首尾匹配，中间100%匹配
        assert len(result) >= 1

    def test_short_content(self):
        """短内容"""
        content = "a\nb"
        find = "a\nb"
        result = list(context_aware_replacer(content, find))
        assert len(result) == 0  # 少于3行不处理


class TestSmartReplace:
    """smart_replace 主函数测试"""

    def test_exact_match(self):
        """精确匹配"""
        result = smart_replace("hello world", "world", "universe")
        assert result == "hello universe"

    def test_whitespace_tolerance(self):
        """空白容忍"""
        content = "  def foo():  \n    pass"
        result = smart_replace(content, "def foo():\npass", "def bar():\nreturn")
        assert "def bar():" in result

    def test_indentation_tolerance(self):
        """缩进容忍"""
        content = "    if True:\n        x = 1"
        result = smart_replace(content, "if True:\n    x = 1", "if False:\n    x = 2")
        assert "if False:" in result

    def test_same_string_error(self):
        """相同字符串报错"""
        with pytest.raises(ValueError, match="must be different"):
            smart_replace("hello", "hello", "hello")

    def test_empty_old_string_error(self):
        """空old_string报错"""
        with pytest.raises(ValueError, match="cannot be empty"):
            smart_replace("hello", "", "world")

    def test_not_found_error(self):
        """未找到报错"""
        with pytest.raises(LookupError, match="not found"):
            smart_replace("hello", "world", "universe")

    def test_multiple_matches_error(self):
        """多匹配报错"""
        with pytest.raises(ValueError, match="multiple matches"):
            smart_replace("hello hello", "hello", "hi")

    def test_replace_all(self):
        """替换所有"""
        result = smart_replace("hello hello", "hello", "hi", replace_all=True)
        assert result == "hi hi"

    def test_multiline_replace(self):
        """多行替换"""
        content = "line1\nline2\nline3"
        result = smart_replace(content, "line2", "replaced")
        assert result == "line1\nreplaced\nline3"

    def test_preserve_surrounding(self):
        """保留周围内容"""
        content = "prefix hello suffix"
        result = smart_replace(content, "hello", "world")
        assert result == "prefix world suffix"

    def test_complex_code_edit(self):
        """复杂代码编辑 - 使用锚定匹配"""
        content = """def calculate(x, y):
    # Add two numbers
    result = x + y
    return result"""

        # 使用首尾行作为锚点的匹配
        old = """def calculate(x, y):
    # different comment
    result = x + y
    return result"""

        new = """def calculate(x, y):
    # different comment
    result = x * y
    return result"""

        result = smart_replace(content, old, new)
        assert "x * y" in result


class TestFindMatch:
    """find_match 测试"""

    def test_returns_actual_match(self):
        """返回实际匹配"""
        content = "  hello  "
        match = find_match(content, "hello")
        assert match is not None
        assert match in content

    def test_returns_none_when_not_found(self):
        """未找到返回None"""
        match = find_match("hello", "world")
        assert match is None

    def test_empty_find(self):
        """空查找"""
        match = find_match("hello", "")
        assert match is None

    def test_whitespace_match(self):
        """空白匹配"""
        content = "  def foo():  "
        match = find_match(content, "def foo():")
        assert match is not None


class TestReplacersPriority:
    """替换器优先级测试"""

    def test_simple_first(self):
        """精确匹配优先"""
        # 确保精确匹配在列表第一位
        assert REPLACERS[0] == simple_replacer

    def test_all_replacers_registered(self):
        """所有替换器已注册"""
        assert len(REPLACERS) >= 6

    def test_replacers_are_callable(self):
        """替换器可调用"""
        for replacer in REPLACERS:
            assert callable(replacer)


class TestEdgeCases:
    """边界情况测试"""

    def test_unicode_content(self):
        """Unicode内容"""
        content = "你好世界"
        result = smart_replace(content, "世界", "宇宙")
        assert result == "你好宇宙"

    def test_special_regex_chars(self):
        """特殊正则字符"""
        content = "hello.*world"
        result = smart_replace(content, ".*", "++")
        assert result == "hello++world"

    def test_newline_only(self):
        """只有换行 - 需要replace_all因为有多个匹配"""
        content = "a\n\n\nb"
        result = smart_replace(content, "\n\n", "\n", replace_all=True)
        assert result == "a\n\nb"

    def test_very_long_content(self):
        """很长的内容"""
        content = "x" * 10000 + "target" + "y" * 10000
        result = smart_replace(content, "target", "replaced")
        assert "replaced" in result
        # 10000 + 8 (replaced) + 10000 = 20008
        assert len(result) == 20008

    def test_single_char_replace(self):
        """单字符替换"""
        result = smart_replace("abc", "b", "x")
        assert result == "axc"
