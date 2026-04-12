from unittest.mock import patch, MagicMock

from ntangible_mcp.server import get_context


def test_get_context_calls_api():
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "entities": [{"name": "Alliance Sports", "type": "partner"}],
        "knowledge": [{"title": "Partnership fact", "kind": "fact"}],
        "query": "Alliance Sports",
        "entity_count": 1,
        "knowledge_count": 1,
    }
    with patch("ntangible_mcp.server._get_client", return_value=mock_client):
        result = get_context(query="Alliance Sports")
    assert "Alliance Sports" in result
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert call_args[0][0] == "/api/mcp/context"
    assert call_args[1]["params"]["q"] == "Alliance Sports"


def test_get_context_with_topic():
    mock_client = MagicMock()
    mock_client.get.return_value = {"entities": [], "knowledge": [], "query": "test", "entity_count": 0, "knowledge_count": 0}
    with patch("ntangible_mcp.server._get_client", return_value=mock_client):
        result = get_context(query="test", topic="marketing")
    call_args = mock_client.get.call_args
    assert call_args[1]["params"]["topic"] == "marketing"
