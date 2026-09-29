#!/usr/bin/env python
"""Generate EMBOSS nodes from the suite's own ACD parameter definitions.

EMBOSS ships one ACD file per program describing, in a formal grammar:

* the program's documentation string and functional group,
* every input and output parameter with its type, required flag, default,
  minimum/maximum and human description,
* **EDAM relations** (topic / operation / data) chosen by the EMBOSS authors.

That makes the ACD the authoritative source for exactly the four things an
admission needs — documentation, inputs, modifiable parameters, outputs — plus
verified ontology annotations. Nothing here is inferred from a name or a README.

The ACD is read from a digest-pinned container, so the parameter set is tied to
the same ``emboss==6.6.0`` build the nodes declare.

Generation is not admission. A generated node renders a command; it is not
evidence that the command installs, runs, or produces correct science. Only a
real queued run with an independent oracle establishes that.

Usage:
    python scripts/generate_emboss_nodes.py \
        --acd-dir artifacts/emboss-acd \
        --nodes-dir bionodulo/nodes/builtin/emboss_family \
        --manifest reports/node-expansion/emboss-generated.json \
        --snapshot reports/biotools_registry/current/registry.jsonl
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re

# ACD parameter types that consume a file path the caller must supply.
# ``outfile`` deliberately does NOT appear here: it is an output kind, and
# listing it as an input made needle, water and seqmatchall look output-less.
INPUT_FILE_TYPES = {
    "seqall", "sequence", "infile", "infilelist", "feat", "featin", "align",
    "codon", "regexp", "inseq", "inseqall", "seqin", "datafile", "dirlist",
    "filelist", "aadata", "mwdata", "protofile", "matrix", "matrixf",
    "translation", "taxon", "discrete", "seqset", "seqsetall",
    "seqallset", "patterns", "words",
}
# Output kinds are not a fixed list. EMBOSS names them by role, so the reliable
# rule is the ``out`` substring (``outseq``, ``outfile``, ``seqoutall``,
# ``outfeat``, ``outfiledata``) plus a few roles that do not contain it. Missing
# ``seqoutall`` is what made seqret and getorf look output-less.
OUTPUT_KIND_HINT = "out"
# ``matrix`` is deliberately absent: EMBOSS uses it for the *scoring matrix input*
# (dotmatcher, prettyplot, showalign), so it must be decided by the section rather
# than treated as an output kind.
EXTRA_OUTPUT_KINDS = {"report", "outtree", "tree", "graph",
                      "graphdata", "xygraph", "barplot", "dotplot", "plot"}
# Types that become a visualisation artifact rather than a data file.
GRAPH_TYPES = {"graph", "graphdata", "xygraph", "barplot", "dotplot", "plot"}
INTEGER_TYPES = {"integer"}
FLOAT_TYPES = {"float"}
BOOLEAN_TYPES = {"boolean"}
LIST_TYPES = {"list", "select", "toggle"}
STRING_TYPES = {"string", "range", "array", "text", "discrete"}

EDAM = re.compile(r"EDAM_(topic|operation|data|format|identifier):(\d+)\s*(.*)")
# Present in every file this generator writes, and in no hand-written node. Used
# to tell the two apart so a re-run refreshes its own output instead of skipping
# it as hand-authored.
GENERATED_MARKER = "Generated from the suite's own ACD definition"
KEY_LINE = re.compile(r"^([a-z_]+):\s*(.*)$")
BLOCK_OPEN = re.compile(r"^([a-z_]+):\s*([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*$")
SECTION_OPEN = re.compile(r"^section:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*$")
SPLIT_BLOCK_NAME = re.compile(r"^[a-z_]+:\s*[A-Za-z_][A-Za-z0-9_]*\s*$")
# The corrected parser discovers file inputs in these previously skipped ACDs.
# Keep the established catalog scope until each new command contract is reviewed;
# inforesidue is already generated and is repaired in this change.
PENDING_SPLIT_BLOCK_REVIEW = {
    "aligncopy", "aligncopypair", "nohtml", "nospace", "notab",
    "seqxref", "seqxrefget", "sizeseq", "skipredundant", "trimspace",
}


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def parse_acd(text: str) -> dict:
    """Parse one ACD file into a program record."""
    lines = text.splitlines()
    program = {"documentation": "", "groups": "", "edam": [], "params": []}
    stack: list[tuple[str, str, dict]] = []  # (kind, name, attrs)
    index = 0

    while index < len(lines):
        raw = lines[index]
        line = raw.strip()
        index += 1
        if not line or line.startswith("#"):
            continue

        # Some shipped ACDs put the opening bracket on the following line for
        # applications, sections, and parameters. Join that declaration before
        # classifying it; otherwise inforesidue loses its description, required
        # code, and outfile despite all three being present in the source.
        if SPLIT_BLOCK_NAME.match(line):
            lookahead = index
            while lookahead < len(lines) and not lines[lookahead].strip():
                lookahead += 1
            if lookahead < len(lines) and lines[lookahead].strip() == "[":
                line += " ["
                index = lookahead + 1

        if line == "]" or line.startswith("]"):
            if stack:
                kind, name, attrs = stack.pop()
                if kind == "param":
                    attrs["name"] = name
                    program["params"].append(attrs)
                elif kind == "application":
                    program.update({k: v for k, v in attrs.items() if k != "params"})
            continue

        section = SECTION_OPEN.match(line)
        if section:
            # An ACD section is NOT a bracketed block. ``section: name [ ... ]``
            # holds only the section's attributes; the parameters follow after
            # that closing bracket and run until ``endsection: name``. Pushing a
            # frame for the attribute block keeps the section on the stack, which
            # is what makes the enclosing section visible to each parameter.
            name = section.group(1)
            stack.append(("section", name, {}))
            stack.append(("section_attrs", name, {}))
            continue
        if line.startswith("endsection:"):
            while stack:
                kind, _name, _attrs = stack.pop()
                if kind == "section":
                    break
            continue

        block = BLOCK_OPEN.match(line)
        if block:
            kind, name = block.group(1), block.group(2)
            if kind == "application":
                stack.append(("application", name, {}))
            else:
                # The declaration kind IS the datatype (``seqall``, ``outseq``,
                # ``integer``, ...). The ``type:`` key inside the block is a
                # sub-type hint such as ``gapany`` and must not be used to
                # classify the parameter. The enclosing section is also recorded:
                # EMBOSS reuses ``align`` and ``sequence`` for both input and
                # output roles, so the section is the only reliable disambiguator.
                section = next((n for k, n, _ in reversed(stack) if k == "section"), "")
                stack.append(("param", name, {"_kind": kind, "_section": section}))
            continue

        match = KEY_LINE.match(line)
        if not match or not stack:
            continue
        key, value = match.group(1), match.group(2)

        # ACD values may be quoted strings spanning several lines.
        if value.startswith('"') and not (len(value) > 1 and value.endswith('"')):
            while index < len(lines):
                value += " " + lines[index].strip()
                index += 1
                if value.rstrip().endswith('"'):
                    break
        value = strip_quotes(re.sub(r"\s+", " ", value))

        kind, _name, attrs = stack[-1]
        if kind == "application":
            if key in ("documentation", "groups"):
                attrs[key] = (attrs.get(key, "") + " " + value).strip()
            elif key == "relations":
                attrs.setdefault("edam", []).append(value)
        else:
            if key == "relations":
                attrs.setdefault("edam", []).append(value)
            else:
                attrs[key] = value

    return program


def edam_buckets(entries: list[str]) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {"topic": [], "operation": [], "data": []}
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        for kind, number, label in EDAM.findall(entry):
            label = label.strip()
            if kind not in out or not label:
                continue
            key = (kind, number)
            if key in seen:
                continue
            seen.add(key)
            out[kind].append({"uri": f"http://edamontology.org/{kind}_{number}", "label": label})
    return out


def classify(param: dict) -> str:
    """Classify by ACD declaration kind, disambiguated by enclosing section.

    Scalar kinds are tunables wherever they appear. For file-like roles the
    section decides, because EMBOSS reuses the same kind (``align``, ``sequence``)
    for both an input and an output: ``water`` declares its alignment output as
    ``align: outfile`` inside ``section: output``, which a kind-only rule
    misreads as an input.
    """
    kind = param.get("_kind", "")
    section = param.get("_section", "")
    if kind in INTEGER_TYPES:
        return "integer"
    if kind in FLOAT_TYPES:
        return "float"
    if kind in BOOLEAN_TYPES:
        return "boolean"
    if kind in LIST_TYPES:
        return "list"
    if kind in STRING_TYPES:
        return "string"
    if kind in GRAPH_TYPES:
        return "graph"
    if section == "output" or OUTPUT_KIND_HINT in kind or kind in EXTRA_OUTPUT_KINDS:
        return "output_file"
    if kind in INPUT_FILE_TYPES or kind.endswith("in"):
        return "input_file"
    # An unrecognised kind is treated as a scalar rather than dropped. Returning
    # "other" silently discarded required parameters such as fuzznuc's ``-pattern``,
    # and a node that omits a required qualifier fails inside the tool with a
    # confusing message instead of failing validation up front.
    return "string"


def frontend_type(kind: str, param: dict) -> tuple[str, dict]:
    if kind == "input_file":
        return "FILE", {}
    if kind == "integer":
        meta: dict = {}
        if param.get("minimum"):
            try:
                meta["min"] = int(float(param["minimum"]))
            except ValueError:
                pass
        if param.get("maximum"):
            try:
                meta["max"] = int(float(param["maximum"]))
            except ValueError:
                pass
        return "INT", meta
    if kind == "float":
        return "FLOAT", {}
    if kind == "boolean":
        return "BOOLEAN", {}
    if kind == "list":
        options = []
        for item in (param.get("values") or "").split(";"):
            if ":" in item:
                options.append(item.split(":", 1)[0].strip())
        meta = {"options": options} if options else {}
        return "STRING", meta
    return "STRING", {}


def python_literal(value) -> str:
    return repr(value)


def acd_literal_default(value: str | None, declared: str) -> object | None:
    """Return a typed literal, leaving ACD expressions to the EMBOSS runtime."""
    if value in (None, "") or "$" in value or "@" in value:
        return None
    if declared == "INT":
        try:
            number = float(value)
            return int(number) if math.isfinite(number) and number.is_integer() else None
        except ValueError:
            return None
    if declared == "FLOAT":
        try:
            number = float(value)
            return number if math.isfinite(number) else None
        except ValueError:
            return None
    if declared == "BOOLEAN":
        upper = value.upper()
        return upper in ("Y", "YES", "TRUE") if upper in (
            "Y", "YES", "TRUE", "N", "NO", "FALSE") else None
    return value


def generate(program_name: str, program: dict, existing: set[str],
             bio_accessions: set[str], source_sha: str, commit_note: str) -> tuple[str | None, dict]:
    params = program.get("params") or []
    classified = [(classify(p), p) for p in params]
    input_files = [p for k, p in classified if k == "input_file"]
    output_files = [p for k, p in classified if k == "output_file"]
    graphs = [p for k, p in classified if k == "graph"]
    tunables = [(k, p) for k, p in classified if k in
                ("integer", "float", "boolean", "list", "string")]

    node_id = f"emboss_{program_name}"
    info = {
        "program": program_name,
        "node_id": node_id,
        "documentation": program.get("documentation", ""),
        "groups": program.get("groups", ""),
        "input_files": [p["name"] for p in input_files],
        "output_files": [p["name"] for p in output_files],
        "graphs": [p["name"] for p in graphs],
        "tunable_params": [p["name"] for _, p in tunables],
        "required_params": [p["name"] for p in params if str(p.get("parameter", "")).upper() == "Y"],
        "edam": edam_buckets(program.get("edam") or []),
        "source_sha256": source_sha,
    }

    if node_id in existing:
        info["status"] = "skipped_already_handwritten"
        return None, info
    if not input_files:
        info["status"] = "skipped_no_file_input"
        return None, info
    # EMBOSS writes its report to stdout when no output qualifier is given, so a
    # program with an input and no declared output is still runnable: the executor
    # captures stdout into the planned file via STDOUT_OUTPUT_INDEX.
    stdout_only = not output_files and not graphs
    info["stdout_only"] = stdout_only

    class_name = "Emboss" + "".join(part.capitalize() for part in program_name.split("_")) + "Node"
    doc = (program.get("documentation") or "").replace('"', "'")[:300]
    tool_id = (f"https://bio.tools/{program_name}" if program_name in bio_accessions
               else "https://bio.tools/emboss")
    buckets = info["edam"]

    primary_input = input_files[0]["name"]
    # ACD distinguishes a required parameter from an additional file input.
    # Keep the primary file mandatory for the node contract, and expose every
    # other file with its declared requiredness. Previously only the primary
    # appeared in INPUT_TYPES while validation demanded every input_file.
    required_input_names = {primary_input} | {
        p["name"] for p in input_files
        if str(p.get("parameter", "")).upper() == "Y"
    }
    # Extensions matter. EMBOSS plot qualifiers are not filenames: ``-graph``
    # takes a DEVICE and the file comes from ``-goutfile <basename>``, which
    # appends a numeric suffix and the device extension, so ``-goutfile g`` with
    # ``-graph png`` yields ``g.1.png``. ACD ``standard:`` conditions mean several
    # graph params are alternatives, so only the first is wired.
    output_specs: list[tuple[str, str]] = []
    for param in output_files:
        ext = "txt" if param.get("_kind") == "report" else "out"
        output_specs.append((param["name"], ext))
    if stdout_only:
        output_specs.append(("stdout", "txt"))
    # EMBOSS plot output is unreliable across programs: ``-graph png -goutfile x``
    # yields ``x.1.png`` for banana but writes nothing at all for charge, even
    # though both exit zero. A plot is a side artifact, so it is declared as an
    # output only when the program has no other output; otherwise the report is the
    # contract and the plot is requested without being required.
    graph_name = graphs[0]["name"] if graphs else None
    if graph_name and not output_specs:
        output_specs.append((graph_name, "1.png"))
    out_names = [name for name, _ in output_specs]

    # Required/optional split, skipping the outputs which are handled by plan.
    req_lines, opt_lines = [], []
    for kind, param in tunables:
        declared, meta = frontend_type(kind, param)
        description = (param.get("information") or param["name"]).replace('"', "'")[:150]
        default = acd_literal_default(param.get("default"), declared)
        if default is not None:
            meta["default"] = default
        meta["description"] = description
        line = f'                "{param["name"]}": ({declared!r}, {meta!r}),'
        if str(param.get("parameter", "")).upper() == "Y":
            req_lines.append(line)
        else:
            opt_lines.append(line)

    knowledge_topics = buckets["topic"] or [{"uri": "http://edamontology.org/topic_0080",
                                             "label": "Sequence analysis"}]
    knowledge = [
        '    KNOWLEDGE = {',
        '        **EmbossBase.KNOWLEDGE,',
        f'        "tool_id": {tool_id!r},',
        f'        "topics": {knowledge_topics!r},',
    ]
    if buckets["operation"]:
        knowledge.append(f'        "operations": {buckets["operation"]!r},')
    knowledge.append('        "reviewed_at": "2026-09-26",')
    knowledge.append('    }')

    # Build the literal strings in Python so the f-string does not have to escape
    # braces, which is where the first version of this generator went wrong.
    filenames = tuple(f"{name}.{ext}" for name, ext in output_specs)
    # RETURN_TYPES must have one entry per output. Emitting a single ("DIRECTORY",)
    # for a multi-output node fails the linter with a length mismatch.
    return_types = repr(tuple("FILE" for _ in out_names))
    stdout_line = "    STDOUT_OUTPUT_INDEX = 0\n" if stdout_only else ""
    return_names = repr(tuple(out_names))
    output_filenames = repr(filenames)
    all_paths = repr(tuple(p["name"] for p in input_files))
    required_paths = repr(tuple(p["name"] for p in input_files
                                if p["name"] in required_input_names))
    output_flags = repr(out_names)
    for param in input_files:
        name = param["name"]
        kind = param.get("_kind", "")
        declared_type = '(("FASTA", "FILE"))' if "seq" in kind else '"FILE"'
        description = (param.get("information") or
                       ("Primary input file" if name == primary_input else "Input file"))
        line = f'                {name!r}: ({declared_type}, {{"description": {description!r}}}),'
        (req_lines if name in required_input_names else opt_lines).append(line)
    required_block = "\n".join(req_lines)
    optional_block = "\n".join(opt_lines)

    body = f'''"""EMBOSS {program_name}: {doc[:90]}.

