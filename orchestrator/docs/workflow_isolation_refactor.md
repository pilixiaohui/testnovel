# Workflow Isolation Refactor

## 目标

一次性收敛工作流隔离策略，减少环境复杂度并消除 runtime 复制导致的版本漂移。

## 关键改动

1. 保留 `runtime_context.py` 作为业务运行配置解析入口（`project_env.json` 强校验）。
2. 移除 runtime 复制部署链路（`orch-runtime` / bootstrap / sync / start）。
3. MAIN 代理工作目录切换到 `<repo>/orchestrator`。
4. 开发/测试/审阅代理工作目录使用 `agent_root`（由 `code_root/frontend_root` 共同父目录推导）。
5. 新增 `blackboard_mirror.py`：将 orchestrator 黑板 markdown 单向镜像到 `<agent_root>/.orchestrator_ctx`。
6. 镜像同步时机固定为“每次派发前”，并写入同步 manifest。
7. 镜像目录定义为只读；若代理改写镜像，立即失败。
8. MAIN/子代理提示词统一路径契约：MAIN 以 `memory/`、`workspace/`、`reports/` 为基准；子代理仅读取 `./.orchestrator_ctx`。

## 结果

- 不再存在 runtime 旧代码漂移问题。
- 环境隔离由“复制代码”改为“代理 cwd + 黑板镜像”，结构更简单。
- 子代理读取所需 markdown 的路径稳定且可审计。
- 旧 runtime 环境变量被硬切断，避免混用配置。
