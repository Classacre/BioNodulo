"""Multi-agent paper-reproduction orchestrator for BioNodulo AI.

Given a paper (already extracted to text), this drives a pipeline of focused
sub-agents toward reproducing the paper's pipeline:

1. ``parse_paper`` extracts a structured :class:`ReproductionPlan` (datasets,
   tools/methods, pipeline steps, expected results).
2. In parallel, a **dataset** sub-agent locates and downloads the referenced
   data, and a **node-author** sub-agent writes custom nodes for any tool the
   built-in registry doesn't cover.
3. A **builder** sub-agent assembles the node graph.
4. A **debug** sub-agent runs the workflow and fixes failures (run -> read logs
   -> edit -> re-run) until it succeeds or the budget is exhausted.
5. A **verify** sub-agent compares outputs against the paper's expected results.

Each sub-agent is the ordinary tool-using assistant loop (:func:`chat_with_tools`)
given a role-specific system prompt and a restricted tool set, so they reuse all
existing tool plumbing. The LLM-driven boundaries (`parse_fn`, `agent_fn`) are
injectable to keep the orchestration unit-testable without a live model.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from bionodulo.ai.assistant import ChatResponse, chat_with_tools
from bionodulo.ai.llm_backend import call_llm, resolve_llm_config, safe_json_parse


@dataclass
class ReproductionPlan:
    """Structured extraction of what a paper requires to reproduce."""

    title: str = ""
    summary: str = ""
    datasets: list[dict[str, Any]] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    expected_results: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReproductionPlan":
        data = data or {}
        datasets = []
        for entry in data.get("datasets", []) or []:
            if isinstance(entry, dict):
                datasets.append(entry)
            elif isinstance(entry, str):
                datasets.append({"accession": entry})
        return cls(
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            datasets=datasets,
            tools=[str(t) for t in (data.get("tools") or [])],
            steps=[str(s) for s in (data.get("steps") or [])],
            expected_results=[str(r) for r in (data.get("expected_results") or [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "datasets": self.datasets,
            "tools": self.tools,
            "steps": self.steps,
            "expected_results": self.expected_results,
        }


PARSE_SYSTEM_PROMPT = (
    "You are a bioinformatics methods extractor. Read the paper text and return a "
    "single JSON object describing what is needed to reproduce its computational "
    "pipeline. Keys: title (string), summary (string), datasets (array of objects "
    "with 'accession' or 'url' and 'description'), tools (array of tool/software "
    "names with versions if given), steps (array of high-level pipeline steps in "
    "order), expected_results (array of the paper's key quantitative claims). "
    "Return ONLY the JSON object."
)

DATASET_AGENT_PROMPT = (
    "You are the DATASET sub-agent for a paper-reproduction task. Find the "
    "sequencing/data accessions or URLs the paper uses and download them with "
    "download_dataset. Use search_literature only to disambiguate. Report exactly "
    "what you downloaded and where."
)

NODE_AUTHOR_AGENT_PROMPT = (
    "You are the NODE-AUTHOR sub-agent. For each tool the paper needs that is not "
    "already a built-in node (check with list_available_nodes / get_node_info), "
    "write a custom node with write_custom_node, including its conda/pip "
    "requirements. Do not build the graph; only ensure the needed nodes exist."
)

BUILDER_AGENT_PROMPT = (
    "You are the WORKFLOW-BUILDER sub-agent. Assemble the node graph that "
    "implements the paper's pipeline steps using add_node/add_edge/update_node "
    "(or load_template as a starting point). Wire inputs/outputs by type. Finish "
    "by calling validate_workflow and fixing any errors you can."
)

DEBUG_AGENT_PROMPT = (
    "You are the DEBUG sub-agent. Call run_workflow; if it fails, read_run_logs "
    "for the failing node, diagnose the root cause, edit the graph, and run again. "
    "Repeat until the run completes or you are truly blocked, then summarize."
)

VERIFY_AGENT_PROMPT = (
    "You are the VERIFY sub-agent. Inspect the run's outputs with "
    "read_workspace_file / read_run_logs and compare them against the paper's "
    "expected results. State clearly whether each expected result was reproduced."
)

DATASET_TOOLS = ["search_literature", "download_dataset", "read_workspace_file", "get_workflow_summary"]
NODE_AUTHOR_TOOLS = ["list_available_nodes", "get_node_info", "write_custom_node", "search_literature"]
BUILDER_TOOLS = [
    "list_available_nodes", "get_node_info", "add_node", "add_edge", "update_node",
    "remove_node", "remove_edge", "load_template", "validate_workflow", "get_workflow_summary",
]
DEBUG_TOOLS = [
    "run_workflow", "read_run_logs", "get_run_status", "update_node", "add_node",
    "add_edge", "remove_node", "validate_workflow", "get_node_info", "get_dependency_report",
]
VERIFY_TOOLS = ["read_workspace_file", "read_run_logs", "get_run_status", "get_workflow_summary"]


# Type of the injectable sub-agent runner.
AgentFn = Callable[..., Awaitable[ChatResponse]]


async def parse_paper(
    paper_text: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
) -> ReproductionPlan:
    """Extract a :class:`ReproductionPlan` from paper text via one LLM pass."""
    config = resolve_llm_config(
        provider=provider, model=model, api_key=api_key, api_base=api_base, max_tokens=2048
    )
    messages = [
        {"role": "system", "content": PARSE_SYSTEM_PROMPT},
        {"role": "user", "content": str(paper_text)[:24000]},
    ]
    response = await call_llm(config, messages, json_mode=True)
    if response.error:
        raise RuntimeError(f"Paper parsing failed: {response.error}")
    return ReproductionPlan.from_dict(safe_json_parse(response.content))


async def _default_agent_fn(
    *,
    role: str,
    role_prompt: str,
    task: str,
    workflow: dict[str, Any] | None,
    tool_names: list[str],
    base_kwargs: dict[str, Any],
) -> ChatResponse:
    """Run one focused sub-agent as a tool-using assistant loop."""
    return await chat_with_tools(
        task,
        workflow=workflow,
        history=[],
        system_prompt=role_prompt,
        tool_names=tool_names,
        **base_kwargs,
    )


def _empty_workflow(workflow_id: str | None) -> dict[str, Any]:
    return {"id": workflow_id or "reproduction", "name": "Reproduction", "nodes": [], "edges": []}


async def reproduce_paper(
    paper_text: str,
    *,
    registry: Any = None,
    settings: Any = None,
    run_queue: Any = None,
    provider: str = "openai",
    model: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    workflow_id: str | None = None,
    parse_fn: Callable[..., Awaitable[ReproductionPlan]] | None = None,
    agent_fn: AgentFn | None = None,
) -> dict[str, Any]:
    """Drive the full paper-reproduction pipeline and return a structured report.

    ``parse_fn`` and ``agent_fn`` are injectable so the orchestration can be
    tested without a live model.
    """
    parse_fn = parse_fn or parse_paper
    agent_fn = agent_fn or _default_agent_fn

    plan = await parse_fn(
        paper_text, provider=provider, model=model, api_key=api_key, api_base=api_base
    )

    base_kwargs = dict(
        registry=registry,
        settings=settings,
        run_queue=run_queue,
        provider=provider,
        model=model,
        api_key=api_key,
        api_base=api_base,
        workflow_id=workflow_id,
    )

    plan_json = plan.to_dict()
    # Phase 1: dataset acquisition and node authoring are independent -> parallel.
    dataset_co = agent_fn(
        role="dataset",
        role_prompt=DATASET_AGENT_PROMPT,
        task=f"Download the datasets for this paper.\nPlan: {plan_json}",
        workflow=_empty_workflow(workflow_id),
        tool_names=DATASET_TOOLS,
        base_kwargs=base_kwargs,
    )
    node_co = agent_fn(
        role="node_author",
        role_prompt=NODE_AUTHOR_AGENT_PROMPT,
        task=f"Ensure nodes exist for these tools: {plan.tools}",
        workflow=_empty_workflow(workflow_id),
        tool_names=NODE_AUTHOR_TOOLS,
        base_kwargs=base_kwargs,
    )
    dataset_res, node_res = await asyncio.gather(dataset_co, node_co)

    # Phase 2: build the graph (needs to know which nodes/data are available).
    builder_res = await agent_fn(
        role="builder",
        role_prompt=BUILDER_AGENT_PROMPT,
        task=(
            "Build the workflow implementing these steps in order: "
            f"{plan.steps}\nTools: {plan.tools}\nDatasets: {plan.datasets}"
        ),
        workflow=_empty_workflow(workflow_id),
        tool_names=BUILDER_TOOLS,
        base_kwargs=base_kwargs,
    )
    workflow = builder_res.proposed_workflow or _empty_workflow(workflow_id)

    # Phase 3: run and auto-debug until it completes.
    debug_res = await agent_fn(
        role="debug",
        role_prompt=DEBUG_AGENT_PROMPT,
        task="Run this workflow and fix any failures until it completes.",
        workflow=workflow,
        tool_names=DEBUG_TOOLS,
        base_kwargs=base_kwargs,
    )
    workflow = debug_res.proposed_workflow or workflow

    # Phase 4: verify outputs against the paper's claims.
    verify_res = await agent_fn(
        role="verify",
        role_prompt=VERIFY_AGENT_PROMPT,
        task=f"Verify the outputs reproduce these expected results: {plan.expected_results}",
        workflow=workflow,
        tool_names=VERIFY_TOOLS,
        base_kwargs=base_kwargs,
    )

    return {
        "plan": plan_json,
        "datasets": dataset_res.reply,
        "custom_nodes": node_res.reply,
        "builder": builder_res.reply,
        "debug": debug_res.reply,
        "verification": verify_res.reply,
        "workflow": workflow,
    }
