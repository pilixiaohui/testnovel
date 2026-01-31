已阅读审阅行为规范  
iteration: 24  

结论：FAIL  
阻塞：前端/后端测试均未通过（前端 `npm run test:unit` 多处失败；后端 `pytest` 14 处失败）；且默认 `npm run test:e2e` 未执行真实接口用例（真实接口用例被 skip），无法证明“真实接口超时”问题已被端到端测试覆盖与防回归。  

## 需求分析（从用户 Task Goal 提取）
- P0：定位“前端在真实接口 E2E 中显示超时”的根本原因，并给出可信证据链/复现路径  
- P0：将前端请求超时时间设置为**最大 10 分钟**，并与**后端实际请求超时**保持一致  
- P0：解释为何现有端到端测试没发现该问题（是否使用 mock），并补充**真实场景**测试以覆盖该问题  
- P1：避免多处魔法数字/漂移；测试应能在失败时快速定位问题（避免长时间挂起）  

## 根因分析（基于现状证据）
- 现有 E2E（Playwright）大量通过 `page.route(...).fulfill(...)` **mock 掉后端接口**，因此无法暴露真实接口“慢响应/超时”类问题：例如 `project/frontend/tests/e2e/core.e2e.spec.ts:41` 起对 `**/api/v1/snowflake/step1..step5b` 等进行 route mock。  
- “真实接口模式”虽已新增用例，但默认运行 `npm run test:e2e` 时该用例被跳过（见后文证据），因此仍可能“看起来 E2E 绿了，但真实接口问题没被覆盖”。  
- 超时配置方面：前端 axios 已设置 `600000ms`（10 分钟），后端 `.env`/配置默认 `600s`，数值对齐；但缺少“单一来源”或对齐校验，存在未来漂移风险。  

## 代码审查结果
### 核心代码文件清单
- 前端请求客户端：`project/frontend/src/api/index.ts`  
- 前端 E2E 配置：`project/frontend/playwright.config.ts`  
- 真实接口 E2E：`project/frontend/tests/e2e/real-api.spec.ts`  
- 后端实际超时配置：`project/backend/.env`、`project/backend/app/config.py`、`project/backend/app/services/topone_client.py`  

### 实现质量评估（与本需求相关）
- 超时上限 10 分钟：已在前端 axios 显式设置 `timeout: 600000`，符合“最大 10 分钟”。证据：`project/frontend/src/api/index.ts:8`。  
- 与后端实际超时统一：后端 `.env` 将 `TOPONE_TIMEOUT_SECONDS=600`（秒），前端为 `600000`（毫秒），数值一致。证据：`project/backend/.env:6` + `project/frontend/src/api/index.ts:8`。  
- DRY/一致性风险（P1）：`600000` 作为魔法数字在多处出现（axios、playwright config、e2e 测试），且未与后端值做联动校验，存在“改一处忘一处”的风险。证据：  
  - `project/frontend/src/api/index.ts:8`  
  - `project/frontend/playwright.config.ts:8`、`project/frontend/playwright.config.ts:18`  
  - `project/frontend/tests/e2e/real-api.spec.ts:9`  

## 测试审查结果（重点）
### E2E（Playwright）
- 测试文件清单：  
  - `project/frontend/tests/e2e/core.e2e.spec.ts`  
  - `project/frontend/tests/e2e/snowflake.spec.ts`  
  - `project/frontend/tests/e2e/simulation.spec.ts`  
  - `project/frontend/tests/e2e/chapter-render.spec.ts`  
  - `project/frontend/tests/e2e/state-extract.spec.ts`  
  - `project/frontend/tests/e2e/version-control.spec.ts`  
  - `project/frontend/tests/e2e/real-api.spec.ts`（新增真实接口模式）  

