# Orchestrator_v2 工作流问题分析报告

**分析时间**: 2026-02-19
**对比文档**: doc/多智能体团队最新博客.md (Anthropic C Compiler 项目)

## 执行摘要

通过分析 `.agent-logs/implementer-1.log` (30,589行日志) 和 3 次失败记录，发现当前 orchestrator_v2 工作流存在**严重的环境配置问题**和**测试反馈机制缺陷**，导致 agent 陷入无限重试循环，与博客中描述的成功实践存在显著差距。

---

## 核心问题清单

### 1. 环境配置错误导致启动失败循环

**问题表现**:
- Agent 容器启动后立即因 `OPENAI_API_KEY` 缺失而失败
- 日志显示至少 **14+ 次连续启动失败**
- 每次失败后 harness 立即重启，形成快速失败循环

**日志证据**:
```
agent-implementer: ERROR: Missing environment variable: `OPENAI_API_KEY`.
----- AGENT-IMPLEMENTER ERROR -----
codex failed
return_code: 1
```

**根本原因**:
- `orchestrator_v2/team/spawner.py:84` 设置了 `VENV_PYTHON=/home/agent/.venv/bin/python`
- 但该路径在容器内不存在（宿主机 `.venv` 未正确挂载或不存在）
- Agent 使用的 CLI 工具 (codex) 需要 `OPENAI_API_KEY`，但容器环境未注入

**博客对比**:
> 博客中使用 Claude API，环境变量管理清晰：
> ```bash
> claude --dangerously-skip-permissions \
>        -p "$(cat AGENT_PROMPT.md)" \
>        --model claude-opus-X-Y
> ```
>
> **我们的问题**: 使用了第三方 CLI (codex)，但未正确配置其依赖的环境变量。

---

### 2. Python 路径配置错误导致测试无法运行

**问题表现**:
- 即使 agent 成功启动，测试命令也因 Python 路径错误而失败
- 日志显示 **8 次测试失败**，其中多次是 `/home/agent/.venv/bin/python: not found`

**日志证据**:
```
## 测试失败（第 1/3 次修复机会）
ERROR: tests failed (failed=1 total=0 framework=unknown duration=0.0s)
STATS: passed=0 failed=1 skipped=0 total=0
---
/bin/sh: 1: /home/agent/.venv/bin/python: not found
```

**根本原因**:
- `project_env.json` 中的测试命令使用 `${VENV_PYTHON:-/home/agent/.venv/bin/python}`
- `spawner.py` 注入了 `VENV_PYTHON=/home/agent/.venv/bin/python` 环境变量
- 但该路径在容器内不存在，导致所有测试命令失败

**Agent 的修复尝试**:
Agent 多次尝试修复此问题：
1. 第 1 次尝试：将 `project_env.json` 改为硬编码 `/usr/bin/python3`
2. 第 2 次尝试：改为 `/usr/bin/python3.11`
3. 但由于 `spawner.py` 持续注入错误的 `VENV_PYTHON`，修复无效

**博客对比**:
> 博客强调 "Put yourself in Claude's shoes"：
> - 测试 harness 应该为 Claude 设计，而不是为人类设计
> - 环境应该开箱即用，不需要 agent 修复基础设施问题
>
> **我们的问题**: Agent 花费大量时间修复环境配置，而不是完成实际任务。

---

### 3. 任务失败后的无限重试循环

**问题表现**:
- TASK-001 失败 3 次后被标记为 FAILED
- 但 monitor 继续重启 agent，agent 重新认领同一任务
- 日志中 TASK-001 出现 **20+ 次**，说明任务被反复认领

**日志证据**:
```bash
$ grep -n "TASK-001" .agent-logs/implementer-1.log | wc -l
20+
```

**失败记录**:
- `tasks/failures/TASK-001_attempt_1.md`: `/home/agent/.venv/bin/python: not found`
- `tasks/failures/TASK-001_attempt_2.md`: 390 passed, 0 failed (但被判定为失败)
- `tasks/failures/TASK-001_attempt_3.md`: 399 passed, 75 skipped (但被判定为失败)

**根本原因**:
- 主仓库和 upstream 仓库状态不同步（已通过 `sync_from_upstream()` 修复）
- 但更深层的问题是：**测试判定逻辑有误**

**attempt_2 的异常**:
```
ERROR: tests failed (failed=0 total=390 framework=pytest duration=4.6s)
STATS: passed=390 failed=0 skipped=0 total=390
```
- 明明 390 个测试全部通过 (failed=0)
- 但被判定为 "tests failed"
- 说明测试 runner 的成功/失败判定逻辑有 bug

