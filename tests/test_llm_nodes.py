from __future__ import annotations

import importlib
import json
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.ai.llm_backend import (
    LLMConfig,
    LLMResponse,
    render_prompt,
    resolve_llm_config,
    safe_json_parse,
)
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_llm_nodes_are_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["llm_prompt"]["display_name"] == "LLM Prompt"
    assert info["llm_prompt"]["category"] == "ai"
    assert info["llm_prompt"]["output"] == ["STRING", "JSON"]
    assert info["llm_prompt"]["output_name"] == ["response", "metadata"]
    assert info["llm_prompt"]["required_conda_packages"] == ["litellm"]
    assert info["llm_prompt"]["search_aliases"]

    assert info["llm_decision"]["display_name"] == "LLM Decision"
    assert info["llm_decision"]["category"] == "ai"
    assert info["llm_decision"]["output"] == ["STRING", "BOOLEAN", "JSON"]
    assert info["llm_decision"]["output_name"] == ["label", "matched", "decision_json"]
    assert info["llm_decision"]["experimental"] is True

    assert info["ai_variant_interpretation"]["display_name"] == "AI Variant Interpretation"
    assert info["ai_variant_interpretation"]["category"] == "ai"
    assert info["ai_variant_interpretation"]["output"] == ["JSON", "CSV"]
    assert info["ai_variant_interpretation"]["output_name"] == ["interpretation_json", "scores_csv"]
    assert info["ai_variant_interpretation"]["required_conda_packages"] == ["litellm", "pandas"]
    assert info["ai_variant_interpretation"]["experimental"] is True
    assert "acmg" in info["ai_variant_interpretation"]["search_aliases"]

    variant_inputs = info["ai_variant_interpretation"]["input"]
    assert set(variant_inputs["required"]) == {"variant_table"}
    assert set(variant_inputs["optional"]) == {
        "framework",
        "gene_context",
        "include_literature",
        "max_variants",
        "provider",
        "model",
        "api_key",
        "api_base",
        "temperature",
        "max_tokens",
        "timeout",
    }


def test_render_prompt_substitutes_context_and_leaves_unknown_variables() -> None:
    assert render_prompt("Analyze {{ gene }} in {{species}}. {{missing}}", {"gene": "TP53", "species": "human"}) == (
        "Analyze TP53 in human. {{missing}}"
    )


def test_resolve_llm_config_uses_explicit_context_and_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai")
    context = SimpleNamespace(resolve_secret=lambda key: "secret-key" if key == "llm_api_key" else None)

    explicit = resolve_llm_config(
        provider="anthropic",
        model="claude-3-5-sonnet",
        api_key="direct-key",
        api_base="https://llm.example.test/v1",
        temperature=0.2,
        max_tokens=512,
        context=context,
    )
    assert explicit == LLMConfig(
        provider="anthropic",
        model="anthropic/claude-3-5-sonnet",
        api_key="direct-key",
        api_base="https://llm.example.test/v1",
        temperature=0.2,
        max_tokens=512,
    )

    from_secret = resolve_llm_config(provider="openai", model="", api_key="", context=context)
    assert from_secret.api_key == "secret-key"
    assert from_secret.model == "openai/gpt-4.1-mini"

    without_secret = resolve_llm_config(provider="openai", model="", api_key="", context=None)
    assert without_secret.api_key == "env-openai"


def test_safe_json_parse_accepts_plain_and_fenced_json() -> None:
    assert safe_json_parse('{"label": "pass"}') == {"label": "pass"}
    assert safe_json_parse('```json\n{"label": "fail"}\n```') == {"label": "fail"}
    assert safe_json_parse("not-json") == {}


@pytest.mark.asyncio
async def test_llm_prompt_renders_template_and_returns_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("llm_prompt")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        calls.append({"config": config, "messages": messages, "json_mode": json_mode})
        return LLMResponse(content='{"answer": "TP53 is a tumor suppressor"}', model=config.model, usage={"total_tokens": 12})

    monkeypatch.setattr(module, "call_llm", fake_call_llm)

    response, metadata = await node_class().run(
        prompt="Summarize {{gene}}",
        variables='{"gene": "TP53"}',
        system_prompt="You are concise.",
        provider="mock",
        model="test-model",
        api_key="unused",
        temperature=0.0,
        max_tokens=128,
        json_mode=True,
    )

    assert response == '{"answer": "TP53 is a tumor suppressor"}'
    assert metadata == {
        "provider": "mock",
        "model": "test-model",
        "json_mode": True,
        "usage": {"total_tokens": 12},
        "parsed_json": {"answer": "TP53 is a tumor suppressor"},
    }
    assert calls[0]["messages"] == [
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "Summarize TP53"},
    ]
    assert calls[0]["json_mode"] is True


