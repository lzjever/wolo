"""
智能文本替换系统

实现多种匹配策略，按优先级尝试，提高编辑成功率。
参考 OpenCode 的 edit.ts 实现。

Usage:
    from wolo.smart_replace import smart_replace, find_match

    # 智能替换
    new_content = smart_replace(content, old_string, new_string)

    # 查找匹配（用于调试）
    match = find_match(content, old_string)
"""

import re
from collections.abc import Callable, Generator

# ==================== 类型定义 ====================

Replacer = Callable[[str, str], Generator[str, None, None]]
"""
替换器类型。

接收 (content, find) 参数，yield 所有可能的匹配字符串。
"""


# ==================== 替换器实现 ====================


def simple_replacer(content: str, find: str) -> Generator[str, None, None]:
    """
    精确匹配。

    最基本的匹配方式，要求完全一致。
    """
    if find in content:
        yield find


def line_trimmed_replacer(content: str, find: str) -> Generator[str, None, None]:
    """
    忽略行首尾空白的匹配。

    比较时忽略每行的首尾空白，但返回原始内容。
    适用于 LLM 生成的代码行首尾有额外空白的情况。

    Example:
        content: "  def foo():  \\n    pass"
        find:    "def foo():\\n  pass"
        -> 匹配成功，返回 "  def foo():  \\n    pass"
    """
    original_lines = content.split("\n")
    search_lines = find.split("\n")

    # 移除末尾空行
    while search_lines and search_lines[-1] == "":
        search_lines.pop()

    if not search_lines:
        return

    for i in range(len(original_lines) - len(search_lines) + 1):
        matches = True
        for j in range(len(search_lines)):
            if original_lines[i + j].strip() != search_lines[j].strip():
                matches = False
                break

        if matches:
            # 计算匹配的实际位置
            start_idx = sum(len(original_lines[k]) + 1 for k in range(i))
            end_idx = start_idx
            for k in range(len(search_lines)):
                end_idx += len(original_lines[i + k])
                if k < len(search_lines) - 1:
                    end_idx += 1

            yield content[start_idx:end_idx]


def indentation_flexible_replacer(content: str, find: str) -> Generator[str, None, None]:
    """
    缩进灵活匹配。

    移除最小公共缩进后比较。
    适用于代码块整体缩进不同的情况。

    Example:
        content: "    def foo():\\n        pass"
        find:    "def foo():\\n    pass"
        -> 匹配成功
    """

    def remove_common_indent(text: str) -> str:
        lines = text.split("\n")
        non_empty = [ln for ln in lines if ln.strip()]
        if not non_empty:
            return text

        min_indent = min(len(ln) - len(ln.lstrip()) for ln in non_empty)
        return "\n".join(ln[min_indent:] if ln.strip() else ln for ln in lines)

    normalized_find = remove_common_indent(find)
    content_lines = content.split("\n")
    find_lines = find.split("\n")

    # 移除末尾空行
    while find_lines and find_lines[-1] == "":
        find_lines.pop()

    if not find_lines:
        return

    for i in range(len(content_lines) - len(find_lines) + 1):
        block = "\n".join(content_lines[i : i + len(find_lines)])
        if remove_common_indent(block) == normalized_find:
            yield block


def whitespace_normalized_replacer(content: str, find: str) -> Generator[str, None, None]:
    """
    空白归一化匹配。

    将连续空白替换为单个空格后比较。
    适用于空白字符数量不一致的情况。

    Example:
        content: "hello    world"
        find:    "hello world"
        -> 匹配成功
    """

    def normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    normalized_find = normalize(find)
    if not normalized_find:
        return

    lines = content.split("\n")

    # 单行匹配
    for line in lines:
        if normalize(line) == normalized_find:
            yield line
        elif normalized_find in normalize(line):
            # 子串匹配 - 构建正则表达式
            words = find.strip().split()
            if words:
                pattern = r"\s+".join(re.escape(w) for w in words)
                try:
                    match = re.search(pattern, line)
                    if match:
                        yield match.group(0)
                except re.error:
                    pass

    # 多行匹配
    find_lines = find.split("\n")
    if len(find_lines) > 1:
        for i in range(len(lines) - len(find_lines) + 1):
            block = "\n".join(lines[i : i + len(find_lines)])
            if normalize(block) == normalized_find:
                yield block


