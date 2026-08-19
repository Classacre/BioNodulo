"""HTTP clients for the BioNodulo cloud API and the local desktop app.

Cloud API: https://bionodulo.com/api (a.k.a. cloud.bionodulo.com).
  - Auth: Clerk session JWT as ``Authorization: Bearer <token>``.
  - Team selection: ``X-Team-Id`` header (optional; defaults to the user's
    first team membership).
  - Responses follow the shared ``ApiResponse<T> = {success, data?, error?}``
    envelope (some endpoints return raw JSON).

Desktop app: the local BioNodulo backend (default http://127.0.0.1:8765).
  Unauthenticated by design in local mode.
"""

from __future__ import annotations

from typing import Any

import httpx

from .auth import USER_AGENT


class ApiError(RuntimeError):
    """An API call failed; message is safe to surface to the model."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CloudClient:
    """Async client for the BioNodulo cloud (website) REST API."""

    def __init__(
        self,
        base_url: str,
        token_provider: Any,
        team_id: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token_provider = token_provider
        self._team_id = team_id
        self._timeout = timeout

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        token = await self._token_provider.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
        }
        if self._team_id:
            headers["X-Team-Id"] = self._team_id
        async with httpx.AsyncClient(
            base_url=self._base_url, headers=headers, timeout=self._timeout
        ) as client:
            resp = await client.request(method, path, params=params, json=json)
        return self._handle(resp, method, path)

    @staticmethod
    def _handle(resp: httpx.Response, method: str, path: str) -> Any:
        try:
            body = resp.json()
        except ValueError:
            body = resp.text
        if resp.status_code >= 400:
            detail = ""
            if isinstance(body, dict):
                detail = str(body.get("error") or body.get("message") or body)[:500]
            else:
                detail = str(body)[:500]
            raise ApiError(
                f"{method} {path} failed with HTTP {resp.status_code}: {detail}",
                status_code=resp.status_code,
            )
        # Unwrap the standard ApiResponse envelope when present.
        if isinstance(body, dict) and "success" in body:
            if body.get("success") is False:
                raise ApiError(
                    f"{method} {path} returned an error: "
                    f"{str(body.get('error'))[:500]}",
                    status_code=resp.status_code,
                )
            return body.get("data", body)
        return body

    # Convenience wrappers
    async def get(self, path: str, **kwargs: Any) -> Any:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Any:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> Any:
        return await self.request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> Any:
        return await self.request("DELETE", path, **kwargs)


class DesktopClient:
    """Async client for a locally running BioNodulo desktop backend."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers={"User-Agent": USER_AGENT},
                timeout=self._timeout,
            ) as client:
                resp = await client.request(method, path, params=params, json=json)
        except httpx.HTTPError as exc:
            raise ApiError(
                f"Cannot reach the local BioNodulo app at {self._base_url}: {exc}. "
                "Start it with `python main.py --dev --port 8765` (or set "
                "BIONODULO_DESKTOP_URL to the right address)."
            ) from exc
        return CloudClient._handle(resp, method, path)

    async def get(self, path: str, **kwargs: Any) -> Any:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Any:
        return await self.request("POST", path, **kwargs)

    async def ping(self) -> bool:
        try:
            await self.get("/api/health")
            return True
        except ApiError:
            return False
