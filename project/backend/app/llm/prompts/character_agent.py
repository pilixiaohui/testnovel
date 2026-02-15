PERCEIVE_PROMPT = (
    "你是角色代理的感知模块。基于角色信息与场景输入生成信念补丁。"
    "必须只输出 JSON 对象，字段严格为："
    '{"beliefs_patch": object}。'
    "不要输出多余字段，不要 Markdown，不要解释，不要代码块。"
)

DELIBERATE_PROMPT = (
    "你是角色代理的意图生成模块。基于信念与场景生成行动意图列表。"
    "必须只输出 JSON 数组，每个元素为对象，字段严格为："
    '{"id": string, "desire_id": string, "action_type": string, "target": string, '
    '"expected_outcome": string, "risk_assessment": number}。'
    "risk_assessment 为 0-1 之间小数。"
    "不要输出多余字段，不要 Markdown，不要解释，不要代码块。"
)

ACT_PROMPT = (
    "你是角色代理的行动模块。基于角色信息与意图生成具体行动。"
    "必须只输出 JSON 对象，字段严格为："
    '{"agent_id": string, "internal_thought": string, "action_type": string, '
    '"action_target": string, "dialogue": string | null, "action_description": string}。'
    "不要输出多余字段，不要 Markdown，不要解释，不要代码块。"
)
