from __future__ import annotations

import json
import urllib.request
from typing import Any

from bionodulo.nodes.base import BaseNode


class ApiNode(BaseNode):
    CATEGORY = "API"
    REQUIRES_EXTERNAL_TOOLS = False

    def resolve_secret(self, context: Any, name: str) -> str:
        if not name:
            return ""
        resolver = getattr(context, "resolve_secret", None)
        return resolver(name) if resolver else ""


class HttpGetNode(ApiNode):
    NODE_ID = "api_http_get"
    DISPLAY_NAME = "HTTP GET"
    DESCRIPTION = "Fetch JSON or text from an external API using server-side secret references."
    SEARCH_ALIASES = ["api", "http", "ncbi", "aws", "omics"]
    RETURN_TYPES = ("FILE", "STRING")
    RETURN_NAMES = ("response_file", "response_text")

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {"url": ("STRING", {"default": "https://example.org"})},
            "optional": {"secret_ref": ("STRING", {"default": ""}), "header_name": ("STRING", {"default": "Authorization"})},
            "hidden": {},
        }

    def run(self, context: Any = None, **kwargs: Any) -> dict[str, Any]:
        if context is None:
            raise RuntimeError("HTTP GET node requires context")
        secret = self.resolve_secret(context, str(kwargs.get("secret_ref") or ""))
        headers = {}
        if secret:
            headers[str(kwargs.get("header_name") or "Authorization")] = secret
        request = urllib.request.Request(str(kwargs["url"]), headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - user-configured local workflow API node
            text = response.read().decode("utf-8", errors="replace")
        output_file = context.node_dir / "api_response.txt"
        try:
            parsed = json.loads(text)
            output_file = context.node_dir / "api_response.json"
            output_file.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
        except json.JSONDecodeError:
            output_file.write_text(text, encoding="utf-8")
        return {"response_file": str(output_file), "response_text": text[:20000]}
