#!/bin/bash

# 停止 Orchestrator V2 工作流脚本
# 用法:
#   ./dev-stop.sh

set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR="/tmp/orchestrator-dev"
PID_FILE="$TMP_DIR/orchestrator.pid"
CONTAINER_PREFIX="orch-agent"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.infra.yml"

if [ $# -ne 0 ]; then
    echo "❌ 不支持参数。"
    echo "用法: ./dev-stop.sh"
    exit 1
fi

echo "🛑 正在停止 Orchestrator V2..."
echo ""

# 1. 停止主进程
if [ -f "$PID_FILE" ]; then
    ORCH_PID=$(cat "$PID_FILE")
    if [ -n "$ORCH_PID" ] && kill -0 "$ORCH_PID" 2>/dev/null; then
        echo "停止主进程 (PID: $ORCH_PID)..."
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
        echo "   主进程已停止"
    else
        echo "   主进程已不存在 (PID: $ORCH_PID)"
    fi
    rm -f "$PID_FILE"
else
    echo "   未找到 PID 文件，跳过主进程停止"
fi

# 2. 停止所有 agent 容器（docker run -d 启动的容器独立于主进程）
AGENT_IDS=$(docker ps -a --filter "name=${CONTAINER_PREFIX}" -q 2>/dev/null || true)
if [ -n "$AGENT_IDS" ]; then
    echo "停止 agent 容器..."
    for cid in $AGENT_IDS; do
        name=$(docker inspect -f '{{.Name}}' "$cid" 2>/dev/null | sed 's|^/||')
        docker rm -f "$cid" >/dev/null 2>&1 || true
        echo "   已移除: $name"
    done
else
    echo "   无运行中的 agent 容器"
fi

# 3. 停止 compose 基础设施（Memgraph 等）
if [ -f "$COMPOSE_FILE" ]; then
    INFRA_RUNNING=$(docker compose -f "$COMPOSE_FILE" ps -q 2>/dev/null || true)
    if [ -n "$INFRA_RUNNING" ]; then
        echo "停止基础设施..."
        docker compose -f "$COMPOSE_FILE" down >/dev/null 2>&1 || true
        echo "   基础设施已停止"
    else
        echo "   无运行中的基础设施"
    fi
fi

echo ""
echo "✅ Orchestrator V2 已完全停止"
