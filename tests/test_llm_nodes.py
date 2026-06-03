from __future__ import annotations

import importlib
import json
from types import SimpleNamespace
from typing import Any

import numpy as np
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

    assert info["ai_sequence_analysis"]["display_name"] == "AI Sequence Analysis"
    assert info["ai_sequence_analysis"]["category"] == "ai"
    assert info["ai_sequence_analysis"]["output"] == ["JSON", "STRING"]
    assert info["ai_sequence_analysis"]["output_name"] == ["analysis_json", "summary_text"]
    assert info["ai_sequence_analysis"]["required_conda_packages"] == ["litellm", "biopython"]
    assert "motif" in info["ai_sequence_analysis"]["search_aliases"]
    assert "fasta" in info["ai_sequence_analysis"]["search_aliases"]

    assert info["ai_report_generator"]["display_name"] == "AI Report Generator"
    assert info["ai_report_generator"]["category"] == "ai"
    assert info["ai_report_generator"]["output"] == ["HTML_REPORT", "STRING"]
    assert info["ai_report_generator"]["output_name"] == ["report_html", "report_markdown"]
    assert info["ai_report_generator"]["required_conda_packages"] == ["litellm"]
    assert "markdown" in info["ai_report_generator"]["search_aliases"]
    assert "report" in info["ai_report_generator"]["search_aliases"]

    assert info["ai_literature_search"]["display_name"] == "AI Literature Search"
    assert info["ai_literature_search"]["category"] == "ai"
    assert info["ai_literature_search"]["output"] == ["JSON", "STRING"]
    assert info["ai_literature_search"]["output_name"] == ["papers_json", "summary_text"]
    assert info["ai_literature_search"]["required_conda_packages"] == ["litellm"]
    assert info["ai_literature_search"]["experimental"] is True
    assert "pubmed" in info["ai_literature_search"]["search_aliases"]
    assert "literature" in info["ai_literature_search"]["search_aliases"]

    assert info["ai_data_extraction"]["display_name"] == "AI Data Extraction"
    assert info["ai_data_extraction"]["category"] == "ai"
    assert info["ai_data_extraction"]["output"] == ["JSON", "CSV"]
    assert info["ai_data_extraction"]["output_name"] == ["extracted_json", "extracted_csv"]
    assert info["ai_data_extraction"]["required_conda_packages"] == ["litellm"]
    assert info["ai_data_extraction"]["experimental"] is True
    assert "entities" in info["ai_data_extraction"]["search_aliases"]
    assert "biocuration" in info["ai_data_extraction"]["search_aliases"]

    assert info["ai_pipeline_advisor"]["display_name"] == "AI Pipeline Advisor"
    assert info["ai_pipeline_advisor"]["category"] == "ai"
    assert info["ai_pipeline_advisor"]["output"] == ["JSON", "STRING"]
    assert info["ai_pipeline_advisor"]["output_name"] == ["recommendations_json", "rationale_text"]
    assert info["ai_pipeline_advisor"]["required_conda_packages"] == ["litellm"]
    assert info["ai_pipeline_advisor"]["experimental"] is True
    assert "pipeline" in info["ai_pipeline_advisor"]["search_aliases"]
    assert "parameters" in info["ai_pipeline_advisor"]["search_aliases"]

    assert info["ai_embedding"]["display_name"] == "AI Embedding"
    assert info["ai_embedding"]["category"] == "ai"
    assert info["ai_embedding"]["output"] == ["EMBEDDING", "JSON"]
    assert info["ai_embedding"]["output_name"] == ["embeddings_npy", "metadata_json"]
    assert info["ai_embedding"]["required_conda_packages"] == ["numpy", "biopython", "torch", "transformers"]
    assert info["ai_embedding"]["experimental"] is True
    assert "esm" in info["ai_embedding"]["search_aliases"]
    assert "dnabert" in info["ai_embedding"]["search_aliases"]

    assert info["ai_sequence_classification"]["display_name"] == "AI Sequence Classification"
    assert info["ai_sequence_classification"]["category"] == "ai"
    assert info["ai_sequence_classification"]["output"] == ["JSON", "CSV"]
    assert info["ai_sequence_classification"]["output_name"] == ["classifications_json", "classifications_csv"]
    assert info["ai_sequence_classification"]["required_conda_packages"] == [
        "numpy",
        "biopython",
        "torch",
        "transformers",
    ]
    assert info["ai_sequence_classification"]["experimental"] is True
    assert "deeploc" in info["ai_sequence_classification"]["search_aliases"]
    assert "signalp" in info["ai_sequence_classification"]["search_aliases"]

    assert info["ai_image_analysis"]["display_name"] == "AI Image Analysis"
    assert info["ai_image_analysis"]["category"] == "ai"
    assert info["ai_image_analysis"]["output"] == ["JSON", "STRING"]
    assert info["ai_image_analysis"]["output_name"] == ["analysis_json", "description_text"]
    assert info["ai_image_analysis"]["required_conda_packages"] == ["litellm"]
    assert info["ai_image_analysis"]["experimental"] is True
    assert "vision" in info["ai_image_analysis"]["search_aliases"]
    assert "microscopy" in info["ai_image_analysis"]["search_aliases"]

    assert info["model_inference"]["display_name"] == "Model Inference"
    assert info["model_inference"]["category"] == "ai"
    assert info["model_inference"]["output"] == ["JSON", "CSV"]
    assert info["model_inference"]["output_name"] == ["predictions_json", "scores_csv"]
    assert info["model_inference"]["required_conda_packages"] == ["numpy", "torch", "transformers"]
    assert info["model_inference"]["experimental"] is True
    assert "huggingface" in info["model_inference"]["search_aliases"]
    assert "transformers" in info["model_inference"]["search_aliases"]

    model_inference_inputs = info["model_inference"]["input"]
    assert set(model_inference_inputs["required"]) == {"input_data", "model_name", "task"}
    assert set(model_inference_inputs["optional"]) == {
        "candidate_labels",
        "batch_size",
        "max_length",
        "top_k",
        "confidence_threshold",
        "compute_device",
        "fallback_backend",
    }

    image_inputs = info["ai_image_analysis"]["input"]
    assert set(image_inputs["required"]) == {"input_image", "analysis_task"}
    assert set(image_inputs["optional"]) == {
        "custom_prompt",
        "expected_ladder",
        "scale_bar",
        "provider",
        "model",
        "api_key",
        "api_base",
        "temperature",
        "max_tokens",
        "timeout",
        "json_mode",
    }

    classification_inputs = info["ai_sequence_classification"]["input"]
    assert set(classification_inputs["required"]) == {"input_fasta", "classifier"}
    assert set(classification_inputs["optional"]) == {
        "custom_model",
        "batch_size",
        "max_length",
        "confidence_threshold",
        "compute_device",
        "top_k",
        "fallback_backend",
    }

    embedding_inputs = info["ai_embedding"]["input"]
    assert set(embedding_inputs["required"]) == {"input_data", "embedding_model"}
    assert set(embedding_inputs["optional"]) == {
        "molecule_type",
        "batch_size",
        "max_length",
        "pooling",
        "layer",
        "normalize",
        "compute_device",
        "fallback_backend",
    }

    advisor_inputs = info["ai_pipeline_advisor"]["input"]
    assert set(advisor_inputs["required"]) == {"experiment_type", "metadata"}
    assert set(advisor_inputs["optional"]) == {
        "analysis_goal",
        "available_inputs",
        "constraints",
        "output_format",
        "provider",
        "model",
        "api_key",
        "api_base",
        "temperature",
        "max_tokens",
        "timeout",
    }

    extraction_inputs = info["ai_data_extraction"]["input"]
    assert set(extraction_inputs["required"]) == {"input_text", "extraction_schema"}
    assert set(extraction_inputs["optional"]) == {
        "custom_entities",
        "input_file",
        "output_format",
        "include_context",
        "normalize_ids",
        "provider",
        "model",
        "api_key",
        "api_base",
        "temperature",
        "max_tokens",
        "timeout",
    }

    literature_inputs = info["ai_literature_search"]["input"]
    assert set(literature_inputs["required"]) == {"research_question"}
    assert set(literature_inputs["optional"]) == {
        "databases",
        "max_results",
        "year_range",
        "search_depth",
        "include_abstracts",
        "ncbi_api_key",
        "email",
        "provider",
        "model",
        "api_key",
        "api_base",
        "temperature",
        "max_tokens",
        "timeout",
    }

    report_inputs = info["ai_report_generator"]["input"]
    assert set(report_inputs["required"]) == {"analysis_data", "report_title"}
    assert set(report_inputs["optional"]) == {
        "report_type",
        "additional_files",
        "output_format",
        "include_visualizations",
        "include_methods",
        "author_name",
        "provider",
        "model",
        "api_key",
        "api_base",
        "temperature",
        "max_tokens",
        "timeout",
    }

    sequence_inputs = info["ai_sequence_analysis"]["input"]
    assert set(sequence_inputs["required"]) == {"input_fasta", "analysis_type"}
    assert set(sequence_inputs["optional"]) == {
        "custom_prompt",
        "max_sequences",
        "max_seq_length",
        "molecule_type",
        "provider",
        "model",
        "api_key",
        "api_base",
        "temperature",
        "max_tokens",
        "timeout",
    }

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


