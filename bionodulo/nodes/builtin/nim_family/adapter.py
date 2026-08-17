"""Shared boundary for NVIDIA NIM biology inference nodes.

Hosted biology NIMs live under ``https://health.api.nvidia.com/v1/biology`` and
take plain JSON with untokenized sequences; self-hosted NIM containers serve
the same paths at ``http://localhost:8000/v1/biology`` (set ``base_url`` or
``BIONODULO_NIM_BASE_URL``). Like the LiteLLM lane, these are model endpoints,
so the adapter talks to them with a direct ``httpx.AsyncClient`` and no netguard
hop; a localhost NIM container must stay reachable.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from bionodulo.core.credentials import REDACTED, resolve_secret_value
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import TokenBucketRateLimiter


NIM_DEFAULT_BASE_URL = "https://health.api.nvidia.com/v1/biology"
NIM_DEFAULT_STATUS_URL = "https://health.api.nvidia.com/v1/status"
NIM_USER_AGENT = "BioNodulo/2.0 (workflow node; NVIDIA NIM)"
NIM_REQUEST_TIMEOUT_S = 300.0
NIM_MAX_RETRIES = 3
NIM_RETRY_DELAY_S = 1.0
NIM_HOSTED_RPM = 40
NIM_DEFAULT_RPM = 30
NIM_API_KEY_ENV_VARS = ("BIONODULO_NIM_API_KEY", "NVIDIA_API_KEY")
NIM_BASE_URL_ENV_VAR = "BIONODULO_NIM_BASE_URL"
NIM_STATUS_URL_ENV_VAR = "BIONODULO_NIM_STATUS_URL"
NIM_POLL_SECONDS_DEFAULT = 10
NIM_BOLTZ2_POLL_HEADER = "NVCF-POLL-SECONDS"


class NimError(RuntimeError):
    """Fatal NIM node error with secrets already stripped."""


class NimInferenceNode(BaseNode):
    """Shared contract for NVIDIA NIM inference nodes."""

    NODE_ID = ""
    CATEGORY = "ai"
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: list[str] = []
    VERSION = "1.0.0"
    DOCUMENTATION_URL = "https://docs.nvidia.com/nim/bionemo/"
    EXPERIMENTAL = True


def resolve_api_key(explicit: Any, context: Any) -> str:
    """Resolve node param -> context secret -> env, or fail closed."""
    resolved = resolve_secret_value(
        explicit,
        context,
        "nim_api_key",
        default=os.environ.get(NIM_API_KEY_ENV_VARS[0], "") or os.environ.get(NIM_API_KEY_ENV_VARS[1], ""),
    )
    if not resolved:
        raise NimError(
            "NVIDIA NIM API key is required: pass api_key, store a nim_api_key workflow secret, "
            f"or set {' or '.join(NIM_API_KEY_ENV_VARS)}"
        )
    return resolved


def resolve_base_url(explicit: Any) -> str:
    base = str(explicit or "").strip() or os.environ.get(NIM_BASE_URL_ENV_VAR, "") or NIM_DEFAULT_BASE_URL
    return base.rstrip("/")


def resolve_status_url(explicit: Any, base_url: str) -> str:
    status = str(explicit or "").strip() or os.environ.get(NIM_STATUS_URL_ENV_VAR, "")
    if status:
        return status.rstrip("/")
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/biology"):
        return trimmed[: -len("biology")] + "status"
    return NIM_DEFAULT_STATUS_URL


def _redact(value: Any) -> Any:
    from bionodulo.core.credentials import redact_tree

    return redact_tree(value)


def _sanitize_error(exc: BaseException) -> str:
    text = _redact(f"{type(exc).__name__}: {exc}")
    return str(text)


def _retry_delay(response: httpx.Response | None, base_delay: float, attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
    return float(base_delay) * (2**attempt)


def _should_retry(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


class NimClient:
    """Direct async NIM client: token-bucket rate limit plus Retry-After-aware retries."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        requests_per_minute: float = NIM_DEFAULT_RPM,
        timeout: float = NIM_REQUEST_TIMEOUT_S,
        retries: int = NIM_MAX_RETRIES,
        retry_delay: float = NIM_RETRY_DELAY_S,
        sleeper: Any = asyncio.sleep,
        clock: Any = time.monotonic,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = float(timeout)
        self.retries = max(1, int(retries))
        self.retry_delay = float(retry_delay)
        self._sleep = sleeper
        self._clock = clock
        self.rate_limiter = (
            TokenBucketRateLimiter(rate_per_second=float(requests_per_minute) / 60.0, burst=1)
            if requests_per_minute and requests_per_minute > 0
            else None
        )

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "User-Agent": NIM_USER_AGENT,
            "Accept": "application/json, application/octet-stream, */*",
            "Authorization": f"Bearer {self.api_key}",
        }
        headers.update(extra or {})
        return headers

    def _scrub(self, value: Any) -> Any:
        if isinstance(value, str):
            return value.replace(self.api_key, REDACTED) if self.api_key else value
        if isinstance(value, dict):
            return {str(key): self._scrub(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._scrub(item) for item in value]
        return value

    async def _request(self, method: str, url: str, *, headers: dict[str, str], json_body: Any = None) -> httpx.Response:
        attempts = self.retries
        last_error: BaseException | None = None
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for attempt in range(attempts):
                if self.rate_limiter is not None:
                    await self.rate_limiter.acquire()
                try:
                    response = await client.request(method, url, headers=headers, json=json_body)
                    if _should_retry(response.status_code) and attempt < attempts - 1:
                        await self._sleep(_retry_delay(response, self.retry_delay, attempt))
                        continue
                    return response
                except httpx.HTTPError as exc:
                    last_error = exc
                    if attempt >= attempts - 1:
                        raise NimError(f"NIM request failed: {self._scrub(_sanitize_error(exc))}") from exc
                    await self._sleep(_retry_delay(None, self.retry_delay, attempt))
        raise NimError(f"NIM request failed: {self._scrub(_sanitize_error(last_error))}" if last_error else "NIM request failed")

    async def post_json(self, endpoint: str, payload: dict[str, Any]) -> httpx.Response:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        return await self._request("POST", url, headers=self._headers({"Content-Type": "application/json"}), json_body=payload)

    async def get_json(self, url: str, *, headers: dict[str, str] | None = None) -> httpx.Response:
        return await self._request("GET", url, headers=self._headers(headers))

    async def post_json_ok(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self.post_json(endpoint, payload)
        if response.status_code >= 400:
            raise NimError(
                f"NIM endpoint {endpoint} failed with HTTP {response.status_code}: "
                f"{self._scrub(_redact(response.text[:500]))}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise NimError(f"NIM endpoint {endpoint} returned a non-JSON body") from exc
        if not isinstance(body, dict):
            raise NimError(f"NIM endpoint {endpoint} response must be a JSON object")
        return body

    async def poll_until_done(
        self,
        status_url: str,
        *,
        poll_seconds: int = NIM_POLL_SECONDS_DEFAULT,
        timeout_s: float,
    ) -> dict[str, Any]:
        deadline = self._clock() + float(timeout_s)
        while True:
            response = await self.get_json(
                status_url,
                headers={NIM_BOLTZ2_POLL_HEADER: str(max(1, int(poll_seconds)))},
            )
            if response.status_code >= 500 and response.status_code != 503:
                raise NimError(f"NIM status poll failed with HTTP {response.status_code}")
            body: dict[str, Any] = {}
            try:
                parsed = response.json()
                if isinstance(parsed, dict):
                    body = parsed
            except ValueError:
                body = {}
            status = str(body.get("status", "")).lower()
            if status in {"failed", "error", "cancelled", "canceled"}:
                detail = body.get("error") or body.get("message") or body.get("response") or body
                raise NimError(f"NIM async request failed: {self._scrub(_redact(detail))}")
            if status in {"complete", "completed", "succeeded", "success", "done", "finished"}:
                payload = body.get("response", body.get("result", body))
                if not isinstance(payload, dict):
                    payload = {"payload": payload}
                return payload
            if self._clock() >= deadline:
                raise NimError(f"NIM async request did not finish within {timeout_s:g}s (last status: {status or 'unknown'})")
            await self._sleep(float(poll_seconds))


def node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def require_artifacts(*paths: Path) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise NimError(f"Expected node artifacts were not created: {', '.join(missing)}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_redact(payload), indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def parse_bool(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{field_name} must be a boolean")


def parse_json_object(value: Any, field_name: str) -> dict[str, Any]:
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


def parse_json_list(value: Any, field_name: str) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return list(value)
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be a JSON list") from exc
    if not isinstance(parsed, list):
        raise ValueError(f"{field_name} must be a JSON list")
    return parsed


def bounded_int(value: Any, field_name: str, minimum: int, maximum: int, default: int) -> int:
    raw = default if value in (None, "") else value
    try:
        number = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if number < minimum or number > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
    return number


def bounded_float(value: Any, field_name: str, minimum: float, maximum: float, default: float) -> float:
    raw = default if value in (None, "") else value
    try:
        number = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number") from exc
    if number < minimum or number > maximum:
        raise ValueError(f"{field_name} must be between {minimum:g} and {maximum:g}")
    return number


def fixture_seed_hex(*parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return digest


def fixture_sequence(seed_hex: str, alphabet: str, length: int) -> str:
    bases = list(alphabet)
    hex_stream: list[str] = []
    counter = 0
    while len(hex_stream) * 32 < length * 2 + 32:
        hex_stream.append(fixture_seed_hex(seed_hex, str(counter)))
        counter += 1
    block = "".join(hex_stream)
    return "".join(bases[int(block[i : i + 2], 16) % len(bases)] for i in range(0, length * 2, 2))[:length]


def fixture_embedding(seed_hex: str, dim: int) -> list[float]:
    block = fixture_seed_hex(seed_hex)
    values: list[float] = []
    index = 0
    while len(values) < dim:
        byte = int(block[(index * 2) % len(block) : (index * 2) % len(block) + 2], 16)
        values.append(round(((byte % 200) - 100) / 1000.0, 6))
        index += 1
    return values


def _numpy() -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise NimError("NIM embedding output requires numpy. Install the numpy package.") from exc
    return np


def save_npz(path: Path, arrays: dict[str, Any]) -> None:
    np = _numpy()
    np.savez(path, **arrays)


def load_npz_bytes(raw: bytes) -> dict[str, Any]:
    import io

    np = _numpy()
    with np.load(io.BytesIO(raw)) as archive:
        return {name: archive[name] for name in archive.files}


def decode_base64_npz(data: str) -> dict[str, Any]:
    import base64

    try:
        raw = base64.b64decode(str(data), validate=True)
    except Exception as exc:
        raise NimError("NIM forward response data is not valid base64 NPZ content") from exc
    return load_npz_bytes(raw)


def mean_pool(axis_zero: Any) -> list[float]:
    np = _numpy()
    array = np.asarray(axis_zero, dtype="float64")
    pooled = array.mean(axis=0) if array.ndim >= 2 else array
    return [round(float(value), 8) for value in pooled]


def redact_for_output(payload: Any) -> Any:
    return _redact(payload)


REDACTED_SENTINEL = REDACTED

__all__ = [
    "NIM_API_KEY_ENV_VARS",
    "NIM_BASE_URL_ENV_VAR",
    "NIM_BOLTZ2_POLL_HEADER",
    "NIM_DEFAULT_BASE_URL",
    "NIM_DEFAULT_RPM",
    "NIM_DEFAULT_STATUS_URL",
    "NIM_HOSTED_RPM",
    "NIM_MAX_RETRIES",
    "NIM_POLL_SECONDS_DEFAULT",
    "NIM_REQUEST_TIMEOUT_S",
    "NIM_RETRY_DELAY_S",
    "NIM_STATUS_URL_ENV_VAR",
    "NIM_USER_AGENT",
    "NimClient",
    "NimError",
    "NimInferenceNode",
    "bounded_float",
    "bounded_int",
    "decode_base64_npz",
    "fixture_embedding",
    "fixture_seed_hex",
    "fixture_sequence",
    "load_npz_bytes",
    "mean_pool",
    "node_output_dir",
    "parse_bool",
    "parse_json_list",
    "parse_json_object",
    "redact_for_output",
    "require_artifacts",
    "resolve_api_key",
    "resolve_base_url",
    "resolve_status_url",
    "save_npz",
    "write_json",
]
