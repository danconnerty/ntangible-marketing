import uuid

from app.models.publishing_connection import (
    AppConnection,
    ConnectionChannel,
    ConnectionStatus,
    PublishingDestination,
)


def test_app_connection_fields():
    connection = AppConnection(
        id=uuid.uuid4(),
        channel=ConnectionChannel.LINKEDIN,
        provider_key="linkedin",
        auth_mode="oauth",
        status=ConnectionStatus.CONNECTED,
        connection_label="NTangible LinkedIn",
        config_json={"api_version": "202504"},
        credential_json={"access_token": "linkedin-token"},
    )

    assert connection.channel == ConnectionChannel.LINKEDIN
    assert connection.status == ConnectionStatus.CONNECTED
    assert connection.provider_key == "linkedin"


def test_publishing_destination_fields():
    destination = PublishingDestination(
        id=uuid.uuid4(),
        app_connection_id=uuid.uuid4(),
        external_id="urn:li:organization:123",
        destination_type="organization",
        label="NTangible Main Page",
        config_json={"organization_urn": "urn:li:organization:123"},
        is_active=True,
    )

    assert destination.label == "NTangible Main Page"
    assert destination.external_id == "urn:li:organization:123"
    assert destination.is_active is True


def test_connection_enums_use_lowercase_values():
    assert AppConnection.__table__.c.channel.type.enums == [
        "x",
        "linkedin",
        "instagram",
        "newsletter",
        "blog",
    ]
    assert AppConnection.__table__.c.status.type.enums == [
        "disconnected",
        "connected",
        "action_required",
        "failed",
    ]
