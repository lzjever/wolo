#!/bin/bash
# check-wolo-version.sh - 检查当前使用的 wolo 代码版本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== 检查 wolo 代码版本 ==="
echo ""

# 检查命令行工具路径
echo "1. 命令行工具路径:"
which wolo 2>/dev/null || echo "  (未找到 wolo 命令)"
echo ""

# 检查 Python 模块路径
echo "2. Python 模块路径:"
python -c "import wolo; print('  ', wolo.__file__)" 2>/dev/null || echo "  (无法导入 wolo 模块)"
echo ""

# 检查是否使用项目代码
echo "3. 是否使用项目代码:"
MODULE_PATH=$(python -c "import wolo; print(wolo.__file__)" 2>/dev/null || echo "")
if [[ "$MODULE_PATH" == *"$SCRIPT_DIR"* ]]; then
    echo "  ✅ 使用项目代码: $MODULE_PATH"
elif [[ -n "$MODULE_PATH" ]]; then
    echo "  ⚠️  使用系统安装版本: $MODULE_PATH"
    echo "  建议: 使用 './wolo-dev' 或 'uv run wolo' 来使用项目代码"
else
    echo "  ❌ 无法确定"
fi
echo ""

# 检查输出模块是否正常加载
echo "4. 代码功能检查:"
python -c "
try:
    from wolo.cli.output import print_agent_start, print_text, print_finish
    from wolo.cli.events import setup_event_handlers
    print('  ✅ 输出模块加载正常')
except Exception as e:
    print(f'  ❌ 检查失败: {e}')
" 2>/dev/null || echo "  ❌ 无法检查"
echo ""

echo "=== 推荐使用方式 ==="
echo "  快速测试: ./wolo-dev 'test'"
echo "  标准方式: uv run wolo 'test'"
echo "  开发模式: uv pip install -e . && wolo 'test'"
