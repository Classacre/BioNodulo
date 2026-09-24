"""Mechanical adjudication of BioNodulo evaluation-study run artifacts.

Loads a task definition (``Possible PhD/evaluation-study/tasks/T*.json``) and a
submission workflow (the JSON artifact a participant or agent produced), checks
the submission against the task's ground truth, and emits a verdict.

Three layers of checking:

1. Structural ground truth: required node types present, required parameters set
   to the expected values, required data-state on specific edges (resolved
   through the semantic checker's propagated state), no forbidden paths.
2. Contract layer: ``bionodulo.workflow.semantic_checks.check_workflow_semantics``
   against the bundled seed contract library (the shipped checker, not an
   idealized one). Whatever it reports is surfaced verbatim in
   ``contract_violations_detected``; often it reports nothing, which is itself
   the measurement: the failure was silent to the deployed checker.
3. Static hazard assessment only. This script does not execute workflows,
   inspect scientific outputs, observe participants, or adjudicate human
   outcomes. ``silent_error`` remains null until a separate observed-trial
   pipeline supplies that evidence. A graph hazard cannot establish a clean
   exit, wrong result, or lack of participant detection.

Usage:
    python adjudicate.py --task tasks/T1.json --submission submissions/T1-planted.json
    python adjudicate.py --task T1.json --submission wf.json --out verdict.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Make the app package importable when the script is run from scripts/evaluation.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bionodulo.nodes.semantic_contracts import SemanticContractLibrary  # noqa: E402
from bionodulo.workflow.semantic_checks import (  # noqa: E402
    SemanticCheckResult,
    check_workflow_semantics,
)

ASSEMBLY_TOKEN_RE = re.compile(r"(grch\d{2}|grcm\d{2}|wbcel235|ara_tha_ta10)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Workflow plumbing


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def nodes_of(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Node id -> node map, tolerating list and dict node collections."""
    raw = workflow.get("nodes", [])
    if isinstance(raw, dict):
        return {node_id: (node if isinstance(node, dict) else {}) for node_id, node in raw.items()}
    return {node["id"]: node for node in raw if isinstance(node, dict) and node.get("id")}


def edges_of(workflow: dict[str, Any]) -> list[dict[str, str]]:
    """Normalized edges: {id, source, source_output, target, target_input}."""
    normalized: list[dict[str, str]] = []
    for edge in workflow.get("edges", []):
        source = edge.get("from") if isinstance(edge.get("from"), dict) else None
        target = edge.get("to") if isinstance(edge.get("to"), dict) else None
        if source is not None and target is not None:
            normalized.append(
                {
                    "id": str(edge.get("id", f"{source.get('node')}-to-{target.get('node')}")),
                    "source": str(source.get("node", "")),
                    "source_output": str(source.get("output", "")),
                    "target": str(target.get("node", "")),
                    "target_input": str(target.get("input", "")),
                }
            )
        elif edge.get("from_node") or edge.get("fromNode"):
            normalized.append(
                {
                    "id": str(edge.get("id", "")),
                    "source": str(edge.get("from_node") or edge.get("fromNode") or ""),
                    "source_output": str(edge.get("from_output") or edge.get("fromOutput") or ""),
                    "target": str(edge.get("to_node") or edge.get("toNode") or ""),
                    "target_input": str(edge.get("to_input") or edge.get("toInput") or ""),
                }
            )
    return normalized


def _params_of(node: dict[str, Any]) -> dict[str, Any]:
    params = node.get("params", {})
    return params if isinstance(params, dict) else {}


# ---------------------------------------------------------------------------
# Ground-truth checks (each returns a list of check result dicts)


