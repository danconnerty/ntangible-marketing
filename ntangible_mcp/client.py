"""HTTP client wrapper for the NTangible Marketing API."""
from __future__ import annotations

import os
from typing import Any

import httpx


class AppClient:
    """Thin HTTP client that forwards MCP calls to the hosted FastAPI app."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ):
        self.base_url = (base_url or os.environ.get("APP_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("APP_API_KEY", "")
        if not self.base_url:
            raise ValueError("APP_BASE_URL is required (env var or constructor arg)")
        if not self.api_key:
            raise ValueError("APP_API_KEY is required (env var or constructor arg)")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=timeout,
        )

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        resp = self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, json: dict[str, Any] | None = None) -> dict:
        resp = self._client.post(path, json=json)
        resp.raise_for_status()
        return resp.json()

    def delete(self, path: str) -> dict:
        resp = self._client.delete(path)
        resp.raise_for_status()
        return resp.json()

    def health_check(self) -> dict:
        """Check API reachability and auth validity."""
        try:
            result = self.get("/system/status")
            return {"status": "ok", "data": result}
        except httpx.HTTPStatusError as exc:
            return {"status": "error", "code": exc.response.status_code, "detail": exc.response.text}
        except httpx.ConnectError as exc:
            return {"status": "unreachable", "detail": str(exc)}
