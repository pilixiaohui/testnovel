已阅读审阅行为规范
iteration: 3
review_mode: single

## 任务理解
对照规格文档：
- `doc/frontend_implementation_spec.md`
- `doc/系统架构与技术规格.md`

对现有前端 E2E 测试进行全面性与合理性评估（范围：`project/frontend/tests/e2e/`），产出：
- 覆盖度矩阵（≥20 功能点，包含文档行号与用例映射）
- 测试质量评估（选择器/断言/等待/E2E真实性）
- 分级问题清单（Critical/High/Medium/Low）
- 可执行的优先级改进建议

## 验收执行
- 命令: `npm run test:e2e` | 返回码: 0 | 结果: 7 passed（约 7.1s）

## 代码深度审查

### 实现代码
- 文件: `project/frontend/src/views/SnowflakeView.vue`
- 检查结果:

| 检查项 | 结果 | 说明 |
|---|---|---|
| 规格一致性 | 存在问题 | 规格要求“完成 Step 6 -> 跳转到编辑器”（`doc/frontend_implementation_spec.md:754`），实现仅执行 `await store.fetchStep6()`（`project/frontend/src/views/SnowflakeView.vue:149`），无跳转逻辑 |
| 可测性 | 合理 | Snowflake 关键控件均有 `data-test`，E2E 选择器可较稳定绑定 |

- 结论: 存在问题

- 文件: `project/frontend/src/views/EditorView.vue`
- 检查结果:

| 检查项 | 结果 | 说明 |
|---|---|---|
| 审核能力暴露 | 存在问题 | 已出现章节审核按钮（`data-test="chapter-approve"`，`project/frontend/src/views/EditorView.vue:90`），但 E2E 完全未覆盖审核行为与 review_status 变化 |
| 与文档关键字段一致性 | 部分满足 | 文档强调 `review_status`（`doc/系统架构与技术规格.md:1879`）与审核端点（`doc/frontend_implementation_spec.md:1108`），但当前测试不验收 |

- 结论: 存在问题

### 测试代码
- 文件: 存在
  - `project/frontend/tests/e2e/core.e2e.spec.ts`
  - `project/frontend/tests/e2e/snowflake.spec.ts`
  - `project/frontend/tests/e2e/simulation.spec.ts`
  - `project/frontend/tests/e2e/playwright.e2e.ts`
  - `project/frontend/playwright.config.ts`

- 覆盖情况（结论级）：

| 功能点 | 有测试 | 正确 |
|---|---:|---:|
| 路由可访问（除 Home） | 是 | 部分 |
| Snowflake 1-6 happy path | 是 | 部分 |
| Simulation Start/Step/Scene happy path | 是 | 部分 |
| Editor Load/Save/Diff/Render happy path | 是 | 部分 |
| World Load/CRUD/Relations（烟测） | 是 | 部分 |
| Settings 真正保存与反馈 | 否 | - |
| Anchor 可达性检查/动态补路相关验收 | 否 | - |
| Chapter/Scene 审核（review_status） | 否 | - |
| 分支/提交/LLM/反馈等模块验收 | 否 | - |

- 结论: 不符合需求（覆盖不足 + 质量问题）

## 覆盖度矩阵（≥20 功能点）
覆盖状态说明：
- ✅ 已覆盖：有 E2E 且对关键结果有断言
- ⚠️ 部分覆盖：有用例但断言弱/只烟测可见性/缺边界错误/严重依赖 mock
- ❌ 未覆盖：无对应 E2E

