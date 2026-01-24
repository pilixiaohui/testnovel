from orchestrator.progress import _parse_dev_plan_progress


def test_parse_dev_plan_progress_counts() -> None:
    dev_plan = """
# Dev Plan

## Milestone M0: Setup

### M0-T1: Task One
- status: DONE

### M0-T2: Task Two
- status: VERIFIED

## Milestone M1: Next

### M1-T1: Task Three
- status: TODO
""".strip()

    progress = _parse_dev_plan_progress(text=dev_plan)
    assert progress["total_tasks"] == 3
    assert progress["completed_tasks"] == 2
    assert progress["verified_tasks"] == 1
    assert progress["todo_tasks"] == 1
    assert progress["current_milestone"] == "M1"
    assert progress["milestones"][0]["milestone_id"] == "M0"
    assert progress["milestones"][0]["percentage"] == 100.0
    assert progress["milestones"][1]["milestone_id"] == "M1"
    assert progress["milestones"][1]["percentage"] == 0.0
    assert len(progress["tasks"]) == 3
    assert progress["tasks"][0]["task_id"] == "M0-T1"
    assert progress["tasks"][0]["title"] == "Task One"
    assert progress["tasks"][0]["status"] == "DONE"
    assert progress["tasks"][0]["milestone_id"] == "M0"
    assert progress["tasks"][2]["task_id"] == "M1-T1"
    assert progress["tasks"][2]["title"] == "Task Three"
