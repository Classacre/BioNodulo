from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.ai.llm_backend import LLMConfig, LLMResponse
from bionodulo.nodes.builtin.llm_family import (
    ai_data_extraction,
    ai_image_analysis,
    ai_literature_search,
    ai_pipeline_advisor,
    ai_report_generator,
    ai_sequence_analysis,
    ai_variant_interpretation,
    llm_decision,
    llm_prompt,
)


def context(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(node_dir=tmp_path, resolve_secret=lambda _key: None)


@pytest.mark.asyncio
async def test_llm_prompt_renders_variables_and_returns_json_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    async def fake_call(config: LLMConfig, messages: list[dict[str, Any]], *, json_mode: bool = False) -> LLMResponse:
        calls.append({"config": config, "messages": messages, "json_mode": json_mode})
        return LLMResponse(content='{"gene": "TP53"}', model=config.model, usage={"total_tokens": 7})

    monkeypatch.setattr(llm_prompt, "call_llm", fake_call)
    response, metadata = await llm_prompt.LLMPromptNode().run(
        prompt="Analyze {{gene}}",
        variables={"gene": "TP53"},
        provider="litellm",
        model="test-model",
        json_mode=True,
    )

    assert response == '{"gene": "TP53"}'
    assert calls[0]["messages"][-1]["content"] == "Analyze TP53"
    assert calls[0]["json_mode"] is True
    assert metadata["parsed_json"] == {"gene": "TP53"}

    async def fake_plain(*_args: Any, **_kwargs: Any) -> LLMResponse:
        return LLMResponse(content="Plain response")

    monkeypatch.setattr(llm_prompt, "call_llm", fake_plain)
    plain, plain_metadata = await llm_prompt.LLMPromptNode().run(
        prompt="Summarize TP53",
        provider="litellm",
        json_mode=False,
    )
    assert plain == "Plain response"
    assert "parsed_json" not in plain_metadata


@pytest.mark.asyncio
async def test_llm_decision_accepts_only_an_allowed_structured_label(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call(*_args: Any, **_kwargs: Any) -> LLMResponse:
        return LLMResponse(content='{"label": "pass", "confidence": 0.9, "reason": "quality"}')

    monkeypatch.setattr(llm_decision, "call_llm", fake_call)
    label, matched, payload = await llm_decision.LLMDecisionNode().run(
        input_data="Q30=94%",
        criteria="Pass if Q30 > 90%",
        labels="pass, fail",
        provider="litellm",
    )

    assert (label, matched) == ("pass", True)
    assert payload["confidence"] == 0.9


@pytest.mark.asyncio
async def test_variant_interpretation_writes_both_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    variants = tmp_path / "variants.csv"
    variants.write_text("chrom,pos,ref,alt,gene\n17,43071077,A,G,BRCA1\n", encoding="utf-8")

    async def fake_call(*_args: Any, **_kwargs: Any) -> LLMResponse:
        return LLMResponse(
            content=json.dumps(
                {
                    "interpretations": [
                        {
                            "variant_id": "17:43071077:A:G",
                            "gene": "BRCA1",
                            "pathogenicity": "uncertain",
                            "confidence": 0.4,
                            "summary": "Review curated evidence.",
                            "evidence": [],
                        }
                    ]
                }
            )
        )

    monkeypatch.setattr(ai_variant_interpretation, "call_llm", fake_call)
    result = await ai_variant_interpretation.AIVariantInterpretationNode().run(
        variant_table=str(variants),
        framework="ACMG",
        provider="litellm",
        context=context(tmp_path),
    )

    assert Path(result["outputs"]["interpretation_json"]).is_file()
    assert Path(result["outputs"]["scores_csv"]).is_file()
    payload = json.loads(Path(result["outputs"]["interpretation_json"]).read_text(encoding="utf-8"))
    assert payload["variant_count"] == 1
    assert payload["interpretations"][0]["gene"] == "BRCA1"


@pytest.mark.asyncio
async def test_sequence_analysis_reads_fasta_and_returns_structured_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fasta = tmp_path / "sequence.fasta"
    fasta.write_text(">seq1\nMTEYKLVVVG\n", encoding="utf-8")

    async def fake_call(*_args: Any, **_kwargs: Any) -> LLMResponse:
        return LLMResponse(content='{"summary": "One protein sequence.", "motifs": []}')

    monkeypatch.setattr(ai_sequence_analysis, "call_llm", fake_call)
    raw_json, summary = await ai_sequence_analysis.AISequenceAnalysisNode().run(
        input_fasta=str(fasta),
        analysis_type="motifs",
        molecule_type="protein",
        provider="litellm",
    )

    assert summary == "One protein sequence."
    assert json.loads(raw_json)["sequence_count"] == 1


@pytest.mark.asyncio
async def test_literature_search_uses_fake_pubmed_and_writes_attested_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call(
        _config: LLMConfig,
        _messages: list[dict[str, Any]],
        *,
        json_mode: bool = False,
    ) -> LLMResponse:
        if json_mode:
            return LLMResponse(content='{"queries": ["TP53 cancer[Title/Abstract]"]}')
        return LLMResponse(content="TP53 evidence summary [PMID:12345].")

    async def fake_json(endpoint: str, _params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        if endpoint == "esearch.fcgi":
            return {"esearchresult": {"idlist": ["12345"], "querytranslation": "TP53"}}
        if endpoint == "esummary.fcgi":
            return {
                "result": {
                    "uids": ["12345"],
                    "12345": {
                        "title": "TP53 review",
                        "pubdate": "2025",
                        "fulljournalname": "Example Journal",
                        "authors": [{"name": "Smith J"}],
                        "elocationid": "doi:10.1000/example",
                    },
                }
            }
        raise AssertionError(endpoint)

    async def fake_text(_endpoint: str, _params: dict[str, Any], **_kwargs: Any) -> str:
        return (
            "<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>12345</PMID><Article><Abstract>"
            "<AbstractText>DNA damage response.</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle>"
            "</PubmedArticleSet>"
        )

    monkeypatch.setattr(ai_literature_search, "call_llm", fake_call)
    monkeypatch.setattr(ai_literature_search, "_request_json", fake_json)
    monkeypatch.setattr(ai_literature_search, "_request_text", fake_text)
    result = await ai_literature_search.AILiteratureSearchNode().run(
        research_question="What does TP53 do in cancer?",
        databases="pubmed",
        search_depth="quick",
        include_abstracts=True,
        provider="litellm",
        context=context(tmp_path),
    )

    payload = result["outputs"]["papers_json"]
    assert payload["papers_found"] == 1
    assert payload["papers"][0]["pmid"] == "12345"
    assert (tmp_path / "ai_literature_search" / "papers.json").is_file()
    assert (tmp_path / "ai_literature_search" / "summary.txt").is_file()


@pytest.mark.asyncio
async def test_data_extraction_writes_json_and_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call(*_args: Any, **_kwargs: Any) -> LLMResponse:
        return LLMResponse(content='{"genes": [{"gene_symbol": "TP53", "normalized_id": "HGNC:11998"}]}')

    monkeypatch.setattr(ai_data_extraction, "call_llm", fake_call)
    result = await ai_data_extraction.AIDataExtractionNode().run(
        input_text="TP53 regulates the DNA damage response.",
        extraction_schema="genes_variants_diseases",
        output_format="both",
        provider="litellm",
        context=context(tmp_path),
    )

    assert Path(result["outputs"]["extracted_json"]).is_file()
    assert Path(result["outputs"]["extracted_csv"]).is_file()


@pytest.mark.asyncio
async def test_pipeline_advisor_writes_selected_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call(*_args: Any, **_kwargs: Any) -> LLMResponse:
        return LLMResponse(content='{"recommended_nodes": [{"node_id": "fastqc"}], "rationale": "Run QC first."}')

    monkeypatch.setattr(ai_pipeline_advisor, "call_llm", fake_call)
    result = await ai_pipeline_advisor.AIPipelineAdvisorNode().run(
        experiment_type="bulk_rnaseq",
        metadata={},
        output_format="both",
        provider="litellm",
        context=context(tmp_path),
    )

    assert Path(result["outputs"]["recommendations_json"]).is_file()
    assert Path(result["outputs"]["rationale_text"]).read_text(encoding="utf-8") == "Run QC first."


@pytest.mark.asyncio
async def test_image_analysis_builds_multimodal_request_and_fails_on_missing_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = tmp_path / "gel.png"
    image.write_bytes(bytes.fromhex("89504e470d0a1a0a"))
    calls: list[list[dict[str, Any]]] = []

    async def fake_call(
        _config: LLMConfig,
        messages: list[dict[str, Any]],
        *,
        json_mode: bool = False,
    ) -> LLMResponse:
        calls.append(messages)
        assert json_mode is True
        return LLMResponse(content='{"description": "Two visible lanes."}')

    monkeypatch.setattr(ai_image_analysis, "call_llm", fake_call)
    result = await ai_image_analysis.AIImageAnalysisNode().run(
        input_image=str(image),
        analysis_task="gel_electrophoresis",
        provider="litellm",
        context=context(tmp_path),
    )

    assert Path(result["outputs"]["analysis_json"]).is_file()
    assert calls[0][1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    with pytest.raises(FileNotFoundError, match="input not found"):
        await ai_image_analysis.AIImageAnalysisNode().run(
            input_image=str(tmp_path / "missing.png"),
            analysis_task="general",
            provider="litellm",
            context=context(tmp_path),
        )


@pytest.mark.asyncio
async def test_report_generator_writes_html_and_rejects_unknown_format(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call(*_args: Any, **_kwargs: Any) -> LLMResponse:
        return LLMResponse(content="# Results\n\nQuality was acceptable.")

    monkeypatch.setattr(ai_report_generator, "call_llm", fake_call)
    result = await ai_report_generator.AIReportGeneratorNode().run(
        analysis_data="Q30=94%",
        report_title="QC Report",
        output_format="both",
        provider="litellm",
        context=context(tmp_path),
    )

    report = Path(result["outputs"]["report_html"])
    assert report.is_file()
    assert "<h1>Results</h1>" in report.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="output_format"):
        await ai_report_generator.AIReportGeneratorNode().run(
            analysis_data="data",
            report_title="Report",
            output_format="pdf",
            provider="litellm",
        )


@pytest.mark.asyncio
async def test_structured_provider_node_rejects_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call(*_args: Any, **_kwargs: Any) -> LLMResponse:
        return LLMResponse(content="not-json")

    monkeypatch.setattr(ai_data_extraction, "call_llm", fake_call)
    with pytest.raises(RuntimeError, match="malformed JSON"):
        await ai_data_extraction.AIDataExtractionNode().run(
            input_text="TP53",
            extraction_schema="genes_variants_diseases",
            provider="litellm",
        )
