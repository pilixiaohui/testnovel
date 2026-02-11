# Orchestrator Repository Mode

## 目标

移除 `orch-runtime` 复制运行机制，统一为**仓库内单一运行模式**：

- 不再使用独立 runtime 目录、bootstrap/sync/start 脚本
- 不再使用 `AINOVEL_ORCHESTRATOR_HOME` 切换运行根目录
- 通过代理工作目录切换实现环境隔离

## 核心机制

1. MAIN 代理工作目录固定为 `<repo>/orchestrator`。
2. IMPLEMENTER/VALIDATE/FINISH_REVIEW 工作目录为 `agent_root`（由 `project_env.json` 中 `code_root/frontend_root` 的共同父目录推导）。
3. orchestrator 黑板仍以 `<repo>/orchestrator/{memory,workspace,reports}` 为唯一真值。
4. 每次派发前，黑板 markdown 单向同步到 `<agent_root>/.orchestrator_ctx/`。
5. `.orchestrator_ctx` 为只读镜像，子代理可读但禁止写入。

## 启动

```bash
./dev-start.sh
```

停止：

```bash
./dev-stop.sh
```

## 快速失败约束

- 检测到 `AINOVEL_ORCHESTRATOR_HOME` 时立即失败（已废弃）。
- 镜像目录被代理改写时立即失败（镜像只读）。
- `project_env.json` 配置错误（路径不存在/字段缺失）立即失败。
