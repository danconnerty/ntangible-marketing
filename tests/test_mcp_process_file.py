from unittest.mock import patch, MagicMock

from ntangible_mcp.server import process_file


def test_process_file_calls_api():
    mock_client = MagicMock()
    mock_client.post.return_value = {"queued": True, "item_id": "abc-123"}
    with patch("ntangible_mcp.server._get_client", return_value=mock_client):
        result = process_file(file_content="This is a test document about marketing strategy.", file_name="strategy.txt")
    assert "queued" in result
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "/api/mcp/process-file"


def test_process_file_with_type():
    mock_client = MagicMock()
    mock_client.post.return_value = {"queued": True}
    with patch("ntangible_mcp.server._get_client", return_value=mock_client):
        result = process_file(file_content="PDF content here", file_name="report.pdf", file_type="application/pdf")
    call_args = mock_client.post.call_args
    body = call_args[1].get("json") or call_args[0][1]
    assert body["file_type"] == "application/pdf"
