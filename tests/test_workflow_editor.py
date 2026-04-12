import uuid
from unittest.mock import MagicMock, patch

from app.models.brain import EntityNode, KnowledgeNode
from app.schemas.workflow_config import WorkflowVersionConfig
from app.services.workflow_editor import WorkflowEditor, _VersionProxy, _WorkflowProxy


def test_build_proposed_config_updates_tone_examples_and_cta_rules():
    editor = WorkflowEditor(MagicMock())
    current = WorkflowVersionConfig().model_dump()

    proposed = editor.build_proposed_config(
        current,
        feedback="This sounds too corporate. Use more hard data, shorter paragraphs, and athlete-facing language.",
        approved_example_ids=["approved-1"],
        rejected_example_ids=["rejected-1"],
    )

    tone_notes = proposed["prompt"]["tone_notes"].lower()
    system_additions = proposed["prompt"]["system_prompt_additions"].lower()

    assert "not corporate" in tone_notes
    assert "athlete" in tone_notes
    assert "data" in system_additions
    assert proposed["retrieval"]["approved_example_ids"] == ["approved-1"]
    assert proposed["retrieval"]["rejected_example_ids"] == ["rejected-1"]


def test_activate_version_marks_new_version_active():
    workflow_id = uuid.uuid4()
    old_node_id = uuid.uuid4()
    new_node_id = uuid.uuid4()

    # Build EntityNode proxy for the workflow
    entity = EntityNode(
        id=workflow_id,
        entity_type="workflow",
        canonical_name="Tuesday LinkedIn TL",
        slug="tuesday-linkedin-tl",
        status="active",
        metadata_={"mode": "manual", "platform": "linkedin"},
    )

    # Build KnowledgeNode proxies for two versions
    old_config_node = KnowledgeNode(
        id=old_node_id,
        kind="workflow_config",
        title="Tuesday LinkedIn TL v1",
        status="active",
        version=1,
        metadata_={"config": WorkflowVersionConfig().model_dump(), "author": "system", "is_active": True},
    )
    new_config_node = KnowledgeNode(
        id=new_node_id,
        kind="workflow_config",
        title="Tuesday LinkedIn TL v2",
        status="pending",
        version=2,
        metadata_={"config": WorkflowVersionConfig().model_dump(), "author": "boss", "is_active": False},
    )

    db = MagicMock()
    editor = WorkflowEditor(db)

    # Patch BrainQuery methods used by WorkflowEditor
    with patch.object(editor, "_get_workflow", return_value=entity), \
         patch.object(editor, "_list_versions", return_value=[
             _VersionProxy.from_node(new_config_node),
             _VersionProxy.from_node(old_config_node),
         ]):

        # db.query(...).filter(...).first() used in activate_version to fetch nodes by ID
        def mock_query(model):
            q = MagicMock()
            def mock_filter(*args, **kwargs):
                f = MagicMock()
                # Return the correct node based on which ID was requested
                def mock_first():
                    # Inspect filter args to figure out which node was looked up
                    for arg in args:
                        try:
                            # SQLAlchemy filter: KnowledgeNode.id == some_uuid
                            right = arg.right.value if hasattr(arg, "right") else None
                            if right == old_node_id:
                                return old_config_node
                            if right == new_node_id:
                                return new_config_node
                        except Exception:
                            pass
                    return None
                f.first = mock_first
                return f
            q.filter = mock_filter
            return q

        db.query.side_effect = mock_query

        activated = editor.activate_version(entity.slug, 2)

    assert activated.id == new_node_id
    assert activated.version_number == 2
    assert activated.is_active is True
    assert new_config_node.status == "active"
    assert old_config_node.status == "superseded"
    db.flush.assert_called()
