"""NIM connectivity smoke test: one-token Evo 2 generate round-trip."""

from __future__ import annotations

import time
from typing import Any


from .adapter import (
    NIM_DEFAULT_RPM,
    NIM_HOSTED_RPM,
    NimClient,
    NimInferenceNode,
    bounded_float,
    node_output_dir,
    parse_bool,
    redact_for_output,
    resolve_api_key,
    resolve_base_url,
    write_json,
)
from .nim_evo2_generate import EVO2_ENDPOINT, normalize_dna_sequence


class NimTestNode(NimInferenceNode):
    """Ping the NVIDIA biology NIM with a minimal Evo 2 generate call."""

    NODE_ID = "nim_test"
    DISPLAY_NAME = "NIM Test"
    DESCRIPTION = (
        "Verify NVIDIA NIM connectivity and credentials with a one-token Evo 2 generate call; "
        "returns ok/fail plus latency. Useful for debugging API key and base_url environments. "
        "fixture_mode=True checks nothing and returns a synthetic ok."
    )
    SEARCH_ALIASES = ["nim", "nvidia", "health", "ping", "connectivity", "diagnostic", "test"]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("health_json",)
    OUTPUT_NODE = True
    DOCUMENTATION_URL = "https://docs.nvidia.com/nim/bionemo/evo2/latest/endpoints.html"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "api_key": ("STRING", {"default": "", "advanced": True}),
                "base_url": ("STRING", {"default": "", "advanced": True}),
                "requests_per_minute": ("FLOAT", {"default": NIM_DEFAULT_RPM, "min": 0, "max": NIM_HOSTED_RPM}),
                "timeout": ("FLOAT", {"default": 60.0, "min": 1, "max": 3600}),
                "fixture_mode": ("BOOLEAN", {"default": False, "description": "Skip the network and return a synthetic ok"}),
            },
            "hidden": {"context": ("CONTEXT", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        return True

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        fixture_mode = parse_bool(kwargs.get("fixture_mode", False), "fixture_mode")
        out_dir = node_output_dir(self, context)
        json_path = out_dir / "nim_health.json"

        if fixture_mode:
            payload = {
                "fixture_mode": True,
                "status": "NON_SCIENTIFIC_FIXTURE_ONLY",
                "ok": True,
                "endpoint": EVO2_ENDPOINT,
                "latency_ms": 0,
                "detail": "fixture_mode: no request was sent",
            }
        else:
            api_key = resolve_api_key(kwargs.get("api_key", ""), context)
            base_url = resolve_base_url(kwargs.get("base_url", ""))
            client = NimClient(
                base_url=base_url,
                api_key=api_key,
                requests_per_minute=bounded_float(
                    kwargs.get("requests_per_minute"), "requests_per_minute", 0, NIM_HOSTED_RPM, NIM_DEFAULT_RPM
                ),
                timeout=bounded_float(kwargs.get("timeout"), "timeout", 1.0, 3600.0, 60.0),
            )
            prompt = normalize_dna_sequence("ACGT", "dna")
            started = time.monotonic()
            try:
                body = await client.post_json_ok(
                    EVO2_ENDPOINT,
                    {"sequence": prompt, "num_tokens": 1, "temperature": 0.7, "top_k": 1},
                )
            except Exception as exc:
                payload = {
                    "fixture_mode": False,
                    "ok": False,
                    "endpoint": EVO2_ENDPOINT,
                    "base_url": base_url,
                    "error": str(redact_for_output(f"{type(exc).__name__}: {exc}")),
                }
            else:
                latency_ms = int((time.monotonic() - started) * 1000)
                payload = {
                    "fixture_mode": False,
                    "ok": True,
                    "endpoint": EVO2_ENDPOINT,
                    "base_url": base_url,
                    "latency_ms": latency_ms,
                    "elapsed_ms": body.get("elapsed_ms"),
                    "response_keys": sorted(str(key) for key in body),
                }

        write_json(json_path, payload)
        if not payload.get("ok"):
            raise RuntimeError(f"NIM health check failed: {payload.get('error', 'unknown error')}")
        return {"outputs": {"health_json": str(json_path)}}


__all__ = ["NimTestNode"]