@pytest.mark.asyncio
async def test_ai_sequence_analysis_writes_json_and_summary(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("ai_sequence_analysis")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    fasta = tmp_path / "sequences.fasta"
    fasta.write_text(
        ">seq1 kinase candidate\n"
        "MTEYKLVVVGAGGVGKSALTIQLIQNHFVDEYDPTIEDSYRKQV\n"
        ">seq2 promoter\n"
        "ATGCGTACGTAGCTAGCTAGCTAGCTAGCTAGCTA\n",
        encoding="utf-8",
    )

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        calls.append({"config": config, "messages": messages, "json_mode": json_mode})
        return LLMResponse(
            content=json.dumps({
                "summary": "seq1 resembles a small GTPase-like protein; seq2 is nucleotide sequence.",
                "sequences": [
                    {
                        "id": "seq1",
                        "molecule_type": "protein",
                        "findings": ["P-loop NTP-binding motif candidate"],
                    },
                    {
                        "id": "seq2",
                        "molecule_type": "dna",
                        "findings": ["GC-rich short nucleotide sequence"],
                    },
                ],
            }),
            model=config.model,
            usage={"total_tokens": 222},
        )

    monkeypatch.setattr(module, "call_llm", fake_call_llm)

    analysis_json, summary_text = await node_class().run(
        input_fasta=str(fasta),
        analysis_type="motifs",
        max_sequences=2,
        max_seq_length=30,
        molecule_type="auto",
        provider="mock",
        model="sequence-model",
        api_key="unused",
        temperature=0.1,
        max_tokens=2048,
    )

    payload = json.loads(analysis_json)
    prompt = calls[0]["messages"][-1]["content"]

    assert payload["analysis_type"] == "motifs"
    assert payload["sequence_count"] == 2
    assert payload["sequences"][0]["id"] == "seq1"
    assert payload["sequences"][0]["sequence"] == "MTEYKLVVVGAGGVGKSALTIQLIQNHFVD"
    assert payload["analysis"]["sequences"][0]["findings"] == ["P-loop NTP-binding motif candidate"]
    assert payload["usage"] == {"total_tokens": 222}
    assert summary_text == "seq1 resembles a small GTPase-like protein; seq2 is nucleotide sequence."
    assert calls[0]["json_mode"] is True
    assert calls[0]["config"].model == "sequence-model"
    assert "Identify conserved motifs" in prompt
    assert "seq1 kinase candidate" in prompt
    assert "Molecule type hint: auto" in prompt


@pytest.mark.asyncio
async def test_ai_sequence_analysis_uses_custom_prompt_and_handles_empty_fasta(tmp_path: Any) -> None:
    node_class = _node_class("ai_sequence_analysis")
    fasta = tmp_path / "empty.fasta"
    fasta.write_text("", encoding="utf-8")

    analysis_json, summary_text = await node_class().run(
        input_fasta=str(fasta),
        analysis_type="custom",
        custom_prompt="Report unusual codon patterns.",
        provider="mock",
        model="sequence-model",
        api_key="unused",
    )

    payload = json.loads(analysis_json)

    assert payload["analysis_type"] == "custom"
    assert payload["sequence_count"] == 0
    assert payload["analysis"] == {}
    assert summary_text == "No sequences found in FASTA input."


@pytest.mark.asyncio
async def test_ai_report_generator_writes_html_and_returns_markdown(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("ai_report_generator")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    qc_table = tmp_path / "qc.tsv"
    qc_table.write_text("sample\tmapped_pct\nS1\t98.2\n", encoding="utf-8")

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        calls.append({"config": config, "messages": messages, "json_mode": json_mode})
        return LLMResponse(
            content=(
                "# RNA-seq QC Report\n\n"
                "## Executive Summary\n"
                "Mapping quality is high for S1.\n\n"
                "## Methods\n"
                "FastQC and alignment metrics were reviewed."
            ),
            model=config.model,
            usage={"total_tokens": 456},
        )

    monkeypatch.setattr(module, "call_llm", fake_call_llm)
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        analysis_data='{"sample": "S1", "mapped_pct": 98.2}',
        report_title="RNA-seq QC Report",
        report_type="qc",
        additional_files=str(qc_table),
        output_format="both",
        include_visualizations=True,
        include_methods=True,
        author_name="BioNodulo Test",
        provider="mock",
        model="report-model",
        api_key="unused",
        temperature=0.3,
        max_tokens=4096,
        context=context,
    )

    report_path = tmp_path / "ai_report_generator" / "report.html"
    markdown = result["outputs"]["report_markdown"]
    html = report_path.read_text(encoding="utf-8")
    prompt = calls[0]["messages"][-1]["content"]

    assert result["outputs"]["report_html"] == str(report_path)
    assert markdown.startswith("# RNA-seq QC Report")
    assert "<!DOCTYPE html>" in html
    assert "<title>RNA-seq QC Report</title>" in html
    assert "<h1>RNA-seq QC Report</h1>" in html
    assert "<h2>Executive Summary</h2>" in html
    assert "Mapping quality is high for S1." in html
    assert "Generated by BioNodulo AI Report Generator" in html
    assert previews == [(str(report_path), "AI Report Generator")]
    assert calls[0]["json_mode"] is False
    assert calls[0]["config"].model == "report-model"
    assert "quality control report" in prompt
    assert "RNA-seq QC Report" in prompt
    assert "BioNodulo Test" in prompt
    assert "qc.tsv" in prompt
    assert "mapped_pct" in prompt
    assert "visualizations" in prompt
    assert "Methods section" in prompt


@pytest.mark.asyncio
async def test_ai_report_generator_supports_markdown_only_output(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("ai_report_generator")
    module = importlib.import_module(node_class.__module__)

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        return LLMResponse(content="# Methods\n\nWorkflow parameters summarized.", model=config.model)

    monkeypatch.setattr(module, "call_llm", fake_call_llm)

    result = await node_class().run(
        analysis_data="tool=STAR\nthreads=12",
        report_title="Methods Draft",
        report_type="methods",
        output_format="markdown",
        provider="mock",
        model="report-model",
        api_key="unused",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    assert result == {"outputs": {"report_html": "", "report_markdown": "# Methods\n\nWorkflow parameters summarized."}}


@pytest.mark.asyncio
async def test_ai_literature_search_queries_pubmed_and_synthesizes_summary(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("ai_literature_search")
    module = importlib.import_module(node_class.__module__)
    json_calls: list[dict[str, Any]] = []
    text_calls: list[dict[str, Any]] = []
    llm_calls: list[dict[str, Any]] = []

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        llm_calls.append({"config": config, "messages": messages, "json_mode": json_mode})
        if json_mode:
            assert "Generate up to 3 PubMed search queries" in messages[-1]["content"]
            return LLMResponse(
                content=json.dumps({"queries": ["TP53 cancer[Title/Abstract]", "TP53 tumor suppressor[Title/Abstract]"]}),
                model=config.model,
                usage={"total_tokens": 44},
            )
        assert "TP53 cancer review" in messages[-1]["content"]
        assert "apoptosis and DNA damage response" in messages[-1]["content"]
        return LLMResponse(
            content="TP53 literature highlights DNA damage response and apoptosis findings [PMID:12345, PMID:67890].",
            model=config.model,
            usage={"total_tokens": 177},
        )

    async def fake_json(endpoint: str, params: dict[str, Any], **_: Any) -> dict[str, Any]:
        json_calls.append({"endpoint": endpoint, "params": dict(params)})
        if endpoint == "esearch.fcgi":
            return {
                "esearchresult": {
                    "count": "2",
                    "idlist": ["12345", "67890"],
                    "querytranslation": "TP53[All Fields]",
                }
            }
        if endpoint == "esummary.fcgi":
            return {
                "result": {
                    "uids": ["12345", "67890"],
                    "12345": {
                        "uid": "12345",
                        "title": "TP53 cancer review",
                        "pubdate": "2025 Jan",
                        "fulljournalname": "Example Journal",
                        "authors": [{"name": "Smith J"}, {"name": "Lee A"}],
                        "elocationid": "doi:10.1000/example",
                    },
                    "67890": {
                        "uid": "67890",
                        "title": "TP53 functional study",
                        "pubdate": "2024 Dec",
                        "fulljournalname": "Another Journal",
                        "authors": [{"name": "Patel R"}],
                    },
                }
            }
        raise AssertionError(f"unexpected endpoint: {endpoint}")

    async def fake_text(endpoint: str, params: dict[str, Any], **_: Any) -> str:
        text_calls.append({"endpoint": endpoint, "params": dict(params)})
        assert endpoint == "efetch.fcgi"
        return """<?xml version="1.0" encoding="UTF-8" ?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345</PMID>
      <Article><Abstract><AbstractText>TP53 regulates apoptosis and DNA damage response.</AbstractText></Abstract></Article>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>67890</PMID>
      <Article><Abstract><AbstractText>TP53 loss alters cell cycle checkpoints.</AbstractText></Abstract></Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""

    monkeypatch.setattr(module, "call_llm", fake_call_llm)
    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_request_text", fake_text)
    context = SimpleNamespace(
        node_dir=tmp_path,
        resolve_secret=lambda key: "secret-key" if key == "ncbi_api_key" else None,
    )

    result = await node_class().run(
        research_question="What is TP53's role in cancer?",
        databases="pubmed",
        max_results=2,
        year_range="2020:2026",
        search_depth="standard",
        include_abstracts=True,
        ncbi_api_key="",
        email="lab@example.org",
        provider="mock",
        model="literature-model",
        api_key="unused",
        temperature=0.1,
        max_tokens=2048,
        context=context,
    )

    payload = result["outputs"]["papers_json"]
    summary = result["outputs"]["summary_text"]
    json_path = tmp_path / "ai_literature_search" / "papers.json"
    summary_path = tmp_path / "ai_literature_search" / "summary.txt"
    saved_payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert payload["papers_found"] == 2
    assert payload["queries_used"] == ["TP53 cancer[Title/Abstract]", "TP53 tumor suppressor[Title/Abstract]"]
    assert payload["papers"][0]["pmid"] == "12345"
    assert payload["papers"][0]["title"] == "TP53 cancer review"
    assert payload["papers"][0]["journal"] == "Example Journal"
    assert payload["papers"][0]["year"] == "2025"
    assert payload["papers"][0]["authors"] == ["Smith J", "Lee A"]
    assert payload["papers"][0]["doi"] == "10.1000/example"
    assert payload["papers"][0]["abstract"] == "TP53 regulates apoptosis and DNA damage response."
    assert payload["papers_json_path"] == str(json_path)
    assert payload["summary_path"] == str(summary_path)
    assert payload["usage"] == {"query_generation": {"total_tokens": 44}, "synthesis": {"total_tokens": 177}}
    assert saved_payload == payload
    assert summary == "TP53 literature highlights DNA damage response and apoptosis findings [PMID:12345, PMID:67890]."
    assert summary_path.read_text(encoding="utf-8") == summary

    assert [call["endpoint"] for call in json_calls] == ["esearch.fcgi", "esummary.fcgi"]
    assert text_calls[0]["endpoint"] == "efetch.fcgi"
    assert json_calls[0]["params"] == {
        "db": "pubmed",
        "term": "TP53 cancer[Title/Abstract]",
        "retmode": "json",
        "retmax": 2,
        "sort": "relevance",
        "tool": "bionodulo",
        "email": "lab@example.org",
        "mindate": "2020",
        "maxdate": "2026",
        "datetype": "pdat",
        "api_key": "secret-key",
    }
    assert json_calls[1]["params"]["id"] == "12345,67890"
    assert text_calls[0]["params"]["id"] == "12345,67890"
    assert [call["json_mode"] for call in llm_calls] == [True, False]
    assert llm_calls[0]["config"].model == "literature-model"


@pytest.mark.asyncio
async def test_ai_literature_search_handles_empty_results_without_synthesis(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("ai_literature_search")
    module = importlib.import_module(node_class.__module__)
    json_calls: list[dict[str, Any]] = []
    llm_calls: list[dict[str, Any]] = []

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        llm_calls.append({"messages": messages, "json_mode": json_mode})
        if json_mode:
            return LLMResponse(content=json.dumps({"queries": ["no hits[Title/Abstract]"]}), model=config.model)
        raise AssertionError("synthesis should not run when PubMed returns no papers")

    async def fake_json(endpoint: str, params: dict[str, Any], **_: Any) -> dict[str, Any]:
        json_calls.append({"endpoint": endpoint, "params": dict(params)})
        assert endpoint == "esearch.fcgi"
        return {"esearchresult": {"count": "0", "idlist": []}}

    async def fake_text(endpoint: str, params: dict[str, Any], **_: Any) -> str:
        raise AssertionError(f"unexpected text request: {endpoint} {params}")

    monkeypatch.setattr(module, "call_llm", fake_call_llm)
    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_request_text", fake_text)

    result = await node_class().run(
        research_question="No hit topic",
        max_results=3,
        search_depth="quick",
        include_abstracts=True,
        provider="mock",
        model="literature-model",
        api_key="unused",
        context=SimpleNamespace(node_dir=tmp_path, resolve_secret=lambda _key: None),
    )

    payload = result["outputs"]["papers_json"]
    summary = result["outputs"]["summary_text"]
    saved_payload = json.loads((tmp_path / "ai_literature_search" / "papers.json").read_text(encoding="utf-8"))

    assert payload["papers_found"] == 0
    assert payload["papers"] == []
    assert payload["queries_used"] == ["no hits[Title/Abstract]"]
    assert summary == "No papers found for the given research question."
    assert saved_payload == payload
    assert [call["endpoint"] for call in json_calls] == ["esearch.fcgi"]
    assert [call["json_mode"] for call in llm_calls] == [True]


@pytest.mark.asyncio
async def test_ai_data_extraction_writes_json_and_flattened_csv(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("ai_data_extraction")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        calls.append({"config": config, "messages": messages, "json_mode": json_mode})
        return LLMResponse(
            content=json.dumps({
                "genes": [
                    {
                        "gene_symbol": "BRCA1",
                        "full_name": "BRCA1 DNA repair associated",
                        "normalized_id": "HGNC:1100",
                        "context": "BRCA1 c.68_69delAG is associated with hereditary breast cancer.",
                    }
                ],
                "variants": [
                    {
                        "hgvs": "NM_007294.4:c.68_69delAG",
                        "gene": "BRCA1",
                        "significance": "pathogenic",
                        "context": "BRCA1 c.68_69delAG is pathogenic.",
                    }
                ],
                "diseases": [
                    {
                        "disease_name": "hereditary breast cancer",
                        "mondo_id": "MONDO:0016419",
                        "context": "hereditary breast cancer",
                    }
                ],
            }),
            model=config.model,
            usage={"total_tokens": 333},
        )

    monkeypatch.setattr(module, "call_llm", fake_call_llm)

    result = await node_class().run(
        input_text="BRCA1 c.68_69delAG is associated with hereditary breast cancer.",
        extraction_schema="genes_variants_diseases",
        output_format="both",
        include_context=True,
        normalize_ids=True,
        provider="mock",
        model="extract-model",
        api_key="unused",
        temperature=0.1,
        max_tokens=2048,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    json_path = tmp_path / "ai_data_extraction" / "extracted.json"
    csv_path = tmp_path / "ai_data_extraction" / "extracted.csv"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    csv_text = csv_path.read_text(encoding="utf-8")
    prompt = calls[0]["messages"][-1]["content"]

    assert result == {"outputs": {"extracted_json": str(json_path), "extracted_csv": str(csv_path)}}
    assert payload["extraction_schema"] == "genes_variants_diseases"
    assert payload["source_text_length"] == 65
    assert payload["entities"]["genes"][0]["gene_symbol"] == "BRCA1"
    assert payload["usage"] == {"total_tokens": 333}
    assert payload["model"] == "extract-model"
    assert "entity_type,field,value,context" in csv_text
    assert "genes,gene_symbol,BRCA1,BRCA1 c.68_69delAG is associated with hereditary breast cancer." in csv_text
    assert "variants,hgvs,NM_007294.4:c.68_69delAG,BRCA1 c.68_69delAG is pathogenic." in csv_text
    assert calls[0]["json_mode"] is True
    assert calls[0]["config"].model == "extract-model"
    assert "genes: list of objects" in prompt
    assert "variants: list of objects" in prompt
    assert "Include the surrounding text context" in prompt
    assert "Add normalized database IDs" in prompt


@pytest.mark.asyncio
async def test_ai_data_extraction_reads_input_file_and_supports_csv_only(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("ai_data_extraction")
    module = importlib.import_module(node_class.__module__)
    input_file = tmp_path / "paper.txt"
    input_file.write_text("Drug X inhibits EGFR in lung cancer.", encoding="utf-8")
    calls: list[dict[str, Any]] = []

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        calls.append({"messages": messages, "json_mode": json_mode})
        return LLMResponse(
            content=json.dumps({
                "drugs": [{"drug_name": "Drug X", "drug_class": "small molecule"}],
                "targets": [{"target_gene": "EGFR", "target_protein": "EGFR"}],
                "relationships": [{"drug": "Drug X", "target": "EGFR", "relationship_type": "inhibits"}],
            }),
            model=config.model,
        )

    monkeypatch.setattr(module, "call_llm", fake_call_llm)

    result = await node_class().run(
        input_text="This text should be ignored.",
        input_file=str(input_file),
        extraction_schema="drugs_targets",
        output_format="csv",
        include_context=False,
        normalize_ids=False,
        provider="mock",
        model="extract-model",
        api_key="unused",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    csv_path = tmp_path / "ai_data_extraction" / "extracted.csv"
    json_path = tmp_path / "ai_data_extraction" / "extracted.json"
    prompt = calls[0]["messages"][-1]["content"]

    assert result == {"outputs": {"extracted_json": "", "extracted_csv": str(csv_path)}}
    assert json_path.exists()
    assert "Drug X inhibits EGFR" in prompt
    assert "This text should be ignored" not in prompt
    assert "Include the surrounding text context" not in prompt
    assert "Add normalized database IDs" not in prompt
    assert "relationships,relationship_type,inhibits," in csv_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_ai_data_extraction_wraps_invalid_json_as_raw_extraction(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("ai_data_extraction")
    module = importlib.import_module(node_class.__module__)

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        return LLMResponse(content="BRCA1; TP53", model=config.model)

    monkeypatch.setattr(module, "call_llm", fake_call_llm)

    result = await node_class().run(
        input_text="BRCA1 and TP53 were mentioned.",
        extraction_schema="custom",
        custom_entities="genes:Gene symbols mentioned in text\npathways:Pathway names",
        output_format="json",
        include_context=True,
        normalize_ids=False,
        provider="mock",
        model="extract-model",
        api_key="unused",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    json_path = tmp_path / "ai_data_extraction" / "extracted.json"
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert result == {"outputs": {"extracted_json": str(json_path), "extracted_csv": ""}}
    assert payload["extraction_schema"] == "custom"
    assert payload["entities"] == {"raw_extraction": "BRCA1; TP53"}
    assert payload["custom_entities"] == ["genes", "pathways"]


@pytest.mark.asyncio
async def test_ai_data_extraction_resolves_api_key_from_context_secret(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("ai_data_extraction")
    module = importlib.import_module(node_class.__module__)
    calls: list[LLMConfig] = []

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        calls.append(config)
        return LLMResponse(content='{"genes": []}', model=config.model)

    monkeypatch.setattr(module, "call_llm", fake_call_llm)

    await node_class().run(
        input_text="BRCA1 was mentioned.",
        extraction_schema="genes_variants_diseases",
        output_format="json",
        provider="mock",
        model="extract-model",
        api_key="",
        context=SimpleNamespace(node_dir=tmp_path, resolve_secret=lambda key: "secret-key" if key == "llm_api_key" else None),
    )

    assert calls[0].api_key == "secret-key"


@pytest.mark.asyncio
async def test_ai_pipeline_advisor_writes_recommendations_and_rationale(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("ai_pipeline_advisor")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        calls.append({"config": config, "messages": messages, "json_mode": json_mode})
        return LLMResponse(
            content=json.dumps({
                "recommended_pipeline": "RNA-seq differential expression",
                "recommended_nodes": [
                    {"node_id": "fastqc", "reason": "Assess read quality"},
                    {"node_id": "salmon_quant", "parameters": {"lib_type": "A"}, "reason": "Transcript quantification"},
                    {"node_id": "deseq2_analysis", "parameters": {"design": "~ condition"}, "reason": "Differential expression"},
                ],
                "parameter_recommendations": {
                    "salmon_quant": {"lib_type": "A"},
                    "deseq2_analysis": {"design": "~ condition"},
                },
                "quality_controls": ["Run FastQC and MultiQC before quantification"],
                "warnings": ["Confirm strandedness before running quantification"],
                "rationale": "Bulk RNA-seq with replicates should use QC, transcript quantification, and differential expression.",
            }),
            model=config.model,
            usage={"total_tokens": 444},
        )

    monkeypatch.setattr(module, "call_llm", fake_call_llm)

    result = await node_class().run(
        experiment_type="bulk_rnaseq",
        metadata='{"organism": "human", "samples": 6, "groups": ["control", "treated"], "paired_end": true}',
        analysis_goal="Find differentially expressed genes",
        available_inputs="FASTQ files, sample sheet",
        constraints="Prefer lightweight tools",
        output_format="both",
        provider="mock",
        model="advisor-model",
        api_key="unused",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    json_path = tmp_path / "ai_pipeline_advisor" / "recommendations.json"
    rationale_path = tmp_path / "ai_pipeline_advisor" / "rationale.txt"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    prompt = calls[0]["messages"][-1]["content"]

    assert result == {"outputs": {"recommendations_json": str(json_path), "rationale_text": str(rationale_path)}}
    assert payload["experiment_type"] == "bulk_rnaseq"
    assert payload["analysis_goal"] == "Find differentially expressed genes"
    assert payload["metadata"]["organism"] == "human"
    assert payload["recommendations"]["recommended_pipeline"] == "RNA-seq differential expression"
    assert payload["recommendations"]["recommended_nodes"][1]["node_id"] == "salmon_quant"
    assert payload["usage"] == {"total_tokens": 444}
    assert payload["model"] == "advisor-model"
    assert rationale_path.read_text(encoding="utf-8").startswith("Bulk RNA-seq with replicates")
    assert calls[0]["json_mode"] is True
    assert calls[0]["config"].model == "advisor-model"
    assert "Experiment type: bulk_rnaseq" in prompt
    assert '"samples": 6' in prompt
    assert "Available inputs: FASTQ files, sample sheet" in prompt
    assert "Prefer lightweight tools" in prompt


@pytest.mark.asyncio
async def test_ai_pipeline_advisor_supports_json_only_and_invalid_response(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("ai_pipeline_advisor")
    module = importlib.import_module(node_class.__module__)

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        return LLMResponse(content="Use QC then alignment.", model=config.model)

    monkeypatch.setattr(module, "call_llm", fake_call_llm)

    result = await node_class().run(
        experiment_type="chip_seq",
        metadata={"target": "H3K27ac", "samples": 4},
        output_format="json",
        provider="mock",
        model="advisor-model",
        api_key="unused",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    json_path = tmp_path / "ai_pipeline_advisor" / "recommendations.json"
    rationale_path = tmp_path / "ai_pipeline_advisor" / "rationale.txt"
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert result == {"outputs": {"recommendations_json": str(json_path), "rationale_text": ""}}
    assert rationale_path.exists()
    assert payload["metadata"] == {"target": "H3K27ac", "samples": 4}
    assert payload["recommendations"] == {"raw_recommendations": "Use QC then alignment."}
    assert rationale_path.read_text(encoding="utf-8") == "Use QC then alignment."


@pytest.mark.asyncio
async def test_ai_pipeline_advisor_resolves_api_key_from_context_secret(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("ai_pipeline_advisor")
    module = importlib.import_module(node_class.__module__)
    calls: list[LLMConfig] = []

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, str]], *, json_mode: bool = False) -> LLMResponse:
        calls.append(config)
        return LLMResponse(content='{"rationale": "Use a standard QC-first workflow."}', model=config.model)

    monkeypatch.setattr(module, "call_llm", fake_call_llm)

    await node_class().run(
        experiment_type="variant_calling",
        metadata="{}",
        output_format="json",
        provider="mock",
        model="advisor-model",
        api_key="",
        context=SimpleNamespace(node_dir=tmp_path, resolve_secret=lambda key: "secret-key" if key == "llm_api_key" else None),
    )

    assert calls[0].api_key == "secret-key"


@pytest.mark.asyncio
async def test_ai_embedding_generates_normalized_fallback_embeddings_from_fasta(
    tmp_path: Any,
) -> None:
    node_class = _node_class("ai_embedding")
    fasta_path = tmp_path / "proteins.fasta"
    fasta_path.write_text(">protA\nMTEYKLVVVG\n>protB\nGAGGVGKSAL\n", encoding="utf-8")

    result = await node_class().run(
        input_data=str(fasta_path),
        embedding_model="esm2_t6_8M",
        molecule_type="protein",
        max_length=8,
        pooling="mean",
        layer=-1,
        normalize=True,
        compute_device="cpu",
        fallback_backend="deterministic",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    npy_path = tmp_path / "ai_embedding" / "embeddings.npy"
    metadata_path = tmp_path / "ai_embedding" / "metadata.json"
    embeddings = np.load(npy_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert result == {"outputs": {"embeddings_npy": str(npy_path), "metadata_json": str(metadata_path)}}
    assert embeddings.shape == (2, 32)
    assert np.allclose(np.linalg.norm(embeddings, axis=1), 1.0)
    assert metadata["backend"] == "deterministic"
    assert metadata["embedding_model"] == "esm2_t6_8M"
    assert metadata["model_name"] == "facebook/esm2_t6_8M_UR50D"
    assert metadata["molecule_type"] == "protein"
    assert metadata["sequence_count"] == 2
    assert metadata["sequence_ids"] == ["protA", "protB"]
    assert metadata["embedding_shape"] == [2, 32]
    assert metadata["truncated_lengths"] == [8, 8]
    assert metadata["normalize"] is True


@pytest.mark.asyncio
async def test_ai_embedding_reads_raw_text_without_normalization(
    tmp_path: Any,
) -> None:
    node_class = _node_class("ai_embedding")

    await node_class().run(
        input_data="BRCA1 regulates DNA repair.\nTP53 responds to DNA damage.",
        embedding_model="text_embedding",
        molecule_type="text",
        max_length=128,
        normalize=False,
        fallback_backend="deterministic",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    embeddings = np.load(tmp_path / "ai_embedding" / "embeddings.npy")
    metadata = json.loads((tmp_path / "ai_embedding" / "metadata.json").read_text(encoding="utf-8"))

    assert embeddings.shape == (2, 32)
    assert not np.allclose(np.linalg.norm(embeddings, axis=1), 1.0)
    assert metadata["sequence_ids"] == ["item_0", "item_1"]
    assert metadata["molecule_type"] == "text"
    assert metadata["backend"] == "deterministic"


@pytest.mark.asyncio
async def test_ai_embedding_empty_input_writes_empty_outputs(
    tmp_path: Any,
) -> None:
    node_class = _node_class("ai_embedding")

    result = await node_class().run(
        input_data="",
        embedding_model="text_embedding",
        molecule_type="text",
        fallback_backend="deterministic",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    npy_path = tmp_path / "ai_embedding" / "embeddings.npy"
    metadata_path = tmp_path / "ai_embedding" / "metadata.json"
    embeddings = np.load(npy_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert result == {"outputs": {"embeddings_npy": str(npy_path), "metadata_json": str(metadata_path)}}
    assert embeddings.shape == (0, 0)
    assert metadata["sequence_count"] == 0
    assert metadata["embedding_shape"] == [0, 0]


@pytest.mark.asyncio
async def test_ai_embedding_parses_long_inline_fasta_without_path_probe_failure(
    tmp_path: Any,
) -> None:
    node_class = _node_class("ai_embedding")
    long_sequence = "M" * 5000

    await node_class().run(
        input_data=f">inline_protein\n{long_sequence}\n",
        embedding_model="esm2_t6_8M",
        molecule_type="protein",
        max_length=64,
        normalize=False,
        fallback_backend="deterministic",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    embeddings = np.load(tmp_path / "ai_embedding" / "embeddings.npy")
    metadata = json.loads((tmp_path / "ai_embedding" / "metadata.json").read_text(encoding="utf-8"))

    assert embeddings.shape == (1, 32)
    assert metadata["sequence_ids"] == ["inline_protein"]
    assert metadata["original_lengths"] == [5000]
    assert metadata["truncated_lengths"] == [64]


@pytest.mark.asyncio
async def test_ai_embedding_preserves_explicit_zero_layer(
    tmp_path: Any,
) -> None:
    node_class = _node_class("ai_embedding")

    await node_class().run(
        input_data="MTEYKLVVVG",
        embedding_model="esm2_t6_8M",
        molecule_type="protein",
        layer=0,
        fallback_backend="deterministic",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    metadata = json.loads((tmp_path / "ai_embedding" / "metadata.json").read_text(encoding="utf-8"))

    assert metadata["layer"] == 0


@pytest.mark.asyncio
async def test_ai_sequence_classification_writes_deterministic_outputs_from_fasta(
    tmp_path: Any,
) -> None:
    node_class = _node_class("ai_sequence_classification")
    fasta_path = tmp_path / "proteins.fasta"
    fasta_path.write_text(">secreted\nMKKLLFAIPLVVPFYSHS\n>membrane\nMALWMRLLPLLALLALWG\n", encoding="utf-8")

    result = await node_class().run(
        input_fasta=str(fasta_path),
        classifier="deeploc",
        max_length=10,
        top_k=3,
        confidence_threshold=0.0,
        fallback_backend="deterministic",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    json_path = tmp_path / "ai_sequence_classification" / "classifications.json"
    csv_path = tmp_path / "ai_sequence_classification" / "classifications.csv"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    rows = csv_path.read_text(encoding="utf-8").splitlines()

    assert result == {"outputs": {"classifications_json": str(json_path), "classifications_csv": str(csv_path)}}
    assert payload["classifier"] == "deeploc"
    assert payload["backend"] == "deterministic"
    assert payload["model"] == "ElnaggarLab/ankh-base"
    assert payload["total_sequences"] == 2
    assert payload["returned_predictions"] == 2
    assert payload["labels"][:3] == ["Cytoplasm", "Nucleus", "Extracellular"]
    assert [prediction["sequence_id"] for prediction in payload["predictions"]] == ["secreted", "membrane"]
    assert payload["predictions"][0]["sequence_length"] == 18
    assert payload["predictions"][0]["truncated_length"] == 10
    assert len(payload["predictions"][0]["top_predictions"]) == 3
    assert rows[0] == "sequence_id,sequence_length,truncated_length,top_prediction,confidence,all_predictions"
    assert rows[1].startswith("secreted,18,10,")


@pytest.mark.asyncio
async def test_ai_sequence_classification_filters_by_confidence(
    tmp_path: Any,
) -> None:
    node_class = _node_class("ai_sequence_classification")
    fasta_path = tmp_path / "proteins.fasta"
    fasta_path.write_text(">low\nACDEFGHIKLMNPQRSTVWY\n", encoding="utf-8")

    await node_class().run(
        input_fasta=str(fasta_path),
        classifier="signalp",
        confidence_threshold=1.1,
        fallback_backend="deterministic",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    payload = json.loads((tmp_path / "ai_sequence_classification" / "classifications.json").read_text(encoding="utf-8"))
    csv_rows = (tmp_path / "ai_sequence_classification" / "classifications.csv").read_text(encoding="utf-8").splitlines()

    assert payload["total_sequences"] == 1
    assert payload["returned_predictions"] == 0
    assert payload["filtered_out"] == 1
    assert payload["predictions"] == []
    assert csv_rows == ["sequence_id,sequence_length,truncated_length,top_prediction,confidence,all_predictions"]


@pytest.mark.asyncio
async def test_ai_sequence_classification_empty_input_writes_empty_outputs(
    tmp_path: Any,
) -> None:
    node_class = _node_class("ai_sequence_classification")
    fasta_path = tmp_path / "empty.fasta"
    fasta_path.write_text("", encoding="utf-8")

    result = await node_class().run(
        input_fasta=str(fasta_path),
        classifier="tmhmm",
        fallback_backend="deterministic",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    json_path = tmp_path / "ai_sequence_classification" / "classifications.json"
    csv_path = tmp_path / "ai_sequence_classification" / "classifications.csv"
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert result == {"outputs": {"classifications_json": str(json_path), "classifications_csv": str(csv_path)}}
    assert payload["total_sequences"] == 0
    assert payload["returned_predictions"] == 0
    assert payload["predictions"] == []


@pytest.mark.asyncio
async def test_ai_sequence_classification_auto_falls_back_without_local_model(
    tmp_path: Any,
) -> None:
    node_class = _node_class("ai_sequence_classification")
    fasta_path = tmp_path / "proteins.fasta"
    fasta_path.write_text(">protein\nMKKLLFAIPLVVPFYSHS\n", encoding="utf-8")

    await node_class().run(
        input_fasta=str(fasta_path),
        classifier="signalp",
        confidence_threshold=0.0,
        fallback_backend="auto",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    payload = json.loads((tmp_path / "ai_sequence_classification" / "classifications.json").read_text(encoding="utf-8"))

    assert payload["backend"] == "deterministic"
    assert payload["returned_predictions"] == 1


@pytest.mark.asyncio
async def test_ai_sequence_classification_local_backend_requires_local_transformer(
    tmp_path: Any,
) -> None:
    node_class = _node_class("ai_sequence_classification")
    fasta_path = tmp_path / "proteins.fasta"
    fasta_path.write_text(">protein\nMKKLLFAIPLVVPFYSHS\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="torch and transformers|required|local"):
        await node_class().run(
            input_fasta=str(fasta_path),
            classifier="signalp",
            fallback_backend="local",
            context=SimpleNamespace(node_dir=tmp_path),
        )


@pytest.mark.asyncio
async def test_ai_sequence_classification_custom_requires_model(
    tmp_path: Any,
) -> None:
    node_class = _node_class("ai_sequence_classification")
    fasta_path = tmp_path / "proteins.fasta"
    fasta_path.write_text(">protein\nMKKLLFAIPLVVPFYSHS\n", encoding="utf-8")

    with pytest.raises(ValueError, match="custom_model"):
        await node_class().run(
            input_fasta=str(fasta_path),
            classifier="custom",
            custom_model="",
            fallback_backend="deterministic",
            context=SimpleNamespace(node_dir=tmp_path),
        )


@pytest.mark.asyncio
async def test_ai_sequence_classification_custom_model_and_top_k_are_clamped(
    tmp_path: Any,
) -> None:
    node_class = _node_class("ai_sequence_classification")
    fasta_path = tmp_path / "proteins.fasta"
    fasta_path.write_text(">protein\nMKKLLFAIPLVVPFYSHS\n", encoding="utf-8")

    await node_class().run(
        input_fasta=str(fasta_path),
        classifier="custom",
        custom_model="local/custom-protein-classifier",
        top_k=10,
        confidence_threshold=0.0,
        fallback_backend="deterministic",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    payload = json.loads((tmp_path / "ai_sequence_classification" / "classifications.json").read_text(encoding="utf-8"))

    assert payload["model"] == "local/custom-protein-classifier"
    assert payload["labels"] == ["class_0", "class_1"]
    assert payload["top_k"] == 2
    assert len(payload["predictions"][0]["top_predictions"]) == 2


@pytest.mark.asyncio
async def test_ai_image_analysis_builds_multimodal_message_and_writes_outputs(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("bionodulo.nodes.builtin.llm")
    calls: list[dict[str, Any]] = []

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, Any]], *, json_mode: bool = False) -> LLMResponse:
        calls.append({"config": config, "messages": messages, "json_mode": json_mode})
        return LLMResponse(
            content=json.dumps({"description": "Gel image with two lanes.", "lanes": [{"lane": 1}, {"lane": 2}]}),
            model=config.model,
            usage={"total_tokens": 8},
        )

    monkeypatch.setattr(module, "call_llm", fake_call_llm)
    node_class = _node_class("ai_image_analysis")
    image_path = tmp_path / "gel.png"
    _write_tiny_png(image_path)

    result = await node_class().run(
        input_image=str(image_path),
        analysis_task="gel_electrophoresis",
        expected_ladder="1000,500,100",
        provider="openai",
        api_key="test-key",
        json_mode=True,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    json_path = tmp_path / "ai_image_analysis" / "analysis.json"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    user_content = calls[0]["messages"][1]["content"]

    assert result == {"outputs": {"analysis_json": str(json_path), "description_text": "Gel image with two lanes."}}
    assert payload["analysis_task"] == "gel_electrophoresis"
    assert payload["mime_type"] == "image/png"
    assert payload["image_size_bytes"] == image_path.stat().st_size
    assert payload["model"] == "openai/gpt-4o"
    assert payload["usage"] == {"total_tokens": 8}
    assert payload["analysis"]["lanes"] == [{"lane": 1}, {"lane": 2}]
    assert calls[0]["json_mode"] is True
    assert "gel electrophoresis" in user_content[0]["text"].lower()
    assert "1000,500,100" in user_content[0]["text"]
    assert user_content[1]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_ai_image_analysis_custom_prompt_plain_text_response(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("bionodulo.nodes.builtin.llm")
    calls: list[dict[str, Any]] = []

    async def fake_call_llm(config: LLMConfig, messages: list[dict[str, Any]], *, json_mode: bool = False) -> LLMResponse:
        calls.append({"config": config, "messages": messages, "json_mode": json_mode})
        return LLMResponse(content="Approximately 42 colonies are visible.", model=config.model)

    monkeypatch.setattr(module, "call_llm", fake_call_llm)
    node_class = _node_class("ai_image_analysis")
    image_path = tmp_path / "colonies.jpg"
    _write_tiny_png(image_path)

    result = await node_class().run(
        input_image=str(image_path),
        analysis_task="custom",
        custom_prompt="Count colonies and report uncertainty.",
        model="gpt-4o",
        api_key="test-key",
        json_mode=False,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    json_path = tmp_path / "ai_image_analysis" / "analysis.json"
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert result["outputs"]["analysis_json"] == str(json_path)
    assert result["outputs"]["description_text"] == "Approximately 42 colonies are visible."
    assert payload["analysis"]["description"] == "Approximately 42 colonies are visible."
    assert calls[0]["json_mode"] is False
    assert calls[0]["messages"][1]["content"][0]["text"] == "Count colonies and report uncertainty."
    assert calls[0]["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_ai_image_analysis_missing_image_writes_error_outputs(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("bionodulo.nodes.builtin.llm")

    async def fake_call_llm(*args: Any, **kwargs: Any) -> LLMResponse:
        raise AssertionError("call_llm should not run for a missing image")

    monkeypatch.setattr(module, "call_llm", fake_call_llm)
    node_class = _node_class("ai_image_analysis")
    missing_path = tmp_path / "missing.png"

    result = await node_class().run(
        input_image=str(missing_path),
        analysis_task="microscopy",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    json_path = tmp_path / "ai_image_analysis" / "analysis.json"
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert result == {"outputs": {"analysis_json": str(json_path), "description_text": f"Image not found: {missing_path}"}}
    assert payload["error"] == f"Image not found: {missing_path}"
    assert payload["analysis_task"] == "microscopy"


def _write_tiny_png(path: Any) -> None:
    path.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
            "de0000000c49444154789c63606060000000040001f61738550000000049454e44ae426082"
        )
    )


@pytest.mark.asyncio
async def test_model_inference_writes_deterministic_text_classification_outputs(
    tmp_path: Any,
) -> None:
    node_class = _node_class("model_inference")
    input_path = tmp_path / "abstracts.txt"
    input_path.write_text("BRCA1 regulates DNA repair.\nTP53 responds to DNA damage.\n", encoding="utf-8")

    result = await node_class().run(
        input_data=str(input_path),
        model_name="facebook/bart-large-mnli",
        task="text_classification",
        candidate_labels="repair, apoptosis, metabolism",
        top_k=2,
        confidence_threshold=0.0,
        fallback_backend="deterministic",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    json_path = tmp_path / "model_inference" / "predictions.json"
    csv_path = tmp_path / "model_inference" / "scores.csv"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    rows = csv_path.read_text(encoding="utf-8").splitlines()

    assert result == {"outputs": {"predictions_json": str(json_path), "scores_csv": str(csv_path)}}
    assert payload["backend"] == "deterministic"
    assert payload["task"] == "text_classification"
    assert payload["model_name"] == "facebook/bart-large-mnli"
    assert payload["input_count"] == 2
    assert payload["returned_predictions"] == 2
    assert payload["labels"] == ["repair", "apoptosis", "metabolism"]
    assert payload["predictions"][0]["input_id"] == "item_0"
    assert len(payload["predictions"][0]["top_predictions"]) == 2
    assert rows[0] == "input_id,input_length,truncated_length,top_prediction,confidence,all_predictions"
    assert rows[1].startswith("item_0,27,27,")


@pytest.mark.asyncio
async def test_model_inference_reads_inline_fasta_for_sequence_classification(
    tmp_path: Any,
) -> None:
    node_class = _node_class("model_inference")

    await node_class().run(
        input_data=">seqA\nMTEYKLVVVG\n>seqB\nGAGGVGKSAL\n",
        model_name="facebook/esm2_t6_8M_UR50D",
        task="sequence_classification",
        candidate_labels="enzyme, receptor",
        max_length=6,
        confidence_threshold=0.0,
        fallback_backend="deterministic",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    payload = json.loads((tmp_path / "model_inference" / "predictions.json").read_text(encoding="utf-8"))

    assert payload["input_count"] == 2
    assert [prediction["input_id"] for prediction in payload["predictions"]] == ["seqA", "seqB"]
    assert payload["predictions"][0]["input_length"] == 10
    assert payload["predictions"][0]["truncated_length"] == 6


@pytest.mark.asyncio
async def test_model_inference_auto_falls_back_and_local_requires_transformers(
    tmp_path: Any,
) -> None:
    node_class = _node_class("model_inference")
    input_path = tmp_path / "items.txt"
    input_path.write_text("one item\n", encoding="utf-8")

    await node_class().run(
        input_data=str(input_path),
        model_name="local/missing-model",
        task="text_classification",
        candidate_labels="a,b",
        confidence_threshold=0.0,
        fallback_backend="auto",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    payload = json.loads((tmp_path / "model_inference" / "predictions.json").read_text(encoding="utf-8"))

    assert payload["backend"] == "deterministic"
    assert payload["returned_predictions"] == 1

    with pytest.raises(RuntimeError, match="torch and transformers|required|local"):
        await node_class().run(
            input_data=str(input_path),
            model_name="local/missing-model",
            task="text_classification",
            candidate_labels="a,b",
            fallback_backend="local",
            context=SimpleNamespace(node_dir=tmp_path),
        )


@pytest.mark.asyncio
async def test_model_inference_empty_input_writes_empty_outputs(
    tmp_path: Any,
) -> None:
    node_class = _node_class("model_inference")

    result = await node_class().run(
        input_data="",
        model_name="local/model",
        task="text_classification",
        fallback_backend="deterministic",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    json_path = tmp_path / "model_inference" / "predictions.json"
    csv_path = tmp_path / "model_inference" / "scores.csv"
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert result == {"outputs": {"predictions_json": str(json_path), "scores_csv": str(csv_path)}}
    assert payload["input_count"] == 0
    assert payload["returned_predictions"] == 0
    assert payload["predictions"] == []
