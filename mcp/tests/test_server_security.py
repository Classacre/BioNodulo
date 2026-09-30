"""Offline security and protocol checks for the personal MCP bridge."""
import asyncio
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastmcp.exceptions import ToolError

from bionodulo_mcp.client import ApiError, DesktopClient
from bionodulo_mcp.install import DEFAULT_REMOTE_URL, install_clients
from bionodulo_mcp import server


class LocalEndpointTests(unittest.TestCase):
    def test_desktop_rejects_non_loopback_and_url_tricks(self):
        for url in (
            "https://127.0.0.1:8765", "http://0.0.0.0:8765",
            "http://192.168.1.4:8765", "http://127.0.0.1.attacker.test:8765",
            "http://user@127.0.0.1:8765", "http://127.0.0.1:8765/elsewhere",
        ):
            with self.subTest(url=url), self.assertRaises(ApiError):
                DesktopClient(url)
        DesktopClient("http://127.0.0.1:8765")

    def test_http_serve_requires_token_and_loopback(self):
        base = [sys.executable, "-m", "bionodulo_mcp.server", "serve", "--transport", "http"]
        env = dict(os.environ, BIONODULO_MCP_TOKEN="")
        result = subprocess.run(base, capture_output=True, text=True, env=env, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires BIONODULO_MCP_TOKEN", result.stderr)
        env["BIONODULO_MCP_TOKEN"] = "test-only"
        result = subprocess.run(base + ["--host", "0.0.0.0"], capture_output=True,
                                text=True, env=env, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("restricted to loopback", result.stderr)

    def test_desktop_only_registration(self):
        env = dict(os.environ, BIONODULO_CLOUD="0")
        cmd = [sys.executable, "-c", "import asyncio; from bionodulo_mcp.server import mcp; "
               "print(','.join(t.name for t in asyncio.run(mcp.list_tools()))); "
               "print(len(asyncio.run(mcp.list_resources()))); "
               "print(len(asyncio.run(mcp.list_prompts())))"]
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=20, check=True)
        tools, resources, prompts = result.stdout.strip().splitlines()
        self.assertEqual(len(tools.split(",")), 11)
        self.assertTrue(all(name.startswith("desktop_") for name in tools.split(",")))
        self.assertEqual((resources, prompts), ("0", "0"))


class ToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_api_failure_is_mcp_tool_error(self):
        with patch.object(server, "_cloud_client") as client:
            client.return_value.get = AsyncMock(side_effect=ApiError("offline"))
            with self.assertRaisesRegex(ToolError, "offline"):
                await server.get_account_info()

    async def test_validation_failure_is_mcp_tool_error(self):
        with self.assertRaisesRegex(ToolError, "days must"):
            await server.get_usage_analytics(4)
        with self.assertRaises(ToolError):
            await server.mcp.call_tool("get_usage_analytics", {"days": 4})

    async def test_file_delete_uses_website_key_and_source(self):
        with patch.object(server, "_cloud_client") as client:
            client.return_value.post = AsyncMock(return_value={"key": "k", "freedBytes": 1})
            await server.delete_file("k", "output")
            client.return_value.post.assert_awaited_once_with(
                "/api/files/delete", json={"key": "k", "source": "output"})

    async def test_upload_reservation_and_completion_match_website(self):
        with patch.object(server, "_cloud_client") as client:
            client.return_value.post = AsyncMock(return_value={"key": "k"})
            await server.get_upload_url("sample.fastq", 512, "text/plain")
            client.return_value.post.assert_awaited_with(
                "/api/files/presign",
                json={"filename": "sample.fastq", "size": 512, "contentType": "text/plain"})
            await server.complete_file_upload("k")
            client.return_value.post.assert_awaited_with("/api/files/complete", json={"key": "k"})


class InstallerTests(unittest.TestCase):
    def test_remote_default_writes_only_url_to_codex(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.toml"
            path.write_text("[mcp_servers.other]\nurl = 'https://other.test/mcp'\n", encoding="utf-8")
            with patch("bionodulo_mcp.install._codex_config_path", return_value=path):
                install_clients(client="codex")
            config = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(config["mcp_servers"]["bionodulo"], {"url": DEFAULT_REMOTE_URL})
            self.assertIn("other", config["mcp_servers"])
            self.assertNotIn("CLERK_SECRET_KEY", path.read_text(encoding="utf-8"))

    def test_remote_rejects_accidental_owner_secret(self):
        with self.assertRaisesRegex(ValueError, "explicit --mode personal"):
            install_clients(client="codex", clerk_secret_key="test-secret")


if __name__ == "__main__":
    unittest.main()
