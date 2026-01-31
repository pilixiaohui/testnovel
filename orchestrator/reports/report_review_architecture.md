已阅读审阅行为规范
iteration: 1
review_mode: single

## 任务理解

审阅的任务：评估技术架构可行性，确认现有代码能否支撑“10章每章2000字”的小说生成（检查后端核心服务、前端组件、雪花法六步骤 API、LLM 集成、Memgraph 存储）。
验收标准：后端雪花流程+锚点流程完整、LLM 接入可用、Memgraph 能存章节/场景、前后端数据契约一致并能产出 10 章/2000 字。

## 验收执行

- 验收命令: `未执行（工单未提供验收命令）`
- 返回码: N/A
- 测试结果: 未执行
- 覆盖率: N/A

## 代码深度审查

### 实现代码审查
- 审查文件: `project/backend/app/main.py:216`
- 审查内容:
  | 检查项 | 结果 | 说明 |
  |-------|------|------|
  | 函数参数/返回值类型 | 符合 | Step1-5b 与锚点 API 均有明确输入输出模型与字段校验 |
  | API 契约一致性 | 不符合 | Step4 SceneNode 与前端类型/展示字段不一致 |
  | 错误处理完整性 | 完整 | 缺字段/空列表直接 4xx 快速失败 |
  | 边界条件处理 | 部分 | anchors 有数量校验，但章节数量未约束为 10 |
- 代码片段证据:
```python
# project/backend/app/main.py:216
@app.post("/api/v1/snowflake/step2", response_model=SnowflakeRoot)
...
@app.post("/api/v1/snowflake/step4", response_model=Step4Result)
...
@app.post("/api/v1/snowflake/step5b")
...
@app.post("/api/v1/roots/{root_id}/anchors")
```
- 实现审查结论: 雪花步骤与锚点 API 已覆盖，但缺少“10章”约束，且 Step4 数据契约与前端不一致。

- 审查文件: `project/backend/app/storage/memgraph_storage.py:1104`
- 审查内容:
  | 检查项 | 结果 | 说明 |
  |-------|------|------|
  | 函数参数/返回值类型 | 符合 | Act/Chapter 创建与返回结构明确 |
  | API 契约一致性 | 符合 | 存储层具备章节与场景持久化 |
  | 错误处理完整性 | 完整 | Act/Chapter 不存在或重复序列直接失败 |
  | 边界条件处理 | 已考虑 | 序号冲突/Act 不存在等边界均处理 |
- 代码片段证据:
```python
# project/backend/app/storage/memgraph_storage.py:1104
def create_act(...):
...
def create_chapter(...):
...
```
- 实现审查结论: Memgraph 存储层具备 Act/Chapter/Scene 存储能力。

- 审查文件: `project/frontend/src/types/snowflake.ts:20`
- 审查内容:
  | 检查项 | 结果 | 说明 |
  |-------|------|------|
  | 函数参数/返回值类型 | 不符合 | 前端 SceneNode 期望 title/sequence_index |
  | API 契约一致性 | 不符合 | 后端 SceneNode 实际为 expected_outcome/conflict_type |
  | 错误处理完整性 | 不涉及 | 类型层未做运行时校验 |
  | 边界条件处理 | 未考虑 | Step4 UI 直接渲染 scene.title |
- 代码片段证据:
```ts
// project/frontend/src/types/snowflake.ts:20
export interface SceneNode {
  id: string
  title: string
  sequence_index: number
  parent_act_id: string
  chapter_id?: string
  is_skeleton: boolean
}
```
```vue
// project/frontend/src/views/SnowflakeView.vue:60
<li v-for="scene in store.scenes" :key="scene.id">{{ scene.title }}</li>
```
- 实现审查结论: 前端直接依赖 title 字段，但后端 Step4 不提供，导致雪花第 4 步展示/契约断裂。

### 测试代码审查
- 测试文件: 存在: `project/backend/tests/test_snowflake_workflow.py:1`, `project/frontend/src/__tests__/fe_api_types_store_alignment.test.ts:1`
- 测试覆盖情况:
  | 功能点 | 是否有测试 | 测试是否正确 |
  |-------|-----------|-------------|
  | Snowflake Step1-4 校验逻辑 | 是 | 是 |
  | Step5a/Step5b 章节数量=10 | 否 | 不适用 |
  | 章节渲染/2000字约束 | 否 | 不适用 |
  | 前后端 SceneNode 契约一致性 | 否 | 不适用 |
- 测试质量结论: 部分符合，核心需求（10章/字数/契约）未覆盖。

## 架构评估（可行性/清单/依赖）

- 可行性评估：需补充
- 已实现
  - Snowflake Step1-5b 与 Anchors API 完整（`project/backend/app/main.py:216`）
  - ToponeGateway 结构化输出入口与渲染调用（`project/backend/app/llm/topone_gateway.py:45`, `project/backend/app/main.py:1199`）
  - Memgraph 章节/场景存储（`project/backend/app/storage/memgraph_storage.py:1104`, `project/backend/app/storage/memgraph_storage.py:1649`）
  - 前端 Snowflake API 调用链（`project/frontend/src/api/snowflake.ts:15`）
- 待实现 / 关键缺口
  - SceneNode 前后端字段不一致（`project/frontend/src/types/snowflake.ts:20` vs `project/backend/app/models.py:41`）。
  - 章节数量与字数约束缺失：Step5b 与渲染提示未限定 10 章/2000 字（`project/backend/app/main.py:285`, `project/backend/app/llm/prompts/step5b.py:1`, `project/backend/app/llm/prompts/renderer.py:1`）。
  - 缺少章节正文生成与持久化链路（仅有 scene render，无 chapter-level content）。
- 关键依赖与集成点状态
  - Memgraph 依赖环境变量 MEMGRAPH_HOST/MEMGRAPH_PORT（`project/backend/app/config.py:66`）。
  - LLM 渲染依赖 SNOWFLAKE_ENGINE=gemini + TopOne API Key（`project/backend/app/main.py:1207`, `project/backend/app/config.py:28`）。

## 结论

结论：FAIL  
失败类型：实现问题  
阻塞：无

## 建议

- 对齐 SceneNode 契约：要么后端 Step4 返回 title/sequence_index（从 SceneOrigin 映射），要么前端改用 expected_outcome/conflict_type 并加适配层（涉及 `project/backend/app/models.py:41` 与 `project/frontend/src/types/snowflake.ts:20`）。
- 明确“10章/2000字”约束：在 Step5b 生成与渲染 prompt 中加入数量与字数硬性要求，并在后端做强校验（不满足即快速失败），对应 `project/backend/app/main.py:285` 与 `project/backend/app/llm/prompts/step5b.py:1`。
- 增加章节正文生成与持久化：新增章节渲染 API + Chapter 模型字段（rendered_content / review_status 等），并在 Memgraph 落盘（`project/backend/app/storage/memgraph_storage.py:1168`）。
- 补充测试：针对 Step5b 章数、章节字数、前后端契约一致性补测试，避免仅停留在 store/type 级校验（`project/backend/tests/test_snowflake_workflow.py:1`）。

【MCP调用简报】
服务: serena  
触发: 架构审查需定位后端/前端实现与契约  
参数: list_dir/read_file/search_for_pattern/execute_shell_command（max_answer_chars=-1）  
结果: 获取 Snowflake API、Memgraph 存储、前端类型与视图的关键实现与行号证据  
状态: 成功