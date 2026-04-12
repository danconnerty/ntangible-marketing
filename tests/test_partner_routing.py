from app.models.workflow import Platform
from app.triggers.partner_events import build_trigger_requests, normalize_partner_event


def test_registration_push_routes_to_x_linkedin_and_instagram():
    event = normalize_partner_event(
        "alliance_fastpitch",
        {
            "event_type": "registration_push",
            "external_event_id": "reg-1",
            "event_name": "Alliance Nationals",
            "registration_deadline": "2026-05-01",
        },
    )

    requests = build_trigger_requests(event)

    assert {request.platform for request in requests} == {
        Platform.X,
        Platform.LINKEDIN,
        Platform.INSTAGRAM,
    }


def test_offer_update_routes_to_x_and_instagram():
    event = normalize_partner_event(
        "fss",
        {
            "event_type": "offer_update",
            "external_event_id": "offer-1",
            "athlete_name": "Jane Smith",
            "offer_school": "Oklahoma",
        },
    )

    requests = build_trigger_requests(event)

    assert {request.platform for request in requests} == {
        Platform.X,
        Platform.INSTAGRAM,
    }