def check_required_node_types(
    required: list[str], nodes: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    present = {node.get("type", "") for node in nodes.values()}
    results = []
    for node_type in required:
        results.append(
            {
                "check": "required_node_type",
                "node_type": node_type,
                "ok": node_type in present,
                "detail": "" if node_type in present else f"no node of type {node_type} present",
            }
        )
    return results


def check_param_requirements(
    requirements: list[dict[str, Any]], nodes: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    results = []
    for requirement in requirements:
        node_type = requirement["node_type"]
        param = requirement["param"]
        expected = str(requirement["expected"])
        matching = [node for node in nodes.values() if node.get("type") == node_type]
        if not matching:
            results.append(
                {
                    "check": "param_requirement",
                    "node_type": node_type,
                    "param": param,
                    "ok": False,
                    "detail": f"no node of type {node_type} to check",
                }
            )
            continue
        offenders = [
            node_id
            for node_id, node in nodes.items()
            if node.get("type") == node_type and str(_params_of(node).get(param)) != expected
        ]
        results.append(
            {
                "check": "param_requirement",
                "node_type": node_type,
                "param": param,
                "expected": expected,
                "ok": not offenders,
                "detail": (
                    "ok"
                    if not offenders
                    else f"{param} != {expected!r} on node(s) {', '.join(sorted(offenders))}"
                ),
            }
        )
    return results


def _state_lookup(
    sem_result: SemanticCheckResult,
    source: str,
    source_output: str,
    dimension: str,
) -> str | None:
    port_states = sem_result.node_states.get(source, {})
    state = port_states.get(source_output)
    if state is None:
        return None
    return state.get(dimension)


def check_edge_states(
    requirements: list[dict[str, Any]],
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, str]],
    sem_result: SemanticCheckResult,
) -> list[dict[str, Any]]:
    results = []
    for requirement in requirements:
        to_type = requirement["to_type"]
        to_input = requirement["to_input"]
        dimension = requirement["dimension"]
        expected = requirement["expected"]
        target_ids = {
            node_id for node_id, node in nodes.items() if node.get("type") == to_type
        }
        feeding = [
            edge
            for edge in edges
            if edge["target"] in target_ids and edge["target_input"] == to_input
        ]
        if not feeding:
            results.append(
                {
                    "check": "edge_state",
                    "to_type": to_type,
                    "to_input": to_input,
                    "dimension": dimension,
                    "expected": expected,
                    "ok": False,
                    "detail": f"no edge feeds {to_type}.{to_input}",
                }
            )
            continue
        observed_values = []
        for edge in feeding:
            observed_values.append(
                (
                    edge["id"],
                    _state_lookup(sem_result, edge["source"], edge["source_output"], dimension),
                )
            )
        fed_targets = {edge["target"] for edge in feeding}
        missing_targets = sorted(target_ids - fed_targets)
        if not missing_targets and all(value == expected for _, value in observed_values):
            ok, detail = True, "ok"
        else:
            described = ", ".join(
                f"{edge_id}={value if value is not None else 'unknown/no-contract'}"
                for edge_id, value in observed_values
            )
            ok, detail = False, (
                f"{dimension} on {to_type}.{to_input} is {described}, expected {expected}; "
                f"targets without an input edge: {missing_targets}"
            )
        results.append(
            {
                "check": "edge_state",
                "to_type": to_type,
                "to_input": to_input,
                "dimension": dimension,
                "expected": expected,
                "ok": ok,
                "detail": detail,
            }
        )
    return results


