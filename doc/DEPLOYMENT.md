
## 运行前提
- Python 3.11+
- 已创建并激活项目虚拟环境
- Memgraph 可访问（本地 Docker 或远程服务）

## 一键启动 Memgraph（本地）

```bash
docker compose -f project/backend/docker-compose.memgraph.yml up -d
```

停止并清理：

```bash
docker compose -f project/backend/docker-compose.memgraph.yml down
```

如需自定义镜像：

```bash
MEMGRAPH_IMAGE=<your-registry>/memgraph/memgraph:latest \
  docker compose -f project/backend/docker-compose.memgraph.yml up -d
```

## 环境变量

必填：
- `SNOWFLAKE_ENGINE`：`local` / `llm` / `gemini`
- `MEMGRAPH_HOST`
- `MEMGRAPH_PORT`

Gemini 模式必填：
- `TOPONE_API_KEY`

可选：
- `TOPONE_BASE_URL`（默认 `https://api.toponeapi.top`）
- `TOPONE_DEFAULT_MODEL`（默认 `gemini-3-pro-preview-11-2025`）
- `TOPONE_SECONDARY_MODEL`（默认 `gemini-3-flash-preview`）
- `TOPONE_TIMEOUT_SECONDS`（默认 `30`）
- `SCENE_MIN_COUNT` / `SCENE_MAX_COUNT`

## 启动 API 服务

```bash
SNOWFLAKE_ENGINE=local \
MEMGRAPH_HOST=localhost \
MEMGRAPH_PORT=7687 \
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 验证

```bash
curl -X POST http://localhost:8000/api/v1/snowflake/step1 \
  -H 'Content-Type: application/json' \
  -d '{"idea": "测试"}'
```

## 远程 Memgraph

将 `MEMGRAPH_HOST` / `MEMGRAPH_PORT` 指向远程服务即可。若使用认证，需在启动后端前配置 `MEMGRAPH_USERNAME` / `MEMGRAPH_PASSWORD`（如已在 Memgraph 启用认证）。

## 数据持久化

`docker-compose.memgraph.yml` 默认挂载 `memgraph_data` 卷用于持久化数据。如需清空本地数据，请执行：

```bash
docker compose -f project/backend/docker-compose.memgraph.yml down -v
```