| 功能点 | 文档行号 | 测试用例 | 覆盖状态 | 备注 |
|---|---:|---|:---:|---|
| HomeView 路由 `/` 可访问 | doc/frontend_implementation_spec.md:925 | - | ❌ | 无首页导航/项目列表相关 E2E |
| SnowflakeView 路由 `/snowflake` 可访问 | doc/frontend_implementation_spec.md:926 | `SnowflakeFlow 基本流程`、`SnowflakeFlow 核心流程` | ✅ | 覆盖路由进入与核心 UI 元素可见 |
| SimulationView 路由 `/simulation/:sceneId?` 可访问 | doc/frontend_implementation_spec.md:927 | `SimulationConsole 基本流程`、`SimulationConsole 核心流程` | ✅ | 覆盖路由进入与核心 UI 元素可见 |
| EditorView 路由 `/editor/:sceneId?` 可访问 | doc/frontend_implementation_spec.md:928 | `SceneEditor 核心流程` | ✅ | 覆盖路由进入与核心 UI 元素可见 |
| WorldView 路由 `/world` 可访问 | doc/frontend_implementation_spec.md:929 | `WorldManager 核心流程` | ✅ | 覆盖路由进入与核心 UI 元素可见 |
| SettingsView 路由 `/settings` 可访问 | doc/frontend_implementation_spec.md:930 | `Settings 保存流程` | ⚠️ | 只验可见性，不点击保存/不验证保存结果（`project/frontend/tests/e2e/core.e2e.spec.ts:329`） |
| Snowflake Step1 输入面板：textarea + 生成按钮 + loglineOptions | doc/frontend_implementation_spec.md:758 | `SnowflakeFlow 基本流程`、`SnowflakeFlow 核心流程` | ⚠️ | 未按规格验证 textarea/radio-group；且使用结构选择器 `section.step-panel`（`project/frontend/tests/e2e/core.e2e.spec.ts:205`） |
| Snowflake Step1：输入想法 -> 生成 10 个 logline | doc/frontend_implementation_spec.md:752 | 同上 | ⚠️ | 未断言数量=10（只断言包含某条文本） |
| Snowflake Step2：选择 logline -> 生成故事结构 | doc/frontend_implementation_spec.md:753 | 同上 | ⚠️ | 仅烟测 Root ready 文案；未校验结构字段（theme/ending/three_disasters 等） |
| Snowflake Step3：生成角色小传（API） | doc/frontend_implementation_spec.md:980 | `SnowflakeFlow 核心流程` | ⚠️ | 只断言角色名可见；不验证卡片字段（doc/frontend_implementation_spec.md:762） |
| Snowflake Step4：生成场景骨架（API） | doc/frontend_implementation_spec.md:981 | `SnowflakeFlow 核心流程` | ⚠️ | 只断言场景标题可见 |
| Snowflake Step5a：生成幕结构（API） | doc/frontend_implementation_spec.md:982 | `SnowflakeFlow 核心流程` | ⚠️ | 仅等待 step5a request |
| Snowflake Step5b：生成章结构（API） | doc/frontend_implementation_spec.md:983 | `SnowflakeFlow 核心流程` | ⚠️ | 未显式等待 step5b；仅通过文案间接覆盖 |
| Snowflake Step6：生成锚点（API） | doc/frontend_implementation_spec.md:990 | `SnowflakeFlow 核心流程` | ⚠️ | 只验 anchors 数量文案；不验锚点字段/顺序/约束 |
| Snowflake Step6 完成后跳转编辑器 | doc/frontend_implementation_spec.md:754 | - | ❌ | 实现缺失（`project/frontend/src/views/SnowflakeView.vue:149`） |
| Simulation 主页面三栏布局/组件：AgentStatePanel + ActionTimeline + ArbitrationResult + ConvergenceIndicator | doc/frontend_implementation_spec.md:770 | `SimulationConsole 基本流程`、`SimulationConsole 核心流程` | ⚠️ | 仅覆盖部分组件可见；未覆盖 ArbitrationResult/ConvergenceIndicator 关键数据展示 |
| AgentStatePanel：beliefs/desires/intentions 展示 | doc/frontend_implementation_spec.md:774 | `SimulationConsole 基本流程` | ⚠️ | 只断言 panel 可见 |
| ActionTimeline：info_gain/agent_actions/conflicts_resolved 展示 | doc/frontend_implementation_spec.md:778 | `SimulationConsole 基本流程` | ⚠️ | 只断言容器/文案 |
| ConvergenceIndicator：(1-distance)*100 + 停滞告警/建议 | doc/frontend_implementation_spec.md:782 | - | ❌ | 未覆盖 distance/告警/建议 |
| Simulation：获取日志（API） | doc/frontend_implementation_spec.md:1019 | `SimulationConsole 核心流程` | ⚠️ | 只断言条数，缺字段/结构断言 |
| Simulation：单回合推演（API） | doc/frontend_implementation_spec.md:1017 | `SimulationConsole 核心流程` | ⚠️ | 断言仅“Converged”可见；不验回合数据 |
| Simulation：场景推演（API） | doc/frontend_implementation_spec.md:1018 | `SimulationConsole 核心流程` | ⚠️ | 仅验证日志条数变化 |
| DM：裁决（API） | doc/frontend_implementation_spec.md:1008；doc/系统架构与技术规格.md:19 | - | ❌ | 规格核心能力未验收 |
| DM：收敛检查（API） | doc/frontend_implementation_spec.md:1009；doc/系统架构与技术规格.md:669 | - | ❌ | 未验收收敛检查流程 |
| Editor：三栏布局 + 场景树 + Tabs（大纲/正文/推演日志）+ SceneContextPanel | doc/frontend_implementation_spec.md:790 | - | ❌ | 未覆盖该规格页面结构与交互 |
| Scene：获取场景上下文（API） | doc/frontend_implementation_spec.md:1046 | `SceneEditor 核心流程` | ⚠️ | 覆盖 happy path；无异常 |
| Scene：完成场景（API） | doc/frontend_implementation_spec.md:1043 | `SceneEditor 核心流程` | ⚠️ | 覆盖保存 request；不校验 payload |
| Scene：版本 diff（API） | doc/frontend_implementation_spec.md:1047 | `SceneEditor 核心流程` | ⚠️ | 覆盖 diff 文本；不验 commit 参数 |
| Scene：渲染场景（API，quality_scores） | doc/frontend_implementation_spec.md:1045 | `SceneEditor 核心流程` | ⚠️ | 只断言 content；不验 quality_scores |
| Scene：标记为脏（API） | doc/frontend_implementation_spec.md:1048 | - | ❌ | 未覆盖 |
| 审核：reviewChapter 端点（API） | doc/frontend_implementation_spec.md:1108 | - | ❌ | 未覆盖 approve/reject |
| 内容审核：review_status 字段（pending/approved/rejected） | doc/系统架构与技术规格.md:1879 | - | ❌ | 未覆盖 review_status 变化与 UI 展示 |
| World：四 Tab（实体/关系图谱/锚点/支线）与实体三栏 | doc/frontend_implementation_spec.md:798 | - | ❌ | 当前 E2E 覆盖的是简化版（无 tabs） |
| World：锚点时间线组件 AnchorTimeline | doc/frontend_implementation_spec.md:802 | - | ❌ | 未覆盖锚点进度/时间线 |
| World：列出实体（API） | doc/frontend_implementation_spec.md:1063 | `WorldManager 核心流程` | ⚠️ | 只断言文字出现；不验筛选/空态 |
| World：创建实体（API） | doc/frontend_implementation_spec.md:1062 | `WorldManager 核心流程` | ⚠️ | 只等待 request；不验证 UI 列表更新 |
| World：创建/更新关系（API） | doc/frontend_implementation_spec.md:1064 | - | ❌ | 未覆盖 |
| Anchor：更新锚点（API） | doc/frontend_implementation_spec.md:992 | - | ❌ | 未覆盖 |
| Anchor：检查可达性（API） | doc/frontend_implementation_spec.md:993；doc/系统架构与技术规格.md:27 | - | ❌ | 规格关键点（锚点不可达/动态补路），E2E 缺失 |
| World：列出支线（API） | doc/frontend_implementation_spec.md:1071 | `WorldManager 核心流程` | ⚠️ | 仅烟测列表文本 |
| World：创建支线（API） | doc/frontend_implementation_spec.md:1070 | - | ❌ | 未覆盖 |
| World：解决支线（API） | doc/frontend_implementation_spec.md:1072 | - | ❌ | 未覆盖 |
| 查询：RootSnapshot（关系图谱数据来源）（API） | doc/frontend_implementation_spec.md:1078 | `WorldManager 核心流程` | ⚠️ | 断言弱（仅包含 `"source"` 字符串） |
| 分支：创建分支（API） | doc/frontend_implementation_spec.md:1027 | - | ❌ | 未覆盖 |
| 分支：切换分支（API） | doc/frontend_implementation_spec.md:1029 | - | ❌ | 未覆盖 |
| 提交：commitScene（API） | doc/frontend_implementation_spec.md:1085 | - | ❌ | 未覆盖 |
| LLM：logicCheck（API） | doc/frontend_implementation_spec.md:1093 | - | ❌ | 未覆盖 |
| 递归反馈：feedbackLoop（API） | doc/frontend_implementation_spec.md:1101 | - | ❌ | 未覆盖 |

