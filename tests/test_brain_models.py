import uuid

from app.models.brain import (
    EntityEdge,
    EntityNode,
    KnowledgeEdge,
    KnowledgeNode,
    TopicProfile,
)


def test_create_topic_profile():
    profile = TopicProfile(
        id=uuid.uuid4(),
        topic_key="ai-marketing",
        display_name="AI Marketing",
        description="All things AI in marketing",
        enabled=True,
        priority="high",
        keywords={"terms": ["ai", "marketing"]},
        context_enabled=True,
        intelligence_enabled=True,
        memory_enabled=True,
        config={"max_depth": 3},
    )

    assert profile.topic_key == "ai-marketing"
    assert profile.display_name == "AI Marketing"
    assert profile.description == "All things AI in marketing"
    assert profile.enabled is True
    assert profile.priority == "high"
    assert profile.keywords == {"terms": ["ai", "marketing"]}
    assert profile.context_enabled is True
    assert profile.intelligence_enabled is True
    assert profile.memory_enabled is True
    assert profile.config == {"max_depth": 3}


def test_create_entity_node():
    node = EntityNode(
        id=uuid.uuid4(),
        entity_type="person",
        canonical_name="Ada Lovelace",
        slug="ada-lovelace",
        description="Pioneer of computing",
        status="active",
        primary_topic_key="computing",
        metadata_={"source": "wikipedia"},
    )

    assert node.entity_type == "person"
    assert node.canonical_name == "Ada Lovelace"
    assert node.slug == "ada-lovelace"
    assert node.status == "active"
    assert node.primary_topic_key == "computing"
    assert node.metadata_ == {"source": "wikipedia"}
    # Verify the DB column is named "metadata"
    assert EntityNode.__table__.c["metadata"].name == "metadata"


def test_create_knowledge_node():
    node = KnowledgeNode(
        id=uuid.uuid4(),
        kind="fact",
        title="Python was created in 1991",
        content="Guido van Rossum created Python.",
        primary_topic_key="programming",
        confidence=0.95,
        trust_score=0.9,
        status="verified",
        version=1,
        is_latest=True,
        metadata_={"citations": 42},
    )

    assert node.kind == "fact"
    assert node.title == "Python was created in 1991"
    assert node.content == "Guido van Rossum created Python."
    assert node.confidence == 0.95
    assert node.trust_score == 0.9
    assert node.status == "verified"
    assert node.version == 1
    assert node.is_latest is True
    assert node.metadata_ == {"citations": 42}
    assert KnowledgeNode.__table__.c["metadata"].name == "metadata"


def test_create_entity_edge():
    src = uuid.uuid4()
    tgt = uuid.uuid4()
    edge = EntityEdge(
        id=uuid.uuid4(),
        source_id=src,
        target_id=tgt,
        source_type="entity",
        target_type="knowledge",
        relation="mentions",
        confidence=0.8,
        metadata_={"weight": 1.0},
    )

    assert edge.source_id == src
    assert edge.target_id == tgt
    assert edge.source_type == "entity"
    assert edge.target_type == "knowledge"
    assert edge.relation == "mentions"
    assert edge.confidence == 0.8
    assert edge.metadata_ == {"weight": 1.0}
    assert EntityEdge.__table__.c["metadata"].name == "metadata"


def test_create_knowledge_edge():
    src = uuid.uuid4()
    tgt = uuid.uuid4()
    edge = KnowledgeEdge(
        id=uuid.uuid4(),
        source_id=src,
        target_id=tgt,
        relation="supersedes",
        confidence=0.99,
        metadata_={"reason": "updated"},
    )

    assert edge.source_id == src
    assert edge.target_id == tgt
    assert edge.relation == "supersedes"
    assert edge.confidence == 0.99
    assert edge.metadata_ == {"reason": "updated"}
    assert KnowledgeEdge.__table__.c["metadata"].name == "metadata"


def test_entity_node_slug_unique_per_type():
    """Verify the unique constraint on (entity_type, slug) exists."""
    constraints = EntityNode.__table__.constraints
    uq = [c for c in constraints if c.name == "uq_entity_type_slug"]
    assert len(uq) == 1
    col_names = {col.name for col in uq[0].columns}
    assert col_names == {"entity_type", "slug"}
