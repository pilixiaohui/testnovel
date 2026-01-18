# Project History (Append-only)

> 本文件由 MAIN 追加写入；每轮必须包含 `## Iteration {iteration}:`。

## Task Goal (New Task) - 2026-01-18T19:52:27
读取 doc/backup_old/graph_refactor_final_plan.md doc/长篇小说生成系统设计.md
doc/topone接口文档.md 完成对 project相关内容的彻底重构
## Iteration 1:
next_agent: REVIEW
reason: 缺少对指定文档与代码现状的可核实证据，无法拆解“project 相关内容彻底重构”的里程碑与验收标准；先让 REVIEW 取证并给出可执行任务拆解。
key_observations:
- report_review.md/report_dev.md/report_test.md/report_finish_review.md 均为空，当前无法进行任何 VERIFIED 判定
- dev_plan 仅包含 M0 两条 TODO，尚未覆盖 New Task 的重构范围
blockers:
- 未明确 project 模块边界、入口/调用链、与 topone 接口集成位置、以及主要重复/耦合点
dev_plan: updated
## Iteration 2:
next_agent: DEV
reason: REVIEW 已完成关键文档与代码现状取证（含可复现命令与 pytest 全绿证据），并给出分步重构拆解；现进入实现阶段，先做存储层解耦（DIP）与 GraphStorage 拆分（SRP），为后续 world_state/时序与 Memgraph 落地铺路。
key_observations:
- 后端当前测试全量通过：`python -m pytest -q` => 93 passed（作为增量重构安全网）
- 存储仍为 Kùzu（`project/backend/app/storage/graph.py`），与文档目标 Memgraph/时序边/快照存在结构性偏差
- `logic_check` 仍使用请求体 world_state（`project/backend/app/main.py:1012`），存在“过期状态推理”风险
- Topone 集成位置明确且与接口文档对齐（`project/backend/app/main.py:955`、`project/backend/app/services/topone_client.py:106-107`、`project/backend/app/config.py:29`）
dev_plan: updated
## Iteration 3:
next_agent: REVIEW
reason: DEV 报告已完成 M2-T1（DIP+SRP 拆分）且 pytest 全绿；按规则需 REVIEW 复核取证后才能将 M2-T1 标记为 VERIFIED。
key_observations:
- DEV 已引入 `GraphStoragePort` 并将 API/业务层依赖改为抽象；`GraphStorage` 拆分为多个职责模块并收敛为 facade（见 report_dev.md）
- DEV 自测：`project/backend` 下 `python -m pytest -q` => 93 passed（见 report_dev.md）
blockers:
- M2-T1 仍缺少 REVIEW 证据，暂不能 VERIFIED

dev_plan: updated
## Iteration 4:
next_agent: TEST
reason: REVIEW 已复核 M2-T1 PASS，可将其从 DONE 升级为 VERIFIED；下一步推进 M2-T2，按 TDD 先补红测锁定 logic_check 图谱取状态行为。
key_observations:
- Iteration 3 REVIEW: project/backend 下 python -m pytest -q => 93 passed, 3 warnings；DIP/SRP/快速失败检查均 PASS
- dev_plan 中 M2-T1 已具备 REVIEW 证据，可升级为 VERIFIED
- M2-T2/M2-T3/M3 任务仍为 TODO，需要先补测试再实现

dev_plan: updated
## Iteration 5:
next_agent: DEV
reason: TEST 已新增 M2-T2 红测并验证当前实现仍信任请求体 world_state；需要 DEV 按测试驱动修改逻辑检察官链路与存储 Port/实现，使其从图谱构建 world_state 并让测试转绿。
key_observations:
- Iteration 4 TEST: 新增 `project/backend/tests/test_logic_check_world_state.py`，执行 `pytest` 得到 `1 failed, 1 passed`（红测建立成功）
- 失败断言表明：locator 存在时 gateway 仍收到来自请求体的 world_state（`{'from_request': True}`），而非 storage 构建值（`{'from_storage': True}`）
- M2-T1 已 VERIFIED；当前阻塞在 M2-T2 的实现落地

