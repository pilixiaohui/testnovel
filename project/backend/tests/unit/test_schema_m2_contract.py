from tests.unit import schema_contract_helpers as helpers


def test_schema_m2_models_and_relationships_exist():
    schema = helpers.get_schema_module()

    node_names = [
        "Act",
        "Chapter",
        "StoryAnchor",
        "CharacterAgentState",
        "SimulationLog",
        "Subplot",
    ]
    for name in node_names:
        cls = helpers.require_class(schema, name)
        helpers.assert_explicit_label(cls)

    relationship_names = [
        "CONTAINS_CHAPTER",
        "CONTAINS_SCENE",
        "DEPENDS_ON",
        "TRIGGERED_AT",
        "AGENT_OF",
    ]
    for name in relationship_names:
        helpers.require_relationship(schema, name)


def test_schema_m2_field_contracts():
    schema = helpers.get_schema_module()

    required_fields = {
        "Act": {"id", "root_id", "sequence", "title", "purpose", "tone"},
        "Chapter": {"id", "act_id", "sequence", "title", "focus", "pov_character_id"},
        "StoryAnchor": {
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
        "CharacterAgentState": {
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
        "SimulationLog": {
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
        "Subplot": {
            "id",
            "root_id",
            "branch_id",
            "title",
            "subplot_type",
            "protagonist_id",
            "central_conflict",
            "status",
        },
    }

    for name, fields in required_fields.items():
        cls = helpers.require_class(schema, name)
        helpers.assert_fields_present(cls, fields)


def test_schema_m2_extended_fields_on_existing_nodes():
    schema = helpers.get_schema_module()

    scene_origin = helpers.require_class(schema, "SceneOrigin")
    helpers.assert_fields_present(scene_origin, {"chapter_id", "is_skeleton"})

    scene_version = helpers.require_class(schema, "SceneVersion")
    helpers.assert_fields_present(scene_version, {"simulation_log_id", "is_simulated"})

    entity = helpers.require_class(schema, "Entity")
    helpers.assert_fields_present(entity, {"has_agent", "agent_state_id"})


def test_schema_m2_default_values():
    schema = helpers.get_schema_module()

    story_anchor_cls = helpers.require_class(schema, "StoryAnchor")
    anchor = helpers.build_instance(
        story_anchor_cls,
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

    simulation_cls = helpers.require_class(schema, "SimulationLog")
    simulation = helpers.build_instance(
        simulation_cls,
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
    helpers.assert_default_values(simulation, {"stagnation_count": 0})

    subplot_cls = helpers.require_class(schema, "Subplot")
    subplot = helpers.build_instance(
        subplot_cls,
        id="subplot-1",
        root_id="root",
        branch_id="main",
        title="subplot",
        subplot_type="mystery",
        protagonist_id="char-1",
        central_conflict="conflict",
    )
    helpers.assert_default_values(subplot, {"status": "dormant"})

    scene_origin_cls = helpers.require_class(schema, "SceneOrigin")
    scene_origin = helpers.build_instance(
        scene_origin_cls,
        id="scene-alpha",
        root_id="root",
        title="Scene 1",
        initial_commit_id="commit-1",
        sequence_index=1,
        parent_act_id="act-1",
    )
    helpers.assert_default_values(scene_origin, {"chapter_id": None, "is_skeleton": False})

    scene_version_cls = helpers.require_class(schema, "SceneVersion")
    scene_version = helpers.build_instance(
        scene_version_cls,
        id="scene-version-1",
        scene_origin_id="scene-alpha",
        commit_id="commit-1",
        pov_character_id="char-1",
        status="draft",
        expected_outcome="expected",
        conflict_type="internal",
        actual_outcome="actual",
    )
    helpers.assert_default_values(
        scene_version,
        {"simulation_log_id": None, "is_simulated": False},
    )

    entity_cls = helpers.require_class(schema, "Entity")
    entity = helpers.build_instance(
        entity_cls,
        id="entity-1",
        root_id="root",
        branch_id="main",
        entity_type="Character",
        semantic_states={},
        arc_status="active",
    )
    helpers.assert_default_values(entity, {"has_agent": False, "agent_state_id": None})


def test_schema_m2_index_definitions():
    schema = helpers.get_schema_module()
    indexes = helpers.collect_index_definitions(schema)
    if not indexes:
        raise AssertionError("schema missing module-level index definitions")

    expected = [
        ("Act", ("id",)),
        ("Act", ("root_id",)),
        ("Chapter", ("id",)),
        ("Chapter", ("act_id",)),
        ("StoryAnchor", ("id",)),
        ("StoryAnchor", ("root_id", "branch_id")),
        ("Subplot", ("id",)),
        ("Subplot", ("root_id", "branch_id")),
        ("CharacterAgentState", ("id",)),
        ("CharacterAgentState", ("character_id",)),
        ("CharacterAgentState", ("branch_id",)),
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
