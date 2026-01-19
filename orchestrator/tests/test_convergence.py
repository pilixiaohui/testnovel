from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from orchestrator import validation
from orchestrator.validation import _archive_verified_tasks
from orchestrator.workflow import _calculate_adaptive_history_window


def _disable_coverage_gate(monkeypatch: pytest.MonkeyPatch, tmp_dir: str) -> None:
    policy = Path(tmp_dir) / "verification_policy.json"
    policy.write_text(
        "\n".join(
            [
                "{",
                '  "version": 1,',
                '  "report_rules": {',
                '    "apply_to": ["REVIEW", "TEST", "FINISH_REVIEW"],',
                '    "require_verdict": true,',
                '    "verdict_prefix": "结论：",',
                '    "verdict_allowed": ["PASS", "FAIL", "BLOCKED"],',
                '    "blocker_prefix": "阻塞：",',
                '    "blocker_clear_value": "无"',
                "  }",
                "}",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(validation, "VERIFICATION_POLICY_FILE", policy)


def test_calculate_adaptive_history_window_shrinks_with_size_and_iteration() -> None:
    assert (
        _calculate_adaptive_history_window(
            iteration=1,
            dev_plan_size=100,
            base_window=10,
            min_window=3,
            max_window=15,
        )
        == 10
    )
    assert (
        _calculate_adaptive_history_window(
            iteration=1,
            dev_plan_size=201,
            base_window=10,
            min_window=3,
            max_window=15,
        )
        == 7
    )
    assert (
        _calculate_adaptive_history_window(
            iteration=1,
            dev_plan_size=301,
            base_window=10,
            min_window=3,
            max_window=15,
        )
        == 3
    )
    assert (
        _calculate_adaptive_history_window(
            iteration=16,
            dev_plan_size=100,
            base_window=10,
            min_window=3,
            max_window=15,
        )
        == 7
    )


def test_check_finish_readiness_allows_todo_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    with TemporaryDirectory() as tmp_dir:
        dev_plan = Path(tmp_dir) / "dev_plan.md"
        dev_plan.write_text(
            "\n".join(
                [
                    "# Dev Plan (Snapshot)",
                    "",
                    "## Milestone M0: Test",
                    "",
                    "### M0-T1: task",
                    "- status: TODO",
                    "- acceptance:",
                    "- ok",
                    "- evidence:",
                    "- none",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(validation, "DEV_PLAN_FILE", dev_plan)
        _disable_coverage_gate(monkeypatch, tmp_dir)
        monkeypatch.setattr(validation, "REQUIRE_ALL_VERIFIED_FOR_FINISH", True)

        is_ready, reason, blockers = validation._check_finish_readiness()
        assert is_ready is True
        assert blockers == []
        assert reason == "所有条件满足"


def test_check_finish_readiness_blocks_done_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    with TemporaryDirectory() as tmp_dir:
        dev_plan = Path(tmp_dir) / "dev_plan.md"
        dev_plan.write_text(
            "\n".join(
                [
                    "# Dev Plan (Snapshot)",
                    "",
                    "## Milestone M0: Test",
                    "",
                    "### M0-T1: task",
                    "- status: DONE",
                    "- acceptance:",
                    "- ok",
                    "- evidence:",
                    "- Iteration X REVIEW: ...",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(validation, "DEV_PLAN_FILE", dev_plan)
        _disable_coverage_gate(monkeypatch, tmp_dir)
        monkeypatch.setattr(validation, "REQUIRE_ALL_VERIFIED_FOR_FINISH", True)

        is_ready, reason, blockers = validation._check_finish_readiness()
        assert is_ready is False
        assert blockers
        assert "非 VERIFIED" in reason


def test_check_finish_readiness_ignores_phase_status_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    dev_plan 扩展格式可能在单个任务块内出现多个 status 行（测试/实现/审阅阶段）。
    FINISH readiness 必须以任务“最终/整体状态”（最后一个 status）为准，而不是把阶段状态当作阻塞。
    """
    with TemporaryDirectory() as tmp_dir:
        dev_plan = Path(tmp_dir) / "dev_plan.md"
        dev_plan.write_text(
            "\n".join(
                [
                    "# Dev Plan (Snapshot)",
                    "",
                    "## Milestone M0: Test",
                    "",
                    "### M0-T1: task",
                    "- acceptance:",
                    "- ok",
                    "- evidence:",
                    "- Iteration 3 REVIEW: ok",
                    "",
                    "#### 测试阶段",
                    "- status: DONE",
                    "- evidence: Iteration 1 TEST: red",
                    "",
                    "#### 实现阶段",
                    "- status: DONE",
                    "- evidence: Iteration 2 DEV: green",
                    "",
                    "#### 审阅阶段",
                    "- status: VERIFIED",
                    "- evidence: Iteration 3 REVIEW: verified",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(validation, "DEV_PLAN_FILE", dev_plan)
        _disable_coverage_gate(monkeypatch, tmp_dir)
        monkeypatch.setattr(validation, "REQUIRE_ALL_VERIFIED_FOR_FINISH", True)

        is_ready, reason, blockers = validation._check_finish_readiness()
        assert is_ready is True
        assert blockers == []
        assert reason == "所有条件满足"


def test_archive_verified_tasks_moves_old_verified_milestones() -> None:
    with TemporaryDirectory() as tmp_dir:
        dev_plan = Path(tmp_dir) / "dev_plan.md"
        archive = Path(tmp_dir) / "dev_plan_archived.md"

        dev_plan.write_text(
            "\n".join(
                [
                    "# Dev Plan (Snapshot)",
                    "",
                    "## Milestone M0: A",
                    "",
                    "### M0-T1: a",
                    "- status: VERIFIED",
                    "- acceptance:",
                    "- ok",
                    "- evidence:",
                    "- Iteration 1 REVIEW: ok",
                    "",
                    "## Milestone M1: B",
                    "",
                    "### M1-T1: b",
                    "- status: VERIFIED",
                    "- acceptance:",
                    "- ok",
                    "- evidence:",
                    "- Iteration 2 REVIEW: ok",
                    "",
                    "## Milestone M2: C",
                    "",
                    "### M2-T1: c",
                    "- status: DONE",
                    "- acceptance:",
                    "- ok",
                    "- evidence:",
                    "- Iteration 3 DEV: ok",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        archive.write_text("# Archive\n", encoding="utf-8")

        archived = _archive_verified_tasks(
            dev_plan_file=dev_plan,
            archive_file=archive,
            keep_recent_milestones=1,
        )
        assert archived == 2

        new_dev_plan = dev_plan.read_text(encoding="utf-8")
        assert "## Milestone M0:" not in new_dev_plan
        assert "## Milestone M1:" not in new_dev_plan
        assert "## Milestone M2:" in new_dev_plan

        archive_text = archive.read_text(encoding="utf-8")
        assert "## Milestone M0:" in archive_text
        assert "## Milestone M1:" in archive_text