## 质量评估
### 选择器稳定性
- 优点：大量 `data-test` 选择器。
- 问题：仍存在结构选择器耦合，例如 `section.step-panel`（`project/frontend/tests/e2e/core.e2e.spec.ts:205`、`project/frontend/tests/e2e/snowflake.spec.ts:90`）。

### 断言完整性
- 主要问题：多数断言停留在“可见/请求发生/文本包含”，缺对业务结果的强断言。
  - Step1 不断言 logline 数量=10（`doc/frontend_implementation_spec.md:752`）。
  - Settings 用例不点击保存、不验证保存反馈（`project/frontend/tests/e2e/core.e2e.spec.ts:329`；对应 UI 有 `settings-save-status`，`project/frontend/src/views/SettingsView.vue:6`）。

### 等待策略
- 多用 `waitForRequest`（请求发出即可），对“响应成功 + UI 更新完成”覆盖不足，存在潜在 flake 风险。

### E2E 真实性
- 大量 `page.route` mock（例如 `project/frontend/tests/e2e/core.e2e.spec.ts:96` 起），更像前端契约/烟测，难发现真实后端契约问题。

## 问题清单（按严重程度）
### Critical
1. 端口/超时硬编码且与配置不一致：
   - baseURL/端口硬编码 5177（`project/frontend/tests/e2e/core.e2e.spec.ts:7`；`project/frontend/tests/e2e/snowflake.spec.ts:7`；`project/frontend/tests/e2e/simulation.spec.ts:7`）
   - dev server 启动硬编码 `--port 5177`（`project/frontend/tests/e2e/core.e2e.spec.ts:42` 等）
   - waitForServer 默认 15000ms（`project/frontend/tests/e2e/core.e2e.spec.ts:14` 等）
   - Playwright config 另用 baseURL 5173（`project/frontend/playwright.config.ts:9`）

