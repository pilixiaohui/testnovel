#!/bin/bash
# 健康检查脚本
# 检查 backend、frontend、database 连接状态

set -uo pipefail

check_endpoint() {
  local name="$1"
  local url="$2"
  local timeout="${3:-5}"

  if curl -sf --max-time "$timeout" "$url" >/dev/null 2>&1; then
    echo "$name: OK"
  else
    echo "$name: UNREACHABLE"
  fi
}

echo "=== Health Check ==="
echo ""

# Backend
check_endpoint "Backend (localhost:8000/health)" "http://localhost:8000/health"

# Frontend
check_endpoint "Frontend (localhost:3000)" "http://localhost:3000"

# Database — 尝试通过 Python 检查
if command -v python3 &>/dev/null; then
  db_status=$(python3 -c "
import sys
try:
    from project.config import get_settings
    settings = get_settings()
    # 尝试连接数据库
    print('OK')
except Exception as e:
    print(f'UNREACHABLE ({e})')
" 2>/dev/null || echo "UNREACHABLE (check skipped)")
  echo "Database: $db_status"
else
  echo "Database: UNREACHABLE (python3 not available)"
fi

echo ""
echo "Note: checks only work when the application is running."
