## 特殊任务：Agent 崩溃分析

当系统检测到某个 agent 反复崩溃时，monitor 会创建一个 blocked 任务。

**你的职责**：分析并报告，通知用户

### 处理流程

**1. 分析崩溃日志**

阅读任务描述中的崩溃记录，识别问题类别：

| 问题类别 | 特征 | 用户需要做什么 |
|---------|------|--------------|
| Orchestrator代码bug | Python异常、语法错误、逻辑错误 | 修复 orchestrator_v2/ 下的代码 |
| 配置错误 | 环境变量缺失、路径错误 | 修改配置文件 |
| 依赖问题 | 模块未找到、版本冲突 | 更新 requirements.txt |
| 环境问题 | Docker错误、网络超时 | 检查Docker/网络环境 |
| 任务问题 | 特定任务反复超时 | 修改或删除问题任务（你可以帮忙处理） |

**2. 创建事故报告**

在 `decisions/incidents/` 创建报告文件：

```markdown
# 事故报告：Agent {agent_id} 反复崩溃

**时间**: {timestamp}
**Agent**: {agent_id} ({role})
**崩溃次数**: {count}

## 问题摘要

{1-2句话描述问题}

## 崩溃日志

{最近3次崩溃的日志}

## 根因分析

{详细分析}

## 建议修复步骤

1. {具体步骤}
2. {具体步骤}
3. 修复后运行: `python -m orchestrator_v2 resume-agent {agent_id}`

## 相关文件

- {需要修改的文件列表}
```

**3. 通过飞书通知用户**

```python
from orchestrator_v2.feishu.client import FeishuClient

client = FeishuClient()
client.send_text(f"""
⚠️ Agent 崩溃警报

**Agent**: {agent_id} ({role})
**问题**: {问题类别}
**状态**: 已暂停

📋 详细报告: decisions/incidents/INCIDENT-{timestamp}.md

💡 建议操作:
{简要修复步骤}

修复后请运行:
`python -m orchestrator_v2 resume-agent {agent_id}`
""")
```

**4. 保持任务在 blocked/**

不要将任务移到 done/。让它保持在 blocked/ 状态，直到用户确认修复。

**注意**:
- 如果是任务问题（特定任务导致崩溃），你可以修改或删除该任务
- 如果是系统问题（orchestrator代码、配置、环境），只能报告给用户
- 系统已通过技术手段防止你修改 orchestrator_v2/ 代码，无需担心误操作
