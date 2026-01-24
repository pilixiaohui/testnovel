#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KUZU_DATA_DIR="${KUZU_DATA_DIR:?KUZU_DATA_DIR is required}"

BACKUP_DIR="${ROOT_DIR}/.tmp/kuzu_backup_$(date +%Y%m%d%H%M%S)"
mkdir -p "${BACKUP_DIR}"
cp -a "${KUZU_DATA_DIR}" "${BACKUP_DIR}/"
rm -rf "${KUZU_DATA_DIR}"

legacy_files=(
  "${ROOT_DIR}/project/backend/app/storage/graph.py"
  "${ROOT_DIR}/project/backend/app/storage/migrations.py"
)

for legacy_file in "${legacy_files[@]}"; do
  if [ ! -f "${legacy_file}" ]; then
    echo "legacy file not found: ${legacy_file}" >&2
    exit 1
  fi
  rm "${legacy_file}"
done

: > "${ROOT_DIR}/project/backend/app/storage/__init__.py"

find "${ROOT_DIR}" -type d -name "__pycache__" -prune -exec rm -rf {} +
rm -rf "${ROOT_DIR}/.pytest_cache"
