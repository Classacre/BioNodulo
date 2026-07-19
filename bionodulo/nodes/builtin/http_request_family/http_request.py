"""Generic HTTP request node for arbitrary REST APIs."""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from bionodulo.core.credentials import resolve_secret_value
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


HTTP_USER_AGENT = "BioNodulo/2.0 (workflow node; generic HTTP)"
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 30.0
MAX_TIMEOUT_S = 300.0
MAX_CACHE_TTL_S = 86400.0
MAX_RATE_LIMIT_PER_SECOND = 1000.0
MAX_RESPONSE_BYTES = 64 * 1024 * 1024
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD")
SENSITIVE_RESPONSE_HEADERS = {
    "authorization",
    "proxy-authenticate",
    "set-cookie",
    "www-authenticate",
}
SENSITIVE_QUERY_KEYS = {
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "key",
    "passwd",
    "password",
    "secret",
    "sig",
    "signature",
    "token",
}
HTTP_API_CACHE = APICache.from_environment(default_ttl_seconds=300.0)


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


def _redact_response_headers(value: Any) -> dict[str, str]:
    headers = dict(value)
    return {
        str(key): "[REDACTED]" if str(key).lower() in SENSITIVE_RESPONSE_HEADERS else str(item)
        for key, item in headers.items()
    }


def _sensitive_query_key(value: str) -> bool:
    key = value.strip().lower().replace("-", "_")
    return key in SENSITIVE_QUERY_KEYS or any(
        marker in key for marker in ("credential", "password", "secret", "signature", "token")
    )


def _redact_url(value: Any) -> str:
    parsed = urlsplit(str(value))
    hostname = parsed.hostname or ""
    rendered_host = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
    if parsed.port is not None:
        rendered_host = f"{rendered_host}:{parsed.port}"
    netloc = f"[REDACTED]@{rendered_host}" if parsed.username is not None else rendered_host
    query = urlencode(
        [
            (key, "[REDACTED]" if _sensitive_query_key(key) else item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        ],
        doseq=True,
    )
    return urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))


def _parse_bool(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{field_name} must be a boolean")


def _auth_headers(kwargs: dict[str, Any], context: Any) -> dict[str, str]:
    mode = str(kwargs.get("auth_mode", "none") or "none").lower()
    if mode == "bearer":
        token = resolve_secret_value(kwargs.get("bearer_token", ""), context, "http_bearer_token", "HTTP_BEARER_TOKEN")
        if not token:
            raise ValueError("auth_mode=bearer requires a bearer token credential")
        return {"Authorization": f"Bearer {token}"}
    if mode == "basic":
        username = str(kwargs.get("username", "") or "")
        password = resolve_secret_value(kwargs.get("password", ""), context, "http_basic_password", "HTTP_BASIC_PASSWORD")
        if not username or not password:
            raise ValueError("auth_mode=basic requires both username and password")
        encoded = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}
    return {}


