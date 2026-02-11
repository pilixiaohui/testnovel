# MCP 工具使用指南

本指南定义了可用的 MCP 工具及其使用规范。

## 1. Serena（代码分析与编辑 - 首选）

**重要**：进行代码检索、分析、编辑时，**必须优先使用 Serena**，而非 bash 命令（如 cat、grep、sed）。

### 工具能力

| 类别 | 工具 | 用途 |
|------|------|------|
| 符号操作 | `find_symbol` | 精确定位函数/类/变量定义 |
| 符号操作 | `find_referencing_symbols` | 查找符号的所有引用 |
| 符号操作 | `get_symbols_overview` | 快速了解文件结构 |
| 符号操作 | `replace_symbol_body` | 替换函数/类体 |
| 符号操作 | `insert_after_symbol` / `insert_before_symbol` | 在符号前后插入代码 |
| 文件操作 | `read_file` | 读取文件内容 |
| 文件操作 | `create_text_file` | 创建新文件 |
| 文件操作 | `list_dir` | 列出目录内容 |
| 文件操作 | `find_file` | 查找文件 |
| 代码搜索 | `search_for_pattern` | 正则搜索（支持 glob 过滤） |
| 文本编辑 | `replace_regex` | 正则替换 |

### 调用策略

1. **理解阶段**：`get_symbols_overview` → 快速了解文件结构
2. **定位阶段**：`find_symbol` → 精确定位符号（支持 name_path/substring_matching）
3. **分析阶段**：`find_referencing_symbols` → 分析依赖关系与调用链
4. **搜索阶段**：`search_for_pattern` → 复杂模式搜索（限定 paths_include_glob）
5. **编辑阶段**：
   - 优先使用符号级操作（`replace_symbol_body`/`insert_*_symbol`）
   - 复杂替换使用 `replace_regex`（明确 `allow_multiple_occurrences`）

### 参数规范

**必须显式传递**：`max_answer_chars: -1`

### 范围控制

- 始终限制 `relative_path` 到相关目录
- 使用 `paths_include_glob`/`paths_exclude_glob` 精准过滤
- 避免全项目无过滤扫描

### 示例

```
# 查找函数定义
find_symbol(name="render_chapter", max_answer_chars=-1)

# 搜索模式
search_for_pattern(
    pattern="def test_.*",
    paths_include_glob="**/tests/**/*.py",
    max_answer_chars=-1
)

# 读取文件（路径相对于工作目录）
read_file(relative_path="src/api/example.py", max_answer_chars=-1)
```

## 2. Context7（官方文档查询）

### 使用流程

1. `resolve-library-id` → 获取库 ID
2. `get-library-docs` → 获取文档内容

### 触发场景

- 框架 API 查询
- 配置文档
- 版本差异
- 迁移指南

### 参数控制

- `tokens` ≤ 5000
- `topic` 指定聚焦范围

## 3. Sequential Thinking（复杂规划）

### 触发场景

- 多步骤任务分解
- 架构设计
- 问题诊断流程

### 输出要求

- 生成 6-10 步可执行计划
- 每步一句话描述
- 不暴露推理过程

### 参数控制

- `total_thoughts` ≤ 10

## 工具选择优先级

1. **代码分析/编辑** → Serena（首选）
2. **文档查询** → Context7
3. **复杂规划** → Sequential Thinking

## 禁止行为（代码操作）

- ❌ 使用 `cat`/`head`/`tail` 读取代码文件（应使用 Serena `read_file`）
- ❌ 使用 `grep`/`rg` 搜索代码（应使用 Serena `search_for_pattern`）
- ❌ 使用 `sed`/`awk` 编辑代码（应使用 Serena 符号操作或 `replace_regex`）
