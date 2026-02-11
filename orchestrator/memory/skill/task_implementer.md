# IMPLEMENTER 任务派发规范

本文档定义 MAIN 代理派发 IMPLEMENTER 任务时的工单规范。

## 工单格式

```markdown
# Current Task (Iteration {N})
assigned_agent: IMPLEMENTER

## 任务目标
{简明描述要实现的功能}

## 需求边界
- 输入：{功能接收什么}
- 输出：{功能产出什么}
- 行为：{功能如何工作}

## 测试场景
1. 正常场景：{标准输入，预期输出}
2. 边界值：{空值、最大值、最小值}
3. 错误处理：{无效输入、网络错误、超时}

## 验收标准（抽象描述）
- {描述要达到的效果，不写具体命令}
- {例如：单元测试通过、无硬编码、登录流程正常}

## 约束条件
- {不能做什么}
- {需要注意什么}

## 执行环境
（由编排器自动注入）
```

**重要**：验收标准只描述"做到什么"，IMPLEMENTER 根据项目实际情况决定用什么命令验证。

---

## TDD 工作流程

IMPLEMENTER 合并了原 TEST 和 DEV 的职责，在单次会话中完成完整的 TDD 流程：

### Phase 1: 红灯阶段（编写测试）
1. 理解需求边界和验收标准
2. 设计测试用例（正常流程 + 边界条件 + 异常场景）
3. 编写测试代码
4. 执行测试，**确认红灯状态**（测试失败是预期的）

### Phase 2: 绿灯阶段（实现功能）
1. 分析测试用例，理解预期行为
2. 实现**最小必要代码**使测试通过
3. 执行测试，**确认绿灯状态**

### Phase 3: 重构阶段（可选）
1. 在测试保护下重构代码
2. 确保测试仍然通过

---

## IMPLEMENTER 的连续上下文

IMPLEMENTER 在多轮迭代中保持连续的会话上下文（通过 resume 机制）：

- **记得之前调研过的代码结构**
- **记得之前做过的设计决策**
- **记得之前写过的测试和实现**

### 工单设计原则

**MAIN 应该提供**：
- 需求边界（输入/输出/行为）
- 抽象验收标准（描述效果，不写命令）
- 约束条件

**MAIN 不应该提供**：
- ❌ 具体代码位置（IMPLEMENTER 自己调研）
- ❌ 实现方案（IMPLEMENTER 自己设计）
- ❌ 代码片段（IMPLEMENTER 自己编写）
- ❌ 具体测试命令（IMPLEMENTER 根据项目工具链决定）

**为什么？** 代码调研是实现的一部分，IMPLEMENTER 有连续上下文，调研结果直接用于实现，效率更高。

---

## Context-centric 优势

IMPLEMENTER 拥有完整 TDD 上下文，避免了原 TEST→DEV 交接时的"电话游戏"问题：

| 旧架构问题 | 新架构解决方案 |
|-----------|---------------|
| TEST 写测试，DEV 不理解测试意图 | IMPLEMENTER 同时理解测试和实现 |
| DEV 修改测试以通过验收 | IMPLEMENTER 不会自己骗自己 |
| 上下文在交接时丢失 | 完整上下文保持在单个代理中 |
| MAIN 调研代码再告诉 DEV | IMPLEMENTER 自己调研，上下文完整 |

---

## MAIN 输出格式

MAIN 派发 IMPLEMENTER 时，必须使用以下 JSON 格式输出（`task_body` 仅填写正文，工单头由编排器自动生成）：

```json
{
  "next_agent": "IMPLEMENTER",
  "reason": "派发原因",
  "history_append": "## Iteration {N}:\nnext_agent: IMPLEMENTER\nreason: {原因}\ndev_plan: {变更}",
  "task_body": "## 任务目标\n...\n\n## 需求边界\n...\n\n## 测试场景\n...\n\n## 验收标准\n...\n\n## 约束条件\n...",
  "dev_plan_next": null
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `next_agent` | ✅ | 固定为 `"IMPLEMENTER"` |
| `reason` | ✅ | 派发原因 |
| `history_append` | ✅ | 追加到 project_history 的内容 |
| `task_body` | ✅ | 仅包含工单正文（禁止包含标题与 assigned_agent） |
| `dev_plan_next` | ✅ | 更新后的 dev_plan，或 `null` 表示不更新 |

### dev_plan_next 更新时机

| 场景 | 是否更新 | 说明 |
|------|---------|------|
| 首次派发任务 | ✅ 更新 | 将任务状态从 TODO 改为 DOING |
| 任务已是 DOING | ❌ 不更新 | 保持 `null` |
| SYNTHESIZER REWORK | ❌ 不更新 | 任务状态保持 DOING |

---

## 派发场景

### 场景 1：新任务开始

```json
{
  "next_agent": "IMPLEMENTER",
  "reason": "开始新任务 M1-T1 的 TDD 实现",
  "history_append": "## Iteration 5:\nnext_agent: IMPLEMENTER\nreason: 开始 M1-T1 TDD 实现\ndev_plan: M1-T1 TODO→DOING",
  "task_body": "## 任务目标\n实现用户登录功能\n\n## 需求边界\n- 输入：用户名、密码\n- 输出：JWT token 或错误信息\n- 行为：验证凭据，成功返回 token\n\n## 测试场景\n1. 正常登录：有效凭据返回 token\n2. 边界值：空用户名、空密码\n3. 错误处理：无效凭据返回 401\n\n## 验收标准\n- 单元测试全部通过\n- 登录流程正常工作\n\n## 约束条件\n- 禁止硬编码用户凭据",
  "dev_plan_next": "# Dev Plan\n\n## M1: 用户认证\n\n### M1-T1: 用户登录\n- status: DOING\n- acceptance: 单元测试通过、登录流程正常"
}
```

### 场景 2：SYNTHESIZER REWORK 后修复

```json
{
  "next_agent": "IMPLEMENTER",
  "reason": "SYNTHESIZER REWORK: ANTI_CHEAT_DETECTOR 发现硬编码",
  "history_append": "## Iteration 8:\nnext_agent: IMPLEMENTER\nreason: 修复硬编码问题\ndev_plan: M1-T1 保持 DOING",
  "task_body": "## 任务目标\n修复 ANTI_CHEAT_DETECTOR 发现的硬编码问题\n\n## 问题清单\n1. [ANTI_CHEAT] 发现硬编码 ID 'scene-1'\n2. [ANTI_CHEAT] 发现硬编码 URL\n\n## 验收标准\n- 无硬编码 ID\n- 无硬编码 URL\n- 单元测试通过\n\n## 约束条件\n- 使用环境变量或配置替代硬编码",
  "dev_plan_next": null
}
```