2. 规格关键链路缺失：
   - Step6 完成应跳转编辑器（`doc/frontend_implementation_spec.md:754`），实现缺失（`project/frontend/src/views/SnowflakeView.vue:149`），测试也缺失。
   - HomeView 导航入口未覆盖（`doc/frontend_implementation_spec.md:925`）。

### High
1. E2E 真实性偏弱：大量 `page.route` mock（`project/frontend/tests/e2e/core.e2e.spec.ts:96` 起），难以发现联调/契约问题。
2. 审核/锚点可达性/支线等核心能力未被验收：
   - `anchorApi.checkAnchor`（`doc/frontend_implementation_spec.md:993`）
   - `reviewApi.reviewChapter`（`doc/frontend_implementation_spec.md:1108`；`review_status` 语义：`doc/系统架构与技术规格.md:1879`）
   - `subplotApi.resolveSubplot`（`doc/frontend_implementation_spec.md:1072`）

### Medium
1. DRY 违反：多个 spec 文件重复 devServer 启停与 waitForServer/jsonResponse（维护成本高）。
2. Playwright 配置与实际运行方式割裂：配置 baseURL/timeout，但测试内部自启服务并覆盖 baseURL，导致 config 形同虚设（`project/frontend/playwright.config.ts:6`）。

### Low
1. 计划文件放在测试目录且包含 `throw`：`project/frontend/tests/e2e/playwright.e2e.ts:42`（未来若命中 testMatch 会直接炸套件）。
2. 缺少异常/边界用例（空输入、4xx/5xx、超时等）。

## 结论
结论：FAIL
失败类型：测试问题
阻塞：覆盖度不足 + 配置硬编码/不一致 + 断言/真实性不足（详见“覆盖度矩阵/问题清单”）

## 建议
### P0（先止血：让测试配置一致且可复现）
1. 统一端口/超时来源：移除 E2E 中 5177/15000 等硬编码，使用可配置的环境变量/Playwright config，并对齐执行环境注入值（端口/等待/timeout）。
2. 统一 dev server 生命周期：用 Playwright `webServer` 启动一次前端服务，避免每个 spec 文件都启动/关闭一次。

### P1（补齐覆盖：按规格把关键链路测到）
1. 补 HomeView 导航与“从 Home 进入雪花流程/编辑器/世界观/推演”的主入口链路（`doc/frontend_implementation_spec.md:925`）。
2. 补 Snowflake Step6 -> Editor 的跳转与验收（`doc/frontend_implementation_spec.md:754`；实现需补齐后再测）。
3. 补 Editor 审核（approve/reject）与 review_status 变化的 E2E（`doc/frontend_implementation_spec.md:1108`；`doc/系统架构与技术规格.md:1879`）。
4. 补 World 锚点可达性检查、支线创建/解决等（`doc/frontend_implementation_spec.md:993`、`doc/frontend_implementation_spec.md:1070`、`doc/frontend_implementation_spec.md:1071`、`doc/frontend_implementation_spec.md:1072`）。

### P2（提高质量：让用例能抓住回归）
1. 强化断言：
   - Snowflake Step1 校验 logline 数量=10（`doc/frontend_implementation_spec.md:752`）
   - 校验关键请求 payload（idea/logline/root_id/branch_id 等）
   - World/Simulation 校验关键字段展示（info_gain、convergence distance、relations 数据结构等）
2. 整理测试目录：将 `project/frontend/tests/e2e/playwright.e2e.ts` 移出 `tests/e2e/` 或改名，避免未来误匹配。

【工具调用简报】
服务: serena
触发: 读取文档/代码、抽取行号证据、生成并写入报告文件
参数: read_file/search_for_pattern/create_text_file（relative_path 限定在 doc/ 与 project/frontend/）
结果: 输出覆盖度矩阵≥20、问题分级、改进建议，并写入 `doc/e2e_test_evaluation_report.md`
状态: 成功

