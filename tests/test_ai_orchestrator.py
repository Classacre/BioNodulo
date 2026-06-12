from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from bionodulo.ai.assistant import ChatResponse
from bionodulo.ai import orchestrator
from bionodulo.ai.orchestrator import ReproductionPlan, parse_paper, reproduce_paper


@pytest.mark.asyncio
async def test_parse_paper_extracts_structured_plan(monkeypatch):
    payload = {
        "title": "A great paper",
        "summary": "RNA-seq differential expression.",
        "datasets": [{"accession": "SRR000001", "description": "control"}, "SRR000002"],
        "tools": ["fastp", "STAR", "DESeq2"],
        "steps": ["QC", "align", "quantify", "DE"],
        "expected_results": ["1200 DE genes at FDR<0.05"],
    }

    async def fake_call_llm(config, messages, **kwargs):
        assert kwargs.get("json_mode") is True
        return SimpleNamespace(content=json.dumps(payload), error="")

    monkeypatch.setattr(orchestrator, "call_llm", fake_call_llm)

    plan = await parse_paper("paper text here", provider="custom")

    assert isinstance(plan, ReproductionPlan)
    assert plan.title == "A great paper"
    assert plan.tools == ["fastp", "STAR", "DESeq2"]
    assert plan.steps[0] == "QC"
    # The bare-string dataset entry is normalized into an accession object.
    assert plan.datasets[1] == {"accession": "SRR000002"}


@pytest.mark.asyncio
async def test_reproduce_paper_runs_subagents_and_threads_workflow():
    plan = ReproductionPlan(
        title="P",
        tools=["fastp", "star"],
        steps=["qc", "align"],
        datasets=[{"accession": "SRR1"}],
        expected_results=["X"],
    )

    async def fake_parse(paper_text, **kwargs):
        return plan

    calls: list[dict] = []
    builder_workflow = {"id": "wf", "nodes": [{"id": "n1", "type": "fastp"}], "edges": []}

    async def fake_agent(*, role, role_prompt, task, workflow, tool_names, base_kwargs):
        calls.append({"role": role, "workflow": workflow, "tool_names": tool_names})
        proposed = builder_workflow if role == "builder" else None
        return ChatResponse(steps=[], reply=f"{role} done", proposed_workflow=proposed)

    report = await reproduce_paper(
        "paper text",
        provider="custom",
        parse_fn=fake_parse,
        agent_fn=fake_agent,
    )

    roles = [c["role"] for c in calls]
    assert roles == ["dataset", "node_author", "builder", "debug", "verify"]

    # Each sub-agent gets only its restricted tool set.
    dataset_call = next(c for c in calls if c["role"] == "dataset")
    assert "download_dataset" in dataset_call["tool_names"]
    assert "run_workflow" not in dataset_call["tool_names"]

    # The builder's proposed workflow is threaded into the debug and verify phases.
    debug_call = next(c for c in calls if c["role"] == "debug")
    verify_call = next(c for c in calls if c["role"] == "verify")
    assert debug_call["workflow"] == builder_workflow
    assert verify_call["workflow"] == builder_workflow

    assert report["plan"]["title"] == "P"
    assert report["workflow"] == builder_workflow
    assert set(report) >= {"plan", "datasets", "custom_nodes", "builder", "debug", "verification", "workflow"}
