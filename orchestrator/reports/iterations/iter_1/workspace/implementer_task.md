# Current Task (Iteration 1)
assigned_agent: IMPLEMENTER
self_test: enabled

## 任务目标
全面调研前端所有功能模块，逐一验证用户报告的问题是否存在，发现其他潜在问题，然后修复所有确认的问题。

## 需求边界

### 用户报告的问题清单（需逐一验证）
1. 项目无法保存 - 项目创建/编辑后无法持久化
2. 提示词不显示实际使用的提示词 - 设置或雪花流程中应显示当前实际使用的LLM提示词内容
3. 标签页切换出错 - 各页面间导航或同一页面内tab切换存在异常
4. 无法提取图信息和推演 - 图知识库提取、推演引擎相关功能前端调用失败或展示异常
5. 设置中LLM配置不显示真实数据库内配置 - SettingsView应从后端读取并展示实际的LLM配置（模型名、API地址等）
6. 项目管理不完善，无法新建项目 - HomeView项目列表/创建功能缺失或不可用
7. 雪花步骤生成内容只显示名字列表 - Step3（角色）、Step4（场景）、Step5（幕/章）等步骤生成的内容应展示完整信息（原始数据+解析结果），而非仅名字

### 额外调研范围
- 对照frontend_implementation_spec.md和系统架构文档，检查前端各模块是否与后端API正确对接
- 检查API调用层（api/*.ts）的请求路径、参数、响应处理是否与后端端点匹配
- 检查Pinia Store的状态管理逻辑是否正确
- 检查路由配置和页面间导航是否正常
- 检查组件是否正确渲染数据

## 调研方法
1. 先阅读前端代码（views、stores、api、components），理解当前实现
2. 对照后端API端点定义，检查前后端契约是否一致
3. 启动前端开发服务器+后端服务，在浏览器中实际操作验证问题
4. 记录所有确认的问题，逐一修复

## 验收标准（抽象描述）
- 所有用户报告的7个问题均已验证并修复（如问题不存在则说明原因）
- 项目可以正常创建、保存、加载
- 雪花流程Step1-6各步骤生成的内容能完整展示（角色的ambition/conflict/epiphany/voice_dna等字段，场景的完整信息，幕/章的结构信息）
- 设置页面显示从后端获取的真实LLM配置
- 标签页/页面切换正常，无JS错误
- 推演功能前端可正常触发并展示结果
- 前端单元测试通过
- 以生成一个10章每章2000字的短篇小说为端到端验收场景，确保多代理推演、图知识库提取等核心流程可用

## 约束条件
- 前端代码路径：/home/zxh/ainovel_v3/project/frontend/
- 后端代码路径：/home/zxh/ainovel_v3/project/backend/
- 技术栈：Vue 3 + TypeScript + Element Plus + Pinia + Vite
- 禁止引入新的第三方依赖（除非绝对必要）
- 禁止修改后端API接口契约（如后端有bug需单独记录）
- 先调研确认问题存在再修复，不要盲目改代码
- 修复时保持最小改动原则，不做不必要的重构

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

