#!/bin/bash

# Orchestrator 工作流启动脚本（仓库内模式）
# 用法:
#   ./dev-start.sh

set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
TMP_DIR="/tmp/orchestrator-dev"
PID_FILE="$TMP_DIR/orchestrator.pid"
LOG_FILE="$TMP_DIR/orchestrator.log"
UI_HOST="127.0.0.1"
UI_PORT="8766"
ORCH_PID=""

if [ $# -ne 0 ]; then
    echo "❌ 不支持参数。"
    echo "用法: ./dev-start.sh"
    exit 1
fi

if [ -n "${AINOVEL_ORCHESTRATOR_HOME:-}" ] || [ -n "${AINOVEL_ORCHESTRATOR_SOURCE_ROOT:-}" ]; then
    echo "❌ 检测到已废弃 runtime 环境变量：AINOVEL_ORCHESTRATOR_HOME / AINOVEL_ORCHESTRATOR_SOURCE_ROOT"
    echo "请先执行: unset AINOVEL_ORCHESTRATOR_HOME AINOVEL_ORCHESTRATOR_SOURCE_ROOT"
    exit 1
fi

cleanup() {
    echo ""
    echo "🛑 停止服务..."
    if [ -n "$ORCH_PID" ] && kill -0 "$ORCH_PID" 2>/dev/null; then
        if ! kill "$ORCH_PID"; then
            echo "❌ 停止失败 (PID: $ORCH_PID)"
        fi
    fi
    rm -f "$PID_FILE"
    echo "✅ 已停止"
    exit 0
}

trap cleanup INT TERM

echo "=========================================="
echo "  Orchestrator 工作流启动"
echo "=========================================="
echo ""

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ 错误: 未找到 python3"
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "❌ 错误: 未找到 curl"
    exit 1
fi

echo "✅ Python: $(python3 --version)"
echo ""

echo "将启动服务:"
echo "  模式: 仓库内运行"
echo "  UI: http://$UI_HOST:$UI_PORT"
echo ""
echo "停止: 按 Ctrl+C 或 ./dev-stop.sh"
echo ""
echo "=========================================="
echo ""

mkdir -p "$TMP_DIR"
if [ -f "$PID_FILE" ]; then
    echo "❌ 检测到已有 PID 文件，请先运行 ./dev-stop.sh"
    exit 1
fi

echo "📡 启动 Orchestrator UI..."
cd "$PROJECT_ROOT"
nohup env -u AINOVEL_ORCHESTRATOR_HOME -u AINOVEL_ORCHESTRATOR_SOURCE_ROOT \
  python3 orchestrator.py --ui --ui-host "$UI_HOST" --ui-port "$UI_PORT" > "$LOG_FILE" 2>&1 &
ORCH_PID=$!
echo "$ORCH_PID" > "$PID_FILE"
echo "   PID: $ORCH_PID"

echo "   等待 UI 启动..."
ui_ready=0
for i in {1..10}; do
    if curl -fsS "http://$UI_HOST:$UI_PORT/" > /dev/null 2>&1; then
        ui_ready=1
        break
    fi
    sleep 1
done
if [ "$ui_ready" -ne 1 ]; then
    echo "❌ UI 启动超时"
    echo ""
    echo "日志内容:"
    cat "$LOG_FILE"
    kill "$ORCH_PID"
    rm -f "$PID_FILE"
    exit 1
fi

echo "   ✅ UI 已启动"
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
