#!/bin/bash
# 应用日志查看脚本
# 用法: bash scripts/app_logs.sh [--tail N] [--grep PATTERN]

set -uo pipefail

TAIL_LINES=50
GREP_PATTERN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tail)
      TAIL_LINES="$2"
      shift 2
      ;;
    --grep)
      GREP_PATTERN="$2"
      shift 2
      ;;
    *)
      echo "Usage: $0 [--tail N] [--grep PATTERN]"
      exit 1
      ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Application Logs ==="
echo ""

# 扫描 backend 日志文件
found_logs=false
for log_dir in "$ROOT/project/backend" "$ROOT/project/backend/logs"; do
  if [[ -d "$log_dir" ]]; then
    for log_file in "$log_dir"/*.log; do
      [[ -f "$log_file" ]] || continue
      found_logs=true
      echo "--- $log_file ---"
      if [[ -n "$GREP_PATTERN" ]]; then
        tail -n "$TAIL_LINES" "$log_file" | grep --color=auto "$GREP_PATTERN" || echo "(no matches)"
      else
        tail -n "$TAIL_LINES" "$log_file"
      fi
      echo ""
    done
  fi
done

# Docker 容器日志（排除 orch-agent 容器）
if command -v docker &>/dev/null; then
  containers=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -v 'orch-agent' || true)
  if [[ -n "$containers" ]]; then
    echo "=== Docker Container Logs ==="
    echo ""
    while IFS= read -r container; do
      echo "--- $container ---"
      if [[ -n "$GREP_PATTERN" ]]; then
        docker logs --tail "$TAIL_LINES" "$container" 2>&1 | grep --color=auto "$GREP_PATTERN" || echo "(no matches)"
      else
        docker logs --tail "$TAIL_LINES" "$container" 2>&1
      fi
      echo ""
    done <<< "$containers"
  fi
fi

if [[ "$found_logs" == "false" ]]; then
  echo "No log files found in project/backend/ or project/backend/logs/"
  echo "Docker containers: $(docker ps --format '{{.Names}}' 2>/dev/null | grep -v 'orch-agent' | tr '\n' ' ' || echo 'none')"
fi
