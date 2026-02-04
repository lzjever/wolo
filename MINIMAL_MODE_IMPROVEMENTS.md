# Minimal 模式改进建议文档

## 当前问题分析

### 1. 快捷键提示显示问题
**问题位置**: `wolo/cli/utils.py` 的 `print_session_info()` 函数

**当前行为**:
- `print_session_info()` 在所有模式下都会显示 session 信息，包括：
  - Session ID
  - Agent 名称
  - 创建时间
  - 消息数量
  - 状态
  - 工作目录
  - **Resume 提示** (当 `show_resume_hints=True` 时)

**问题**: 
- 在 minimal 模式下，这些信息对 script 解析没有价值
- Resume 提示（如 "Resume: wolo session resume ..."）是交互式提示，不适合 script

**调用位置**:
- `wolo/cli/commands/run.py:202` - 创建 session 后显示
- `wolo/cli/commands/session.py:102, 199, 274` - session 命令显示
- `wolo/cli/execution.py:396` - watch 模式显示

### 2. UI 快捷键提示问题
**问题位置**: `wolo/cli/execution.py:51` - `ui.print_shortcuts()`

**当前行为**:
- 在 `run_single_task_mode()` 中，如果启用了 UI (`enable_ui_state=True`)，会打印快捷键提示：
  ```
  [快捷键: ^A:插话 ^B:打断 ^P:暂停 ^S:Shell ^L:MCP ^H:帮助 ^C:退出]
  ```

**问题**:
- minimal 模式应该禁用 UI，但需要确认逻辑
- 即使禁用了 UI，可能还有其他地方会显示快捷键

### 3. Agent 名称提示问题
**问题位置**: `wolo/cli/execution.py:61`

**当前行为**:
- 打印 agent 名称提示：`{agent_name}: `
- 这个在 minimal 模式下可能不需要，因为最终输出会包含 agent 信息

## 改进建议

### 优先级 1: 必须修复（影响 script 解析）

#### 1.1 禁用 `print_session_info()` 在 minimal 模式
**方案**: 
- 修改 `print_session_info()` 函数，接受可选的 `output_config` 参数
- 如果是 `OutputStyle.MINIMAL`，跳过所有显示
- 或者创建一个新的 `should_show_session_info(output_config)` 检查函数

**影响范围**:
- `wolo/cli/utils.py` - `print_session_info()` 函数
- 所有调用 `print_session_info()` 的地方需要传递 `output_config`

**建议实现**:
```python
def print_session_info(
    session_id: str, 
    show_resume_hints: bool = True,
    output_config: OutputConfig | None = None
) -> None:
    # 如果是 minimal 模式，完全跳过
    if output_config and output_config.style == OutputStyle.MINIMAL:
        return
    # ... 原有逻辑
```

#### 1.2 禁用 UI 快捷键提示在 minimal 模式
**方案**:
- 在 `run_single_task_mode()` 中检查 output style
- 如果是 minimal，即使 `enable_ui_state=True` 也不打印快捷键

**影响范围**:
- `wolo/cli/execution.py` - `run_single_task_mode()` 函数
- 需要传递 `output_config` 到 execution 函数

### 优先级 2: 建议改进（提升 script 友好度）

#### 2.1 Agent 名称提示
**当前**: `{agent_name}: ` 在每行开始显示
**建议**: minimal 模式下不显示实时提示，只在最终输出中包含 agent 信息

**影响**:
- `wolo/cli/execution.py:61` - agent 名称打印
- `wolo/cli/events.py` - `on_agent_start()` 事件处理

#### 2.2 错误输出格式
**当前**: 错误可能混在正常输出中
**建议**: minimal 模式下，错误应该：
- 输出到 stderr（而不是 stdout）
- 使用结构化格式（JSON 模式下包含在 JSON 中）
- 文本模式下使用明确的 "Error:" 前缀

**影响**:
- `wolo/cli/output/minimal.py` - `on_error()` 方法
- 所有错误输出位置

#### 2.3 进度指示器
**检查**: 是否有任何 "..." 或进度条输出
**建议**: minimal 模式下完全禁用

#### 2.4 时间戳
**当前**: 某些输出可能包含时间戳
**建议**: minimal 模式下不显示时间戳（除非明确启用）

### 优先级 3: 可选改进（进一步优化）

#### 3.1 退出码标准化
**建议**: 
- minimal 模式下，确保退出码符合 Unix 约定：
  - 0 = 成功
  - 1 = 一般错误
  - 2 = 配置错误
  - 3 = session 错误
  - 等等

**当前状态**: 已有 `ExitCode` 枚举，需要确认是否一致使用

#### 3.2 输出缓冲
**建议**: 
- minimal 模式下，考虑禁用输出缓冲（`-u` 标志效果）
- 或者明确刷新 stdout/stderr

#### 3.3 环境变量检测
**建议**: 
- 如果检测到非 TTY（`!sys.stdout.isatty()`），自动使用 minimal 模式
- 或者提供 `WOLO_OUTPUT_STYLE` 环境变量

#### 3.4 结构化输出增强
**建议**: 
- JSON 模式下，添加更多元数据：
  - `session_id`
  - `workdir`
  - `execution_time_ms`
  - `tool_calls` 详细信息（包括参数）

## 实施计划

### Phase 1: 核心修复（必须）
1. ✅ 修改 `print_session_info()` 支持 output_config 检查
2. ✅ 修改所有调用点传递 output_config
3. ✅ 禁用 UI 快捷键提示在 minimal 模式
4. ✅ 测试验证

### Phase 2: 输出优化（建议）
1. 优化 agent 名称显示
2. 改进错误输出格式
3. 移除所有进度指示器
4. 测试验证

### Phase 3: 增强功能（可选）
1. 退出码标准化检查
2. 输出缓冲优化
3. 环境变量自动检测
4. JSON 输出增强

## 测试用例

### Test Case 1: Session Info 不显示
```bash
wolo -O minimal "test" 2>&1 | grep -v "Session:" | grep -v "Agent:" | grep -v "Created:"
# 应该没有 session 信息输出
```

### Test Case 2: 快捷键提示不显示
```bash
wolo -O minimal "test" 2>&1 | grep -v "快捷键"
# 应该没有快捷键提示
```

### Test Case 3: JSON 输出纯净
```bash
wolo --json "test" 2>&1 | jq .
# 应该输出有效的 JSON，没有额外文本
```

### Test Case 4: 错误输出到 stderr
```bash
wolo -O minimal "invalid command" 2>&1 > stdout.txt 2> stderr.txt
# stdout.txt 应该为空或只有正常输出
# stderr.txt 应该包含错误信息
```

## 向后兼容性

- ✅ 不影响 `default` 和 `verbose` 模式
- ✅ 不影响交互式使用
- ✅ 只影响 `minimal` 模式的输出格式

## 相关文件清单

需要修改的文件：
1. `wolo/cli/utils.py` - `print_session_info()` 函数
2. `wolo/cli/execution.py` - `run_single_task_mode()` 函数
3. `wolo/cli/commands/run.py` - 传递 output_config
4. `wolo/cli/commands/session.py` - 传递 output_config
5. `wolo/cli/output/minimal.py` - 优化错误输出
6. `wolo/cli/events.py` - 优化 agent_start 处理

需要检查的文件：
1. `wolo/cli/commands/repl.py` - 确认 minimal 模式下的行为
2. `wolo/ui.py` - 确认 UI 快捷键逻辑
3. 所有错误输出位置