Generated from the suite's own ACD definition for {program_name} in the pinned
emboss==6.6.0 image. ACD SHA-256: {source_sha}

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class {class_name}(EmbossBase):
    """{doc[:150]}"""

    NODE_ID = {node_id!r}
    DISPLAY_NAME = {("EMBOSS " + program_name)!r}
    CATEGORY = "emboss"
    DESCRIPTION = {doc!r}
    SEARCH_ALIASES = ["emboss", {program_name!r}]
    RETURN_TYPES = {return_types}
    RETURN_NAMES = {return_names}
    OUTPUT_FILENAMES = {output_filenames}
{stdout_line}    REQUIRED_EXECUTABLES = [{program_name!r}]
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/{program_name}.html"
    PATH_INPUTS = {all_paths}
    REQUIRED_PATH_INPUTS = {required_paths}
{chr(10).join(knowledge)}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {{
            "required": {{
{required_block}
            }},
            "optional": {{
{optional_block}
            }},
            "hidden": {{"output": ("STRING", {{}})}},
        }}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = [{program_name!r}]
        for name in cls.PATH_INPUTS:
            value = inputs.get(name)
            if value not in (None, ""):
                command.extend([f"-{{name}}", str(value)])
        output_dir = cls.output_dir(inputs)
        graph_flag = {graph_name!r}
        # A stdout-only program has no output qualifier at all; its planned file
        # is filled by the executor's stdout capture instead.
        declared: list[str] = [] if {stdout_only!r} else list({output_flags})
        for index, flag in enumerate(declared):
            if flag == graph_flag:
                command.extend([f"-{{flag}}", "png", "-goutfile", str(output_dir / flag)])
            else:
                command.extend([f"-{{flag}}", str(output_dir / cls.OUTPUT_FILENAMES[index])])
        # Request the plot even when it is not a required output, so EMBOSS does
        # not fall back to an interactive device and hang.
        if graph_flag and graph_flag not in declared:
            command.extend([f"-{{graph_flag}}", "png", "-goutfile", str(output_dir / graph_flag)])
        # Required scalar parameters must be rendered too. Emitting only the
        # optional ones silently dropped inputs like fuzznuc's ``-pattern`` and
        # made the tool fail with "Bad value for '-pattern'".
        declared_types = cls.INPUT_TYPES()
        for category in ("required", "optional"):
            for name, spec in declared_types.get(category, {{}}).items():
                if name in cls.PATH_INPUTS:
                    continue
                value = inputs.get(name)
                if value in (None, ""):
                    continue
                declared = spec[0] if isinstance(spec, (list, tuple)) else spec
                if declared == "FILE":
                    continue
                default = spec[1].get("default") if isinstance(spec, tuple) and len(spec) > 1 else None
                if declared == "BOOLEAN":
                    command.extend([f"-{{name}}", "Y" if value else "N"])
                    continue
                if value == default:
                    continue
                command.extend([f"-{{name}}", str(value)])
        # EMBOSS prompts for confirmation on some programs; -auto makes it
        # non-interactive, which is required in a batch runner.
        command.append("-auto")
        return command