def block_anchor_replacer(content: str, find: str) -> Generator[str, None, None]:
    """
    块锚定匹配。

    首尾行精确匹配（trim后），中间内容使用相似度匹配。
    适用于代码块中间部分有差异的情况。

    Example:
        content: "def foo():\\n    # comment\\n    x = 1\\n    return x"
        find:    "def foo():\\n    y = 2\\n    return x"
        -> 可能匹配成功（如果相似度足够）
    """
    search_lines = find.split("\n")

    # 至少需要3行才能使用锚定匹配
    if len(search_lines) < 3:
        return

    # 移除末尾空行
    while search_lines and search_lines[-1] == "":
        search_lines.pop()

    if len(search_lines) < 3:
        return

    first_line = search_lines[0].strip()
    last_line = search_lines[-1].strip()
    original_lines = content.split("\n")

    # 收集所有候选
    candidates: list[tuple[int, int]] = []

    for i in range(len(original_lines)):
        if original_lines[i].strip() != first_line:
            continue

        # 找到首行匹配，寻找尾行
        for j in range(i + 2, len(original_lines)):
            if original_lines[j].strip() == last_line:
                candidates.append((i, j))
                break  # 只匹配第一个尾行

    if not candidates:
        return

    # 单候选使用宽松阈值
    if len(candidates) == 1:
        i, j = candidates[0]
        block_lines = original_lines[i : j + 1]
        yield "\n".join(block_lines)
        return

    # 多候选选择最佳匹配
    best_match = None
    best_similarity = -1.0

    for i, j in candidates:
        block_lines = original_lines[i : j + 1]
        similarity = _calculate_similarity(block_lines, search_lines)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = "\n".join(block_lines)

    if best_match and best_similarity >= 0.3:
        yield best_match


def trimmed_boundary_replacer(content: str, find: str) -> Generator[str, None, None]:
    """
    边界trim匹配。

    对 find 进行 trim 后尝试匹配。
    适用于 find 有多余首尾空白的情况。
    """
    trimmed = find.strip()

    if trimmed == find:
        # 已经是 trim 过的，不需要这个替换器
        return

    if not trimmed:
        return

    if trimmed in content:
        yield trimmed

    # 块匹配
    lines = content.split("\n")
    find_lines = find.split("\n")

    for i in range(len(lines) - len(find_lines) + 1):
        block = "\n".join(lines[i : i + len(find_lines)])
        if block.strip() == trimmed:
            yield block


def escape_normalized_replacer(content: str, find: str) -> Generator[str, None, None]:
    """
    转义字符归一化匹配。

    处理转义字符差异。
    """

    def unescape(text: str) -> str:
        replacements = {
            "\\n": "\n",
            "\\t": "\t",
            "\\r": "\r",
            "\\'": "'",
            '\\"': '"',
            "\\`": "`",
            "\\\\": "\\",
            "\\$": "$",
        }
        result = text
        for escaped, unescaped in replacements.items():
            result = result.replace(escaped, unescaped)
        return result

    unescaped_find = unescape(find)

    if unescaped_find == find:
        # 没有转义字符
        return

    # 直接匹配
    if unescaped_find in content:
        yield unescaped_find

    # 块匹配
    lines = content.split("\n")
    find_lines = unescaped_find.split("\n")

    for i in range(len(lines) - len(find_lines) + 1):
        block = "\n".join(lines[i : i + len(find_lines)])
        if unescape(block) == unescaped_find:
            yield block


def context_aware_replacer(content: str, find: str) -> Generator[str, None, None]:
    """
    上下文感知匹配。

    首尾行作为锚点，中间内容允许50%差异。
    """
    find_lines = find.split("\n")

    if len(find_lines) < 3:
        return

    # 移除末尾空行
    while find_lines and find_lines[-1] == "":
        find_lines.pop()

    if len(find_lines) < 3:
        return

    content_lines = content.split("\n")
    first_line = find_lines[0].strip()
    last_line = find_lines[-1].strip()

    for i in range(len(content_lines)):
        if content_lines[i].strip() != first_line:
            continue

        for j in range(i + 2, len(content_lines)):
            if content_lines[j].strip() == last_line:
                block_lines = content_lines[i : j + 1]

                # 检查行数是否匹配
                if len(block_lines) != len(find_lines):
                    continue

                # 计算中间行匹配率
                matching = 0
                total = 0

                for k in range(1, len(block_lines) - 1):
                    block_line = block_lines[k].strip()
                    find_line = find_lines[k].strip()

                    if block_line or find_line:
                        total += 1
                        if block_line == find_line:
                            matching += 1

                # 至少50%匹配
                if total == 0 or matching / total >= 0.5:
                    yield "\n".join(block_lines)
                    break