**博客对比**:
> 博客强调 "Write extremely high-quality tests"：
> - 测试 verifier 必须接近完美，否则 Claude 会解决错误的问题
> - 测试结果必须清晰明确，不能有歧义
>
> **我们的问题**: 测试 runner 本身有 bug，给出错误的失败信号。

---

### 4. 测试反馈信息质量低

**问题表现**:
- 测试失败时，错误信息不够清晰
- Agent 需要多次尝试才能定位问题

**attempt_2 的错误信息**:
```
TOP_FAILURES:
- tests/integration/test_chapter_render_api.py :: test_chapter_render_too_short_returns_400 ::
- tests/integration/test_chapter_render_api.py :: test_chapter_render_too_long_returns_400 ::
```
- 只有测试名称，没有具体错误信息
- Agent 无法从这些信息中判断问题所在

**博客对比**:
> 博客强调 "Context window pollution"：
> - 测试 harness 不应打印数千字节的无用信息
> - 最多打印几行输出，详细信息记录到文件
> - 如果有错误，应该在同一行打印 ERROR 和原因，方便 grep
>
> **我们的问题**: 错误信息不够结构化，缺少关键细节。

---

### 5. Time Blindness 问题未解决

**问题表现**:
- Agent 可能花费大量时间在环境修复上
- 没有快速测试选项来避免长时间等待

**博客对比**:
> 博客提到 "Time blindness"：
> - Claude 无法感知时间，会愉快地花费数小时运行测试
> - 解决方案：提供 `--fast` 选项，运行 1% 或 10% 的随机样本
> - 样本对每个 agent 是确定性的，但跨 VM 随机，确保覆盖所有文件
>
> **我们的实现**:
> - `project_env.json` 有 `test_fast_sample_rate: 0.1`
> - 但从日志看，agent 似乎没有使用快速测试
> - 每次测试都运行完整测试套件（390+ 测试）

---

### 6. 缺少进度心跳机制的有效性验证

**问题表现**:
- Agent prompt 中要求定期更新 `PROGRESS.md` 和 push heartbeat
- 但从日志看，agent 在环境问题上卡住，无法执行到心跳逻辑

**博客对比**:
> 博客中 agent 会维护 running doc of failed approaches
> - 记录尝试过的方案和失败原因
> - 帮助其他 agent 避免重复错误
>
> **我们的问题**: Agent 连基本环境都无法启动，无法执行高级协作逻辑。

---

## 与博客设计原则的对比

### ✅ 我们做对的地方

1. **Git-based 任务锁机制**: 使用 `current_tasks/` 文件作为锁，利用 git 原子性
2. **Bare upstream 仓库**: 作为单一真相源
3. **Agent 自主决策**: 让 agent 自己决定任务是否失败
4. **进度日志**: `PROGRESS.md` 记录团队进度

### ❌ 我们的主要差距

| 博客原则 | 我们的实现 | 差距 |
|---------|-----------|------|
| **环境开箱即用** | Agent 需要修复环境配置 | 🔴 严重 |
| **高质量测试** | 测试 runner 有 bug，误判成功为失败 | 🔴 严重 |
| **清晰的错误信息** | 错误信息缺少细节 | 🟡 中等 |
| **Time blindness 对策** | 有配置但未生效 | 🟡 中等 |
| **Context window 管理** | 日志过于冗长 | 🟡 中等 |
| **并行化支持** | 单 agent，无并行 | 🟢 轻微 |

---

## 根本原因分析

### 问题根源：基础设施不稳定

博客项目成功的关键是：
> "I built a harness that sticks Claude in a simple loop"

**简单循环的前提**:
1. 环境稳定可靠
2. 测试反馈准确
3. Agent 只需关注业务逻辑

**我们的现状**:
1. 环境配置错误，agent 无法启动
2. 测试 runner 有 bug，给出错误信号
3. Agent 花费大量时间修复基础设施

### 类比：建筑工人 vs 修理工

**博客中的 agent**: 像建筑工人，在稳定的工地上盖房子
**我们的 agent**: 像修理工，不断修复工地的基础设施问题

---

## 优先级修复建议

### P0: 修复环境配置（阻塞所有工作）

1. **修复 Python 路径问题**
   - 选项 A: 在容器内创建 `/home/agent/.venv` 并正确挂载
   - 选项 B: 移除 `VENV_PYTHON` 环境变量，使用系统 Python
   - **推荐**: 选项 B，简化配置

2. **修复 API Key 注入**
   - 如果使用 codex CLI，确保 `OPENAI_API_KEY` 正确注入
   - 或者切换到 Claude API（与博客一致）

**文件修改**:
- `orchestrator_v2/team/spawner.py:84`: 移除或修复 `VENV_PYTHON`
- `orchestrator_v2/config.py`: 检查 `VENV_DIR` 和 `VENV_MOUNT_PATH` 配置

