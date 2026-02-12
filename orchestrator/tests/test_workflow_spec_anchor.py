import orchestrator.workflow as workflow


def test_guarded_blackboard_paths_include_spec_workflow_artifacts() -> None:
    guarded_paths = workflow._guarded_blackboard_paths()

    assert workflow.SPECS_CONSTITUTION_FILE in guarded_paths
    assert workflow.SPECS_STATE_FILE in guarded_paths
