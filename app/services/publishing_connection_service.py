from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.publishing_connection import (
    AppConnection,
    ConnectionChannel,
    ConnectionStatus,
    PublishingDestination,
)


class PublishingConnectionService:
    def __init__(self, db: Session):
        self.db = db

    def get_connection(self, channel: str | ConnectionChannel) -> AppConnection | None:
        normalized = self._normalize_channel(channel)
        query = getattr(self.db, "query", None)
        if query is None:
            return None
        connection = (
            query(AppConnection)
            .filter(AppConnection.channel == normalized)
            .first()
        )
        if not isinstance(connection, AppConnection):
            return None
        return connection

    def upsert_connection(
        self,
        *,
        channel: str | ConnectionChannel,
        provider_key: str,
        auth_mode: str,
        connection_label: str | None = None,
        config_json: dict[str, Any] | None = None,
        credential_json: dict[str, Any] | None = None,
        status: str | ConnectionStatus = ConnectionStatus.CONNECTED,
    ) -> AppConnection:
        normalized = self._normalize_channel(channel)
        normalized_status = self._normalize_status(status)
        connection = self.get_connection(normalized)

        if connection is None:
            connection = AppConnection(
                id=uuid.uuid4(),
                channel=normalized,
                provider_key=provider_key,
                auth_mode=auth_mode,
                status=normalized_status,
                connection_label=connection_label,
                config_json=dict(config_json or {}),
                credential_json=dict(credential_json or {}),
            )
            self.db.add(connection)
            return connection

        connection.provider_key = provider_key
        connection.auth_mode = auth_mode
        connection.status = normalized_status
        connection.connection_label = connection_label
        connection.config_json = dict(config_json or {})
        connection.credential_json = dict(credential_json or {})
        if normalized_status == ConnectionStatus.CONNECTED:
            connection.last_validated_at = datetime.now(timezone.utc)
            connection.last_error = None
        return connection

    def add_destination(
        self,
        *,
        channel: str | ConnectionChannel,
        external_id: str,
        destination_type: str,
        label: str,
        config_json: dict[str, Any] | None = None,
        activate: bool = False,
    ) -> PublishingDestination:
        connection = self.get_connection(channel)
        if connection is None:
            raise ValueError(f"Connection not found for channel: {self._normalize_channel(channel).value}")

        if activate:
            for destination in connection.destinations:
                destination.is_active = False

        destination = PublishingDestination(
            id=uuid.uuid4(),
            app_connection_id=connection.id,
            external_id=external_id,
            destination_type=destination_type,
            label=label,
            config_json=dict(config_json or {}),
            is_active=activate or not any(item.is_active for item in connection.destinations),
        )
        connection.destinations.append(destination)
        self.db.add(destination)
        return destination

    def set_active_destination(
        self,
        channel: str | ConnectionChannel,
        destination_id: str | uuid.UUID,
    ) -> PublishingDestination:
        connection = self.get_connection(channel)
        if connection is None:
            raise ValueError(f"Connection not found for channel: {self._normalize_channel(channel).value}")

        target = None
        for destination in connection.destinations:
            destination.is_active = destination.id == destination_id
            if destination.is_active:
                target = destination

        if target is None:
            raise ValueError(f"Destination not found for channel: {self._normalize_channel(channel).value}")
        return target

    def remove_destination(
        self,
        channel: str | ConnectionChannel,
        destination_id: str | uuid.UUID,
    ) -> None:
        connection = self.get_connection(channel)
        if connection is None:
            raise ValueError(f"Connection not found for channel: {self._normalize_channel(channel).value}")

        remaining = [destination for destination in connection.destinations if destination.id != destination_id]
        if len(remaining) == len(connection.destinations):
            raise ValueError(f"Destination not found for channel: {self._normalize_channel(channel).value}")

        connection.destinations[:] = remaining
        if remaining and not any(item.is_active for item in remaining):
            remaining[0].is_active = True

    def resolve_active_publish_target(self, channel: str | ConnectionChannel) -> dict[str, Any] | None:
        connection = self.get_connection(channel)
        if connection is None or connection.status != ConnectionStatus.CONNECTED:
            return None

        destination = next((item for item in connection.destinations if item.is_active), None)
        if destination is None:
            return None

        return {
            "channel": connection.channel.value,
            "connection": connection,
            "destination": destination,
            "credentials": dict(connection.credential_json or {}),
            "config": {
                "provider_key": connection.provider_key,
                "auth_mode": connection.auth_mode,
                **dict(connection.config_json or {}),
                **dict(destination.config_json or {}),
            },
        }

    def list_connection_summaries(self) -> list[dict[str, Any]]:
        connections = self.db.query(AppConnection).order_by(AppConnection.channel.asc()).all()
        summaries: list[dict[str, Any]] = []
        for connection in connections:
            active = next((item for item in connection.destinations if item.is_active), None)
            summaries.append(
                {
                    "id": str(connection.id),
                    "channel": connection.channel.value,
                    "provider_key": connection.provider_key,
                    "auth_mode": connection.auth_mode,
                    "status": connection.status.value,
                    "connection_label": connection.connection_label,
                    "active_destination_label": active.label if active else None,
                    "active_destination_id": str(active.id) if active else None,
                    "destinations": [
                        {
                            "id": str(destination.id),
                            "external_id": destination.external_id,
                            "destination_type": destination.destination_type,
                            "label": destination.label,
                            "is_active": destination.is_active,
                            "config_json": dict(destination.config_json or {}),
                        }
                        for destination in connection.destinations
                    ],
                }
            )
        return summaries

    def _normalize_channel(self, channel: str | ConnectionChannel) -> ConnectionChannel:
        if isinstance(channel, ConnectionChannel):
            return channel
        return ConnectionChannel(str(channel).lower())

    def _normalize_status(self, status: str | ConnectionStatus) -> ConnectionStatus:
        if isinstance(status, ConnectionStatus):
            return status
        return ConnectionStatus(str(status).lower())
