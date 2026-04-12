import json
from unittest.mock import patch, MagicMock

from app.services.processor.intelligence import (
    build_intelligence_prompt,
    parse_intelligence_output,
    run_intelligence_stage,
    IntelligenceResult,
)


def test_build_intelligence_prompt():
    stage1 = {
        "summary": "Meeting with Alliance Sports on April 15",
        "knowledge_kind": "event",
        "entities": [{"name": "Alliance Sports", "type": "partner", "relation": "meeting partner"}],
    }
    graph_context = {
        "entities": [
            {
                "name": "Alliance Sports",
                "type": "partner",
                "edges": [{"relation": "partner_of", "target": "NTangible"}],
                "knowledge": [{"title": "Alliance partnership launched Q1", "kind": "fact"}],
            }
        ],
    }
    system_prompt, user_prompt = build_intelligence_prompt(stage1_output=stage1, graph_context=graph_context)
    assert "Alliance Sports" in user_prompt
    assert "partner_of" in user_prompt
    assert "partnership launched" in user_prompt
    assert "new_edges" in system_prompt
    assert "contradictions" in system_prompt


def test_parse_intelligence_output_valid():
    raw = {
        "new_edges": [
            {"source": "Alliance Sports", "target": "NTangible", "relation": "meeting_scheduled", "confidence": 0.9, "edge_type": "entity"}
        ],
        "updated_knowledge": [],
        "contradictions": [],
        "implications": "The meeting suggests continued partnership engagement.",
    }
    result = parse_intelligence_output(raw)
    assert isinstance(result, IntelligenceResult)
    assert len(result.new_edges) == 1
    assert result.new_edges[0]["relation"] == "meeting_scheduled"
    assert result.implications == "The meeting suggests continued partnership engagement."


def test_parse_intelligence_output_empty():
    raw = {"new_edges": [], "updated_knowledge": [], "contradictions": [], "implications": None}
    result = parse_intelligence_output(raw)
    assert len(result.new_edges) == 0
    assert result.implications is None


def test_run_intelligence_stage_calls_llm():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "new_edges": [
            {"source": "Alliance Sports", "target": "NTangible", "relation": "expanding_partnership", "confidence": 0.85, "edge_type": "entity"}
        ],
        "updated_knowledge": [],
        "contradictions": [],
        "implications": "Partnership is growing.",
    })
    mock_response.usage.prompt_tokens = 200
    mock_response.usage.completion_tokens = 100

    with patch("app.services.processor.intelligence._get_openai_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        result = run_intelligence_stage(
            stage1_output={"summary": "Test", "knowledge_kind": "fact", "entities": []},
            graph_context={"entities": []},
        )
    assert isinstance(result, IntelligenceResult)
    assert len(result.new_edges) == 1
    assert result.implications == "Partnership is growing."
