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