@pytest.mark.asyncio
async def test_llm_decision_parses_allowed_label_and_reports_match(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("llm_decision")
    module = importlib.import_module(node_class.__module__)

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        assert json_mode is True
        assert "Allowed labels: pass, review, fail" in messages[-1]["content"]
        return LLMResponse(
            content='{"label": "review", "confidence": 0.81, "reason": "Depth is borderline"}',
            model=config.model,
        )

    monkeypatch.setattr(module, "call_llm", fake_call_llm)

    label, matched, decision_json = await node_class().run(
        input_data="sample=S1 depth=18 contamination=0.02",
        criteria="Route samples with depth under 20 to review.",
        labels="pass, review, fail",
        default_label="fail",
        provider="mock",
        model="decision-model",
        api_key="unused",
    )

    assert label == "review"
    assert matched is True
    assert decision_json["label"] == "review"
    assert decision_json["confidence"] == 0.81
    assert decision_json["reason"] == "Depth is borderline"


@pytest.mark.asyncio
async def test_llm_decision_uses_default_label_when_response_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("llm_decision")
    module = importlib.import_module(node_class.__module__)

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        return LLMResponse(content='{"label": "unknown", "reason": "ambiguous"}', model=config.model)

    monkeypatch.setattr(module, "call_llm", fake_call_llm)

    assert await node_class().run(
        input_data="sample=S2",
        criteria="Classify sample",
        labels="pass, fail",
        default_label="fail",
        provider="mock",
        model="decision-model",
        api_key="unused",
    ) == ("fail", False, {"label": "fail", "matched": False, "raw_label": "unknown", "reason": "ambiguous"})


@pytest.mark.asyncio
async def test_ai_variant_interpretation_writes_json_and_scores_csv(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("ai_variant_interpretation")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    variant_table = tmp_path / "variants.tsv"
    variant_table.write_text(
        "chrom\tpos\tref\talt\tgene\tconsequence\taf\n"
        "17\t43044295\tG\tA\tBRCA1\tmissense_variant\t0.00001\n"
        "7\t140453136\tA\tT\tBRAF\tmissense_variant\t0.02\n",
        encoding="utf-8",
    )

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        calls.append({"config": config, "messages": messages, "json_mode": json_mode})
        return LLMResponse(
            content=json.dumps({
                "interpretations": [
                    {
                        "variant_id": "17:43044295:G>A",
                        "gene": "BRCA1",
                        "pathogenicity": "Likely pathogenic",
                        "confidence": 0.86,
                        "evidence": ["PM2", "PP3"],
                        "summary": "Rare BRCA1 missense variant with supporting computational evidence.",
                    },
                    {
                        "variant_id": "7:140453136:A>T",
                        "gene": "BRAF",
                        "pathogenicity": "VUS",
                        "confidence": 0.52,
                        "evidence": ["limited context"],
                        "summary": "BRAF variant needs external review.",
                    },
                ]
            }),
            model=config.model,
            usage={"total_tokens": 321},
        )

    monkeypatch.setattr(module, "call_llm", fake_call_llm)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        variant_table=str(variant_table),
        framework="ACMG",
        gene_context="Hereditary cancer panel",
        include_literature=True,
        max_variants=10,
        provider="mock",
        model="variant-model",
        api_key="unused",
        temperature=0.1,
        max_tokens=2048,
        context=context,
    )

    json_path = tmp_path / "ai_variant_interpretation" / "interpretation_json.json"
    csv_path = tmp_path / "ai_variant_interpretation" / "scores_csv.csv"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    scores_csv = csv_path.read_text(encoding="utf-8")

    assert result == {"outputs": {"interpretation_json": str(json_path), "scores_csv": str(csv_path)}}
    assert payload["variant_count"] == 2
    assert payload["framework"] == "ACMG"
    assert payload["gene_context"] == "Hereditary cancer panel"
    assert payload["include_literature"] is True
    assert payload["interpretations"][0]["pathogenicity"] == "Likely pathogenic"
    assert payload["usage"] == {"total_tokens": 321}
    assert "variant_id,gene,pathogenicity,confidence,summary" in scores_csv
    assert "17:43044295:G>A,BRCA1,Likely pathogenic,0.86" in scores_csv

    prompt = calls[0]["messages"][-1]["content"]
    assert calls[0]["json_mode"] is True
    assert calls[0]["config"].model == "variant-model"
    assert "ACMG" in prompt
    assert "Hereditary cancer panel" in prompt
    assert "BRCA1" in prompt
    assert "Return a JSON object" in prompt


@pytest.mark.asyncio
async def test_ai_variant_interpretation_handles_empty_variant_table(tmp_path: Any) -> None:
    node_class = _node_class("ai_variant_interpretation")
    variant_table = tmp_path / "variants.tsv"
    variant_table.write_text("chrom\tpos\tref\talt\tgene\n", encoding="utf-8")

    result = await node_class().run(
        variant_table=str(variant_table),
        provider="mock",
        model="variant-model",
        api_key="unused",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    json_path = tmp_path / "ai_variant_interpretation" / "interpretation_json.json"
    csv_path = tmp_path / "ai_variant_interpretation" / "scores_csv.csv"
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert result == {"outputs": {"interpretation_json": str(json_path), "scores_csv": str(csv_path)}}
    assert payload["variant_count"] == 0
    assert payload["interpretations"] == []
    assert csv_path.read_text(encoding="utf-8") == "variant_id,gene,pathogenicity,confidence,summary\n"
