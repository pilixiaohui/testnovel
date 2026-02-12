from pathlib import Path

from orchestrator.config import PROMPTS_DIR


def test_subagent_prompts_enforce_blackboard_permission_contract() -> None:
    required_fragments = (
        "./.orchestrator_ctx/**/*.{md,json}",
        "禁止读取 `orchestrator/`",
        "禁止修改 `./.orchestrator_ctx/`",
        "禁止直接写入 `orchestrator/reports/`",
    )

    prompt_files = sorted(PROMPTS_DIR.glob("subagent_prompt_*.md"))
    assert prompt_files, "no prompt files found"

    for prompt_file in prompt_files:
        if prompt_file.name == "subagent_prompt_main.md":
            continue

        content = prompt_file.read_text(encoding="utf-8")
        missing = [fragment for fragment in required_fragments if fragment not in content]
        assert not missing, f"{prompt_file.name} missing permission fragments: {missing}"
