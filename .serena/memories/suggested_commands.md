安装依赖：`cd ainovel2 && npm install`
开发模式：`npm run dev`（默认端口 3000，0.0.0.0）。
构建生产：`npm run build`
本地预览生产包：`npm run preview`
环境变量：在 ainovel2/.env.local 写 `GEMINI_API_KEY=xxx` 以通过 Vite 注入 process.env.API_KEY/GEMINI_API_KEY。