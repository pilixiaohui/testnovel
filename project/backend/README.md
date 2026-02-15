# Backend Notes

## 启动命令

从仓库根目录执行（先设置 `BACKEND_HOST` 绑定地址）：

```bash
cd project/backend
export BACKEND_HOST=<bind-host>
./.venv/bin/python -m uvicorn app.main:app --host "$BACKEND_HOST" --port 8000 --reload
```

或使用环境变量指定引擎：

```bash
cd project/backend
export BACKEND_HOST=<bind-host>
SNOWFLAKE_ENGINE=gemini ./.venv/bin/python -m uvicorn app.main:app --host "$BACKEND_HOST" --port 8000 --reload
```

生产环境（不带热重载）：

```bash
cd project/backend
export BACKEND_HOST=<bind-host>
SNOWFLAKE_ENGINE=gemini ./.venv/bin/python -m uvicorn app.main:app --host "$BACKEND_HOST" --port 8000
```

## 配置说明

- 启动必须显式配置 `SNOWFLAKE_ENGINE`（local/llm/gemini），无默认值。
- 环境变量：`SCENE_MIN_COUNT` 与 `SCENE_MAX_COUNT` 控制生成场景数量范围，默认 50-100。
- TopOne 模型默认值：`TOPONE_DEFAULT_MODEL=gemini-3-pro-preview-11-2025`，`TOPONE_SECONDARY_MODEL=gemini-3-flash-preview`，可在 `.env` 覆盖。
- 数据库路径：`KUZU_DB_PATH` 的相对路径以仓库根目录为基准，默认 `backend/data/snowflake.db`，与 `.env` 示例和健康检查保持一致。
- 协商 WebSocket `/ws/negotiation` 已移除，当前不可用。

## Memgraph 本地集成测试

本仓库提供 Memgraph 存储（时序状态 + world_state 查询 + snapshot）的最小闭环集成测试。

启动/停止 Memgraph（从仓库根目录执行）：

```bash
docker compose -f project/backend/docker-compose.memgraph.yml up -d
docker compose -f project/backend/docker-compose.memgraph.yml down
```

受限网络 / 无法访问 Docker Hub：

1) 指定可访问的镜像源（显式提供，不做自动回退）：

```bash
MEMGRAPH_IMAGE=<your-registry>/memgraph/memgraph:latest \
  docker compose -f project/backend/docker-compose.memgraph.yml up -d
```

2) 或离线加载镜像后再启动（命令模板）：

```bash
# 在可访问 Docker Hub 的机器上：
docker pull memgraph/memgraph:latest
docker save memgraph/memgraph:latest -o memgraph-memgraph-latest.tar

# 将 tar 复制到受限机器上后：
docker load -i memgraph-memgraph-latest.tar
docker compose -f project/backend/docker-compose.memgraph.yml up -d
```

运行集成测试（从仓库根目录执行；确保使用项目 venv）：

```bash
cd project/backend
./.venv/bin/python -m pytest -q -rs -k memgraph
```

如果希望 Memgraph 未启动时直接失败（而不是 skip）：

```bash
cd project/backend
REQUIRE_MEMGRAPH=1 ./.venv/bin/python -m pytest -q -k memgraph
```

如果你使用的是远程/自建 Memgraph，可显式指定连接（绕过 docker 拉取）：

```bash
cd project/backend
MEMGRAPH_BOLT_URI=bolt://<host>:7687 ./.venv/bin/python -m pytest -q -k memgraph
```

（可选）如需认证：`MEMGRAPH_USERNAME` / `MEMGRAPH_PASSWORD`。