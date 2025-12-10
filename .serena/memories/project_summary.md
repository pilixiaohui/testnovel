项目目的：前端演示版“工业级长篇生成系统”UI，提供雪花法步骤、剧情大纲图和写作画布，所有数据目前保存在浏览器 localStorage，直接在前端调用 Gemini API（需 API Key）。
技术栈：Vite + React 19 + TypeScript，Tailwind CDN 注入样式，React Router 7、ReactFlow、Recharts、Lucide 图标，@google/genai 客户端；tsconfig 使用 bundler 模块解析和 jsx=react-jsx。
主要结构：
- index.html：Tailwind CDN 与 importmap，包含 ReactFlow 样式。
- App.tsx：全局状态（ProjectState）与上下文、路由（Dashboard、SnowflakeWorkshop、GraphOutline、WriteCanvas）、localStorage 持久化，API Key 仅存内存。
- pages/*：Dashboard（概览统计）、SnowflakeWorkshop（雪花法步骤）、GraphOutline（ReactFlow 场景/幕图）、WriteCanvas（Beat/正文生成、实体状态展示）。
- services/geminiService.ts：封装 Gemini 请求（logline 扩展、角色、结构、Beat Sheet、Beat prose、全文生成、状态逆向提取），直接使用前端传入 API Key。
- types.ts：项目/角色/幕/场景/节拍/实体等数据模型和 SnowflakeStep 枚举。
运行端口：vite dev 默认 3000，host 0.0.0.0，API Key 由 Vite define 注入 process.env.API_KEY/GEMINI_API_KEY。