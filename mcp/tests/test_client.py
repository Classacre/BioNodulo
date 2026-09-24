"""Offline regression checks for health and transport failure handling."""
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from bionodulo_mcp.client import ApiError, CloudClient


class CloudClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_health_needs_no_auth_and_sends_no_bearer(self):
        real_client = httpx.AsyncClient
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={"status": "ok"})

        def client_factory(**kwargs):
            return real_client(**kwargs, transport=httpx.MockTransport(respond))

        with patch("bionodulo_mcp.client.httpx.AsyncClient", side_effect=client_factory):
            result = await CloudClient("https://example.test", None).get("/api/health")
        self.assertEqual(result, {"status": "ok"})
        self.assertNotIn("authorization", requests[0].headers)

    async def test_authenticated_calls_still_use_provider(self):
        provider = AsyncMock()
        provider.get_token.return_value = "test-token"
        real_client = httpx.AsyncClient
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={"success": True, "data": {"id": "test"}})

        with patch("bionodulo_mcp.client.httpx.AsyncClient", side_effect=lambda **kw: real_client(**kw, transport=httpx.MockTransport(respond))):
            result = await CloudClient("https://example.test", provider).get("/api/me")
        self.assertEqual(result, {"id": "test"})
        self.assertEqual(requests[0].headers["authorization"], "Bearer test-token")

    async def test_network_failure_returns_safe_api_error(self):
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.request.side_effect = httpx.ConnectError("sensitive upstream details")
        with patch("bionodulo_mcp.client.httpx.AsyncClient", return_value=client):
            with self.assertRaisesRegex(ApiError, "ConnectError") as caught:
                await CloudClient("https://example.test", None).get("/api/health")
        self.assertNotIn("sensitive", str(caught.exception))

    async def test_health_tool_does_not_construct_authenticated_client(self):
        from bionodulo_mcp.server import get_service_health
        with patch("bionodulo_mcp.server._cloud_client", side_effect=AssertionError("auth must not run")), patch.object(CloudClient, "get", new=AsyncMock(return_value={"status": "ok"})):
            self.assertEqual(await get_service_health(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