服务: bash(shell_command)
触发: 执行验收命令获取可复现证据
参数: workdir=/home/zxh/ainovel_v3/project/frontend；cmd=`npm run test:e2e`
结果: Exit 0；7 passed（约 7.1s）
状态: 成功


## 补充分析：配置与运行时功能

本节聚焦用户在实际使用中关心的功能：
1) 错误处理与重试；2) 提示词配置；3) 模型配置（base URL/模型选择）；4) 超时时间配置；5) 创作过程保存（自动/手动/反馈）。

### 覆盖度矩阵（新增功能点 ≥10）
覆盖状态说明沿用主报告：✅/⚠️/❌ 代表 E2E 覆盖情况。

| 功能点 | 文档/代码行号 | 测试用例 | 覆盖状态 | 备注 |
|---|---|---|:---:|---|
| API 失败时错误提示（toast） | `project/frontend/src/api/index.ts:17` | - | ❌ | 实现存在（Axios 拦截器显示 detail），但 E2E 未覆盖 |
| API 失败后的“用户重试”机制（按钮/重试策略） | `project/frontend/src/api/index.ts:19` | - | ❌ | 未见重试策略/重试 UI；仅有 Promise reject |
| WorldView 加载失败的错误展示与可重试入口 | `project/frontend/src/views/WorldView.vue:105` | - | ❌ | 多处 `catch (error) { return }` 静默失败，用户不可见/不可重试 |
| SimulationView 加载失败的错误展示与可重试入口 | `project/frontend/src/views/SimulationView.vue:121` | - | ❌ | 失败仅 setStatus('idle')，无错误展示/重试引导 |
| Settings 页面是否承载配置能力（提示词/模型/超时等） | `project/frontend/src/views/SettingsView.vue:4` | `Settings 保存流程` | ⚠️ | 页面明确写“ No settings available.”，E2E 仅验证可见性 |
| Settings 保存动作与保存反馈 | `project/frontend/src/views/SettingsView.vue:5`、`project/frontend/src/views/SettingsView.vue:6` | `Settings 保存流程` | ⚠️ | 现有 E2E 不点击保存，不验证 `settings-save-status` |
| 前端 API baseURL 配置（VITE_API_BASE_URL） | `doc/frontend_implementation_spec.md:878`、`doc/frontend_implementation_spec.md:881`、`project/frontend/src/api/index.ts:4` | - | ❌ | 仅环境变量驱动，无 UI；E2E 未覆盖 |
| Vite 启动时对 API baseURL 的强约束（缺失即失败） | `project/frontend/vite.config.ts:14` | - | ❌ | 属于启动期约束，E2E 未覆盖该失败路径 |
| LLM API Base URL 配置（TOPONE_BASE_URL） | `doc/系统架构与技术规格.md:73`、`project/frontend/src/views/SettingsView.vue:4` | - | ❌ | 规格给出后端配置项，前端无对应配置入口 |
| LLM 默认模型/快速模型选择（TOPONE_DEFAULT_MODEL/SECONDARY_MODEL） | `doc/系统架构与技术规格.md:74`、`doc/系统架构与技术规格.md:75`、`project/frontend/src/views/SettingsView.vue:4` | - | ❌ | 前端无模型选择 UI；E2E 未覆盖 |
| LLM 超时配置（TOPONE_TIMEOUT_SECONDS） | `doc/系统架构与技术规格.md:76`、`project/frontend/src/views/SettingsView.vue:4` | - | ❌ | 前端无配置入口；E2E 未覆盖 |
| 前端请求超时（Axios timeout）可配置性 | `project/frontend/src/api/index.ts:8` | - | ❌ | timeout 固定 30000ms；无设置页/无 E2E |
| 提示词体系存在（Prompt 设计/模板） | `doc/系统架构与技术规格.md:1601`、`doc/系统架构与技术规格.md:1641`、`doc/系统架构与技术规格.md:1686`、`doc/系统架构与技术规格.md:1719` | - | ❌ | 规格中有 Prompt 设计，但前端无“查看/编辑/保存”能力与 E2E |
| 创作过程：手动保存场景（Save 按钮 + saveScene） | `project/frontend/src/views/EditorView.vue:10`、`project/frontend/src/views/EditorView.vue:288` | `SceneEditor 核心流程` | ⚠️ | 仅 happy path 且依赖 mock；断言不够强（不验成功反馈/不验真实后端） |
| 创作过程：保存失败的错误展示（scene-error） | `project/frontend/src/views/EditorView.vue:17`、`project/frontend/src/views/EditorView.vue:297` | - | ❌ | 有错误 UI，但 E2E 未覆盖失败场景 |
| 创作过程：保存状态反馈（last_saved_at/提示） | `project/frontend/src/stores/editor.ts:10`、`project/frontend/src/stores/editor.ts:56` | - | ❌ | store 有 last_saved_at，但 UI 未展示且 E2E 未验收 |
| 创作过程：自动保存（定时/防抖/离开提示） | `project/frontend/src/views/EditorView.vue:288` | - | ❌ | 仅见手动保存实现；未见自动保存/离开保护相关验收 |

