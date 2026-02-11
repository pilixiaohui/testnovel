#!/bin/bash

# 停止 Orchestrator 工作流脚本（仓库内模式）
# 用法:
#   ./dev-stop.sh

set -e

TMP_DIR="/tmp/orchestrator-dev"
PID_FILE="$TMP_DIR/orchestrator.pid"
ORCH_PID=""

if [ $# -ne 0 ]; then
    echo "❌ 不支持参数。"
    echo "用法: ./dev-stop.sh"
    exit 1
fi

echo "🛑 正在停止 Orchestrator..."
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
    echo "❌ 进程不存在 (PID: $ORCH_PID)"
    rm -f "$PID_FILE"
    exit 1
fi

echo "停止 Orchestrator (PID: $ORCH_PID)..."
if ! kill "$ORCH_PID"; then
    echo "❌ 停止失败 (PID: $ORCH_PID)"
    exit 1
fi

for i in {1..5}; do
    if ! kill -0 "$ORCH_PID" 2>/dev/null; then
        break
    fi
    sleep 1
done
if kill -0 "$ORCH_PID" 2>/dev/null; then
    echo "❌ 停止超时 (PID: $ORCH_PID)"
    exit 1
fi

rm -f "$PID_FILE"
echo "✅ Orchestrator 已停止"