dev_plan: updated
## Iteration 6:
next_agent: REVIEW
reason: DEV 已实现 M2-T2 并使红测转绿（tests/test_logic_check_world_state.py），但 dev_plan 中该任务尚无 REVIEW 证据，需复核后才能 VERIFIED。
key_observations:
- Iteration 4 TEST: 新增红测并确认旧实现缺陷（1 failed, 1 passed）
- Iteration 5 DEV: 已在 Port/GraphStorage/logic_check_endpoint 落地修复；`tests/test_logic_check_world_state.py` 2 passed，后端全量 pytest 95 passed
blockers:
- M2-T2 缺少 REVIEW 证据，暂不能 VERIFIED

dev_plan: updated
## Iteration 7:
next_agent: DEV
reason: REVIEW 已取证确认 M2-T2 PASS，可将其从 DONE 升级为 VERIFIED；下一步启动 M2-T3（Memgraph 存储最小闭环），推进 Kuzu -> Memgraph 的主线重构。
key_observations:
- Iteration 6 REVIEW: `tests/test_logic_check_world_state.py` 2 passed，后端全量 pytest 95 passed；locator 路径覆盖 world_state；Port/实现一致；无吞异常/兜底扫描命中
- 当前 dev_plan 仍有 M2-T3/M3 TODO，未满足 FINISH 硬条件
dev_plan: updated
## Iteration 8:
next_agent: REVIEW
reason: DEV 已完成 M2-T3 的实现与文档，但尚无 REVIEW 证据；且 DEV 报告当前环境 docker 不可用导致 Memgraph 集成测试无法跑到“绿”，需要 REVIEW 复核取证并给出可执行的验证/降级方案。
key_observations:
- Iteration 7 DEV: 新增 Memgraph 存储最小闭环、docker-compose、README 与集成测试；全量 pytest 95 passed, 1 skipped（Memgraph 未启动）
- M2-T3 当前缺少 REVIEW 证据，不能 VERIFIED
- 若 docker 在本环境确实不可用，M2-T3 的“可复现集成验证”可能被环境阻塞，需要明确下一步（例如改用可运行的环境/远程 Memgraph）
dev_plan: updated
## Iteration 9:
next_agent: DEV
reason: M2-T3 取证被环境阻塞（Docker Hub 不可达无法拉取镜像），且存在 `python` 非项目 venv 导致 neo4j 缺失的可复现性问题；派 DEV 通过 compose/README 调整降低耦合并提供可替换镜像源/离线加载方案，解除阻塞。
key_observations:
- Iteration 8 REVIEW: `./.venv/bin/python -m pytest -q` 基线全绿（95 passed, 1 skipped）；Memgraph 测试门禁语义符合预期（默认 skip；REQUIRE_MEMGRAPH=1 严格 fail）
- 阻塞根因：`docker compose up -d` 拉取 `memgraph/memgraph:latest` 失败（Docker Hub registry 超时不可达），无法获得“Memgraph 运行时集成测试绿测”证据
- 可复现性风险：README/命令若使用非 `project/backend/.venv` 的 `python` 会触发 `ModuleNotFoundError: neo4j`
blockers:
- Docker Hub 不可达导致无法启动 Memgraph 容器
- 运行命令未强制使用项目 venv，导致依赖缺失报错

dev_plan: updated
## Iteration 10:
next_agent: REVIEW
reason: DEV 已按 Iteration 8 REVIEW 建议修复 M2-T3 的可复现性问题（README 强制使用项目 venv、docker-compose 支持 MEMGRAPH_IMAGE 覆盖、集成测试支持 MEMGRAPH_BOLT_URI）；需要 REVIEW 复核并在可连接 Memgraph 的环境下将 `REQUIRE_MEMGRAPH=1 ... -k memgraph` 跑到绿，以推进 M2-T3 -> VERIFIED。
key_observations:
- Iteration 9 DEV: `project/backend/docker-compose.memgraph.yml` 支持 `MEMGRAPH_IMAGE`；`project/backend/README.md` 统一用 `./.venv/bin/python -m pytest ...` 并补充受限网络/离线镜像/远程 Memgraph 指引；`project/backend/tests/test_memgraph_storage_integration.py` 支持 `MEMGRAPH_BOLT_URI` 且补齐门禁/优先级测试；全量 pytest `100 passed, 1 skipped`
- M2-T3 仍缺少“Memgraph 运行时绿测”的 REVIEW 证据，当前无法 VERIFIED；若环境仍不可拉取镜像且无可用远程 Memgraph，将继续阻塞
- dev_plan 仍有 M3-T1(DOING)/M3-T2(TODO)，未满足 FINISH 硬条件
dev_plan: updated
