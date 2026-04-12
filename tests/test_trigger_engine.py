from app.models.workflow import Platform
from app.triggers.partner_events import build_trigger_requests, normalize_partner_event


def test_commitment_update_routes_to_x_and_instagram_and_uses_score_tier():
    normalized = normalize_partner_event(
        "alliance_fastpitch",
        {
            "event_type": "commitment_update",
            "external_event_id": "evt-commit-1",
            "athlete_name": "Jane Smith",
            "commitment_school": "Oklahoma",
            "position": "SS",
            "score": 712,
            "score_tier": "Gold",
        },
    )

    requests = build_trigger_requests(normalized)

    assert {request.platform for request in requests} == {Platform.X, Platform.INSTAGRAM}
    assert requests[0].pillar == "client_proof"
    assert all("Gold" in request.context for request in requests)
    assert all("712" not in request.context for request in requests)
    assert all(request.dynamic_value_groups == [] for request in requests)
    x_request = next(request for request in requests if request.platform == Platform.X)
    instagram_request = next(request for request in requests if request.platform == Platform.INSTAGRAM)
    assert x_request.content_type == "data_drop"
    assert instagram_request.content_type == "partner_content"


def test_leaderboard_routes_to_x_linkedin_and_instagram_with_dynamic_scores():
    normalized = normalize_partner_event(
        "alliance_fastpitch",
        {
            "event_type": "leaderboard_published",
            "external_event_id": "evt-board-1",
            "event_name": "Alliance Nationals",
            "athlete_count": 128,
            "top_performers": [
                {"athlete_name": "Jane Smith", "score": 812},
                {"athlete_name": "Ava Brown", "score": 804},
            ],
        },
    )

    requests = build_trigger_requests(normalized)
    dynamic_values = {value for request in requests for group in request.dynamic_value_groups for value in group}

    assert {request.platform for request in requests} == {
        Platform.X,
        Platform.LINKEDIN,
        Platform.INSTAGRAM,
    }
    assert "812" in dynamic_values
    assert "804" in dynamic_values
    assert "128" in dynamic_values
    assert any("Alliance Nationals" in request.context for request in requests)
