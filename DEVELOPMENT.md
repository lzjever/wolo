# 在 Repo 目录下使用当前代码版本的最佳实践

## 问题

当你在 repo 目录下开发时，系统可能使用的是全局安装的 `wolo` 命令（如 `/home/percy/.local/bin/wolo`），而不是当前 repo 中的代码。这会导致修改不生效。

## 解决方案

### 方案 1: 使用 `uv run`（推荐）⭐

`uv run` 会自动使用项目中的代码，无需额外配置：

```bash
cd /home/percy/works/mygithub/mbos-agent/wolo

# 直接运行（使用项目中的代码）
uv run wolo -O minimal "给我讲个笑话"

# 或者使用完整路径
uv run python -m wolo.cli.main -O minimal "给我讲个笑话"
```

**优点**:
- ✅ 自动使用项目中的代码
- ✅ 无需安装
- ✅ 自动管理依赖
- ✅ 隔离环境

**缺点**:
- 需要每次输入 `uv run`

### 方案 2: 可编辑安装（开发时推荐）⭐

在项目目录下安装为可编辑模式：

```bash
cd /home/percy/works/mygithub/mbos-agent/wolo

# 使用 uv 安装（推荐）
uv pip install -e .

# 或者使用 pip
pip install -e .
```

安装后，`wolo` 命令会使用项目中的代码：

```bash
# 现在直接运行即可
wolo -O minimal "给我讲个笑话"
```

**优点**:
- ✅ 直接使用 `wolo` 命令
- ✅ 代码修改立即生效（因为是可编辑安装）
- ✅ 适合日常开发

**缺点**:
- 需要先安装
- 如果切换项目，可能需要重新安装

### 方案 3: 使用 PYTHONPATH（临时测试）

临时设置 Python 路径：

```bash
cd /home/percy/works/mygithub/mbos-agent/wolo

# 方法 A: 使用环境变量
PYTHONPATH=. python -m wolo.cli.main -O minimal "给我讲个笑话"

# 方法 B: 使用 sys.path（在代码中）
python -c "import sys; sys.path.insert(0, '.'); from wolo.cli import main_async; main_async()"
```

**优点**:
- ✅ 快速测试
- ✅ 不需要安装

**缺点**:
- ❌ 需要每次设置
- ❌ 可能遇到导入问题

### 方案 4: 创建本地 wrapper 脚本（可选）

创建一个 `wolo-dev` 脚本：

```bash
#!/bin/bash
# wolo-dev - 使用项目中的代码运行 wolo

cd "$(dirname "$0")"
uv run wolo "$@"
```

**使用方法**:
```bash
chmod +x wolo-dev
./wolo-dev -O minimal "给我讲个笑话"
```

## 快速开始

### 方法 A: 使用 `wolo-dev` 脚本（最简单）⭐

项目根目录提供了一个 `wolo-dev` 脚本：

```bash
cd /home/percy/works/mygithub/mbos-agent/wolo

# 直接使用（自动使用项目代码）
./wolo-dev -O minimal "给我讲个笑话"
```

**优点**: 最简单，无需任何设置

### 方法 B: 使用 `uv run`（推荐）

```bash
cd /home/percy/works/mygithub/mbos-agent/wolo

# 直接运行
uv run wolo -O minimal "给我讲个笑话"
```

**优点**: 标准方式，自动管理依赖

### 方法 C: 可编辑安装（适合长期开发）

```bash
cd /home/percy/works/mygithub/mbos-agent/wolo

# 安装一次
uv pip install -e .

# 之后直接使用
wolo -O minimal "给我讲个笑话"
```

**优点**: 安装后可以直接使用 `wolo` 命令

## 推荐工作流

### 日常开发

1. **首次设置**（可选，如果使用方法 C）:
   ```bash
   cd /home/percy/works/mygithub/mbos-agent/wolo
   uv pip install -e .
   ```

2. **日常使用**:
   ```bash
   # 方法 A: 使用脚本
   ./wolo-dev -O minimal "test"
   
   # 方法 B: 使用 uv run
   uv run wolo -O minimal "test"
   
   # 方法 C: 直接使用（如果已安装）
   wolo -O minimal "test"
   ```

3. **测试新功能**:
   ```bash
   # 使用 wolo-dev 或 uv run 确保使用最新代码
   ./wolo-dev -O minimal "test"
   # 或
   uv run wolo -O minimal "test"
   ```

### CI/CD 或脚本

使用 `uv run` 确保一致性：

```bash
#!/bin/bash
cd /path/to/wolo
uv run wolo -O minimal "$@"
```

## 验证当前使用的版本

检查当前使用的代码路径：

```bash
# 方法 1: 检查 wolo 模块路径
python -c "import wolo; print('wolo 模块路径:', wolo.__file__)"

# 方法 2: 检查命令行工具路径
which wolo

# 方法 3: 检查导入的代码
python -c "from wolo.cli.utils import print_session_info; import inspect; print('print_session_info 位置:', inspect.getfile(print_session_info))"
```

**期望结果**（使用项目代码）:
```
wolo 模块路径: /home/percy/works/mygithub/mbos-agent/wolo/wolo/__init__.py
```

**错误结果**（使用系统安装）:
```
wolo 模块路径: /home/percy/.local/lib/python3.13/site-packages/wolo/__init__.py
```

## 常见问题

### Q: 为什么 `wolo` 命令使用的是旧代码？

**A**: 系统 PATH 中可能有全局安装的 `wolo`（如通过 pipx 或 pip install --user）。

**解决**:
1. 使用 `uv run wolo` 代替 `wolo`
2. 或者重新安装：`uv pip install -e .`

### Q: `uv run` 很慢？

**A**: 首次运行会安装依赖，之后会缓存。如果仍然慢，检查是否有网络问题。

### Q: 如何确保 CI/CD 使用项目代码？

**A**: 在 CI 脚本中使用 `uv run` 或 `python -m wolo.cli.main`。

## 项目配置建议

### 1. 添加开发脚本到 `pyproject.toml`

```toml
[project.scripts]
wolo = "wolo.cli:main_async"
wolo-dev = "wolo.cli:main_async"  # 可选：开发版本
```

### 2. 创建 `Makefile` 或脚本

```makefile
.PHONY: run
run:
	uv run wolo $(ARGS)

.PHONY: install-dev
install-dev:
	uv pip install -e .

.PHONY: test-minimal
test-minimal:
	uv run wolo -O minimal "test"
```

### 3. 在 README 中说明

在 README.md 中添加开发说明：

```markdown
## 开发模式

在项目目录下开发时，推荐使用：

```bash
# 安装为可编辑模式
uv pip install -e .

# 或直接使用 uv run
uv run wolo [args]
```
```

## 总结

**最佳实践**（按优先级）:
1. ⭐ **最简单**: 使用 `./wolo-dev` 脚本（项目根目录）
2. ⭐ **标准方式**: 使用 `uv run wolo`（推荐用于 CI/CD）
3. ⭐ **长期开发**: 使用 `uv pip install -e .`，然后直接使用 `wolo` 命令

**快速选择**:
- 🚀 **快速测试**: `./wolo-dev -O minimal "test"`
- 🔧 **日常开发**: `uv pip install -e .` + `wolo -O minimal "test"`
- 🤖 **CI/CD**: `uv run wolo -O minimal "test"`

**避免**:
- ❌ 直接使用全局安装的 `wolo`（可能不是最新代码）
- ❌ 手动修改 `sys.path`（容易出错）
- ❌ 忘记检查当前使用的代码版本
