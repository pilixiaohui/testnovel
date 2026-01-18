已阅读开发行为规范  
iteration: 9

## 改了哪里

- `project/backend/docker-compose.memgraph.yml:3`
  - 将 Memgraph 镜像从硬编码改为可配置：`image: ${MEMGRAPH_IMAGE:-memgraph/memgraph:latest}`

- `project/backend/README.md:13`
  - 所有 pytest 命令统一为 `./.venv/bin/python -m pytest ...`，避免 `python` 非 venv 导致依赖缺失误报
  - 增加“受限网络 / 无法访问 Docker Hub”说明：
    - `MEMGRAPH_IMAGE` 覆盖镜像源示例（显式提供，不做自动回退）
    - `docker save` / `docker load` 离线镜像加载命令模板
    - 远程/自建 Memgraph 连接示例（`MEMGRAPH_BOLT_URI`）

- `project/backend/tests/test_memgraph_storage_integration.py:9`
  - 新增连接配置入口：优先读 `MEMGRAPH_BOLT_URI`，兼容保留 `MEMGRAPH_URI`，默认仍为 `bolt://localhost:7687`

- `project/backend/tests/test_memgraph_storage_integration.py:31`
  - Memgraph 不可用且未设置 `REQUIRE_MEMGRAPH=1` 时的 skip 文案增强：明确如何启动（含 `MEMGRAPH_IMAGE`）/如何指定连接（`MEMGRAPH_BOLT_URI`）/如何强制失败（`REQUIRE_MEMGRAPH=1`）

- `project/backend/tests/test_memgraph_storage_integration.py:49`
  - 补充最小化测试：覆盖 `MEMGRAPH_BOLT_URI` 优先级、默认值，以及门禁语义（skip vs REQUIRE_MEMGRAPH=1 直接抛错）

## 为什么这样改（对齐验收标准）

- Compose 镜像源可替换：通过 `MEMGRAPH_IMAGE` 显式覆盖镜像地址（KISS），不做任何“失败后自动换源/自动回退”（符合快速失败与禁兜底要求）
- 文档命令可复现：README 统一使用 `./.venv/bin/python`，并提供受限网络下两条可执行路径（镜像源覆盖/离线加载；另补充远程连接入口）
- 集成测试配置入口最小化：只新增 `MEMGRAPH_BOLT_URI` 读取并保持原有门禁逻辑不变；`REQUIRE_MEMGRAPH=1` 仍会在连接失败时快速失败
- DRY/兼容性：不引入新配置文件/复杂逻辑，且保留 `MEMGRAPH_URI` 以避免破坏现有用法

## 如何自测

在本机执行（实际运行结果摘要）：

```bash
cd project/backend
./.venv/bin/python -m pytest -q
```

- 结果：`100 passed, 1 skipped`

```bash
cd project/backend
./.venv/bin/python -m pytest -q -rs -k memgraph
```

- 结果：Memgraph 不可用时 `SKIPPED`，并在 `-rs` 输出中包含明确指引（`MEMGRAPH_IMAGE` / `MEMGRAPH_BOLT_URI` / `REQUIRE_MEMGRAPH=1`）

## 风险与遗留

- 需要用户自行提供可访问的 `MEMGRAPH_IMAGE`（私有仓库/镜像加速/离线加载后的 tag），这是刻意的“显式配置”设计；不会自动兜底换源
- 若使用远程 Memgraph 且需认证，请同步设置 `MEMGRAPH_USERNAME` / `MEMGRAPH_PASSWORD`

## 工具调用简报

【MCP调用简报】  
服务: serena  
触发: 定位并最小化修改 compose/README/集成测试以解除 Docker Hub 阻塞  
参数: `read_file(max_answer_chars=-1)`, `replace_regex`, `apply_patch`  
结果: 更新 3 个目标文件；新增最小化测试覆盖新配置入口与门禁语义  
状态: 成功

【本地命令简报】  
- `cd project/backend && ./.venv/bin/python -m pytest -q`（全量回归）  
- `cd project/backend && ./.venv/bin/python -m pytest -q -rs -k memgraph`（验证 skip 指引与门禁输出）