### 补充问题清单（按严重程度）

#### Critical
- 配置能力缺失：Settings 页无任何实际配置项（`project/frontend/src/views/SettingsView.vue:4`），无法覆盖用户要求的“提示词/模型/baseURL/超时”等真实使用场景。
- 错误处理不一致且存在静默失败：WorldView 多处直接 `return`（`project/frontend/src/views/WorldView.vue:105` 等），SimulationView 失败只切状态（`project/frontend/src/views/SimulationView.vue:121`），用户不可见也无重试指引。

#### High
- 超时与 baseURL 全部为硬编码/构建期环境变量：Axios timeout 固定 30000ms（`project/frontend/src/api/index.ts:8`），且无 UI/无 E2E；LLM 超时/模型/baseURL 仅存在于后端规格（`doc/系统架构与技术规格.md:73`、`doc/系统架构与技术规格.md:74`、`doc/系统架构与技术规格.md:75`、`doc/系统架构与技术规格.md:76`），前端未覆盖。
- E2E 缺失失败路径：无任何用例覆盖 API 4xx/5xx/超时、错误提示展示、用户重试成功等核心链路（尽管 `api/index.ts` 已有 toast 能力：`project/frontend/src/api/index.ts:17`）。

#### Medium
- “保存体验”验收不足：Editor 仅用 dirty 标识间接反馈，last_saved_at 未展示且无 E2E（`project/frontend/src/stores/editor.ts:10`、`project/frontend/src/stores/editor.ts:56`）。

#### Low
- Settings 用例过弱：仅验证按钮存在（`project/frontend/tests/e2e/core.e2e.spec.ts:329`），未点击、不验证 `settings-save-status`（`project/frontend/src/views/SettingsView.vue:6`）。

### 补充改进建议
- P0（可见性与可用性）：
  - 统一错误处理：禁止静默 `catch { return }`，至少需要可见错误提示 + 明确重试入口（按钮/再次执行），并补 E2E 覆盖失败->提示->重试成功。
  - 为创作保存提供明确反馈：展示“已保存时间/保存成功提示/保存失败原因”，并补失败场景 E2E（触发 500/超时）。

- P1（配置能力）：
  - 在 Settings 增加最小闭环的配置项与持久化（提示词/模型/baseURL/超时）：能编辑、保存、重启/刷新后仍生效；并补 E2E：编辑->保存->生效验证。

- P2（测试设计）：
  - 将现有大量 mock 用例明确定位为“前端契约烟测”，新增少量“真 E2E（连后端或最小 stub 服务）”覆盖：错误重试、保存、关键配置生效。


## 补充分析：创作流程与数据管理

本节根据用户 Iteration 6/7 的补充要求，聚焦：
1) **图信息提取到世界观**（正文/雪花流程均需支持手动提取与提交）；
2) **正文生成步骤**（章节/正文渲染）；
并主动补充：3) **创作链路完整性**（雪花→正文→审核→发布/产出）；4) **版本与分支管理**；5) **数据快照/备份能力**。

### 覆盖度矩阵（新增功能点 ≥15）
覆盖状态说明沿用主报告：✅/⚠️/❌ 代表 E2E 覆盖情况。

