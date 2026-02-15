#!/bin/bash

# Orchestrator V2 工作流启动脚本
# 用法:
#   ./dev-start.sh          # 启动 UI 监控
#   ./dev-start.sh team     # 启动完整 agent 团队（含 UI）

set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
TMP_DIR="/tmp/orchestrator-dev"
PID_FILE="$TMP_DIR/orchestrator.pid"
LOG_FILE="$TMP_DIR/orchestrator.log"
UI_HOST="127.0.0.1"
UI_PORT="8766"
ORCH_PID=""

MODE="${1:-ui}"

cleanup() {
    echo ""
    echo "🛑 停止服务..."
    if [ -n "$ORCH_PID" ] && kill -0 "$ORCH_PID" 2>/dev/null; then
        kill "$ORCH_PID" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    echo "✅ 已停止"
    exit 0
}

trap cleanup INT TERM

echo "=========================================="
echo "  Orchestrator V2 工作流启动"
echo "=========================================="
echo ""

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ 错误: 未找到 python3"
    exit 1
fi

echo "✅ Python: $(python3 --version)"
echo "   模式: $MODE"
echo ""

# 确保项目已初始化
cd "$PROJECT_ROOT"
python3 -m orchestrator_v2 init 2>/dev/null || true

mkdir -p "$TMP_DIR"
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "❌ 检测到已有运行实例 (PID: $OLD_PID)，请先运行 ./dev-stop.sh"
        exit 1
    fi
    rm -f "$PID_FILE"
fi

if [ "$MODE" = "team" ]; then
    echo "📡 启动 Agent 团队 + UI..."
    shift
    nohup python3 -m orchestrator_v2 team "$@" > "$LOG_FILE" 2>&1 &
else
    echo "📡 启动 UI 监控..."
    nohup python3 -m orchestrator_v2 ui --host "$UI_HOST" --port "$UI_PORT" > "$LOG_FILE" 2>&1 &
fi

ORCH_PID=$!
echo "$ORCH_PID" > "$PID_FILE"
echo "   PID: $ORCH_PID"

echo "   等待服务启动..."
ready=0
for i in {1..10}; do
    if ! kill -0 "$ORCH_PID" 2>/dev/null; then
        echo "❌ 进程已退出"
        echo ""
        echo "日志内容:"
        cat "$LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
    if command -v curl >/dev/null 2>&1 && curl -fsS "http://$UI_HOST:$UI_PORT/" > /dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 1
done

if [ "$ready" -ne 1 ]; then
    # 进程还活着但 UI 没响应 — team 模式下 UI 可能还在初始化，不算失败
    if [ "$MODE" = "team" ]; then
        echo "   ⚠️  UI 尚未就绪（团队模式下可能需要更长时间）"
    else
        echo "❌ UI 启动超时"
        echo ""
        echo "日志内容:"
        cat "$LOG_FILE"
        kill "$ORCH_PID" 2>/dev/null || true
        rm -f "$PID_FILE"
        exit 1
    fi
else
    echo "   ✅ UI 已启动"
fi

echo ""
echo "=========================================="
echo "  ✅ 启动成功"
echo "=========================================="
echo ""
echo "访问: http://$UI_HOST:$UI_PORT"
echo ""
echo "日志:"
echo "  tail -f $LOG_FILE"
echo ""
echo "停止: ./dev-stop.sh 或 Ctrl+C"
echo ""

wait "$ORCH_PID"
wait_status=$?
rm -f "$PID_FILE"
exit "$wait_status"