'''
    info["status"] = "generated"
    return body, info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--acd-dir", type=Path, required=True)
    parser.add_argument("--nodes-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--commit", default="emboss 6.6.0")
    args = parser.parse_args()

    accessions: set[str] = set()
    with args.snapshot.open(encoding="utf-8") as handle:
        for line in handle:
            accessions.add(json.loads(line)["biotoolsID"].casefold())

    # Existing ownership must come from the real node index, not from a filename
    # glob: the hand-written EMBOSS nodes are named ``transeq.py``/``pepstats.py``
    # while generated ones are ``emboss_<program>.py``, so a glob on the generated
    # pattern silently misses them and produces two owners for one NODE_ID.
    # Files this generator wrote are recognised by their marker and are excluded,
    # so re-running can refresh them instead of skipping them as "hand-written".
    existing: set[str] = set()
    for path in args.nodes_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if GENERATED_MARKER in text:
            continue
        existing.add(path.stem)
        existing.add(f"emboss_{path.stem}")

    results = []
    for acd in sorted(args.acd_dir.glob("*.acd")):
        program_name = acd.stem
        import hashlib
        text = acd.read_text(encoding="utf-8", errors="replace")
        source_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        program = parse_acd(text)
        body, info = generate(program_name, program, existing, accessions, source_sha, args.commit)
        if program_name in PENDING_SPLIT_BLOCK_REVIEW and body:
            body = None
            info["status"] = "skipped_pending_contract_review"
            info["reason"] = (
                "The split-bracket ACD was previously unparsed; newly visible "
                "inputs and outputs require a separate command-contract review."
            )
        if body:
            (args.nodes_dir / f"emboss_{program_name}.py").write_text(body, encoding="utf-8", newline="\n")
        results.append(info)

    statuses = Counter(r["status"] for r in results)
    manifest = {
        "schema_version": 1,
        "source": "EMBOSS ACD files from quay.io/biocontainers/emboss:6.6.0--h0f19ade_14",
        "programs_seen": len(results),
        "statuses": dict(statuses.most_common()),
        "generated_node_ids": sorted(r["node_id"] for r in results if r["status"] == "generated"),
        "scope": (
            "Generated contracts from the suite's own parameter definitions. No tool was "
            "executed; no scientific result was validated. ACD parameters describe the "
            "upstream program, not this project's admission of it."
        ),
        "records": results,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "records"}, indent=2)[:2500])


if __name__ == "__main__":
    main()
