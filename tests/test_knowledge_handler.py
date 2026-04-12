from unittest.mock import MagicMock, patch

from app.services.processor.handlers.knowledge import handle, resolve_entity, _assign_topic_key
from app.services.processor.handlers.base import HandlerResult
from app.services.processor.classifier import ClassificationResult


def test_knowledge_handler_creates_typed_knowledge_node():
    classification = ClassificationResult(
        summary="Meeting with Alliance Sports CEO",
        is_knowledge=True,
        knowledge_kind="event",
        topic_key="work",
        confidence=0.9,
        knowledge_entities=[
            {"name": "Alliance Sports", "type": "partner", "relation": "meeting partner"},
        ],
    )
    mock_db = MagicMock()
    with patch("app.services.processor.handlers.knowledge.BrainQuery") as MockBQ, \
         patch("app.services.processor.handlers.knowledge.run_intelligence_stage") as mock_intel:
        mock_bq = MockBQ.return_value
        mock_bq.get_entity_by_slug.return_value = None
        mock_entity = MagicMock(); mock_entity.id = "ent-1"
        mock_bq.create_entity.return_value = mock_entity
        mock_knowledge = MagicMock(); mock_knowledge.id = "kn-1"
        mock_bq.create_knowledge_node.return_value = mock_knowledge
        mock_bq.get_edges_from.return_value = []
        mock_bq.get_edges_to.return_value = []

        from app.services.processor.intelligence import IntelligenceResult
        mock_intel.return_value = IntelligenceResult(new_edges=[], implications=None)

        result = handle(db=mock_db, raw_payload={"from": "dan@partner.co"}, classification=classification)

    assert result.handler_name == "knowledge"
    assert result.success is True
    call_kwargs = mock_bq.create_knowledge_node.call_args[1]
    assert call_kwargs["kind"] == "event"
    assert call_kwargs["primary_topic_key"] == "work"
    assert call_kwargs["confidence"] == 0.9


def test_knowledge_handler_runs_intelligence_stage():
    classification = ClassificationResult(
        summary="Alliance expanding contract",
        is_knowledge=True,
        knowledge_kind="fact",
        topic_key="work",
        confidence=0.85,
        knowledge_entities=[
            {"name": "Alliance Sports", "type": "partner", "relation": "contract expansion"},
        ],
    )
    mock_db = MagicMock()
    mock_existing = MagicMock(); mock_existing.id = "existing-ent"
    mock_existing.canonical_name = "Alliance Sports"
    mock_existing.entity_type = "partner"

    with patch("app.services.processor.handlers.knowledge.BrainQuery") as MockBQ, \
         patch("app.services.processor.handlers.knowledge.run_intelligence_stage") as mock_intel:
        mock_bq = MockBQ.return_value
        mock_bq.get_entity_by_slug.return_value = mock_existing
        mock_knowledge = MagicMock(); mock_knowledge.id = "kn-1"
        mock_bq.create_knowledge_node.return_value = mock_knowledge
        mock_edge = MagicMock()
        mock_edge.relation = "partner_of"
        mock_edge.target_id = "ntangible-id"
        mock_bq.get_edges_from.return_value = [mock_edge]
        mock_bq.get_edges_to.return_value = []
        # Mock the knowledge query for graph context
        mock_db.query.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = []

        from app.services.processor.intelligence import IntelligenceResult
        mock_intel.return_value = IntelligenceResult(
            new_edges=[{"source": "Alliance Sports", "target": "NTangible", "relation": "expanding_partnership", "confidence": 0.85, "edge_type": "entity"}],
            implications="Partnership is growing.",
        )

        result = handle(db=mock_db, raw_payload={"from": "dan@partner.co"}, classification=classification)

    mock_intel.assert_called_once()
    assert result.success is True


def test_knowledge_handler_not_knowledge():
    classification = ClassificationResult(summary="Not knowledge", is_knowledge=False)
    result = handle(db=MagicMock(), raw_payload={}, classification=classification)
    assert result is None


def test_resolve_entity_exact_slug_match():
    mock_bq = MagicMock()
    mock_entity = MagicMock(); mock_entity.id = "ent-1"
    mock_bq.get_entity_by_slug.return_value = mock_entity
    resolved, created = resolve_entity(mock_bq, name="Alliance Sports", entity_type="company", topic_key="work")
    assert resolved.id == "ent-1"
    assert created is False


def test_resolve_entity_creates_new_with_topic():
    mock_bq = MagicMock()
    mock_bq.get_entity_by_slug.return_value = None
    mock_new = MagicMock(); mock_new.id = "new-ent"
    mock_bq.create_entity.return_value = mock_new
    resolved, created = resolve_entity(mock_bq, name="New Company", entity_type="company", topic_key="work")
    assert created is True
    call_kwargs = mock_bq.create_entity.call_args[1]
    assert call_kwargs["primary_topic_key"] == "work"


def test_assign_topic_key():
    assert _assign_topic_key("person", "work") == "people"
    assert _assign_topic_key("company", None) == "work"
    assert _assign_topic_key("partner", "projects") == "marketing"
    assert _assign_topic_key("product", None) == "projects"
    assert _assign_topic_key("topic", "finance") == "finance"
    assert _assign_topic_key("org", None) == "work"
    assert _assign_topic_key("place", None) == "work"
