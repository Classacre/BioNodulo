"""BIONODULO_LLM_API_KEY is the canonical worker-side key env for custom providers."""
import os
from unittest import mock

from bionodulo.ai.llm_backend import resolve_llm_config


def test_custom_provider_prefers_bionodulo_llm_api_key() -> None:
    env = {"BIONODULO_LLM_API_KEY": "sk-kimi-test", "OPENAI_API_KEY": "sk-openai", "LITELLM_API_KEY": "sk-litellm"}
    with mock.patch.dict(os.environ, env, clear=False):
        cfg = resolve_llm_config(provider="custom", api_base="https://api.kimi.com/coding/v1", model="kimi-k3")
    assert cfg.api_key == "sk-kimi-test"


def test_custom_provider_falls_back_to_openai_key() -> None:
    env = {"OPENAI_API_KEY": "sk-openai"}
    with mock.patch.dict(os.environ, env, clear=False):
        cfg = resolve_llm_config(provider="custom", api_base="https://x.example/v1")
    assert cfg.api_key == "sk-openai"
