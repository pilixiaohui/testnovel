# Dev Plan (Snapshot)

> 本文件由 MAIN 维护（可覆盖编辑）。它是当前计划与进度的快照；事实证据以 `orchestrator/reports/report_review.md` 与 `orchestrator/memory/project_history.md` 为准。

## 约束（强制）
- 任务总数必须保持在几十条以内（少而硬）
- 每个任务块必须包含：`acceptance / evidence`
- status 支持两种格式（向后兼容）：
  - 旧格式：任务块内至少 1 行 `status: <TODO|DOING|BLOCKED|DONE|VERIFIED>`
  - 新格式：包含 `#### 测试阶段/实现阶段/审阅阶段`，且每个阶段内都有 `status:` + `evidence:`
- status 只允许：TODO / DOING / BLOCKED / DONE / VERIFIED
- 只有 **REVIEW 的证据** 才能把 DONE -> VERIFIED（evidence 必须引用 Iteration 与验证方式）

---

## Milestone M0: 引导与黑板契约

### M0-T1: 建立 dev_plan 状态机
- acceptance:
- `orchestrator/memory/dev_plan.md` 存在并遵循固定字段
- 每轮在 `orchestrator/memory/project_history.md` 留痕（说明改了什么/为什么）

#### 测试阶段
- status: DONE
- evidence:

#### 实现阶段
- status: DONE
- evidence:

#### 审阅阶段
- status: VERIFIED
- evidence:
- Iteration 1 REVIEW: `orchestrator/memory/dev_plan.md` 存在；`orchestrator/memory/project_history.md` 含 `## Iteration 1:` 留痕（见 orchestrator/reports/report_review.md）

### M0-T2: 审阅代理输出可核实证据
- acceptance:
- `orchestrator/reports/report_review.md` 包含可复现的命令与关键输出摘要
- 进度核实：逐条对照 dev_plan 的任务给出 PASS/FAIL 与证据

#### 测试阶段
- status: DONE
- evidence:

#### 实现阶段
- status: DONE
- evidence:

#### 审阅阶段
- status: VERIFIED
- evidence:
- Iteration 1 REVIEW: `wc/rg/pytest` 证据齐全；`project/backend` 下 `python -m pytest -q` => 93 passed（见 orchestrator/reports/report_review.md）

---

## Milestone M1: 需求与现状取证（Project 重构）

### M1-T1: 阅读关键文档并提炼重构目标/约束
- acceptance:
- 逐份阅读并提炼：project 术语、边界、流程/数据流、约束（含快速失败/禁止防御性编程）
- 明确与现有代码中 project 模块的映射点（文件/模块层面）

#### 测试阶段
- status: DONE
- evidence:

#### 实现阶段
- status: DONE
- evidence:

#### 审阅阶段
- status: VERIFIED
- evidence:
- Iteration 1 REVIEW: 三份文档与代码映射（见 orchestrator/reports/report_review.md）

### M1-T2: 代码现状取证：定位 project 相关模块、入口与调用链
- acceptance:
- 给出模块清单（入口/领域/集成/基础设施）
- 给出至少 1 条入口到核心逻辑调用链证据

#### 测试阶段
- status: DONE
- evidence:

#### 实现阶段
- status: DONE
- evidence:

#### 审阅阶段
- status: VERIFIED
- evidence:
- Iteration 1 REVIEW: Snowflake Step4 落库链路与 Topone 链路（见 orchestrator/reports/report_review.md）

### M1-T3: 输出可执行的重构拆解（面向 dev_plan 的任务颗粒）
- acceptance:
- 产出目标结构草图
- 产出迁移步骤（每步可独立验证）

#### 测试阶段
- status: DONE
- evidence:

#### 实现阶段
- status: DONE
- evidence:

#### 审阅阶段
- status: VERIFIED
- evidence:
- Iteration 1 REVIEW: 分步路线与验证方式（见 orchestrator/reports/report_review.md）

---

## Milestone M2: Project 模块重构（实现）

### M2-T1: 存储层解耦（DIP）+ GraphStorage 拆分（SRP）
- acceptance:
- 引入最小存储接口（Port/Protocol/ABC），调用方依赖抽象而非 Kùzu 具体实现
- `GraphStorage` 按职责拆分；`storage/graph.py` 收敛为 facade
- `project/backend` 下 pytest 全绿

#### 测试阶段
- status: DONE
- evidence:

