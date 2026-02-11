# Current Task (Iteration 2)
assigned_agent: IMPLEMENTER
self_test: enabled

## 继续任务：修复剩余6个前端核心问题

上轮你修复了导航高亮归一化问题（标签页切换出错），做得不错。但用户报告的7个问题中还有6个未调研和修复，请继续逐一处理。

### 剩余问题清单（按优先级排序）

1. **项目管理不完善，无法新建项目** — HomeView项目列表/创建功能缺失或不可用，这是最基础的功能
2. **项目无法保存** — 项目创建/编辑后无法持久化到后端
3. **雪花步骤生成内容只显示名字列表** — Step3（角色）应展示ambition/conflict/epiphany/voice_dna等完整字段，Step4（场景）应展示完整信息，Step5（幕/章）应展示purpose/tone/focus等
4. **设置中LLM配置不显示真实数据库内配置** — SettingsView应从后端API读取并展示实际的LLM配置
5. **提示词不显示实际使用的提示词** — 雪花流程或设置中应能查看当前使用的LLM提示词
6. **无法提取图信息和推演** — 图知识库提取（state/extract）、推演引擎（simulation）相关功能前端调用或展示异常

### 工作方法
- 先阅读相关前端代码（views、stores、api、components），确认问题是否存在
- 对照后端API端点，检查前后端契约是否一致
- 确认问题存在后再修复，每个问题都要有对应的单元测试
- 启动前端开发服务器用Playwright MCP做基本自测
- 本轮尽量多修复几个问题，不要只修一个就停

### 验收标准
- 至少修复3个以上剩余问题
- 每个修复都有对应的单元测试
- 前端单元测试全部通过
- 用Playwright MCP自测基本功能可用

### 约束
- 前端代码路径：/home/zxh/ainovel_v3/project/frontend/
- 后端代码路径：/home/zxh/ainovel_v3/project/backend/
- 禁止修改后端API接口
- 先调研确认问题存在再修复
- 保持最小改动原则

## 执行环境
- 工作目录: /home/zxh/ainovel_v3/project
- 项目根目录: /home/zxh/ainovel_v3
- 业务代理根目录: /home/zxh/ainovel_v3/project
- 代码目录: /home/zxh/ainovel_v3/project/backend
- 前端目录: /home/zxh/ainovel_v3/project/frontend
- Python: /usr/bin/python3.11
- 后端地址: http://127.0.0.1:8000
- 前端 URL: http://127.0.0.1:5185
- 测试执行配置:
  - 前端开发端口: 5185
  - 服务启动等待: 6.0秒
  - unit测试超时: 120.0秒
  - integration测试超时: 300.0秒
  - e2e测试超时: 600.0秒
- 环境变量:
  - MEMGRAPH_HOST=localhost
  - MEMGRAPH_PORT=7687

