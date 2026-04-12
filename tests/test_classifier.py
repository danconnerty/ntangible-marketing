import json
from unittest.mock import patch, MagicMock

from app.services.processor.classifier import (
    classify_item,
    build_classifier_prompt,
    parse_classification,
    ClassificationResult,
)


def test_build_classifier_prompt_email():
    payload = {"from": "dan@partner.co", "subject": "Partnership update", "body": "Here's the latest on our project with Alliance Sports..."}
    workflows = [
        {"slug": "partner-update", "name": "Partner Update", "description": "Updates about partners"},
        {"slug": "linkedin-company-update", "name": "LinkedIn Company Update", "description": "LinkedIn posts"},
    ]
    entity_types = ["company", "person", "partner", "topic"]
    system_prompt, user_prompt = build_classifier_prompt(
        source_type="gmail", raw_payload=payload, active_workflows=workflows, entity_types=entity_types,
    )
    assert "gmail" in user_prompt.lower()
    assert "dan@partner.co" in user_prompt
    assert "partner-update" in system_prompt
    assert "company" in system_prompt


def test_parse_classification_valid():
    raw = {
        "summary": "Partnership update from Dan about Alliance Sports",
        "is_knowledge": True,
        "knowledge_entities": [
            {"name": "Alliance Sports", "type": "company", "relation": "partnership update"},
            {"name": "Dan Connerty", "type": "person", "relation": "sender"},
        ],
        "is_workflow_trigger": True,
        "workflow_slugs": ["partner-update"],
        "workflow_reason": "Partner relationship update",
        "is_alert": False,
        "alert_reason": None,
    }
    result = parse_classification(raw)
    assert isinstance(result, ClassificationResult)
    assert result.is_knowledge is True
    assert len(result.knowledge_entities) == 2
    assert result.knowledge_entities[0]["name"] == "Alliance Sports"
    assert result.is_workflow_trigger is True
    assert result.workflow_slugs == ["partner-update"]
    assert result.is_alert is False


def test_parse_classification_minimal():
    raw = {"summary": "Junk email", "is_knowledge": False, "knowledge_entities": [], "is_workflow_trigger": False, "workflow_slugs": [], "workflow_reason": None, "is_alert": False, "alert_reason": None}
    result = parse_classification(raw)
    assert result.is_knowledge is False
    assert result.is_workflow_trigger is False
    assert result.is_alert is False


def test_classify_item_calls_llm():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "summary": "Test email",
        "is_knowledge": True,
        "knowledge_entities": [{"name": "Test Co", "type": "company", "relation": "mentioned"}],
        "is_workflow_trigger": False,
        "workflow_slugs": [],
        "workflow_reason": None,
        "is_alert": False,
        "alert_reason": None,
    })
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    with patch("app.services.processor.classifier._get_openai_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        result = classify_item(
            source_type="gmail",
            raw_payload={"from": "test@test.com", "subject": "Test", "body": "Hello"},
            active_workflows=[],
            entity_types=["company"],
        )
    assert result.is_knowledge is True
    assert result.knowledge_entities[0]["name"] == "Test Co"


def test_parse_classification_with_layers():
    raw = {
        "summary": "Alliance Sports partnership deadline",
        "is_knowledge": True,
        "knowledge_kind": "deadline",
        "topic_key": "partnerships",
        "confidence": 0.92,
        "knowledge_entities": [{"name": "Alliance Sports", "type": "company", "relation": "partner"}],
        "is_workflow_trigger": False,
        "workflow_slugs": [],
        "workflow_reason": None,
        "is_alert": False,
        "alert_reason": None,
    }
    result = parse_classification(raw)
    assert result.knowledge_kind == "deadline"
    assert result.topic_key == "partnerships"
    assert result.confidence == 0.92


def test_parse_classification_defaults_new_fields():
    raw = {"summary": "Minimal item", "is_knowledge": False}
    result = parse_classification(raw)
    assert result.knowledge_kind is None
    assert result.topic_key is None
    assert result.confidence == 0.5


def test_build_classifier_prompt_includes_topics():
    payload = {"from": "jane@corp.com", "subject": "Q2 Partnership Review", "body": "Let's review our Q2 partner performance."}
    workflows = [{"slug": "partner-update", "name": "Partner Update", "description": "Partner updates"}]
    entity_types = ["company", "person"]
    topics = [
        {"key": "partnerships", "label": "Partnerships"},
        {"key": "sales", "label": "Sales Pipeline"},
    ]
    system_prompt, user_prompt = build_classifier_prompt(
        source_type="gmail",
        raw_payload=payload,
        active_workflows=workflows,
        entity_types=entity_types,
        topics=topics,
    )
    assert "partnerships" in system_prompt
    assert "sales" in system_prompt
    assert "knowledge_kind" in system_prompt
    assert "topic_key" in system_prompt
    assert "confidence" in system_prompt
    assert "is_knowledge" in system_prompt