#### 实现阶段
- status: DONE
- evidence:

#### 审阅阶段
- status: VERIFIED
- evidence:
- Iteration 2 DEV: 完成 ports + 拆分（见 orchestrator/reports/report_dev.md）
- Iteration 3 REVIEW: pytest 全绿 + DIP/SRP/无吞异常取证（见 orchestrator/reports/report_review.md）

### M2-T2: 逻辑检察官/状态流改造：从图谱构建 world_state（快速失败）
- acceptance:
- locator（三件套）齐全时：world_state 必须来自图谱，不得信任请求体
- 新增/更新测试先红后绿；pytest 全绿

#### 测试阶段
- status: DONE
- evidence:

#### 实现阶段
- status: DONE
- evidence:

#### 审阅阶段
- status: VERIFIED
- evidence:
- Iteration 4 TEST: 红测建立（见 orchestrator/reports/report_test.md）
- Iteration 5 DEV: 实现转绿（见 orchestrator/reports/report_dev.md）
- Iteration 6 REVIEW: 复核取证与回归（见 orchestrator/reports/report_review.md）

### M2-T3: Memgraph 存储落地（Dual-subgraph + Temporal edge + Snapshot）
- acceptance:
- 最小闭环能力：写入/读取 entity 时序状态（start_scene_seq/end_scene_seq）、按 scene_seq 查询 world_state、snapshot 生成与读取
- 无 fallback：连接/查询失败必须显式失败（快速失败）
- 可复现集成验证：
  - 文档命令使用项目 venv（`./.venv/bin/python`）
  - docker-compose 镜像可显式配置（`MEMGRAPH_IMAGE`）或离线 `docker load` 后使用本地 tag
  - 测试可指向远程/自建 Memgraph（`MEMGRAPH_BOLT_URI`）
  - Memgraph 可连接环境中：`REQUIRE_MEMGRAPH=1 MEMGRAPH_BOLT_URI=... ./.venv/bin/python -m pytest -q -rs -k memgraph` 跑绿

#### 测试阶段
- status: DONE
- evidence:

#### 实现阶段
- status: DONE
- evidence:

#### 审阅阶段
- status: DONE
- evidence:
- Iteration 7 DEV: 实现 `MemgraphWorldStateStorage` + 集成测试 + compose + README + 依赖（见 orchestrator/reports/report_dev.md）
- Iteration 8 REVIEW: 取证确认门禁语义与实现关键点；指出 Docker Hub 不可达导致无法跑到绿、以及 `python` 非项目 venv 会缺 `neo4j` 的可复现性风险（见 orchestrator/reports/report_review.md）
- Iteration 9 DEV: compose 支持 `MEMGRAPH_IMAGE` 覆盖；README 统一使用 `./.venv/bin/python` 并补充受限网络/离线镜像/远程 Memgraph 指引；集成测试支持 `MEMGRAPH_BOLT_URI` 且补齐门禁/优先级测试；`./.venv/bin/python -m pytest -q` => `100 passed, 1 skipped`（见 orchestrator/reports/report_dev.md）

---

## Milestone M3: 测试与验证

### M3-T1: 补齐关键单元/契约/集成测试（覆盖重构风险面）
- acceptance:
- 覆盖：branch 隔离、时序回溯、logic_check 图谱取状态、Topone 错误语义契约
- 测试可复现运行（至少 pytest；如包含 Memgraph 集成测试则提供命令）

#### 测试阶段
- status: DOING
- evidence:

#### 实现阶段
- status: DOING
- evidence:

#### 审阅阶段
- status: DOING
- evidence:
- Iteration 4 TEST: `project/backend/tests/test_logic_check_world_state.py`（见 orchestrator/reports/report_test.md）
- Iteration 7 DEV: `project/backend/tests/test_memgraph_storage_integration.py`（见 orchestrator/reports/report_dev.md）
- Iteration 9 DEV: Memgraph 集成测试补齐配置/门禁相关覆盖；全量 pytest `100 passed, 1 skipped`（见 orchestrator/reports/report_dev.md）

### M3-T2: REVIEW 复核并推进全部任务到 VERIFIED
- acceptance:
- REVIEW 对照每条任务 acceptance 给出 PASS/FAIL 与证据
- 所有任务最终状态为 VERIFIED

#### 测试阶段
- status: TODO
- evidence:

#### 实现阶段
- status: TODO
- evidence:

#### 审阅阶段
- status: TODO
- evidence:
