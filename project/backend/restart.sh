#!/bin/bash

# 杀掉占用8000端口的进程
kill -9 $(lsof -t -i:8000) 2>/dev/null

# 启动服务
BACKEND_HOST="${BACKEND_HOST:?BACKEND_HOST is required}"
./.venv/bin/python -m uvicorn app.main:app --host "$BACKEND_HOST" --port 8000 --reload