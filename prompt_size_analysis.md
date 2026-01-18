# Orchestrator Prompt Size 错误根本原因分析

## 错误信息
```
RuntimeError: MAIN prompt too large len=25053 > 20000. Please archive dev_plan and/or reduce injected history.
```

## 根本原因

### 1. **report_review.md 过大是主要原因**
- **当前大小**: 19,586 字符 (278 行)
- **占比**: 约占总 prompt 的 51%
- **问题**: REVIEW agent 在 Iteration 1 生成了一份极其详细的审阅报告，包含：
  - 完整的代码清单（A1-A2 部分）
  - 详细的 REST API 路由列表
  - 8 个差距点的详细分析
  - 建议的 dev_plan 更新草案（M7-M8）
  - M6 任务的复核结论

### 2. **Prompt 组成部分分析**

```
组件                              字符数    占比
================================================
System Prompt (main)              9,024    23.6%
Memory Files:
  - global_context.md               886     2.3%
  - project_history.md            6,343    16.6%
  - dev_plan.md                   2,186     5.7%
Report Files:
  - report_review.md             19,586    51.2%  ← 问题所在
  - report_dev.md                    31     0.1%
  - report_finish_review.md          41     0.1%
  - report_test.md                   32     0.1%
Iteration/Task strings            ~200     0.5%
================================================
总计                             ~38,329   100%
```

### 3. **为什么会超过限制**

配置的限制是 `MAX_PROMPT_SIZE = 20000` 字符，但实际构建的 prompt 达到了 25,053 字符。

**计算验证**:
- 基础组件总和: 38,329 字符
- 实际报错: 25,053 字符
- 差异原因:
  - `_inject_project_history_recent()` 使用了历史窗口机制，只注入最近 N 轮迭代
  - 当前是新任务的 Iteration 2，历史窗口设置为 `MIN_HISTORY_WINDOW = 3`
  - 但即使缩减了历史，report_review.md 的 19,586 字符仍然导致总量超标

### 4. **触发条件**

在 `orchestrator/workflow.py:1317-1335` 中的逻辑：

```python
# 第一次检查
if prompt_len > MAX_PROMPT_SIZE:
    # 尝试缩减到最小历史窗口
    if adaptive_window != MIN_HISTORY_WINDOW:
        adaptive_window = MIN_HISTORY_WINDOW
        main_prompt = _build_main_prompt(...)
        prompt_len = len(main_prompt)
    # 第二次检查，仍然过大则抛出异常
    if prompt_len > MAX_PROMPT_SIZE:
        raise RuntimeError(...)
```

系统已经尝试将历史窗口缩减到最小值（3 轮迭代），但由于 report_review.md 过大，总 prompt 仍然超过 20,000 字符限制。

## 解决方案

### 短期方案（立即可用）

1. **清理 report_review.md**
   ```bash
   # 将当前报告归档
   mv orchestrator/reports/report_review.md \
      orchestrator/reports/report_review_iteration1_archived.md

   # 创建精简版本（只保留结论和关键发现）
   echo "已阅读审阅行为规范\niteration: 1\n\n结论：PASS\n阻塞：无" > \
      orchestrator/reports/report_review.md
   ```

2. **增加 MAX_PROMPT_SIZE 限制**（临时措施）
   ```python
   # orchestrator/config.py:65
   MAX_PROMPT_SIZE = 30000  # 从 20000 增加到 30000
   ```

### 中期方案（优化架构）

1. **实现报告摘要机制**
   - 在 `_inject_file()` 中添加报告摘要逻辑
   - 当报告超过阈值（如 5000 字符）时，只注入摘要部分
   - 完整报告保存在文件中供需要时查阅

2. **报告分段存储**
   - 将详细的代码清单、API 列表等移到单独的文件
   - report_review.md 只保留结论、阻塞项和关键发现
   - 通过引用指向详细文档

3. **动态报告裁剪**
   ```python
   def _inject_report_with_limit(path: Path, max_chars: int = 5000) -> str:
       content = _read_text(path)
       if len(content) > max_chars:
           # 提取摘要部分（前 N 行或特定标记）
           lines = content.splitlines()
           summary = extract_summary(lines, max_chars)
           return _inject_text(path, summary + "\n\n[完整报告已截断]")
       return _inject_text(path, content)
   ```

### 长期方案（系统重构）

1. **实现增量上下文管理**
   - 使用向量数据库存储历史报告
   - 根据当前任务动态检索相关上下文
   - 只注入与当前迭代相关的历史片段

2. **报告模板标准化**
   - 定义报告的最大长度限制
   - 强制 REVIEW/DEV/TEST agent 输出符合长度约束的报告
   - 在 system prompt 中明确要求简洁性

3. **分层上下文注入**
   - Level 1: 必需上下文（dev_plan, 当前迭代信息）
   - Level 2: 最近报告摘要
   - Level 3: 历史上下文（按需加载）

## 建议的立即行动

1. **清理当前的 report_review.md**，保留核心结论
2. **临时提高 MAX_PROMPT_SIZE** 到 30000
3. **在 REVIEW agent 的 system prompt 中添加长度约束**：
   ```markdown
   ## 报告长度要求
   - 报告总长度不得超过 5000 字符
   - 代码清单使用引用而非完整列举
   - 差距分析保持简洁，每项不超过 3 行
   ```

## 预防措施

1. **添加报告大小监控**
   ```python
   def _validate_report_size(report_path: Path, max_size: int = 10000):
       size = len(_read_text(report_path))
       if size > max_size:
           _append_log_line(
               f"WARNING: {report_path.name} size {size} exceeds {max_size}\n"
           )
   ```

2. **在每次 agent 运行后检查报告大小**
3. **定期归档历史报告**，只保留最近 2-3 轮的完整报告

## 总结

**根本原因**: REVIEW agent 生成的报告过于详细（19,586 字符），占据了 prompt 预算的 51%，导致即使缩减历史窗口到最小值，总 prompt 仍然超过 20,000 字符限制。

**核心问题**: 缺乏报告长度控制机制，agent 可以生成任意长度的输出。

**解决方向**: 实现报告摘要机制 + 长度约束 + 动态裁剪。