| 功能点 | 文档/代码行号 | 测试用例 | 覆盖状态 | 备注 |
|---|---|---|:---:|---|
| Snowflake Step6 完成后跳转 Editor（创作链路闭环入口） | `doc/frontend_implementation_spec.md:754`、`project/frontend/src/views/SnowflakeView.vue:148` | `SnowflakeFlow 核心流程` | ❌ | 现测仅验证 Anchors 数量（`project/frontend/tests/e2e/core.e2e.spec.ts:195`），不验证路由跳转；实现也无跳转 |
| Snowflake 生成 root_id/branch_id 后写入“当前项目”状态（Home 可见/可继续创作） | `doc/frontend_implementation_spec.md:603`、`project/frontend/src/stores/snowflake.ts:129`、`project/frontend/src/stores/project.ts:1` | - | ❌ | 文档期望 ProjectStore 管理 currentRootId/currentBranchId；实现仅有 project_id/project_name，且 Snowflake 不写入 |
| Editor/Simulation 路由参数 `:sceneId?` 驱动加载真实场景 | `doc/frontend_implementation_spec.md:742`、`doc/frontend_implementation_spec.md:928`、`project/frontend/src/views/EditorView.vue:189`、`project/frontend/src/views/SimulationView.vue:80` | `SceneEditor 核心流程`、`SimulationConsole 核心流程` | ⚠️ | 测试访问 `/editor/scene-1`/`/simulation/scene-1`，但实现内部 sceneId 固定 `scene-1`，未真正消费路由参数 |
| 章节正文生成（renderChapter）能力：调用 `/chapters/{id}/render` 并展示 content + quality_scores | `doc/frontend_implementation_spec.md:457`、`doc/系统架构与技术规格.md:726`、`doc/frontend_implementation_spec.md:984` | - | ❌ | 前端未实现 renderChapter API/按钮/展示；未找到 `renderChapter` 调用 |
| Snowflake Step5 生成 chapters 后：可选择章节并进入“正文生成/编辑”步骤 | `doc/frontend_implementation_spec.md:983`、`doc/frontend_implementation_spec.md:928`、`project/frontend/src/views/SnowflakeView.vue:136`、`project/frontend/src/views/EditorView.vue:63` | - | ❌ | Snowflake 仅展示计数；Editor 仅有 Chapter Review 列表，不提供章节正文渲染入口 |
| Chapter 审核流程（Approve/Reject）E2E：点击后状态更新（review_status） | `doc/frontend_implementation_spec.md:592`、`doc/系统架构与技术规格.md:728`、`project/frontend/src/views/EditorView.vue:90`、`project/frontend/src/api/chapter.ts:9` | - | ❌ | UI 已有按钮与状态标签，但 E2E 未覆盖；且实现使用 POST，与文档 PUT 存在契约偏差风险 |
| Scene 审核流程（reviewScene）UI/调用链路 | `doc/frontend_implementation_spec.md:518`、`doc/系统架构与技术规格.md:727` | - | ❌ | 前端未实现 scene review API 与对应 UI（全局未找到 `reviewScene` 调用） |
| 图信息提取：手动触发 stateExtract（从当前正文/渲染结果提取 entity_changes/relation_changes） | `doc/frontend_implementation_spec.md:574`、`doc/系统架构与技术规格.md:766`、`project/frontend/src/api/llm.ts:8` | - | ❌ | 前端仅有 API 封装，未接入任何 View；E2E 无覆盖 |
| 图信息提交：手动触发 stateCommit（将提取结果应用到世界观） | `doc/frontend_implementation_spec.md:575`、`doc/系统架构与技术规格.md:767`、`project/frontend/src/api/llm.ts:10` | - | ❌ | 缺少“预览差异→确认提交→世界观刷新”的端到端闭环 |
| 雪花流程中随时“提取/提交图信息到世界观”（不只正文） | `doc/frontend_implementation_spec.md:574`、`doc/frontend_implementation_spec.md:926`、`project/frontend/src/views/SnowflakeView.vue:1` | - | ❌ | SnowflakeView 无提取入口；E2E 无覆盖 |
| WorldView 承载“应用提取变更/刷新图谱”的入口（与 stateCommit 组合） | `doc/frontend_implementation_spec.md:575`、`doc/frontend_implementation_spec.md:929`、`project/frontend/src/views/WorldView.vue:10` | - | ❌ | WorldView 当前仅 CRUD/Relations 烟测按钮，无“提取结果应用/回滚”入口 |
| 场景版本对比 Diff（from/to commit 可配置，而非硬编码） | `doc/系统架构与技术规格.md:717`、`project/frontend/src/views/EditorView.vue:191`、`project/frontend/src/views/EditorView.vue:301` | `SceneEditor 核心流程` | ⚠️ | E2E 仅断言 diff 输出包含 `+new`（`project/frontend/tests/e2e/core.e2e.spec.ts:258`），未验证 commit 选择/真实版本链路；实现 commitId 常量硬编码 |
| 场景版本提交 Commit（commitScene）UI：提交 message/scene_ids，生成 commit_id | `doc/frontend_implementation_spec.md:563`、`doc/系统架构与技术规格.md:757`、`project/frontend/src/api/commit.ts:3` | - | ❌ | 仅有 API 封装，无 UI/无 E2E；现有 Editor “Save”走 completeScene，不产生提交 |
| Dirty scenes 列表（列出脏场景）与后端 dirty 标记闭环 | `doc/frontend_implementation_spec.md:517`、`project/frontend/src/api/scene.ts:62`、`project/frontend/src/views/EditorView.vue:16` | - | ❌ | E2E 只验证前端 `Dirty` 标识；未覆盖 `/dirty` 与 `/dirty_scenes` 真实链路 |
| 分支管理 UI：创建/切换/合并/回滚（Branch） | `doc/系统架构与技术规格.md:692`、`doc/frontend_implementation_spec.md:546`、`project/frontend/src/api/branch.ts:3` | - | ❌ | 有 API 封装但无路由/页面/组件；E2E 无覆盖 |
| Fork 分支：从提交/场景 fork（fork_from_commit / fork_from_scene） | `doc/系统架构与技术规格.md:697`、`doc/系统架构与技术规格.md:698`、`project/frontend/src/api/branch.ts:23` | - | ❌ | 无 UI/无 E2E |
| 分支历史/根快照（用于备份/导出/恢复的基础能力） | `doc/frontend_implementation_spec.md:555`、`doc/系统架构与技术规格.md:700`、`doc/系统架构与技术规格.md:750`、`project/frontend/src/api/branch.ts:37` | - | ❌ | 文档定义 history/snapshot，但前端无入口/无 E2E |
| 提交 GC（孤立提交回收） | `doc/frontend_implementation_spec.md:564`、`doc/系统架构与技术规格.md:758`、`project/frontend/src/api/commit.ts:6` | - | ❌ | 无 UI/无 E2E |