- 有效测试数量 vs 问题测试数量（以“能否覆盖真实接口超时问题”为口径）：  
  - 可跑的 E2E 用例：17  
  - 默认执行下：15 passed + **2 skipped（真实接口模式）** ⇒ 对“真实接口超时”问题的防回归覆盖为 **0（P0 缺口）**  
  - 大量 mock 用例：对 UI 冒烟/契约有价值，但对“真实接口超时”问题属于**场景不匹配**（P1 警告：过度 Mock）  

- 关键问题测试详情  
  1) `project/frontend/tests/e2e/core.e2e.spec.ts:41` 等：通过 `page.route(...).fulfill(...)` mock 真实 API，无法发现真实接口超时（问题类型：过度 Mock / 与真实场景脱节）。  
  2) `project/frontend/tests/e2e/real-api.spec.ts:5` 起：真实接口模式依赖 `E2E_API_MODE=real`，默认不设置则跳过（问题类型：真实场景测试默认不执行，P0 缺口）。  
  3) `project/frontend/tests/e2e/real-api.spec.ts:50-53`：通过读取源码字符串断言 `timeout: 600000`，属于“静态断言”，较脆弱（问题类型：脆弱测试，P1）。  

- 我实际运行验证  
  - 默认 E2E：`cd project/frontend && npm run test:e2e` → `15 passed, 2 skipped`（跳过的正是 `real-api.spec.ts` 两条）。  
  - 真实接口模式（我启动本地后端在 8001，避免与 8000 冲突，并设置 `E2E_API_MODE=real` + `VITE_API_PROXY_TARGET`）：`npx playwright test tests/e2e/real-api.spec.ts` → `2 passed`。  
  - 结论：真实接口用例“能跑”，但**默认不跑**，仍无法满足“应该对真实场景进行测试”的要求。  

### 前端单测（Vitest）
- 命令：`cd project/frontend && npm run test:unit` → **失败**（4 个文件失败，11 failed）。  
- 关键失败证据：  
  - `project/frontend/src/views/EditorView.vue:202` 单测环境中 `useRoute()` 依赖未注入导致崩溃（报错栈指向该行）。  
  - `project/frontend/src/stores/snowflake.ts:147` 使用 `anchorApi.generateAnchors`，但单测的 `vi.mock('@/api/anchor')` 未导出 `anchorApi` 导致失败（报错明确提示缺少 export）。  
- 这属于质量门槛阻塞（P0）：测试未通过无法证明变更可回归。  

### 后端测试（Pytest）
- 命令：`cd project/backend && ./.venv/bin/python -m pytest -q` → **失败**（`14 failed, 420 passed`）。  
- 失败多集中在 snowflake/scene 相关结构校验（示例：场景 `title/sequence_index` 缺失导致 Pydantic 校验失败），会影响真实接口链路稳定性；在“真实接口超时”议题下，这同样是交付阻塞（P0）。  

## 验收检查（逐条对照需求）
1) P0：超时最大 10 分钟  
- 结论：部分满足（配置已改）  
- 证据：`project/frontend/src/api/index.ts:8` 设置 `timeout: 600000`（ms）。  

2) P0：统一为后端实际请求超时  
- 结论：部分满足（数值对齐，但缺少强约束/联动）  
- 证据：`project/backend/.env:6` 为 `TOPONE_TIMEOUT_SECONDS=600`（s），`project/frontend/src/api/index.ts:8` 为 `600000`（ms）。  

3) P0：解释 E2E 为何没发现（是否 mock）并补真实场景测试  
- 结论：未满足（默认 E2E 仍不覆盖真实接口；真实用例默认 skipped）  
- 证据：  
  - 大量 mock：`project/frontend/tests/e2e/core.e2e.spec.ts:41-57` 等  
  - 默认执行跳过真实接口用例：`npm run test:e2e` 输出 `2 skipped`（对应 `project/frontend/tests/e2e/real-api.spec.ts:35`、`:50`）  
  - 真实接口用例需要显式 `E2E_API_MODE=real`：`project/frontend/tests/e2e/real-api.spec.ts:5`、`:31-32`  

