import tests.unit.models_contract_helpers as model_helpers
import tests.unit.schema_contract_helpers as helpers


def _field_names(cls: type) -> set[str]:
    return set((getattr(cls, "__annotations__", {}) or {}).keys())


def test_schema_anchor_models_exist():
    schema = helpers.get_schema_module()
    cls = helpers.require_class(schema, "StoryAnchor")
    helpers.assert_explicit_label(cls)


def test_schema_anchor_fields():
    schema = helpers.get_schema_module()
    anchor_cls = helpers.require_class(schema, "StoryAnchor")
    helpers.assert_fields_present(
        anchor_cls,
        {
            "id",
            "root_id",
            "branch_id",
            "sequence",
            "anchor_type",
            "description",
            "constraint_type",
            "required_conditions",
            "deadline_scene",
            "achieved",
        },
    )


def test_schema_anchor_indexes():
    schema = helpers.get_schema_module()
    indexes = helpers.collect_index_definitions(schema)
    if not indexes:
        raise AssertionError("schema missing module-level index definitions")

    expected = [
        ("StoryAnchor", ("id",)),
        ("StoryAnchor", ("root_id", "branch_id")),
    ]

    missing = [
        (label, props)
        for label, props in expected
        if not helpers.index_present(indexes, label, props)
    ]
    if missing:
        raise AssertionError(f"schema missing required index definitions: {missing}")


def test_schema_anchor_defaults():
    schema = helpers.get_schema_module()
    anchor_cls = helpers.require_class(schema, "StoryAnchor")
    anchor = helpers.build_instance(
        anchor_cls,
        id="root:anchor:1",
        root_id="root",
        branch_id="main",
        sequence=1,
        anchor_type="inciting_incident",
        description="desc",
        constraint_type="hard",
        required_conditions="{}",
    )
    helpers.assert_default_values(anchor, {"achieved": False, "deadline_scene": None})


def test_models_anchor_fields_match_schema():
    schema = helpers.get_schema_module()
    schema_cls = helpers.require_class(schema, "StoryAnchor")
    model_cls = model_helpers.require_model("StoryAnchor")

    missing = _field_names(schema_cls) - _field_names(model_cls)
    if missing:
        raise AssertionError(f"models.StoryAnchor missing fields: {sorted(missing)}")


def test_models_anchor_defaults():
    model_cls = model_helpers.require_model("StoryAnchor")
    anchor = model_cls(
        id="root:anchor:1",
        root_id="root",
        branch_id="main",
        sequence=1,
        anchor_type="inciting_incident",
        description="desc",
        constraint_type="hard",
        required_conditions="{}",
    )
    assert anchor.achieved is False
    assert anchor.deadline_scene is None
