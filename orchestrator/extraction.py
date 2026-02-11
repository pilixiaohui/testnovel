"""
extraction.py - 鲁棒的验证信息提取模块

提供多层降级策略从 IMPLEMENTER 报告中提取验证信息：
1. YAML 提取 → 2. JSON 提取 → 3. 正则提取 → 4. 原文降级

同时提供容错的 JSON 提取函数用于解析验证器输出。
"""
from __future__ import annotations

import json
import re
from typing import Any

from .types import ExtractedValidationInfo


def extract_validation_info(report: str) -> ExtractedValidationInfo:
    """
    多层降级策略提取验证信息。

    Args:
        report: IMPLEMENTER 报告内容

    Returns:
        ExtractedValidationInfo: 提取的验证信息
    """
    if not report:
        return {"extraction_method": "fallback", "raw_yaml": ""}

    # 1. 尝试 YAML 提取
    result = _extract_from_yaml(report)
    if result:
        return result

    # 2. 尝试 JSON 提取
    result = _extract_from_json(report)
    if result:
        return result

    # 3. 尝试正则提取
    result = _extract_from_regex(report)
    if result:
        return result

    # 4. 原文降级
    return {
        "raw_yaml": report[:2000],
        "extraction_method": "fallback",
    }


def _extract_from_yaml(report: str) -> ExtractedValidationInfo | None:
    """
    从报告中提取 YAML 格式的验证信息。

    查找 "## 验证信息" 小节下的 YAML 代码块。
    """
    lines = report.splitlines()
    in_validation_section = False
    yaml_content: list[str] = []
    in_yaml_block = False

    for line in lines:
        # 检测验证信息小节开始
        if "## 验证信息" in line:
            in_validation_section = True
            continue

        # 检测下一个二级标题（验证信息小节结束）
        if in_validation_section and line.startswith("## ") and "验证信息" not in line:
            break

        if not in_validation_section:
            continue

        # 检测 YAML 代码块
        if line.strip().startswith("```yaml"):
            in_yaml_block = True
            continue
        if line.strip() == "```" and in_yaml_block:
            in_yaml_block = False
            continue

        if in_yaml_block:
            yaml_content.append(line)

    if not yaml_content:
        return None

    yaml_text = "\n".join(yaml_content)

    # 尝试解析 YAML 提取结构化信息
    result: ExtractedValidationInfo = {
        "raw_yaml": yaml_text,
        "extraction_method": "yaml",
    }

    # 简单解析常见字段（不依赖 PyYAML）
    test_commands = _extract_yaml_list(yaml_text, "test_commands")
    if test_commands:
        result["test_commands"] = test_commands

    api_signatures = _extract_yaml_list(yaml_text, "api_signatures")
    if api_signatures:
        result["api_signatures"] = api_signatures

    modified_files = _extract_yaml_list(yaml_text, "modified_files")
    if modified_files:
        result["modified_files"] = modified_files

    return result


def _extract_yaml_list(yaml_text: str, key: str) -> list[str]:
    """从 YAML 文本中提取列表字段"""
    result: list[str] = []
    lines = yaml_text.splitlines()
    in_list = False

    for line in lines:
        # 检测列表开始
        if line.strip().startswith(f"{key}:"):
            in_list = True
            continue

        if in_list:
            # 检测列表项
            if line.strip().startswith("- "):
                item = line.strip()[2:].strip()
                # 移除引号
                if (item.startswith('"') and item.endswith('"')) or \
                   (item.startswith("'") and item.endswith("'")):
                    item = item[1:-1]
                result.append(item)
            # 检测列表结束（遇到非缩进行或新的键）
            elif line.strip() and not line.startswith(" ") and not line.startswith("\t"):
                break

    return result


def _extract_from_json(report: str) -> ExtractedValidationInfo | None:
    """
    从报告中提取 JSON 格式的验证信息。

    查找 JSON 代码块或内联 JSON 对象。
    """
    # 查找 JSON 代码块
    json_block_pattern = r"```json\s*([\s\S]*?)\s*```"
    matches = re.findall(json_block_pattern, report)

    for match in matches:
        try:
            data = json.loads(match)
            if isinstance(data, dict):
                result: ExtractedValidationInfo = {
                    "extraction_method": "json",
                }

                if "test_commands" in data and isinstance(data["test_commands"], list):
                    result["test_commands"] = [str(c) for c in data["test_commands"]]

                if "api_signatures" in data and isinstance(data["api_signatures"], list):
                    result["api_signatures"] = [str(s) for s in data["api_signatures"]]

                if "modified_files" in data and isinstance(data["modified_files"], list):
                    result["modified_files"] = [str(f) for f in data["modified_files"]]

                if any(k in result for k in ["test_commands", "api_signatures", "modified_files"]):
                    return result
        except json.JSONDecodeError:
            continue

    return None


