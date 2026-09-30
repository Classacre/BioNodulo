"""A DOI chat turn uses verified paper evidence before proposing a draft."""
from __future__ import annotations

import pytest

from bionodulo.ai import assistant, research_tools
from bionodulo.ai.runtime import ModelTurn


DOI = "10.1186/s13059-014-0550-8"


@pytest.mark.asyncio
async def test_bare_doi_grounds_and_proposes_a_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    events = []
    model_messages = []
    rounds = 0
    drafted = {"nodes": [{"id": "analysis", "type": "deseq2_analysis", "params": {}}], "edges": []}

    async def execute(name, _arguments, _ctx):
        if name == "get_paper":
            return {"status": "ok", "result": {"title": "DESeq2 methods paper", "abstract": "Differential analysis of count data."}}
        assert name == "add_node"
        return {"status": "ok", "result": {"workflow": drafted}, "mutates": True}

    async def full_text(_doi):
        return {"title": "DESeq2 methods paper", "source_url": "https://europepmc.org/articles/PMC4302049",
                "full_text_excerpt": "Materials and methods: raw count matrix and sample design.",
                "full_text_truncated": False}

    async def model(**kwargs):
        nonlocal rounds
        rounds += 1
        model_messages.append(kwargs["messages"])
        if rounds == 1:
            return ModelTurn("", [{"id": "add_1", "name": "add_node", "arguments": {"node_type": "deseq2_analysis"}}])
        return ModelTurn("Draft requires user counts, sample metadata, and a contrast; no run was performed.")

    monkeypatch.setattr(assistant, "aexecute_tool", execute)
    monkeypatch.setattr(research_tools, "open_access_excerpt_by_doi", full_text)
    monkeypatch.setattr(assistant, "_call_llm", model)

    response = await assistant.chat_with_tools(DOI, workflow={"nodes": [], "edges": []}, history=[],
                                               api_key="test", on_step=events.append)
    assert response.proposed_workflow == drafted
    assert [step.type for step in events[:2]] == ["tool_call", "tool_result"]
    assert events[0].name == "get_paper"
    assert "open_access_full_text_excerpt" in str(model_messages[0])
    assert "https://europepmc.org/articles/PMC4302049" in str(model_messages[0])
    assert "full_text_excerpt" not in str([message for message in model_messages[0] if message["role"] == "system"])
    assert "full_text_excerpt" in str([message for message in model_messages[0] if message["role"] == "user"])
    assert any(step.type == "propose_changes" for step in response.steps)
    assert "no run" in response.reply
    assert "https://doi.org/10.1186/s13059-014-0550-8" in response.reply
    assert "https://europepmc.org/articles/PMC4302049" in response.reply
    assert "No execution or reproduction" in response.reply


@pytest.mark.asyncio
async def test_unverifiable_doi_stops_before_model_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    async def execute(_name, _arguments, _ctx):
        return {"status": "error", "error": "not found"}

    async def no_full_text(_doi):
        return None

    async def forbidden_model(**_kwargs):
        raise AssertionError("The model must not draft from an unverified DOI")

    monkeypatch.setattr(assistant, "aexecute_tool", execute)
    monkeypatch.setattr(research_tools, "open_access_excerpt_by_doi", no_full_text)
    monkeypatch.setattr(assistant, "_call_llm", forbidden_model)
    response = await assistant.chat_with_tools(f"https://doi.org/{DOI}", workflow=None,
                                               history=[], api_key="test")
    assert response.proposed_workflow is None
    assert response.steps[-1].type == "error"
    assert "attach the paper" in response.steps[-1].content


@pytest.mark.asyncio
async def test_abstract_only_draft_marks_methods_unverified(monkeypatch: pytest.MonkeyPatch) -> None:
    async def execute(_name, _arguments, _ctx):
        return {"status": "ok", "result": {"title": "Methods paper", "abstract": "A method for count data."}}

    async def no_full_text(_doi):
        return None

    async def model(**_kwargs):
        return ModelTurn("A conceptual workflow needs user input choices.")

    monkeypatch.setattr(assistant, "aexecute_tool", execute)
    monkeypatch.setattr(research_tools, "open_access_excerpt_by_doi", no_full_text)
    monkeypatch.setattr(assistant, "_call_llm", model)
    response = await assistant.chat_with_tools(DOI, workflow=None, history=[], api_key="test")
    assert "Only the abstract was available" in response.reply
    assert response.proposed_workflow is None