## 差距清单
- 需求“真实场景必须被 E2E 覆盖” → 当前默认 E2E 跑的是 mock 套件 → 真实接口超时仍可能回归/漏检 → 影响：问题无法被 CI/回归测试及时发现（P0）。  
- 质量门槛（测试必须通过） → 前端单测失败 + 后端 pytest 失败 → 无法证明整体可用性（P0）。  
- 超时配置“统一” → 目前是多处硬编码 600000/600 → 缺少对齐校验与单一来源 → 影响：未来易漂移（P1）。  

## 落地建议（可执行）
1) P0：让真实接口 E2E 成为**必跑**（至少在 CI 的一个 job）  
- 方案：CI 中新增 `E2E_API_MODE=real` 的 job，并确保后端（含 Memgraph）可用；或将真实接口用例与 mock 用例分开命令（例如 `test:e2e:mock` / `test:e2e:real`），避免“默认全跳过”。  
- 同时将 `real-api.spec.ts` 的后端可用性检查改为命中真实存在的 endpoint（目前 `/api/v1/health` 并未在后端实现，容易误判）。  

2) P0：修复前端单测与后端 pytest 失败  
- 前端：补齐 router 注入/测试挂载方式；更新 `@/api/anchor` 的 mock 使其导出 `anchorApi`（对应 `project/frontend/src/stores/snowflake.ts:147`）。  
- 后端：修复 SceneNode 结构生成/序列化与 Pydantic 模型不一致导致的校验失败（多用例已爆）。  

3) P1：消除超时魔法数字与漂移风险  
- 前端将 `600000` 抽为常量并在 axios + playwright config + real api e2e 中复用；并在测试中读取后端 `.env`/配置（仅取 `TOPONE_TIMEOUT_SECONDS`）做一致性断言，防止两边超时配置分叉。  

## 证据
### 运行命令与关键输出摘要
- `cd project/frontend && npm run test:e2e`  
  - 结果：`15 passed, 2 skipped`（跳过：`tests/e2e/real-api.spec.ts` 两条真实接口用例）  
- `cd project/frontend && npm run test:unit`  
  - 结果：失败（`11 failed`）；关键栈：`project/frontend/src/views/EditorView.vue:202`、`project/frontend/src/stores/snowflake.ts:147`  
- `cd project/backend && ./.venv/bin/python -m pytest -q`  
  - 结果：失败（`14 failed, 420 passed`）  
- 真实接口模式验证（我本地起后端 8001）：  
  - `E2E_API_MODE=real VITE_API_PROXY_TARGET=http://127.0.0.1:8001 npx playwright test tests/e2e/real-api.spec.ts` → `2 passed`  

### 关键代码引用
```ts
// project/frontend/src/api/index.ts:8
timeout: 600000,
```

```env
# project/backend/.env:6
TOPONE_TIMEOUT_SECONDS=600
```

```ts
// project/frontend/tests/e2e/core.e2e.spec.ts:41
await page.route('**/api/v1/snowflake/step1', (route) => route.fulfill(...))
```

```ts
// project/frontend/tests/e2e/real-api.spec.ts:5,31-32
const isRealApiMode = process.env.E2E_API_MODE === 'real'
test.skip(!isRealApiMode, '需要真实后端，设置 E2E_API_MODE=real')
```

## 工具调用简报
【MCP调用简报】  
服务: serena  
触发: 定位超时配置、E2E 测试实现与 mock 证据  
参数: `search_for_pattern(timeout|mock|SNOWFLAKE_ENGINE)`, `read_file(...)`, `list_dir(...)`  
结果: 命中前端 axios/playwright/real-api 用例与后端 TOPONE_TIMEOUT_SECONDS 配置  
状态: 成功  

【工具调用简报】  
服务: bash(shell_command)  
触发: 运行 E2E/单测/后端 pytest，并获取带行号代码证据  
参数: `npm run test:e2e`, `npm run test:unit`, `pytest -q`, `nl -ba ...`  
结果: E2E 默认跳过真实接口用例；前端单测失败；后端 pytest 失败；行号证据已采集  
状态: 成功