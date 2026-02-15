import tests.unit.models_contract_helpers as model_helpers
import tests.unit.schema_contract_helpers as helpers


def _field_names(cls: type) -> set[str]:
    return set((getattr(cls, "__annotations__", {}) or {}).keys())


def test_schema_simulation_models_exist():
    schema = helpers.get_schema_module()
    cls = helpers.require_class(schema, "SimulationLog")
    helpers.assert_explicit_label(cls)


def test_schema_simulation_fields():
    schema = helpers.get_schema_module()
    log_cls = helpers.require_class(schema, "SimulationLog")
    helpers.assert_fields_present(
        log_cls,
        {
            "id",
            "scene_version_id",
            "round_number",
            "agent_actions",
            "dm_arbitration",
            "narrative_events",
            "sensory_seeds",
            "convergence_score",
            "drama_score",
            "info_gain",
            "stagnation_count",
        },
    )


def test_schema_simulation_indexes():
    schema = helpers.get_schema_module()
    indexes = helpers.collect_index_definitions(schema)
    if not indexes:
        raise AssertionError("schema missing module-level index definitions")

    expected = [
        ("SimulationLog", ("id",)),
        ("SimulationLog", ("scene_version_id",)),
    ]

    missing = [
        (label, props)
        for label, props in expected
        if not helpers.index_present(indexes, label, props)
    ]
    if missing:
        raise AssertionError(f"schema missing required index definitions: {missing}")


def test_schema_simulation_defaults():
    schema = helpers.get_schema_module()
    log_cls = helpers.require_class(schema, "SimulationLog")
    log = helpers.build_instance(
        log_cls,
        id="sim:scene:round:1",
        scene_version_id="scene-version-1",
        round_number=1,
        agent_actions="[]",
        dm_arbitration="{}",
        narrative_events="[]",
        sensory_seeds="[]",
        convergence_score=0.5,
        drama_score=0.4,
        info_gain=0.3,
    )
    helpers.assert_default_values(log, {"stagnation_count": 0})


def test_models_simulation_fields_match_schema():
    schema = helpers.get_schema_module()
    schema_cls = helpers.require_class(schema, "SimulationLog")
    model_cls = model_helpers.require_model("SimulationLog")

    missing = _field_names(schema_cls) - _field_names(model_cls)
    if missing:
        raise AssertionError(f"models.SimulationLog missing fields: {sorted(missing)}")


def test_models_simulation_defaults():
    model_cls = model_helpers.require_model("SimulationLog")
    log = model_cls(
        id="sim:scene:round:1",
        scene_version_id="scene-version-1",
        round_number=1,
        agent_actions="[]",
        dm_arbitration="{}",
        narrative_events="[]",
        sensory_seeds="[]",
        convergence_score=0.5,
        drama_score=0.4,
        info_gain=0.3,
    )
    assert log.stagnation_count == 0
