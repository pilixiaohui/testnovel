from __future__ import annotations

import json
import re

from .contracts import VALID_OVERALL_VERDICTS


def _extract_json_text(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        raise RuntimeError("SYNTHESIZER output is empty")

    # 1) 直接 JSON
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    # 2) fenced code block
    code_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    for block in code_blocks:
        candidate = block.strip()
        if candidate.startswith("{") and candidate.endswith("}"):
            return candidate

    # 3) 提取最外层大括号
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()

    raise RuntimeError("SYNTHESIZER output does not contain JSON object")


def parse_synthesizer_output(*, output_text: str) -> dict[str, object]:
    json_text = _extract_json_text(output_text)
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"SYNTHESIZER JSON parse failed: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("SYNTHESIZER output must be a JSON object")

    verdict = payload.get("overall_verdict")
    if not isinstance(verdict, str) or verdict.upper() not in VALID_OVERALL_VERDICTS:
        raise RuntimeError("SYNTHESIZER output missing valid overall_verdict")

    for list_field in ("decision_basis", "blockers", "recommendations"):
        value = payload.get(list_field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise RuntimeError(f"SYNTHESIZER output field {list_field} must be string list")

    payload["overall_verdict"] = verdict.upper()
    return payload
