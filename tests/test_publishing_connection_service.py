import uuid
from unittest.mock import MagicMock

from app.models.publishing_connection import (
    AppConnection,
    ConnectionChannel,
    ConnectionStatus,
    PublishingDestination,
)
from app.services.publishing_connection_service import PublishingConnectionService


def _connection_query(connection):
    query = MagicMock()
    query.filter.return_value.first.return_value = connection
    return query


def test_resolve_active_publish_target_returns_active_destination():
    active = PublishingDestination(
        id=uuid.uuid4(),
        app_connection_id=uuid.uuid4(),
        external_id="urn:li:organization:555",
        destination_type="organization",
        label="NTangible Primary",
        config_json={"organization_urn": "urn:li:organization:555"},
        is_active=True,
    )
    inactive = PublishingDestination(
        id=uuid.uuid4(),
        app_connection_id=uuid.uuid4(),
        external_id="urn:li:organization:777",
        destination_type="organization",
        label="Legacy Page",
        config_json={"organization_urn": "urn:li:organization:777"},
        is_active=False,
    )
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
    connection.destinations = [inactive, active]

    db = MagicMock()
    db.query.return_value = _connection_query(connection)

    target = PublishingConnectionService(db).resolve_active_publish_target("linkedin")

    assert target["connection"] is connection
    assert target["destination"] is active
    assert target["channel"] == "linkedin"
    assert target["credentials"]["access_token"] == "linkedin-token"
    assert target["config"]["organization_urn"] == "urn:li:organization:555"


def test_upsert_connection_updates_existing_channel():
    connection = AppConnection(
        id=uuid.uuid4(),
        channel=ConnectionChannel.X,
        provider_key="twikit",
        auth_mode="manual",
        status=ConnectionStatus.FAILED,
        connection_label="Old X",
        config_json={"publisher_type": "twikit"},
        credential_json={"access_token": "old-token"},
    )

    db = MagicMock()
    db.query.return_value = _connection_query(connection)

    updated = PublishingConnectionService(db).upsert_connection(
        channel="x",
        provider_key="tweepy",
        auth_mode="oauth",
        connection_label="Primary X",
        config_json={"publisher_type": "tweepy"},
        credential_json={"access_token": "new-token"},
        status="connected",
    )

    assert updated is connection
    assert updated.provider_key == "tweepy"
    assert updated.auth_mode == "oauth"
    assert updated.connection_label == "Primary X"
    assert updated.config_json == {"publisher_type": "tweepy"}
    assert updated.credential_json == {"access_token": "new-token"}
    assert updated.status == ConnectionStatus.CONNECTED


def test_set_active_destination_deactivates_others():
    first = PublishingDestination(
        id=uuid.uuid4(),
        app_connection_id=uuid.uuid4(),
        external_id="page-1",
        destination_type="page",
        label="Page 1",
        config_json={"page_id": "page-1"},
        is_active=True,
    )
    second = PublishingDestination(
        id=uuid.uuid4(),
        app_connection_id=first.app_connection_id,
        external_id="page-2",
        destination_type="page",
        label="Page 2",
        config_json={"page_id": "page-2"},
        is_active=False,
    )
    connection = AppConnection(
        id=uuid.uuid4(),
        channel=ConnectionChannel.LINKEDIN,
        provider_key="linkedin",
        auth_mode="oauth",
        status=ConnectionStatus.CONNECTED,
        connection_label="LinkedIn",
        config_json={},
        credential_json={},
    )
    connection.destinations = [first, second]

    db = MagicMock()
    db.query.return_value = _connection_query(connection)

    selected = PublishingConnectionService(db).set_active_destination("linkedin", second.id)

    assert selected is second
    assert first.is_active is False
    assert second.is_active is True
