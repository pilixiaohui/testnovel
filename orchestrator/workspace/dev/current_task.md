# Current Task (Iteration 9)
assigned_agent: DEV

## 目标
- 解除 M2-T3 的验证阻塞：在 Docker Hub 不可达/受限网络场景下，仍能“可复现地”启动 Memgraph 并跑通集成测试到绿（或至少提供明确可执行的替代方案/配置入口）。

## 背景（阻塞证据）
- REVIEW（Iteration 8）确认：本环境 `docker compose up -d` 无法从 Docker Hub 拉取 `memgraph/memgraph:latest`（registry 超时），因此无法将 `REQUIRE_MEMGRAPH=1 ... -k memgraph` 跑到绿。
- 同时发现：直接运行 `python -m pytest -q` 会因 `python` 指向非项目 venv 导致 `neo4j` 缺失而报错；而 `./.venv/bin/python -m pytest -q` 是绿的。

## 本轮范围
- 只做“可复现性/环境解耦”相关改动：
  - `project/backend/docker-compose.memgraph.yml`
  - `project/backend/README.md`
  - `project/backend/tests/test_memgraph_storage_integration.py`（如需改进提示/配置入口）

## 任务要求（KISS + 快速失败）
1) Compose 镜像源可替换
- 让 `project/backend/docker-compose.memgraph.yml` 支持通过环境变量覆盖镜像（例如 `MEMGRAPH_IMAGE`），避免硬编码只能从 Docker Hub 拉取。
- 不要添加任何“失败后自动回退/自动换源”的兜底逻辑；配置由使用者显式提供。

2) 文档命令必须可复现
- 在 `project/backend/README.md` 中：
  - 所有 pytest 命令统一使用 `./.venv/bin/python`（或明确要求先激活该 venv），避免 `neo4j` 缺失误报。
  - 增加一段“受限网络/无法访问 Docker Hub”的处理说明：
    - 如何设置 `MEMGRAPH_IMAGE` 指向可访问镜像源（由用户环境决定）
    - 或如何通过 `docker load` 加载离线镜像后再启动（给出命令模板）

3) 集成测试配置入口（可选，但若做必须最小化）
- 如有必要，可在 `tests/test_memgraph_storage_integration.py` 增加对 `MEMGRAPH_BOLT_HOST/PORT` 或 `MEMGRAPH_BOLT_URI` 的读取（默认保持 localhost:7687），以支持连接到用户自建/远程 Memgraph（用于绕过 docker 拉取）。
- 保持门禁语义不变：默认 skip；`REQUIRE_MEMGRAPH=1` 必须快速失败。

## 验收标准
- `cd project/backend && ./.venv/bin/python -m pytest -q` 全绿（不得引入回归）
- `cd project/backend && ./.venv/bin/python -m pytest -q -rs -k memgraph` 在 Memgraph 不可用时可 skip，并输出明确指引（如何启动/如何配置镜像/如何指定连接）
- README 中提供两种可执行路径：
  1) docker compose 启动（含 `MEMGRAPH_IMAGE` 覆盖示例）
  2) 离线镜像加载或远程 Memgraph 连接（至少一种）

## TDD 要求
- 若你修改了测试逻辑（例如新增 env 配置入口），请先补/改测试验证门禁语义（红-绿-重构）。
- 若仅修改 README/compose 且不改 Python 逻辑：不强制新增测试，但必须跑全量 pytest 作为回归。
