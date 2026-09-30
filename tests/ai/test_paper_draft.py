"""A DOI chat turn uses verified paper evidence before proposing a draft."""
from __future__ import annotations

import pytest

from bionodulo.ai import assistant, research_tools
from bionodulo.ai.runtime import ModelTurn
from bionodulo.ai.tools import execute_tool
from bionodulo.nodes.registry import NodeRegistry


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
                                               api_key="test", registry=NodeRegistry.create_isolated(),
                                               on_step=events.append)
    assert response.proposed_workflow is not None
    assert {node["type"] for node in response.proposed_workflow["nodes"]} == {"deseq2_analysis", "input_file"}
    assert {edge["to"]["input"] for edge in response.proposed_workflow["edges"]} == {"count_matrix", "sample_info"}
    assert [step.type for step in events[:2]] == ["tool_call", "tool_result"]
    assert events[0].name == "get_paper"
    assert "open_access_full_text_excerpt" in str(model_messages[0])
    assert "https://europepmc.org/articles/PMC4302049" in str(model_messages[0])
    assert "full_text_excerpt" not in str([message for message in model_messages[0] if message["role"] == "system"])
    assert "full_text_excerpt" in str([message for message in model_messages[0] if message["role"] == "user"])
    assert "paper DOI cited by node" in str(model_messages[0])
    assert "count_matrix" in str(model_messages[0])
    assert any(step.type == "propose_changes" for step in response.steps)
    assert "not a run" in response.reply
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


@pytest.mark.asyncio
async def test_bare_doi_keeps_primary_method_and_wires_input_placeholders(monkeypatch: pytest.MonkeyPatch) -> None:
    events = []
    rounds = 0

    async def execute(name, arguments, ctx):
        if name == "get_paper":
            return {"status": "ok", "result": {"title": "DESeq2 method", "abstract": "RNA-seq count analysis."}}
        return execute_tool(name, arguments, ctx)

    async def full_text(_doi):
        return {"title": "DESeq2 method", "source_url": "https://europepmc.org/articles/PMC4302049",
                "full_text_excerpt": "Materials and methods: count matrix and sample information.",
                "full_text_truncated": True}

    async def model(**kwargs):
        nonlocal rounds
        rounds += 1
        if rounds == 1:
            assert not any(tool["function"]["name"] == "list_available_nodes" for tool in kwargs["tools"])
            return ModelTurn("", [{"id": "wrong", "name": "add_node", "arguments": {"node_type": "salmon_quant"}}])
        if rounds == 2:
            return ModelTurn("", [{"id": "method", "name": "add_node", "arguments": {"node_type": "deseq2_analysis"}}])
        return ModelTurn("The paper has no datasets and the defaults exactly match the original study.")

    monkeypatch.setattr(assistant, "aexecute_tool", execute)
    monkeypatch.setattr(research_tools, "open_access_excerpt_by_doi", full_text)
    monkeypatch.setattr(assistant, "_call_llm", model)
    registry = NodeRegistry.create_isolated()
    response = await assistant.chat_with_tools(DOI, workflow={"nodes": [], "edges": []}, history=[],
                                               api_key="test", registry=registry, on_step=events.append)
    graph = response.proposed_workflow
    assert graph is not None
    assert sorted(node["type"] for node in graph["nodes"]) == ["deseq2_analysis", "input_file", "input_file"]
    assert {edge["to"]["input"] for edge in graph["edges"]} == {"count_matrix", "sample_info"}
    assert {edge["from"]["output"] for edge in graph["edges"]} == {"file"}
    assert all(node["params"]["file"] == "" for node in graph["nodes"] if node["type"] == "input_file")
    assert execute_tool("validate_workflow", {}, assistant.ToolContext(workflow=graph, registry=registry))["result"]["valid"]
    assert "outside this paper" in str([step.result for step in events if step.name == "add_node"])
    assert [step.workflow for step in events if step.type == "propose_changes"][-1] == graph
    assert "not verified" in response.reply.lower()
    assert "paper reports dataset accessions" in response.reply
    assert "defaults exactly match" not in response.reply