def _collect_assembly_tokens(nodes: dict[str, dict[str, Any]]) -> set[str]:
    tokens: set[str] = set()
    for node in nodes.values():
        for value in _params_of(node).values():
            if isinstance(value, str):
                tokens.update(match.group(1).lower() for match in ASSEMBLY_TOKEN_RE.finditer(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        tokens.update(
                            match.group(1).lower()
                            for match in ASSEMBLY_TOKEN_RE.finditer(item)
                        )
    return tokens


def check_assembly_consistency(
    requirement: dict[str, Any], nodes: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    expected = {token.lower() for token in requirement.get("expected_tokens", [])}
    observed = _collect_assembly_tokens(nodes)
    if not observed:
        return {
            "check": "assembly_consistency",
            "ok": False,
            "detail": "no reference/annotation assembly tokens found in node params; unverifiable",
            "observed": sorted(observed),
            "expected": sorted(expected),
        }
    stray = observed - expected
    return {
        "check": "assembly_consistency",
        "ok": not stray,
        "detail": (
            "ok"
            if not stray
            else f"assembly tokens {sorted(stray)} conflict with expected {sorted(expected)}"
        ),
        "observed": sorted(observed),
        "expected": sorted(expected),
    }


def _reaches(
    start: str,
    target: str,
    target_input: str,
    edges: list[dict[str, str]],
) -> bool:
    frontier = [(start, "")]  # (node, input port we entered through)
    seen: set[str] = set()
    while frontier:
        node, _entered = frontier.pop()
        if node == target and _entered in ("", target_input):
            return True
        if node in seen:
            continue
        seen.add(node)
        for edge in edges:
            if edge["source"] == node:
                frontier.append((edge["target"], edge["target_input"]))
    return False


def check_forbidden_paths(
    forbidden: list[dict[str, Any]],
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, str]],
) -> list[dict[str, Any]]:
    results = []
    for rule in forbidden:
        offenders = [
            node_id
            for node_id, node in nodes.items()
            if node.get("type") == rule["node_type"]
            and all(_params_of(node).get(key) == value for key, value in rule.get("params", {}).items())
        ]
        target_ids = {
            node_id for node_id, node in nodes.items() if node.get("type") == rule["to_type"]
        }
        feeding = [
            node_id
            for node_id in offenders
            if any(_reaches(node_id, target, rule["to_input"], edges) for target in target_ids)
        ]
        results.append(
            {
                "check": "forbidden_path",
                "node_type": rule["node_type"],
                "params": rule.get("params", {}),
                "to_type": rule["to_type"],
                "to_input": rule["to_input"],
                "ok": not feeding,
                "detail": (
                    "ok"
                    if not feeding
                    else f"forbidden path: {rule['node_type']} {rule.get('params', {})} feeds {rule['to_type']}.{rule['to_input']} via {', '.join(sorted(feeding))}"
                ),
            }
        )
    return results


def check_control_task(
    task: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
    ground_checks: list[dict[str, Any]],
) -> list[str]:
    """T5: false-positive changes = structural changes a clean task never needed."""
    false_positives = [
        check["detail"] for check in ground_checks if not check["ok"]
    ]
    admissible = set(task["ground_truth"].get("admissible_node_types", []))
    extra = sorted(
        {
            node.get("type", "")
            for node in nodes.values()
            if node.get("type") and node.get("type") not in admissible
        }
    )
    for node_type in extra:
        false_positives.append(f"unnecessary node of type {node_type} added to a clean task")
    return false_positives


def check_ambiguous_task(
    task: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """T6: report graph hints; intent and actual examination are unobserved."""
    ground = task["ground_truth"]
    detection_types = set(ground.get("detection_node_types", []))
    detection_present = any(
        node.get("type") in detection_types for node in nodes.values()
    )
    deliberate_values = set(ground.get("deliberate_strand_values", ["1", "2"]))
    strand_choices = {
        str(_params_of(node).get("strand_specificity"))
        for node in nodes.values()
        if node.get("type") == "featurecounts"
    }
    deliberate = bool(strand_choices & deliberate_values)
    if detection_present or deliberate:
        handling = "graph_hint_present_unverified"
    else:
        handling = "no_graph_hint"
    return {
        "ambiguity_handling": handling,
        "detection_node_present": detection_present,
        "strand_specificity_values": sorted(strand_choices),
        "sealed_truth": ground.get("sealed_strandedness_truth"),
    }


# ---------------------------------------------------------------------------
# Verdict


def adjudicate(
    task: dict[str, Any],
    submission: dict[str, Any],
    library: SemanticContractLibrary | None = None,
) -> dict[str, Any]:
    """Judge one submission against one task definition."""
    nodes = nodes_of(submission)
    edges = edges_of(submission)
    ground = task.get("ground_truth", {})

    sem_result = check_workflow_semantics(submission, library=library)
    contract_violations = [
        {
            "edge": violation.edge_id,
            "dimension": violation.dimension,
            "producer": violation.producer_node,
            "guarantees": violation.producer_guarantee,
            "consumer": violation.consumer_node,
            "assumes": violation.consumer_assumption,
            "explanation": violation.explanation(),
        }
        for violation in sem_result.violations
    ]

    checks: list[dict[str, Any]] = []
    checks.extend(check_required_node_types(ground.get("required_node_types", []), nodes))
    checks.extend(check_param_requirements(ground.get("param_requirements", []), nodes))
    checks.extend(check_edge_states(ground.get("required_edge_states", []), nodes, edges, sem_result))
    for rule in ground.get("forbidden_paths", []):
        checks.extend(check_forbidden_paths([rule], nodes, edges))
    if "assembly_consistency" in ground:
        checks.append(check_assembly_consistency(ground["assembly_consistency"], nodes))

    planted = task.get("planted_failure")
    task_class = task.get("task_class", "planted_failure")
    notes: list[str] = []

    if planted is not None:
        signature = planted["signature"]
        kind = signature["kind"]
        if kind == "assembly_consistency":
            signature_checks = [c for c in checks if c["check"] == "assembly_consistency"]
        elif kind == "param_value":
            signature_checks = [
                c
                for c in checks
                if c["check"] == "param_requirement"
                and c.get("node_type") == signature["node_type"]
                and c.get("param") == signature["param"]
            ]
        elif kind == "edge_state":
            signature_checks = [
                c
                for c in checks
                if c["check"] == "edge_state"
                and c.get("to_type") == signature["to_type"]
                and c.get("to_input") == signature["to_input"]
                and c.get("dimension") == signature["dimension"]
            ]
        elif kind == "forbidden_path":
            signature_checks = [
                c
                for c in checks
                if c["check"] == "forbidden_path" and c.get("node_type") == signature["node_type"]
            ]
        else:
            raise ValueError(f"unknown planted-failure signature kind: {kind}")
        failure_present = bool(signature_checks) and not all(c["ok"] for c in signature_checks)
        failure_class = planted["class"] if failure_present else "none"
        if failure_present:
            detection_types = set(task.get("detection_node_types", []))
            if detection_types and any(
                node.get("type") in detection_types for node in nodes.values()
            ):
                notes.append(
                    "a detection node is present but the static hazard persists; "
                    "execution and participant interpretation were not observed"
                )
        else:
            notes.append("planted failure not present in submission (fixed or avoided)")
    else:
        failure_present = False
        failure_class = "none"

    ambiguity: dict[str, Any] | None = None
    false_positives: list[str] | None = None
    if task_class == "clean_control":
        false_positives = check_control_task(task, nodes, checks)
        if false_positives:
            failure_class = "false_positive_change"
    elif task_class == "ambiguous":
        ambiguity = check_ambiguous_task(task, nodes)
        if ambiguity["ambiguity_handling"] == "no_graph_hint":
            failure_class = "ambiguity_unresolved"
            notes.append(
                "no graph evidence of a strandedness check; participant examination is unknown"
            )

    if sem_result.violations:
        notes.append(
            "the shipped semantic checker reported "
            f"{len(sem_result.violations)} contract violation(s) on this submission"
        )

    return {
        "task_id": task.get("task_id"),
        "analysis_type": task.get("analysis_type"),
        "task_class": task_class,
        "planted_failure_expected": planted is not None,
        "failure_present": failure_present,
        "static_hazard_present": failure_present,
        "silent_error": None,
        "evidence_level": "static_workflow_only",
        "endpoint_status": "unobserved",
        "endpoint_eligible": task.get("endpoint_eligible", True),
        "failure_class": failure_class,
        "contract_violations_detected": contract_violations,
        "checker_warnings": sem_result.warnings,
        "ground_truth_checks": checks,
        "false_positive_changes": false_positives,
        "ambiguity": ambiguity,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--task", required=True, help="path to a task definition JSON")
    parser.add_argument("--submission", required=True, help="path to a workflow artifact JSON")
    parser.add_argument("--library", default=None, help="optional path to a contract library JSON")
    parser.add_argument("--out", default=None, help="optional path to write the verdict JSON")
    args = parser.parse_args(argv)

    task = load_json(args.task)
    submission = load_json(args.submission)
    library = SemanticContractLibrary.load(args.library) if args.library else None

    verdict = adjudicate(task, submission, library=library)
    rendered = json.dumps(verdict, indent=2)
    if args.out:
        Path(args.out).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
