提交前检查：
- 如有依赖或配置变更，重新运行 `npm install` 确认锁文件更新。
- 执行 `npm run build` 确认前端编译通过（项目无测试/ lint 配置）。
- 若涉及 Gemini 交互逻辑或状态流，手动在 `npm run dev` 下验证 Dashboard/SnowflakeWorkshop/GraphOutline/WriteCanvas 的主路径和 localStorage 持久化。
- 变更 API Key 处理逻辑时，确认未把密钥写入存储或提交。