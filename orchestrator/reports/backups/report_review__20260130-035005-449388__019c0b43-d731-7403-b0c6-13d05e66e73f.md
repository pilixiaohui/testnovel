已阅读审阅行为规范
iteration: 1
review_mode: single

## 任务理解

审阅的任务：识别“10 章×每章 2000 字”小说生成流程的潜在阻塞点和技术风险  
验收标准：输出高/中/低风险清单、每项缓解建议、标注阻塞性风险

## 验收执行

- 验收命令: `未提供（风险审阅任务）`
- 返回码: N/A
- 测试结果: 未执行
- 覆盖率: N/A

## 代码深度审查

### 实现代码审查

- 审查文件: `project/frontend/src/views/EditorView.vue`
- 审查内容:
  | 检查项 | 结果 | 说明 |
  |-------|------|------|
  | 函数参数/返回值类型 | 符合 | 前端类型标注正常 |
  | API 契约一致性 | 不符合 | 调用 renderScene 传空 payload，与后端必填字段冲突 |
  | 错误处理完整性 | 不完整 | 仅统一提示“Failed to render scene”，无具体错误提示/字段缺失指引 |
  | 边界条件处理 | 未考虑 | 未处理渲染参数缺失与长文本超时 |

- 代码片段证据:
```ts
// project/frontend/src/views/EditorView.vue:134
const rendered = (await renderScene(context.id, branchId, {})) as { content?: string }
```

- 实现审查结论: 存在问题（渲染接口必失败）

- 审查文件: `project/backend/app/models.py`
- 审查内容:
  | 检查项 | 结果 | 说明 |
  |-------|------|------|
  | 函数参数/返回值类型 | 符合 | Pydantic 必填字段完整 |
  | API 契约一致性 | 不符合 | 与前端空 payload 调用不匹配 |
  | 错误处理完整性 | 完整 | 由 Pydantic 直接拒绝缺字段请求 |
  | 边界条件处理 | 已考虑 | min_length 约束明确 |

- 代码片段证据:
```py
# project/backend/app/models.py:400
class SceneRenderPayload(BaseModel):
    voice_dna: str = Field(..., min_length=1)
    conflict_type: str = Field(..., min_length=1)
    outline_requirement: str = Field(..., min_length=1)
    user_intent: str = Field(..., min_length=1)
    expected_outcome: str = Field(..., min_length=1)
```

- 实现审查结论: 存在问题（契约冲突）

- 审查文件: `project/backend/app/services/smart_renderer.py`
- 审查内容:
  | 检查项 | 结果 | 说明 |
  |-------|------|------|
  | 函数参数/返回值类型 | 符合 | 结构清晰 |
  | API 契约一致性 | 不符合 | 依赖 llm.generate_prose，但注入的 LLM 实现未提供该方法 |
  | 错误处理完整性 | 不完整 | 仅对 llm 为 None 做快速失败，缺少接口不匹配校验 |
  | 边界条件处理 | 未考虑 | 大量 rounds 时无分段或长度控制 |

- 代码片段证据:
```py
# project/backend/app/services/smart_renderer.py:40
content = await self.llm.generate_prose(
    beats=beats,
    sensory=sensory_details,
    style=style_context,
    pov=pov,
)
```

- 实现审查结论: 存在问题（LLM 接口缺失风险）

### 测试代码审查
- 测试文件: 存在：`project/frontend/tests/e2e/snowflake.spec.ts`, `project/backend/tests/test_api_minimal.py`
- 测试覆盖情况:
  | 功能点 | 是否有测试 | 测试是否正确 |
  |-------|-----------|-------------|
  | 10 章 × 2000 字输出 | 否 | 不适用 |
  | 渲染接口必填字段校验 | 否 | 不适用 |
  | LLM 长文本分段策略 | 否 | 不适用 |
- 测试质量结论: 部分符合（缺少针对目标需求的端到端与长文本测试）

## 风险清单

### 高风险
- [阻塞] 渲染接口契约冲突：前端传空 payload，后端 SceneRenderPayload 全必填，渲染必失败  
  缓解：前端补齐必填字段（voice_dna/conflict_type/outline_requirement/user_intent/expected_outcome），或提供专用的“最小渲染”接口并明确必填字段
- [阻塞] 章节正文生成与持久化缺失：后端仅有 scene render；Chapter schema 未含 rendered_content，缺少 /chapters/{id}/render 能力  
  缓解：新增章节渲染接口与存储字段，明确章节内容生成流程与长度约束
- [阻塞] 运行依赖强约束：SNOWFLAKE_ENGINE 与 TOPONE_API_KEY 未配置即启动失败；Memgraph 必填  
  缓解：部署前强制环境检查与运行手册，确保配额与连通性
- SmartRenderer 与 LLM 接口不匹配：SmartRenderer 依赖 generate_prose，但注入 LLM 未实现  
  缓解：统一 LLM 接口（补齐 generate_prose 或改用 render_scene），保持单一契约

### 中风险
- 长文本无分段策略：2000 字 × 10 章可能触发 token 限制/JSON 解析失败/超时  
  缓解：引入明确的分段/合并策略与长度目标校验（不做兜底重试，失败即提示）
- Scene 数量硬约束（默认 50-100）与 10 章目标不匹配：成本与时延压力显著  
  缓解：提供可配置场景数量或为“短篇模式”单独参数
- 前端请求超时 30s：长文本生成可能超时  
  缓解：改为异步任务 + 轮询/回调，或显式提升超时阈值

### 低风险
- 生成流程缺少进度与状态反馈：长任务易被用户误判为卡死  
  缓解：前端显示进度/阶段日志与明确错误原因

## 结论

结论：FAIL  
失败类型：实现问题  
阻塞：渲染接口契约冲突导致渲染必失败；章节正文生成与存储缺失；运行依赖未满足将导致服务无法启动

## 建议

- 先对齐渲染接口契约：前端必须提供 SceneRenderPayload 必填字段，且在 UI 上给出字段来源与校验提示
- 增加“章节渲染与存储”能力，明确 10 章 × 2000 字的生成入口与字段约束，避免仅停留在大纲/场景层
- 统一 SmartRenderer 与 LLM 接口，避免 generate_prose 缺失导致运行时异常
- 明确长文本分段策略与 token 预算，避免一次性请求导致超限或 JSON 解析失败
- 增加覆盖“10 章 × 2000 字”的端到端测试（可用 LLM mock），并验证渲染参数契约

【MCP调用简报】
服务: serena  
触发: 项目上下文与结构确认  
参数: activate_project=/home/zxh/ainovel_v3, list_dir(根/前端/测试)  
结果: 获取目录结构与测试分布  
状态: 成功

【MCP调用简报】
服务: serena  
触发: 需求与核心实现审阅  
参数: read_file(doc/frontend_implementation_spec.md, requirements/系统架构与技术规格.md, 多个实现文件)  
结果: 获取接口契约、后端/前端实现细节  
状态: 成功

【MCP调用简报】
服务: serena  
触发: 风险证据定位  
参数: search_for_pattern(LLM/渲染/章节), execute_shell_command(nl -ba 定位行号)  
结果: 命中渲染契约冲突与 SmartRenderer 接口依赖  
状态: 成功