def _request_body(body_format: str, body: Any) -> tuple[Any | None, Any | None]:
    mode = str(body_format or "none").lower()
    if mode not in {"none", "json", "form", "text"}:
        raise ValueError(f"Unsupported body_format: {body_format}")
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
    raise AssertionError(f"Unhandled body_format: {body_format}")


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
    cache = HTTP_API_CACHE if cache_ttl and cache_ttl > 0 else None
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
    VERSION = "1.0.0"
    GIT_URL = "https://github.com/encode/httpx.git"
    GIT_COMMIT = "26d48e0634e6ee9cdc0533996db289ce4b430177"
    LIBRARY_VERSION = "httpx 0.28.1"
    PRODUCT_SOURCE_COMMIT = "4382f1f4b19a9202dbd3cca0d25c300b9e1e2af6"
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
                "body": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "displayOptions": {"show": {"body_format": ["json", "text", "form"]}},
                    },
                ),
                "auth_mode": ("STRING", {"default": "none", "options": ["none", "bearer", "basic"]}),
                "bearer_token": (
                    "STRING",
                    {
                        "default": "",
                        "advanced": True,
                        "displayOptions": {"show": {"auth_mode": ["bearer"]}},
                    },
                ),
                "username": (
                    "STRING",
                    {
                        "default": "",
                        "advanced": True,
                        "displayOptions": {"show": {"auth_mode": ["basic"]}},
                    },
                ),
                "password": (
                    "STRING",
                    {
                        "default": "",
                        "advanced": True,
                        "displayOptions": {"show": {"auth_mode": ["basic"]}},
                    },
                ),
                "timeout": ("FLOAT", {"default": REQUEST_TIMEOUT_S, "min": 1, "max": MAX_TIMEOUT_S}),
                "follow_redirects": ("BOOLEAN", {"default": True}),
                "cache_ttl": ("FLOAT", {"default": 0, "min": 0, "max": MAX_CACHE_TTL_S, "description": "Cache GET/HEAD responses for N seconds; 0 disables cache"}),
                "rate_limit_per_second": ("FLOAT", {"default": 0, "min": 0, "max": MAX_RATE_LIMIT_PER_SECOND, "description": "Maximum requests per second; 0 disables rate limiting"}),
                "output_name": ("STRING", {"default": "", "description": "Optional response filename stem"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        url = str(inputs.get("url", "") or "").strip()
        if not url.startswith(("http://", "https://")):
            return "HTTP Request requires an http:// or https:// URL"
        method = str(inputs.get("method", "GET") or "GET").upper()
        if method not in HTTP_METHODS:
            return f"Unsupported HTTP method: {method}"
        auth_mode = str(inputs.get("auth_mode", "none") or "none").lower()
        if auth_mode not in {"none", "bearer", "basic"}:
            return f"Unsupported auth_mode: {auth_mode}"
        try:
            _parse_mapping(inputs.get("query_params", "{}"), "query_params")
            _parse_mapping(inputs.get("headers", "{}"), "headers")
            _request_body(str(inputs.get("body_format", "none")), inputs.get("body", ""))
            _parse_bool(inputs.get("follow_redirects", True), "follow_redirects")
        except ValueError as exc:
            return str(exc)
        for field, default, minimum, maximum in (
            ("timeout", REQUEST_TIMEOUT_S, 1.0, MAX_TIMEOUT_S),
            ("cache_ttl", 0.0, 0.0, MAX_CACHE_TTL_S),
            ("rate_limit_per_second", 0.0, 0.0, MAX_RATE_LIMIT_PER_SECOND),
        ):
            raw_value = inputs.get(field, default)
            if raw_value is None or str(raw_value).strip() == "":
                raw_value = default
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                return f"{field} must be a number"
            if value < minimum or value > maximum:
                return f"{field} must be between {minimum:g} and {maximum:g}"
        return True

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")
        url = str(kwargs.get("url", "") or "").strip()
        from bionodulo.core.netguard import assert_safe_url

        assert_safe_url(url)  # SSRF guard: block loopback/link-local/private hosts
        method = str(kwargs.get("method", "GET") or "GET").upper()

        params = _parse_mapping(kwargs.get("query_params", "{}"), "query_params")
        headers = {
            "User-Agent": HTTP_USER_AGENT,
            **_string_headers(_parse_mapping(kwargs.get("headers", "{}"), "headers")),
        }
        headers.update(_auth_headers(kwargs, context))
        json_body, data = _request_body(str(kwargs.get("body_format", "none")), kwargs.get("body", ""))
        timeout_value = kwargs.get("timeout", REQUEST_TIMEOUT_S)
        timeout = float(REQUEST_TIMEOUT_S if timeout_value in (None, "") else timeout_value)
        follow_redirects = _parse_bool(kwargs.get("follow_redirects", True), "follow_redirects")
        cache_value = kwargs.get("cache_ttl", 0)
        rate_value = kwargs.get("rate_limit_per_second", 0)
        cache_ttl = float(0 if cache_value in (None, "") else cache_value)
        rate_limit_per_second = float(0 if rate_value in (None, "") else rate_value)

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
        if "json" in content_type:
            extension = ".json"
        elif content_type.startswith("text/") or not content_type:
            extension = ".txt"
        else:
            extension = ".bin"
        output_name = str(kwargs.get("output_name", "") or "").strip()
        filename = _safe_filename(output_name or "response") + extension
        body_path = _node_output_dir(self, context) / filename
        content = getattr(response, "content", None)
        if isinstance(content, bytes):
            if len(content) > MAX_RESPONSE_BYTES:
                raise RuntimeError(f"HTTP response exceeds the {MAX_RESPONSE_BYTES}-byte node limit")
            body_path.write_bytes(content)
        else:
            text = str(response.text)
            if len(text.encode("utf-8")) > MAX_RESPONSE_BYTES:
                raise RuntimeError(f"HTTP response exceeds the {MAX_RESPONSE_BYTES}-byte node limit")
            body_path.write_text(text, encoding="utf-8")

        metadata: dict[str, Any] = {
            "status_code": response.status_code,
            "url": _redact_url(response.url),
            "content_type": content_type,
            "headers": _redact_response_headers(response.headers),
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
