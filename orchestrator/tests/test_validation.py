import pytest

from orchestrator.validation import _validate_history_append, _validate_task_content


def test_validate_history_append_ok() -> None:
    entry = "## Iteration 3:\n- dev_plan: no change"
    assert _validate_history_append(iteration=3, entry=entry) == entry


def test_validate_history_append_requires_dev_plan() -> None:
    entry = "## Iteration 2:\n- note: missing dev_plan"
    with pytest.raises(RuntimeError):
        _validate_history_append(iteration=2, entry=entry)


def test_validate_task_content_ok() -> None:
    task = "# Current Task (Iteration 1)\nassigned_agent: DEV\n- do something"
    assert _validate_task_content(iteration=1, expected_agent="DEV", task=task) == task


def test_validate_task_content_requires_agent() -> None:
    task = "# Current Task (Iteration 1)\n- no agent"
    with pytest.raises(RuntimeError):
        _validate_task_content(iteration=1, expected_agent="DEV", task=task)