def _extract_from_regex(report: str) -> ExtractedValidationInfo | None:
    """
    使用正则表达式从报告中提取验证信息。

    作为 YAML/JSON 提取失败时的降级方案。
    """
    result: ExtractedValidationInfo = {
        "extraction_method": "regex",
    }

    # 提取测试命令（常见模式）
    test_cmd_patterns = [
        r"pytest\s+[\w/\-\.]+",
        r"python\s+-m\s+pytest\s+[\w/\-\.]+",
        r"npm\s+(?:run\s+)?test",
        r"yarn\s+test",
    ]
    test_commands: list[str] = []
    for pattern in test_cmd_patterns:
        matches = re.findall(pattern, report)
        test_commands.extend(matches)
    if test_commands:
        result["test_commands"] = list(set(test_commands))

    # 提取修改的文件（常见模式）
    file_patterns = [
        r"(?:修改|创建|更新|删除)(?:了)?(?:文件)?[：:]\s*`?([a-zA-Z0-9_/\-\.]+\.[a-zA-Z]+)`?",
        r"(?:Modified|Created|Updated|Deleted)[：:]?\s*`?([a-zA-Z0-9_/\-\.]+\.[a-zA-Z]+)`?",
    ]
    modified_files: list[str] = []
    for pattern in file_patterns:
        matches = re.findall(pattern, report, re.IGNORECASE)
        modified_files.extend(matches)
    if modified_files:
        result["modified_files"] = list(set(modified_files))

    # 如果提取到任何信息，返回结果
    if "test_commands" in result or "modified_files" in result:
        return result

    return None


def _extract_balanced_json(text: str, required_key: str) -> dict[str, Any] | None:
    """在文本中查找包含 required_key 的 JSON 对象，使用平衡括号匹配。

    比简单正则更鲁棒，能正确处理嵌套的 {} 和 []。
    """
    search_key = f'"{required_key}"'
    start_pos = 0
    while True:
        key_idx = text.find(search_key, start_pos)
        if key_idx == -1:
            return None

        # 向前找到最近的 '{'
        brace_idx = text.rfind("{", 0, key_idx)
        if brace_idx == -1:
            start_pos = key_idx + len(search_key)
            continue

        # 从 brace_idx 开始，计数括号深度找到匹配的 '}'
        depth = 0
        in_string = False
        escape_next = False
        i = brace_idx
        while i < len(text):
            ch = text[i]
            if escape_next:
                escape_next = False
                i += 1
                continue
            if ch == "\\":
                if in_string:
                    escape_next = True
                i += 1
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
            elif not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[brace_idx : i + 1]
                        try:
                            parsed = json.loads(candidate)
                            if isinstance(parsed, dict) and required_key in parsed:
                                return parsed
                        except json.JSONDecodeError:
                            pass
                        break
            i += 1

        start_pos = key_idx + len(search_key)


def extract_validator_output(output: str) -> dict[str, Any] | None:
    """
    从验证器输出提取 JSON，带容错处理。

    支持多种 JSON 格式和常见问题修复。

    Args:
        output: 验证器输出文本

    Returns:
        解析后的 JSON 对象，或 None（解析失败时）
    """
    if not output:
        return None

    # 1. 尝试直接解析整个输出
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        pass

    # 2. 查找 JSON 代码块
    json_block_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    matches = re.findall(json_block_pattern, output)
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    # 3. 查找包含 "validator" 或 "verdict" 的 JSON 对象（平衡括号匹配）
    result = _extract_balanced_json(output, required_key="validator")
    if result is not None:
        return result
    result = _extract_balanced_json(output, required_key="verdict")
    if result is not None:
        return result

    # 4. 尝试修复常见 JSON 问题
    # 查找最外层的 { }
    start = output.find("{")
    end = output.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = output[start:end + 1]

        # 修复常见问题
        # 4.1 移除尾部逗号
        json_str = re.sub(r",\s*([}\]])", r"\1", json_str)

        # 4.2 修复单引号
        json_str = json_str.replace("'", '"')

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    return None


def extract_test_commands_from_report(report: str) -> list[str]:
    """
    从报告中提取测试命令列表。

    便捷函数，用于快速获取测试命令。
    """
    info = extract_validation_info(report)
    return info.get("test_commands", [])


def extract_modified_files_from_report(report: str) -> list[str]:
    """
    从报告中提取修改文件列表。

    便捷函数，用于快速获取修改文件。
    """
    info = extract_validation_info(report)
    return info.get("modified_files", [])
