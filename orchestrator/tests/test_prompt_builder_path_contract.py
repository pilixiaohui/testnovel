from pathlib import Path

from orchestrator.prompt_builder import _build_blackboard_access_rules, _build_dispatch_path_contract


def test_build_blackboard_access_rules_with_reports_forbidden() -> None:
    rules = _build_blackboard_access_rules(forbid_reports_write=True)
    assert len(rules) == 3
    assert any(".orchestrator_ctx/**/*.{md,json}" in line for line in rules)
    assert any("禁止修改 `./.orchestrator_ctx/`" in line for line in rules)
    assert any("禁止直接写入 `orchestrator/reports/`" in line for line in rules)


def test_build_blackboard_access_rules_without_reports_forbidden() -> None:
    rules = _build_blackboard_access_rules(forbid_reports_write=False)
    assert len(rules) == 2
    assert all("orchestrator/reports" not in line for line in rules)


def test_build_dispatch_path_contract_with_active_change_id() -> None:
    contract = _build_dispatch_path_contract(
        agent_cwd=Path('/home/zxh/ainovel_v3/project'),
        active_change_id='CHG-0009',
    )

    assert 'agent_cwd: /home/zxh/ainovel_v3/project' in contract
    assert 'mirror_root: /home/zxh/ainovel_v3/project/.orchestrator_ctx' in contract
    assert 'specs_visible_root: /home/zxh/ainovel_v3/project/.orchestrator_ctx/memory/specs' in contract
    assert 'changes/CHG-0009/tasks.md' in contract


def test_build_dispatch_path_contract_without_active_change_id_uses_placeholder() -> None:
    contract = _build_dispatch_path_contract(
        agent_cwd=Path('/tmp/project'),
        active_change_id=None,
    )

    assert 'changes/<change_id>/tasks.md' in contract
