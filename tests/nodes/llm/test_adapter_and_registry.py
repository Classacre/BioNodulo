from __future__ import annotations

from typing import Any

import pytest

from bionodulo.ai.llm_backend import LLMConfig, LLMResponse
from bionodulo.nodes.builtin import llm_family as llm
from bionodulo.nodes.builtin.llm_family import adapter, ai_embedding, ai_sequence_classification


EXPECTED_IDS = {
    "ai_data_extraction",
    "ai_embedding",
    "ai_image_analysis",
    "ai_literature_search",
    "ai_pipeline_advisor",
    "ai_report_generator",
    "ai_sequence_analysis",
    "ai_sequence_classification",
    "ai_variant_interpretation",
    "embedding_generation",
    "fine_tune_llm",
    "llm_decision",
    "llm_prompt",
    "model_inference",
}


def test_llm_ids_have_focused_owners_and_pinned_authority() -> None:
    classes = [getattr(llm, name) for name in llm.__all__]

    assert {node_class.NODE_ID for node_class in classes} == EXPECTED_IDS
    assert all(node_class.__module__.startswith("bionodulo.nodes.builtin.llm_family.") for node_class in classes)
    assert len({node_class.__module__ for node_class in classes}) == len(classes)
    assert llm.LLMPromptNode.VERSION == "1.87.1"
    assert llm.LLMPromptNode.GIT_COMMIT == "cc9b99c2e35795476c7a00e34a85ee0573d6d66c"
    assert adapter.LITELLM_MAIN_SOURCE_SHA256 == (
        "41836055172c66154795feb7637d05cd5a1669590a12a60ecb4f5e1a95b2ed06"
    )
    assert llm.AIEmbeddingNode.GIT_COMMIT == "8cb5963cc22174954e7dca2c0a3320b7dc2f4edc"
    assert ai_sequence_classification.TRANSFORMERS_MODELING_AUTO_SHA256 == (
        "6e4fa67c88e02a8b84d46d7b1719e760f197073b7b233bcf30eeb596f5a5f07a"
    )
    assert ai_sequence_classification.TRANSFORMERS_MODELING_UTILS_SHA256 == (
        "bf1c6b2a43cf7c36fb79f37c981424dd6ae78eb863fcaa5d2a37e76c9828611d"
    )
    assert ai_embedding._EMBEDDING_MODEL_REGISTRY["esm2_t6_8M"] == {
        "model": "facebook/esm2_t6_8M_UR50D",
        "revision": "c731040fcd8d73dceaa04b0a8e6329b345b0f5df",
        "url": "https://huggingface.co/facebook/esm2_t6_8M_UR50D",
    }
    assert ai_sequence_classification.NAMED_CLASSIFIER_AUTHORITIES["deeploc"] == {
        "tool": "DeepLoc",
        "version": "2.1",
        "url": "https://services.healthtech.dtu.dk/services/DeepLoc-2.1/",
        "status": "disabled_without_revision_pinned_task_model",
    }
    assert llm.FineTuneLLMNode.GIT_COMMIT == "77daa8d3b7decf2b40238ab47e2c1bd0f26c7749"


def test_provider_configuration_rejects_unsupported_and_unroutable_values() -> None:
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        adapter._llm_config_from_kwargs({"provider": "mock"})

    with pytest.raises(ValueError, match="requires api_base"):
        adapter._llm_config_from_kwargs({"provider": "custom", "model": "model"})

    config = adapter._llm_config_from_kwargs(
        {"provider": "custom", "model": "model", "api_base": "https://llm.example/v1"}
    )
    assert config.api_base == "https://llm.example/v1"


@pytest.mark.asyncio
async def test_provider_boundary_fails_on_errors_empty_content_and_malformed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = LLMConfig(provider="litellm", model="test-model")

    async def provider_error(*_args: Any, **_kwargs: Any) -> LLMResponse:
        return LLMResponse(content="", error="provider unavailable")

    monkeypatch.setattr(adapter, "_backend_call_llm", provider_error)
    with pytest.raises(RuntimeError, match="provider unavailable"):
        await adapter.call_llm(config, [{"role": "user", "content": "hello"}])

    async def empty_response(*_args: Any, **_kwargs: Any) -> LLMResponse:
        return LLMResponse(content="")

    monkeypatch.setattr(adapter, "_backend_call_llm", empty_response)
    with pytest.raises(RuntimeError, match="empty completion"):
        await adapter.call_llm(config, [{"role": "user", "content": "hello"}])

    async def malformed_response(*_args: Any, **_kwargs: Any) -> LLMResponse:
        return LLMResponse(content="not-json")

    monkeypatch.setattr(adapter, "_backend_call_llm", malformed_response)
    with pytest.raises(RuntimeError, match="malformed JSON"):
        await adapter.call_llm(config, [{"role": "user", "content": "hello"}], json_mode=True)


@pytest.mark.asyncio
async def test_provider_boundary_requires_credentials_for_remote_openai() -> None:
    config = LLMConfig(provider="openai", model="openai/gpt-4.1-mini", api_key="")
    with pytest.raises(ValueError, match="API key is required"):
        await adapter.call_llm(config, [{"role": "user", "content": "hello"}])
