# Wolo vs OpenCode Tool 对比分析报告

## 一、工具清单对比

### 1.1 核心工具对比表

| 工具 | OpenCode | Wolo | 差距分析 |
|------|----------|------|----------|
| **bash/shell** | ✅ 完整 | ⚠️ 基础 | 缺少: 命令解析、权限检查、实时输出流、超时处理优化 |
| **read** | ✅ 完整 | ⚠️ 基础 | 缺少: 图片/PDF支持、二进制检测、文件建议、LSP集成、行号格式化 |
| **write** | ✅ 完整 | ⚠️ 基础 | 缺少: diff生成、LSP诊断、文件时间追踪 |
| **edit** | ✅ 高级 | ⚠️ 基础 | 缺少: 9种智能匹配算法、LSP诊断、diff生成、文件锁 |
| **multiedit** | ⚠️ 基础 | ⚠️ 基础 | 两者都是简单批量编辑 |
| **grep** | ✅ 完整 | ⚠️ 基础 | 缺少: ripgrep集成、按修改时间排序、结果限制 |
| **glob** | ✅ 完整 | ⚠️ 基础 | 缺少: ripgrep集成、按修改时间排序 |
| **web_search** | ✅ Exa API | ⚠️ DuckDuckGo | 缺少: 高级搜索参数、livecrawl、搜索类型 |
| **web_fetch** | ✅ 完整 | ⚠️ 基础 | 缺少: 格式选择(markdown/text/html)、HTML转换 |
| **task** | ✅ 完整 | ⚠️ 基础 | 缺少: 会话继续、权限传递、实时状态更新 |
| **todowrite** | ✅ 完整 | ✅ 完整 | 基本对齐 |
| **todoread** | ✅ 有 | ❌ 无 | 完全缺失 |

### 1.2 OpenCode 独有工具

| 工具 | 功能 | 重要性 | 实现难度 |
|------|------|--------|----------|
| **question** | 向用户提问并等待回答 | ⭐⭐⭐⭐⭐ | 中 |
| **batch** | 并行执行多个工具调用 | ⭐⭐⭐⭐ | 中 |
| **codesearch** | 搜索代码文档/API | ⭐⭐⭐ | 低(API调用) |
| **apply_patch** | 应用补丁格式的修改 | ⭐⭐⭐ | 高 |
| **lsp** | LSP操作(定义跳转等) | ⭐⭐⭐⭐ | 高 |
| **plan_enter/exit** | 计划模式切换 | ⭐⭐ | 中 |
| **list (ls)** | 智能目录列表 | ⭐⭐ | 低 |
| **skill** | 技能/插件系统 | ⭐⭐ | 高 |

### 1.3 Wolo 独有工具

| 工具 | 说明 |
|------|------|
| 无 | Wolo 没有 OpenCode 缺失的独特工具 |

---

## 二、关键功能差距详解

### 2.1 Edit 工具差距 (最关键)

OpenCode 的 edit 工具有 **9 种智能匹配算法**:

| 算法 | 功能 | Wolo 状态 |
|------|------|-----------|
| SimpleReplacer | 精确匹配 | ✅ 有 |
| LineTrimmedReplacer | 忽略行首尾空白 | ❌ 无 |
| BlockAnchorReplacer | 首尾行锚定+模糊中间 | ❌ 无 |
| WhitespaceNormalizedReplacer | 空白归一化 | ❌ 无 |
| IndentationFlexibleReplacer | 缩进灵活匹配 | ❌ 无 |
| EscapeNormalizedReplacer | 转义字符归一化 | ❌ 无 |
| TrimmedBoundaryReplacer | 边界trim匹配 | ❌ 无 |
| ContextAwareReplacer | 上下文感知匹配 | ❌ 无 |
| MultiOccurrenceReplacer | 多次出现处理 | ❌ 无 |

**影响**: LLM 生成的代码经常有轻微的空白/缩进差异，智能匹配能大幅提高编辑成功率。

### 2.2 输出截断系统

OpenCode 有完整的 `Truncate` 系统:
- 最大 2000 行 / 50KB
- 超出部分保存到文件
- 提示用户使用 grep/read 查看
- 7天自动清理

**Wolo 状态**: ❌ 无截断系统，大输出会消耗大量 token

### 2.3 LSP 集成

OpenCode 在多个工具中集成 LSP:
- edit/write 后自动检查诊断错误
- read 时预热 LSP 客户端
- 专门的 lsp 工具进行代码导航

**Wolo 状态**: ❌ 完全没有 LSP 集成

### 2.4 权限系统

OpenCode 有完整的权限系统:
- 每个工具调用前 `ctx.ask()` 请求权限
- 支持 allow/deny/ask 三种策略
- 外部目录访问检查

**Wolo 状态**: ⚠️ 有基础的 agent 权限，但没有细粒度的工具权限

### 2.5 文件时间追踪

OpenCode 的 `FileTime` 系统:
- 追踪文件读取时间
- 编辑前检查文件是否被外部修改
- 防止覆盖用户的手动修改

**Wolo 状态**: ❌ 无文件时间追踪

---

## 三、三阶段改进计划

### 第一阶段：高效用 + 易实现 (1-2周)