@pytest.mark.asyncio
async def test_bare_doi_without_model_edits_still_drafts_cited_method(monkeypatch: pytest.MonkeyPatch) -> None:
    async def execute(name, _arguments, _ctx):
        assert name == "get_paper"
        return {"status": "ok", "result": {"title": "DESeq2 method", "abstract": "RNA-seq count analysis."}}

    async def full_text(_doi):
        return None

    async def model(**_kwargs):
        return ModelTurn("Would you like me to begin?")

    monkeypatch.setattr(assistant, "aexecute_tool", execute)
    monkeypatch.setattr(research_tools, "open_access_excerpt_by_doi", full_text)
    monkeypatch.setattr(assistant, "_call_llm", model)
    response = await assistant.chat_with_tools(DOI, workflow={"nodes": [], "edges": []}, history=[],
                                               api_key="test", registry=NodeRegistry.create_isolated())
    assert response.proposed_workflow is not None
    assert len(response.proposed_workflow["edges"]) == 2
    assert "Would you like" not in response.reply
    assert "Only the abstract" in response.reply


def test_cited_draft_rejects_incompatible_edges_and_separates_placeholders() -> None:
    registry = NodeRegistry.create_isolated()
    ctx = assistant.ToolContext(workflow={"nodes": [], "edges": []}, registry=registry)
    contracts = assistant.catalog_matches_for_paper(ctx, DOI, "DESeq2")
    methods = [contract for contract in contracts if contract["match_reason"] == "paper DOI cited by node"]
    helpers = assistant.input_helpers_for_contracts(ctx, methods)
    graph, error = assistant._complete_cited_paper_draft(ctx.workflow, registry, methods, helpers)
    assert not error and graph is not None
    assert len({tuple(node["position"]) for node in graph["nodes"]}) == len(graph["nodes"])
    assert len({edge["from"]["node"] for edge in graph["edges"]}) == 2
    graph["edges"][0]["from"]["output"] = "invented_output"
    rejected, error = assistant._complete_cited_paper_draft(graph, registry, methods, helpers)
    assert rejected is None
    assert "incompatible named ports" in error


@pytest.mark.asyncio
async def test_exhausted_model_does_not_claim_a_completed_paper_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    async def execute(name, _arguments, _ctx):
        if name != "get_paper":
            return {"status": "ok", "result": {}}
        return {"status": "ok", "result": {"title": "DESeq2 method", "abstract": "RNA-seq count analysis."}}

    async def no_full_text(_doi):
        return None

    async def failed_model(**_kwargs):
        return ModelTurn("", [{"id": "inspect", "name": "get_workflow_summary", "arguments": {}}])

    monkeypatch.setattr(assistant, "aexecute_tool", execute)
    monkeypatch.setattr(research_tools, "open_access_excerpt_by_doi", no_full_text)
    monkeypatch.setattr(assistant, "_call_llm", failed_model)
    response = await assistant.chat_with_tools(DOI, workflow=None, history=[], api_key="test",
                                               registry=NodeRegistry.create_isolated(), max_tool_rounds=1)
    assert response.proposed_workflow is None
    assert "I drafted" not in response.reply
    assert any(step.type == "error" for step in response.steps)


@pytest.mark.asyncio
async def test_pdf_draft_receives_catalog_contracts_and_connected_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    rounds = 0
    monkeypatch.setattr(assistant, "_extract_pdf_text", lambda _data: "Moderated estimation of fold change with DESeq2\nAbstract: Count analysis.")

    async def model(**kwargs):
        nonlocal rounds
        rounds += 1
        if rounds == 1:
            assert "tool identity appears in supplied paper heading" in str(kwargs["messages"])
            assert not any(tool["function"]["name"] == "search_literature" for tool in kwargs["tools"])
            return ModelTurn("", [{"id": "method", "name": "add_node", "arguments": {"node_type": "deseq2_analysis"}}])
        return ModelTurn("Drafted the method using the uploaded preprint; supply your own count data.")

    monkeypatch.setattr(assistant, "_call_llm", model)
    events = []
    response = await assistant.chat_with_tools("Build a workflow from this paper.", workflow=None, history=[],
        api_key="test", registry=NodeRegistry.create_isolated(), on_step=events.append,
        files=[{"name": "author-preprint.pdf", "mime_type": "application/pdf", "data_url": "data:application/pdf;base64,dGVzdA=="}])
    assert response.proposed_workflow is not None
    assert len(response.proposed_workflow["edges"]) == 2
    assert len(response.proposed_workflow["nodes"]) == 3
    assert "attached PDF" in response.proposed_workflow["description"]
    assert "doi.org" not in response.reply
    assert [event.workflow for event in events if event.type == "propose_changes"][-1] == response.proposed_workflow
