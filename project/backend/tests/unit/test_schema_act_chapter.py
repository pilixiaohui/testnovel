import tests.unit.schema_contract_helpers as helpers


def test_schema_act_chapter_models_exist():
    schema = helpers.get_schema_module()

    for name in ("Act", "Chapter"):
        cls = helpers.require_class(schema, name)
        helpers.assert_explicit_label(cls)


def test_schema_act_chapter_fields():
    schema = helpers.get_schema_module()

    act_cls = helpers.require_class(schema, "Act")
    helpers.assert_fields_present(
        act_cls,
        {"id", "root_id", "sequence", "title", "purpose", "tone"},
    )

    chapter_cls = helpers.require_class(schema, "Chapter")
    helpers.assert_fields_present(
        chapter_cls,
        {"id", "act_id", "sequence", "title", "focus", "pov_character_id"},
    )


def test_schema_act_chapter_indexes():
    schema = helpers.get_schema_module()
    indexes = helpers.collect_index_definitions(schema)
    if not indexes:
        raise AssertionError("schema missing module-level index definitions")

    expected = [
        ("Act", ("id",)),
        ("Act", ("root_id",)),
        ("Chapter", ("id",)),
        ("Chapter", ("act_id",)),
    ]

    missing = [
        (label, props)
        for label, props in expected
        if not helpers.index_present(indexes, label, props)
    ]
    if missing:
        raise AssertionError(f"schema missing required index definitions: {missing}")