| 优先级 | 任务 | 效用 | 难度 | 说明 |
|--------|------|------|------|------|
| P0 | **输出截断系统** | ⭐⭐⭐⭐⭐ | 低 | 防止大输出消耗 token，参考 `truncation.ts` |
| P0 | **Edit 智能匹配** | ⭐⭐⭐⭐⭐ | 中 | 至少实现 LineTrimmed + IndentationFlexible |
| P1 | **todoread 工具** | ⭐⭐⭐ | 低 | 简单添加，完善 todo 功能 |
| P1 | **Read 行号格式化** | ⭐⭐⭐ | 低 | 输出 `00001| code` 格式，便于 LLM 定位 |
| P1 | **Grep 使用 ripgrep** | ⭐⭐⭐⭐ | 低 | 性能大幅提升，结果按修改时间排序 |
| P2 | **Web fetch 格式选择** | ⭐⭐ | 低 | 支持 markdown/text/html 输出 |

**第一阶段目标**: 提升核心工具的可靠性和效率

### 第二阶段：中等效用 + 中等难度 (2-3周)

| 优先级 | 任务 | 效用 | 难度 | 说明 |
|--------|------|------|------|------|
| P0 | **Question 工具** | ⭐⭐⭐⭐⭐ | 中 | 允许 LLM 向用户提问，大幅提升交互能力 |
| P0 | **Batch 工具** | ⭐⭐⭐⭐ | 中 | 并行执行工具，提升效率 |
| P1 | **Edit diff 生成** | ⭐⭐⭐ | 中 | 显示修改内容，便于用户审查 |
| P1 | **文件时间追踪** | ⭐⭐⭐ | 中 | 防止覆盖用户修改 |
| P1 | **Read 图片/PDF 支持** | ⭐⭐⭐ | 中 | 支持多模态输入 |
| P2 | **Read 二进制检测** | ⭐⭐ | 低 | 避免读取二进制文件 |
| P2 | **Read 文件建议** | ⭐⭐ | 低 | 文件不存在时建议相似文件 |

**第二阶段目标**: 增强交互能力和用户体验

### 第三阶段：高级功能 (3-4周)

| 优先级 | 任务 | 效用 | 难度 | 说明 |
|--------|------|------|------|------|
| P0 | **LSP 集成** | ⭐⭐⭐⭐ | 高 | 编辑后检查错误，代码导航 |
| P1 | **Apply Patch 工具** | ⭐⭐⭐ | 高 | 支持补丁格式，适合大规模修改 |
| P1 | **细粒度权限系统** | ⭐⭐⭐ | 中 | 每个工具调用的权限控制 |
| P2 | **CodeSearch 工具** | ⭐⭐⭐ | 低 | 集成 Exa API 搜索代码文档 |
| P2 | **Plan 模式切换** | ⭐⭐ | 中 | plan_enter/plan_exit 工具 |
| P3 | **Skill/Plugin 系统** | ⭐⭐ | 高 | 可扩展的工具系统 |

**第三阶段目标**: 达到与 OpenCode 功能对等

---

## 四、实现建议

### 4.1 第一阶段重点代码参考

**输出截断** - 参考 `truncation.ts`:
```python
MAX_LINES = 2000
MAX_BYTES = 50 * 1024

def truncate_output(text: str) -> tuple[str, bool, str | None]:
    """截断输出，返回 (内容, 是否截断, 保存路径)"""
```

**Edit 智能匹配** - 参考 `edit.ts` 的 Replacer 模式:
```python
def line_trimmed_replace(content: str, find: str) -> str | None:
    """忽略行首尾空白的匹配"""
    
def indentation_flexible_replace(content: str, find: str) -> str | None:
    """缩进灵活匹配"""
```

### 4.2 依赖建议

| 功能 | 推荐依赖 |
|------|----------|
| ripgrep | 系统安装 `rg` 命令 |
| HTML转Markdown | `markdownify` 或 `html2text` |
| Diff生成 | `difflib` (标准库) |
| LSP | `pygls` 或直接调用 LSP 进程 |

### 4.3 测试策略

每个阶段完成后:
1. 单元测试覆盖新功能
2. 集成测试验证工具链
3. 实际任务测试（如修复 bug、重构代码）

---

## 五、总结

### 当前差距评估

| 维度 | OpenCode | Wolo | 差距 |
|------|----------|------|------|
| 工具数量 | 14+ | 11 | 🔴 缺少 3+ 关键工具 |
| Edit 可靠性 | 95%+ | 70% | 🔴 缺少智能匹配 |
| 输出管理 | 完善 | 无 | 🔴 大输出问题 |
| LSP 集成 | 完善 | 无 | 🟡 高级功能缺失 |
| 权限系统 | 完善 | 基础 | 🟡 安全性不足 |
| 用户交互 | 丰富 | 基础 | 🟡 缺少 question 工具 |

### 投入产出比排序

1. **输出截断** - 投入小，立即解决 token 浪费
2. **Edit 智能匹配** - 投入中，大幅提升编辑成功率
3. **Question 工具** - 投入中，质的交互提升
4. **Batch 工具** - 投入中，效率提升
5. **LSP 集成** - 投入大，专业级功能
