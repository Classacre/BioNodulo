"""Generic HTTP request node for arbitrary REST APIs."""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


HTTP_USER_AGENT = "BioNodulo/2.0 (workflow node; generic HTTP)"
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 30.0
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD")


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _safe_filename(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return name or "response"


def _parse_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be a JSON object") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return parsed


def _string_headers(value: dict[str, Any]) -> dict[str, str]:
    return {str(key): str(header_value) for key, header_value in value.items()}


def _resolve_secret(context: Any, *keys: str) -> str:
    if context is None or not hasattr(context, "resolve_secret"):
        return ""
    for key in keys:
        value = context.resolve_secret(key)
        if value:
            return str(value)
    return ""


def _auth_headers(kwargs: dict[str, Any], context: Any) -> dict[str, str]:
    mode = str(kwargs.get("auth_mode", "none") or "none").lower()
    if mode == "bearer":
        token = str(kwargs.get("bearer_token", "") or "").strip()
        token = token or _resolve_secret(context, "http_bearer_token", "HTTP_BEARER_TOKEN")
        return {"Authorization": f"Bearer {token}"} if token else {}
    if mode == "basic":
        username = str(kwargs.get("username", "") or "")
        password = str(kwargs.get("password", "") or "")
        password = password or _resolve_secret(context, "http_basic_password", "HTTP_BASIC_PASSWORD")
        if not username and not password:
            return {}
        encoded = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}
    return {}


def _request_body(body_format: str, body: Any) -> tuple[Any | None, Any | None]:
    mode = str(body_format or "none").lower()
    if mode == "none" or body in (None, ""):
        return None, None
    if mode == "json":
        try:
            return json.loads(str(body)), None
        except json.JSONDecodeError as exc:
            raise ValueError("body must be valid JSON when body_format=json") from exc
    if mode == "form":
        return None, _parse_mapping(body, "body")
    if mode == "text":
        return None, str(body)
    raise ValueError(f"Unsupported body_format: {body_format}")


async def _request(
    *,
    method: str,
    url: str,
    params: dict[str, Any],
    headers: dict[str, str],
    json_body: Any | None,
    data: Any | None,
    timeout: float,
    follow_redirects: bool,
    retries: int = MAX_RETRIES,
    retry_delay: float = RETRY_DELAY_S,
    cache_ttl: float | None = None,
    rate_limit_per_second: float | None = None,
) -> httpx.Response:
    cache = APICache(ttl_seconds=cache_ttl) if cache_ttl and cache_ttl > 0 else None
    rate_limiter = (
        TokenBucketRateLimiter(rate_per_second=rate_limit_per_second, burst=1)
        if rate_limit_per_second and rate_limit_per_second > 0
        else None
    )
    client = APIHttpClient(cache=cache, rate_limiter=rate_limiter)
    try:
        return await client.request(
            method,
            url,
            params=params,
            headers=headers,
            json=json_body,
            data=data,
            timeout=timeout,
            follow_redirects=follow_redirects,
            retries=retries,
            retry_delay=retry_delay,
            cache_ttl=cache_ttl,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f"HTTP Request failed with HTTP {status}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"HTTP Request failed: {exc}") from exc


class HTTPRequestNode(BaseNode):
    """Make a generic HTTP request and write the response body to disk."""

    NODE_ID = "http_request"
    DISPLAY_NAME = "HTTP Request"
    CATEGORY = "api"
    DESCRIPTION = "Call any HTTP or REST API with query parameters, headers, auth, and JSON/text/form bodies."
    SEARCH_ALIASES = ["http", "request", "rest", "api", "web", "fetch", "url", "json"]
    RETURN_TYPES = ("FILE", "JSON")
    RETURN_NAMES = ("response_body", "metadata")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = "https://developer.mozilla.org/en-US/docs/Web/HTTP"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "url": ("STRING", {"default": "", "description": "HTTP or HTTPS URL"}),
                "method": (list(HTTP_METHODS), {"default": "GET"}),
            },
            "optional": {
                "query_params": ("STRING", {"default": "{}", "multiline": True, "description": "JSON object of query parameters"}),
                "headers": ("STRING", {"default": "{}", "multiline": True, "description": "JSON object of request headers"}),
                "body_format": ("STRING", {"default": "none", "options": ["none", "json", "text", "form"]}),
                "body": ("STRING", {"default": "", "multiline": True}),
                "auth_mode": ("STRING", {"default": "none", "options": ["none", "bearer", "basic"]}),
                "bearer_token": ("STRING", {"default": "", "advanced": True}),
                "username": ("STRING", {"default": "", "advanced": True}),
                "password": ("STRING", {"default": "", "advanced": True}),
                "timeout": ("FLOAT", {"default": REQUEST_TIMEOUT_S, "min": 1}),
                "follow_redirects": ("BOOLEAN", {"default": True}),
                "cache_ttl": ("FLOAT", {"default": 0, "min": 0, "description": "Cache GET/HEAD responses for N seconds; 0 disables cache"}),
                "rate_limit_per_second": ("FLOAT", {"default": 0, "min": 0, "description": "Maximum requests per second; 0 disables rate limiting"}),
                "output_name": ("STRING", {"default": "", "description": "Optional response filename stem"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        url = str(kwargs.get("url", "") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("HTTP Request requires an http:// or https:// URL")
        method = str(kwargs.get("method", "GET") or "GET").upper()
        if method not in HTTP_METHODS:
            raise ValueError(f"Unsupported HTTP method: {method}")

        params = _parse_mapping(kwargs.get("query_params", "{}"), "query_params")
        headers = {
            "User-Agent": HTTP_USER_AGENT,
            **_string_headers(_parse_mapping(kwargs.get("headers", "{}"), "headers")),
        }
        headers.update(_auth_headers(kwargs, context))
        json_body, data = _request_body(str(kwargs.get("body_format", "none")), kwargs.get("body", ""))
        timeout = float(kwargs.get("timeout", REQUEST_TIMEOUT_S) or REQUEST_TIMEOUT_S)
        follow_redirects = bool(kwargs.get("follow_redirects", True))
        cache_ttl = float(kwargs.get("cache_ttl", 0) or 0)
        rate_limit_per_second = float(kwargs.get("rate_limit_per_second", 0) or 0)

        request_options: dict[str, Any] = {}
        if cache_ttl > 0:
            request_options["cache_ttl"] = cache_ttl
        if rate_limit_per_second > 0:
            request_options["rate_limit_per_second"] = rate_limit_per_second

        response = await _request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            json_body=json_body,
            data=data,
            timeout=timeout,
            follow_redirects=follow_redirects,
            **request_options,
        )

        content_type = str(response.headers.get("content-type", "")).split(";", 1)[0].strip().lower()
        extension = ".json" if "json" in content_type else ".txt"
        output_name = str(kwargs.get("output_name", "") or "").strip()
        filename = _safe_filename(output_name or "response") + extension
        body_path = _node_output_dir(self, context) / filename
        body_path.write_text(response.text, encoding="utf-8")

        metadata: dict[str, Any] = {
            "status_code": response.status_code,
            "url": str(response.url),
            "content_type": content_type,
            "headers": dict(response.headers),
            "response_body": str(body_path),
        }
        if "json" in content_type:
            try:
                if hasattr(response, "json"):
                    metadata["json"] = response.json()
                else:
                    metadata["json"] = json.loads(response.text)
            except (TypeError, ValueError):
                pass

        return {
            "outputs": {
                "response_body": str(body_path),
                "metadata": metadata,
            }
        }
