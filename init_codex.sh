#!/usr/bin/env bash
# 用法: source ./init_codex.sh
set -euo pipefail

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "请使用 'source ${BASH_SOURCE[0]}' 来执行此脚本，以便正确设置 CODEX_HOME 环境变量。" >&2
  exit 1
fi

SOURCE_DIR="/home/zxh/.codex"
SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
TARGET_DIR="$PROJECT_ROOT/.codex"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "未找到源目录 $SOURCE_DIR" >&2
  return 1
fi

mkdir -p "$TARGET_DIR"

copy_count=0

shopt -s nullglob
for cfg in "$SOURCE_DIR"/*.toml "$SOURCE_DIR"/*.json; do
  filename="$(basename "$cfg")"
  dest="$TARGET_DIR/$filename"
  if [[ -f "$dest" ]]; then
    continue
  fi
  cp "$cfg" "$dest"
  copy_count=$((copy_count + 1))
  echo "已复制配置文件: $filename"
done
shopt -u nullglob

agents_src="$SOURCE_DIR/AGENTS.md"
agents_dest="$TARGET_DIR/AGENTS.md"
if [[ -f "$agents_src" ]]; then
  if [[ ! -f "$agents_dest" ]]; then
    cp "$agents_src" "$agents_dest"
    copy_count=$((copy_count + 1))
    echo "已复制文档: AGENTS.md"
  fi
else
  echo "警告：未找到 $agents_src" >&2
fi

prompt_files=(
  "subagent_prompt_dev.md"
  "subagent_prompt_review.md"
  "subagent_prompt_test.md"
)

for prompt in "${prompt_files[@]}"; do
  prompt_src="$SOURCE_DIR/$prompt"
  prompt_dest="$TARGET_DIR/$prompt"
  if [[ -f "$prompt_src" ]]; then
    if [[ ! -f "$prompt_dest" ]]; then
      cp "$prompt_src" "$prompt_dest"
      copy_count=$((copy_count + 1))
      echo "已复制子代理规范: $prompt"
    fi
  else
    echo "警告：未找到 $prompt_src" >&2
  fi
done

if [[ $copy_count -eq 0 ]]; then
  echo "没有需要新增的配置文件或文档，跳过复制。"
fi

export CODEX_HOME="$TARGET_DIR"
echo "CODEX_HOME 已设置为 $CODEX_HOME"

if [[ -d "$PROJECT_ROOT" ]]; then
  export SERENA_PROJECT="$PROJECT_ROOT"
  export CODEX_PROJECT_ROOT="$PROJECT_ROOT"
  echo "Serena 项目已自动激活：$SERENA_PROJECT"
else
  echo "警告：未找到项目目录 $PROJECT_ROOT，无法自动激活 Serena 项目。" >&2
fi

return 0