### P1: 修复测试 runner 判定逻辑（导致误判）

**问题定位**:
```python
# orchestrator_v2/harness/agent_loop.py 或 testing/runner.py
# 需要找到测试结果判定逻辑
```

**修复方向**:
- 当 `passed=390 failed=0` 时，应该判定为成功
- 检查是否有其他隐含的失败条件（如 warnings、skipped）

### P2: 改进测试反馈质量

1. **结构化错误输出**
   ```
   ERROR: test_foo failed
   Reason: AssertionError: expected 200, got 400
   File: tests/integration/test_api.py:42
   ```

2. **减少 context pollution**
   - 成功的测试只打印一行摘要
   - 失败的测试打印详细信息到文件，只在 stdout 打印文件路径

3. **实现快速测试**
   - 确保 `test_fast_sample_rate` 配置生效
   - 在 agent prompt 中明确说明何时使用快速测试

### P3: 增强监控和可观测性

1. **Monitor 应该检测环境问题**
   - 如果 agent 连续启动失败 N 次，创建 blocked 任务通知用户
   - 不要无限重试明显的配置错误

2. **Agent 日志分级**
   - ERROR: 阻塞性问题（环境配置、测试 runner bug）
   - WARNING: 可恢复问题（测试失败、merge 冲突）
   - INFO: 正常进度

---

## 长期改进方向

### 1. 测试基础设施自动化

**博客启示**:
> "I had to constantly remind myself that I was writing this test harness for Claude and not for myself"

**改进方向**:
- 创建 `orchestrator_v2/testing/validator.py`，验证测试环境
- 在 agent 启动前运行 pre-flight check
- 如果环境不满足要求，立即失败并给出清晰错误

### 2. 实现快速反馈循环

**博客实践**:
- 快速测试（1-10% 样本）用于日常开发
- 完整测试用于 CI gate
- 每个 agent 的样本是确定性的，避免 flaky tests

**实现建议**:
```python
# orchestrator_v2/testing/sampler.py
def get_test_sample(agent_id: str, sample_rate: float) -> list[str]:
    """返回该 agent 应该运行的测试列表（确定性采样）"""
    seed = hash(agent_id) % 1000000
    random.seed(seed)
    all_tests = discover_all_tests()
    return random.sample(all_tests, int(len(all_tests) * sample_rate))
```

### 3. 改进 Agent Prompt

**当前问题**:
- Prompt 假设环境已经就绪
- 没有处理环境问题的指导

**改进方向**:
```markdown
## 环境问题处理

如果遇到以下问题，立即创建 blocked 任务：
1. Python 解释器不存在
2. 依赖包缺失
3. API Key 未配置

不要尝试修复这些问题，这是 orchestrator 的责任。
```

### 4. 实现 Oracle-based 并行化

**博客实践**:
> "I wrote a new test harness that randomly compiled most of the kernel using GCC, and only the remaining files with Claude's C Compiler"

**应用到我们的场景**:
- 当所有测试都通过后，如何继续并行工作？
- 可以让不同 agent 优化不同模块的性能
- 或者让 agent 处理不同类型的任务（实现 vs 重构 vs 文档）

---

## 立即行动项

### 今天必须修复（阻塞所有工作）

1. [ ] 修复 `spawner.py` 中的 `VENV_PYTHON` 配置
2. [ ] 验证容器内 Python 环境可用
3. [ ] 修复测试 runner 的成功/失败判定逻辑

### 本周修复（影响效率）

1. [ ] 实现快速测试采样
2. [ ] 改进测试错误信息格式
3. [ ] 添加 pre-flight 环境检查

### 下周改进（提升质量）

1. [ ] 重构 agent prompt，明确环境问题处理策略
2. [ ] 实现 monitor 的智能故障检测
3. [ ] 添加 agent 日志分析工具

---

## 结论

当前 orchestrator_v2 的核心问题是**基础设施不稳定**，导致 agent 无法专注于业务逻辑。博客项目成功的关键是为 Claude 创造了一个稳定、清晰、易于理解的工作环境。

**关键洞察**:
> "The scaffolding runs Claude in a loop, but that loop is only useful if Claude can tell how to make progress."

我们的循环存在，但 agent 无法判断如何前进，因为：
1. 环境配置错误阻止了启动
2. 测试反馈不准确，误导了决策
3. 错误信息不清晰，增加了调试难度

**修复优先级**: P0 环境配置 > P1 测试判定 > P2 反馈质量 > P3 监控增强

修复这些问题后，我们才能真正实现博客中描述的"多个 Claude 实例在共享代码库上并行工作，无需人工干预"的愿景。
