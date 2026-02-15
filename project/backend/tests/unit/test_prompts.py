from .llm_contract_helpers import (
    get_prompt_submodule,
    get_prompts_module,
    require_prompt,
)


def test_step5_prompts_present():
    prompts = get_prompts_module()
    require_prompt(prompts, "SNOWFLAKE_STEP5A_SYSTEM_PROMPT")
    require_prompt(prompts, "SNOWFLAKE_STEP5B_SYSTEM_PROMPT")
    require_prompt(prompts, "STORY_ANCHORS_SYSTEM_PROMPT")


def test_character_agent_prompts_present():
    prompts = get_prompt_submodule("character_agent")
    require_prompt(prompts, "PERCEIVE_PROMPT")
    require_prompt(prompts, "DELIBERATE_PROMPT")
    require_prompt(prompts, "ACT_PROMPT")


def test_world_master_prompts_present():
    prompts = get_prompt_submodule("world_master")
    require_prompt(prompts, "ARBITRATION_PROMPT")
    require_prompt(prompts, "CONVERGENCE_CHECK_PROMPT")


def test_renderer_prompt_present():
    prompts = get_prompt_submodule("renderer")
    require_prompt(prompts, "SMART_RENDER_PROMPT")
