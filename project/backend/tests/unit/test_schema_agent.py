import tests.unit.models_contract_helpers as model_helpers
import tests.unit.schema_contract_helpers as helpers


def _field_names(cls: type) -> set[str]:
    return set((getattr(cls, "__annotations__", {}) or {}).keys())


def test_schema_agent_models_exist():
    schema = helpers.get_schema_module()
    cls = helpers.require_class(schema, "CharacterAgentState")
    helpers.assert_explicit_label(cls)


def test_schema_agent_fields():
    schema = helpers.get_schema_module()
    agent_cls = helpers.require_class(schema, "CharacterAgentState")
    helpers.assert_fields_present(
        agent_cls,
        {
            "id",
            "character_id",
            "branch_id",
            "beliefs",
            "desires",
            "intentions",
            "memory",
            "private_knowledge",
            "last_updated_scene",
            "version",
        },
    )


def test_schema_agent_indexes():
    schema = helpers.get_schema_module()
    indexes = helpers.collect_index_definitions(schema)
    if not indexes:
        raise AssertionError("schema missing module-level index definitions")

    expected = [
        ("CharacterAgentState", ("id",)),
        ("CharacterAgentState", ("character_id",)),
        ("CharacterAgentState", ("branch_id",)),
    ]

    missing = [
        (label, props)
        for label, props in expected
        if not helpers.index_present(indexes, label, props)
    ]
    if missing:
        raise AssertionError(f"schema missing required index definitions: {missing}")


def test_schema_agent_defaults():
    schema = helpers.get_schema_module()
    agent_cls = helpers.require_class(schema, "CharacterAgentState")
    agent = helpers.build_instance(
        agent_cls,
        id="agent:char-1",
        character_id="char-1",
        branch_id="main",
        beliefs="{}",
        desires="[]",
        intentions="[]",
        memory="[]",
        private_knowledge="{}",
        last_updated_scene=1,
    )
    helpers.assert_default_values(agent, {"version": 1})


def test_models_agent_fields_match_schema():
    schema = helpers.get_schema_module()
    schema_cls = helpers.require_class(schema, "CharacterAgentState")
    model_cls = model_helpers.require_model("CharacterAgentState")

    missing = _field_names(schema_cls) - _field_names(model_cls)
    if missing:
        raise AssertionError(
            f"models.CharacterAgentState missing fields: {sorted(missing)}"
        )


def test_models_agent_defaults():
    model_cls = model_helpers.require_model("CharacterAgentState")
    agent = model_cls(
        id="agent:char-1",
        character_id="char-1",
        branch_id="main",
        beliefs="{}",
        desires="[]",
        intentions="[]",
        memory="[]",
        private_knowledge="{}",
        last_updated_scene=1,
    )
    assert agent.version == 1
