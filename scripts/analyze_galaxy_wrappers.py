#!/usr/bin/env python
"""Analyse Galaxy tool XML wrappers and classify how far each can be converted.

Galaxy wrappers are not all equally convertible. Some declare a simple argv with
a pinned container; others are Cheetah programs with conditionals, loops and
shell pipelines. This reports the honest tier breakdown *before* any node is
generated, so the count that follows can be defended.

Tiers:

``convertible``
    Has a container, at least one input and one output, and a command whose
    executable form can be derived without evaluating conditionals.
``conditional``
    Command contains Cheetah branching/looping, so the argv depends on runtime
    parameter values. The static parts are still recoverable.
``no_container``
    No ``<container>``; the runtime would have to be resolved from conda
    requirements or left unbound.
``no_command``
    No ``<command>`` element at all.

Nothing here executes anything. It is a source-shape census.

Usage:
    python scripts/analyze_galaxy_wrappers.py \
        --wrappers-dir artifacts/galaxy-wrappers \
        --manifest artifacts/galaxy-wrappers-manifest.json \
        --output reports/galaxy-ingestion/wrapper-analysis.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

# Cheetah control flow. Presence means the argv depends on parameter values.
CHEETAH_CONTROL = re.compile(r"#(if|else|elif|for|set|end|slurp|echo|def|import|from)\b")
CHEETAH_VAR = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_.]*\}?")
SHELL_OPERATORS = re.compile(r"(\|\||&&|[|<>]|\$\()")


def text_of(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def analyze_one(path: Path) -> dict:
    record: dict = {"local_file": path.name, "parsed": False}
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        record["error"] = f"ParseError: {exc}"
        return record
    record["parsed"] = True
    record["tool_id"] = root.get("id")
    record["version"] = root.get("version")
    record["name"] = root.get("name")
    record["description"] = text_of(root.find("description"))[:200]
    record["profile"] = root.get("profile")

    # Container / requirements
    containers = []
    for container in root.iter("container"):
        if container.text and container.text.strip():
            containers.append({"type": container.get("type", "docker"), "image": container.text.strip()})
    record["containers"] = containers
    requirements = [
        {"type": r.get("type"), "version": r.get("version"), "name": (r.text or "").strip()}
        for r in root.iter("requirement")
    ]
    record["requirements"] = requirements

    # Command shape
    command_el = root.find("command")
    command = text_of(command_el)
    record["command_chars"] = len(command)
    record["detect_errors"] = command_el.get("detect_errors") if command_el is not None else None
    record["has_cheetah_control"] = bool(CHEETAH_CONTROL.search(command))
    record["has_cheetah_var"] = bool(CHEETAH_VAR.search(command))
    record["has_shell_operators"] = bool(SHELL_OPERATORS.search(command))
    record["is_stdlib_python"] = bool(re.match(r"^\s*python\S*\s+\S+\.py\b", command))
    record["is_rscript"] = bool(re.match(r"^\s*Rscript\b", command))
    record["is_shell_script"] = bool(re.search(r"\.sh\b", command[:200]))

    # Inputs / outputs
    inputs = root.find("inputs")
    params: list[dict] = []
    if inputs is not None:
        for param in inputs.iter("param"):
            params.append({
                "name": param.get("name"),
                "type": param.get("type"),
                "format": param.get("format"),
                "optional": param.get("optional"),
                "multiple": param.get("multiple"),
            })
    record["param_count"] = len(params)
    record["params"] = params[:40]
    outputs = root.find("outputs")
    data_outputs = []
    if outputs is not None:
        for data in outputs.iter("data"):
            data_outputs.append({
                "name": data.get("name"),
                "format": data.get("format"),
                "from_work_dir": data.get("from_work_dir"),
            })
    record["output_count"] = len(data_outputs)
    record["outputs"] = data_outputs[:20]

    # Citations and tests
    dois = []
    for citation in root.iter("citation"):
        if citation.get("type") == "doi" and citation.text:
            dois.append(citation.text.strip())
    record["citation_dois"] = dois
    record["has_tests"] = root.find("tests") is not None
    tests = root.find("tests")
    record["test_count"] = len(list(tests.iter("test"))) if tests is not None else 0

    # Tier
    if not command:
        record["tier"] = "no_command"
    elif not containers:
        record["tier"] = "no_container"
    elif record["has_cheetah_control"]:
        record["tier"] = "conditional"
    elif not params or not data_outputs:
        record["tier"] = "no_io"
    else:
        record["tier"] = "convertible"
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--wrappers-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    by_local = {w["local_file"]: w["wrapper_path"] for w in manifest["wrappers"]}

    records = []
    for path in sorted(args.wrappers_dir.iterdir()):
        if not path.is_file():
            continue
        record = analyze_one(path)
        record["wrapper_path"] = by_local.get(path.name, "")
        records.append(record)

    tiers = Counter(r.get("tier", "unparsed") for r in records)
    report = {
        "schema_version": 1,
        "repository": manifest["repository"],
        "commit": manifest["commit"],
        "wrappers_extracted": manifest["extracted"],
        "analyzed": len(records),
        "tiers": dict(tiers.most_common()),
        "with_container": sum(1 for r in records if r.get("containers")),
        "with_tests": sum(1 for r in records if r.get("has_tests")),
        "with_citations": sum(1 for r in records if r.get("citation_dois")),
        "with_cheetah_control": sum(1 for r in records if r.get("has_cheetah_control")),
        "distinct_containers": len({c["image"] for r in records for c in r.get("containers") or []}),
        "convertible_tool_ids": sorted({r["tool_id"] for r in records
                                        if r.get("tier") == "convertible" and r.get("tool_id")}),
        "scope": (
            "Source-shape census only. A tier is a statement about what the wrapper declares, "
            "not evidence that the tool installs, runs, or produces correct science."
        ),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "records"}, indent=2)[:2000])


if __name__ == "__main__":
    main()
