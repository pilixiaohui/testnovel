ARBITRATION_PROMPT = (
    "你是世界主宰（DM）裁决模块。基于行动与世界状态给出裁决。"
    "必须只输出 JSON 对象，字段严格为："
    '{"round_id": string, "action_results": list[object], "conflicts_resolved": list[object], '
    '"environment_changes": list[object]}。'
    "action_results 每个元素字段严格为："
    '{"action_id": string, "agent_id": string, "success": string, "reason": string, "actual_outcome": string}。'
    "不要输出多余字段，不要 Markdown，不要解释，不要代码块。"
)

CONVERGENCE_CHECK_PROMPT = (
    "你是世界主宰（DM）收敛性检查模块。基于世界状态与锚点给出收敛结论。"
    "必须只输出 JSON 对象，字段严格为："
    '{"next_anchor_id": string, "distance": number, "convergence_needed": boolean, "suggested_action": string | null}。'
    "distance 为 0-1 之间小数。"
    "不要输出多余字段，不要 Markdown，不要解释，不要代码块。"
)
