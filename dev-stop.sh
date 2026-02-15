#!/bin/bash

# 停止 Orchestrator V2 工作流脚本
# 用法:
#   ./dev-stop.sh

set -e

TMP_DIR="/tmp/orchestrator-dev"
PID_FILE="$TMP_DIR/orchestrator.pid"

if [ $# -ne 0 ]; then
    echo "❌ 不支持参数。"
    echo "用法: ./dev-stop.sh"
    exit 1
fi

echo "🛑 正在停止 Orchestrator V2..."
echo ""

if [ ! -f "$PID_FILE" ]; then
    echo "❌ 未找到 PID 文件，请确认 dev-start.sh 是否已启动"
    exit 1
fi

ORCH_PID=$(cat "$PID_FILE")
if [ -z "$ORCH_PID" ]; then
    echo "❌ PID 为空: $PID_FILE"
    rm -f "$PID_FILE"
    exit 1
fi

if ! kill -0 "$ORCH_PID" 2>/dev/null; then
    echo "⚠️  进程已不存在 (PID: $ORCH_PID)，清理 PID 文件"
    rm -f "$PID_FILE"
    exit 0
fi

echo "停止进程 (PID: $ORCH_PID)..."
kill "$ORCH_PID" 2>/dev/null || true

for i in {1..5}; do
    if ! kill -0 "$ORCH_PID" 2>/dev/null; then
        break
    fi
    sleep 1
done

if kill -0 "$ORCH_PID" 2>/dev/null; then
    echo "⚠️  SIGTERM 超时，发送 SIGKILL..."
    kill -9 "$ORCH_PID" 2>/dev/null || true
    sleep 1
fi

rm -f "$PID_FILE"
echo "✅ Orchestrator V2 已停止"