### 补充问题清单（按严重程度）

#### Critical
- **“图信息提取→提交→世界观更新”闭环缺失**：仅有 `llmApi.stateExtract/stateCommit` API 声明（`project/frontend/src/api/llm.ts:8`、`project/frontend/src/api/llm.ts:10`），无任何前端入口与 E2E，无法满足“创作中手动提取当前图信息到世界观”的真实使用需求。
- **章节正文生成步骤缺失**：文档提供 `POST /api/v1/chapters/{chapter_id}/render`（`doc/系统架构与技术规格.md:726`、`doc/frontend_implementation_spec.md:457`），但前端无实现/无 E2E；导致“正文生成”只能停留在 Scene render 的局部能力。

#### High
- **创作链路割裂**：文档期望 Step6 后跳转 Editor（`doc/frontend_implementation_spec.md:754`），但实现无跳转（`project/frontend/src/views/SnowflakeView.vue:148`），E2E 也未验证跳转。
- **版本/分支能力无 UI 验收**：Branch/Commit/History/Snapshot 在文档中属于核心能力（`doc/系统架构与技术规格.md:692`、`doc/系统架构与技术规格.md:700`、`doc/系统架构与技术规格.md:750`、`doc/系统架构与技术规格.md:757`），前端仅停留在 API 封装，缺少端到端覆盖。

#### Medium
- **路由参数未真正驱动数据加载**：Editor/Simulation 固定 `scene-1`（`project/frontend/src/views/EditorView.vue:189`、`project/frontend/src/views/SimulationView.vue:80`），导致“通过 URL 打开指定场景”的可用性与可测性存在风险。
- **审核流程验收不足**：Editor 已提供章节审核按钮（`project/frontend/src/views/EditorView.vue:90`），但 E2E 未覆盖 review_status 的变化与异常分支。

#### Low
- **E2E 更偏“接口契约烟测”而非“创作闭环验收”**：对版本/分支/状态提取等关键链路缺少真实状态验证，仅验证请求发生或页面可见。

### 补充改进建议（P0/P1/P2）
- P0（补闭环，确保真实可用）：
  - 在 Editor + Snowflake 提供“提取图信息”入口：调用 `stateExtract` 后展示变更 diff（entity_changes/relation_changes），用户确认后调用 `stateCommit`，并在 WorldView 刷新展示。
  - 章节正文生成最小闭环：为 Chapter 增加 render 按钮与输出区，接入 `/chapters/{id}/render`，并补 E2E：渲染成功 + quality_scores 验证。

- P1（补创作链路与验收）：
  - Snowflake Step6 完成后跳转 Editor，并将 root_id/branch_id 写入全局项目状态（Home 可见、World/Editor/Simulation 共享）。
  - 将路由参数与真实数据加载打通（Editor/Simulation 消费 `:sceneId`），补 E2E：访问不同 sceneId 的差异行为。

- P2（补版本/分支/数据管理能力）：
  - 增加最小分支/提交/快照 UI：创建/切换/merge/revert/reset、commit message、history/snapshot 展示；补 E2E 覆盖关键链路。
  - 将现有 Diff 从“硬编码 commitId”升级为“可选择真实 commit 对比”，并补失败路径与权限/冲突提示。
