from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import LOG_SUMMARY_CONFIG_FILE
from .file_ops import _atomic_write_text, _read_text, _require_file

_SUMMARY_SYSTEM_INSTRUCTION = (
    "你是日志分析助手，目标是快速让用户理解代理当前在做什么。"
    "输出要求：中文、简短、直指要点。"
    "必须包含：修改思路、具体操作、与需求/规范的符合性评估、风险或待确认项。"
)


@dataclass(frozen=True)
class LogSummaryConfig:
    base_url: str
    api_key: str
    model: str


def _require_non_empty_str(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def load_log_summary_config(path: Path = LOG_SUMMARY_CONFIG_FILE) -> LogSummaryConfig:
    _require_file(path)
    data = json.loads(_read_text(path))
    if not isinstance(data, dict):
        raise ValueError("log summary config must be a JSON object")
    return LogSummaryConfig(
        base_url=_require_non_empty_str(data, "base_url"),
        api_key=_require_non_empty_str(data, "api_key"),
        model=_require_non_empty_str(data, "model"),
    )


def save_log_summary_config(
    payload: dict[str, Any], path: Path = LOG_SUMMARY_CONFIG_FILE
) -> LogSummaryConfig:
    if not isinstance(payload, dict):
        raise ValueError("log summary config payload must be an object")
    config = LogSummaryConfig(
        base_url=_require_non_empty_str(payload, "base_url"),
        api_key=_require_non_empty_str(payload, "api_key"),
        model=_require_non_empty_str(payload, "model"),
    )
    body = json.dumps(
        {"base_url": config.base_url, "api_key": config.api_key, "model": config.model},
        ensure_ascii=False,
        indent=2,
    )
    _atomic_write_text(path, body + "\n")
    return config


def _build_prompt(logs: str) -> str:
    if not logs.strip():
        raise ValueError("logs must not be empty")
    return (
        "请基于以下日志增量输出简要总结（4-6条，条目化）。\n"
        "必须包含：\n"
        "1) 修改思路\n"
        "2) 具体操作\n"
        "3) 对比需求的符合性/规范性评估\n"
        "4) 风险或待确认项\n"
        "日志：\n"
        f"{logs.strip()}"
    )


def _post_json(*, url: str, payload: dict[str, Any], timeout_seconds: float = 30.0) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read()
        if response.status != 200:
            raise RuntimeError(f"LLM request failed: status={response.status}")
    return json.loads(raw.decode("utf-8"))


def summarize_logs(*, logs: str, config: LogSummaryConfig) -> str:
    prompt = _build_prompt(logs)
    base_url = config.base_url.rstrip("/")
    endpoint = f"{base_url}/v1beta/models/{config.model}:generateContent"
    url = f"{endpoint}?{urlencode({'key': config.api_key})}"
    payload = {
        "systemInstruction": {"parts": [{"text": _SUMMARY_SYSTEM_INSTRUCTION}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                ],
            }
        ],
        "generationConfig": {"temperature": 0.2, "topP": 1},
    }
    data = _post_json(url=url, payload=payload)
    candidates = data["candidates"]
    if not candidates:
        raise ValueError("LLM response missing candidates")
    parts = candidates[0]["content"]["parts"]
    text = "".join(part["text"] for part in parts)
    if not text.strip():
        raise ValueError("LLM response text is empty")
    return text.strip()
