import pytest

import orchestrator.workflow as workflow


def test_validate_artifact_update_file_for_change_accepts_allowed_artifacts() -> None:
    workflow._validate_artifact_update_file_for_change(
        relative_path="changes/CHG-0001/tasks.md",
        active_change_id="CHG-0001",
    )


def test_validate_artifact_update_file_for_change_rejects_other_change() -> None:
    with pytest.raises(ValueError, match="active change"):
        workflow._validate_artifact_update_file_for_change(
            relative_path="changes/CHG-9999/tasks.md",
            active_change_id="CHG-0001",
        )


def test_validate_artifact_update_file_for_change_rejects_unknown_artifact() -> None:
    with pytest.raises(ValueError, match="supported change artifact"):
        workflow._validate_artifact_update_file_for_change(
            relative_path="changes/CHG-0001/notes.md",
            active_change_id="CHG-0001",
        )