# ==================== 辅助函数 ====================


def _calculate_similarity(block_lines: list[str], search_lines: list[str]) -> float:
    """
    计算两个代码块的相似度。

    只比较中间行（排除首尾锚点行）。
    """
    if len(block_lines) < 3 or len(search_lines) < 3:
        return 1.0

    # 只比较中间行
    middle_block = [ln.strip() for ln in block_lines[1:-1]]
    middle_search = [ln.strip() for ln in search_lines[1:-1]]

    if not middle_block or not middle_search:
        return 1.0

    # 简单的行匹配计数
    matches = 0
    total = max(len(middle_block), len(middle_search))

    for i, b in enumerate(middle_block):
        if i < len(middle_search) and b == middle_search[i]:
            matches += 1

    return matches / total if total > 0 else 1.0


def _levenshtein_distance(a: str, b: str) -> int:
    """
    计算 Levenshtein 编辑距离。
    """
    if not a:
        return len(b)
    if not b:
        return len(a)

    # 使用动态规划
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,  # 删除
                dp[i][j - 1] + 1,  # 插入
                dp[i - 1][j - 1] + cost,  # 替换
            )

    return dp[m][n]


# ==================== 替换器优先级列表 ====================

REPLACERS: list[Replacer] = [
    simple_replacer,
    line_trimmed_replacer,
    indentation_flexible_replacer,
    whitespace_normalized_replacer,
    block_anchor_replacer,
    trimmed_boundary_replacer,
    escape_normalized_replacer,
    context_aware_replacer,
]


# ==================== 主函数 ====================


def smart_replace(
    content: str,
    old_string: str,
    new_string: str,
    *,
    replace_all: bool = False,
) -> str:
    """
    智能替换文本。

    按优先级尝试多种匹配策略：
    1. simple_replacer - 精确匹配
    2. line_trimmed_replacer - 忽略行首尾空白
    3. indentation_flexible_replacer - 缩进灵活
    4. whitespace_normalized_replacer - 空白归一化
    5. block_anchor_replacer - 块锚定
    6. trimmed_boundary_replacer - 边界trim
    7. escape_normalized_replacer - 转义归一化
    8. context_aware_replacer - 上下文感知

    Args:
        content: 原始内容
        old_string: 要替换的文本
        new_string: 替换后的文本
        replace_all: 是否替换所有匹配（默认只替换第一个）

    Returns:
        替换后的内容

    Raises:
        ValueError: old_string == new_string
        LookupError: 未找到匹配
        ValueError: 找到多个匹配但 replace_all=False
    """
    if old_string == new_string:
        raise ValueError("old_string and new_string must be different")

    if not old_string:
        raise ValueError("old_string cannot be empty")

    for replacer in REPLACERS:
        for search in replacer(content, old_string):
            index = content.find(search)
            if index == -1:
                continue

            if replace_all:
                return content.replace(search, new_string)

            # 检查是否有多个匹配
            last_index = content.rfind(search)
            if index != last_index:
                raise ValueError(
                    "Found multiple matches for old_string. "
                    "Provide more surrounding lines in old_string to identify the correct match, "
                    "or use replace_all=True."
                )

            return content[:index] + new_string + content[index + len(search) :]

    raise LookupError("old_string not found in content")


def find_match(content: str, find: str) -> str | None:
    """
    查找匹配的字符串。

    返回在 content 中实际匹配的字符串，如果未找到返回 None。
    用于调试和测试。

    Args:
        content: 要搜索的内容
        find: 要查找的字符串

    Returns:
        匹配的字符串，或 None
    """
    if not find:
        return None

    for replacer in REPLACERS:
        for search in replacer(content, find):
            if search in content:
                return search

    return None
