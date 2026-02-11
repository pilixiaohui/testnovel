import orchestrator.codex_runner as codex_runner


def test_resolve_agent_permissions_main_forces_read_only() -> None:
    sandbox_mode, approval_policy = codex_runner._resolve_agent_permissions(
        agent="MAIN",
        sandbox_mode="workspace-write",
        approval_policy="auto-edit",
    )

    assert sandbox_mode == codex_runner.MAIN_SANDBOX_MODE
    assert approval_policy == codex_runner.MAIN_APPROVAL_POLICY


def test_resolve_agent_permissions_non_main_keeps_input() -> None:
    sandbox_mode, approval_policy = codex_runner._resolve_agent_permissions(
        agent="IMPLEMENTER",
        sandbox_mode="workspace-write",
        approval_policy="on-request",
    )

    assert sandbox_mode == "workspace-write"
    assert approval_policy == "on-request"
