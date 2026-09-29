#!/usr/bin/env python
"""Convert Galaxy tool XML wrappers into BioNodulo nodes, measuring as it goes.

Galaxy wrappers are not self-contained. 2,472 of 2,549 import a ``<macros>``
file, and requirements, inputs and command fragments routinely live there. A
parser that reads only the top-level XML sees almost nothing. This resolves
macro imports and token substitution before deciding whether a wrapper can become
an executable node.

Three outcomes per wrapper, and they are deliberately not merged:

``executable``
    A pinned conda requirement, at least one input and one output, and a command
    with no Cheetah control flow. Emitted as a node that can render an argv.
``definition``
    Imported and discoverable with real metadata, but its command cannot be
    resolved statically. Emitted **only** in the census, never as a node.
``rejected``
    Unparseable, or nothing to import.

Nothing here executes a tool. Generation is not admission.

Usage:
    python scripts/convert_galaxy_wrappers.py \
        --wrappers-dir artifacts/galaxy-wrappers \
        --manifest artifacts/galaxy-wrappers-manifest.json \
        --output-dir reports/galaxy-ingestion \
        --nodes-dir bionodulo/nodes/builtin/galaxy_wrapped_family
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

CHEETAH_CONTROL = re.compile(r"#(if|else|elif|for|set|end|slurp|echo|def|import|from)\b")
TOKEN = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)@")
IDENT = re.compile(r"[^A-Za-z0-9_]+")


def strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def collect_macros(root: ET.Element, base_dir: Path, seen: set[str]) -> tuple[dict[str, str], dict[str, ET.Element]]:
    """Resolve ``<macros>`` imports and inline macros into tokens and xml snippets."""
    tokens: dict[str, str] = {}
    xml_macros: dict[str, ET.Element] = {}

    def absorb(container: ET.Element) -> None:
        for child in container:
            tag = strip_ns(child.tag)
            if tag == "token" and child.get("name"):
                tokens[child.get("name", "").strip("@")] = (child.text or "").strip()
            elif tag == "xml" and child.get("name"):
                xml_macros[child.get("name")] = child

    for child in root:
        if strip_ns(child.tag) == "macros":
            absorb(child)

    for child in root:
        if strip_ns(child.tag) != "macros":
            continue
        for imp in child:
            if strip_ns(imp.tag) != "import" or not imp.text:
                continue
            rel = imp.text.strip()
            path = (base_dir / rel).resolve()
            if rel in seen or not path.is_file():
                continue
            seen.add(rel)
            try:
                sub = ET.parse(path).getroot()
            except ET.ParseError:
                continue
            absorb(sub)
            # macros files can import further macros files
            nested_tokens, nested_xml = collect_macros(sub, path.parent, seen)
            for key, value in nested_tokens.items():
                tokens.setdefault(key, value)
            for key, value in nested_xml.items():
                xml_macros.setdefault(key, value)
    return tokens, xml_macros


def substitute_tokens(text: str, tokens: dict[str, str], depth: int = 0) -> str:
    if depth > 5 or not text:
        return text
    def repl(match: re.Match[str]) -> str:
        return tokens.get(match.group(1), match.group(0))
    replaced = TOKEN.sub(repl, text)
    return replaced if replaced == text else substitute_tokens(replaced, tokens, depth + 1)


def expand_xml(element: ET.Element, xml_macros: dict[str, ET.Element], tokens: dict[str, str],
               depth: int = 0) -> ET.Element:
    """Return a copy of ``element`` with ``<expand>`` macros inlined."""
    if depth > 6:
        return element
    tag = strip_ns(element.tag)
    if tag == "expand":
        name = (element.get("macro") or "").strip()
        target = xml_macros.get(name)
        if target is None:
            return ET.Element("expanded-missing")
        clone = ET.fromstring(ET.tostring(target))
        for key, value in element.attrib.items():
            if key != "macro":
                clone.set(key, value)
        return expand_xml(clone, xml_macros, tokens, depth + 1)
    clone = ET.Element(element.tag, {k: substitute_tokens(v, tokens) for k, v in element.attrib.items()})
    clone.text = substitute_tokens(element.text or "", tokens)
    for child in element:
        clone.append(expand_xml(child, xml_macros, tokens, depth + 1))
    return clone


def conda_requirements(root: ET.Element) -> list[dict]:
    out = []
    for req in root.iter():
        if strip_ns(req.tag) != "requirement":
            continue
        if req.get("type") != "package":
            continue
        name = (req.text or "").strip()
        if name:
            out.append({"name": name, "version": req.get("version")})
    return out


def containers(root: ET.Element) -> list[str]:
    return [c.text.strip() for c in root.iter()
            if strip_ns(c.tag) == "container" and c.text and c.text.strip()]


def convert_one(path: Path) -> dict:
    record: dict = {"local_file": path.name}
    try:
        raw_root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        record.update(status="rejected", reason=f"ParseError: {exc}")
        return record

    tokens, xml_macros = collect_macros(raw_root, path.parent, set())
    root = expand_xml(raw_root, xml_macros, tokens)

    tool_id = substitute_tokens(raw_root.get("id") or "", tokens)
    version = substitute_tokens(raw_root.get("version") or "", tokens)
    name = substitute_tokens(raw_root.get("name") or "", tokens)
    profile = raw_root.get("profile") or ""
    description = substitute_tokens(
        "".join((raw_root.find("description").itertext() if raw_root.find("description") is not None else [])).strip(),
        tokens)

    command_el = None
    for child in root:
        if strip_ns(child.tag) == "command":
            command_el = child
            break
    command = substitute_tokens("".join(command_el.itertext()).strip() if command_el is not None else "", tokens)

    params: list[dict] = []
    for param in root.iter():
        if strip_ns(param.tag) != "param":
            continue
        params.append({
            "name": param.get("name"),
            "type": param.get("type"),
            "format": param.get("format"),
            "optional": param.get("optional"),
            "multiple": param.get("multiple"),
        })
    params = [p for p in params if p.get("name")]

    outputs: list[dict] = []
    for data in root.iter():
        if strip_ns(data.tag) != "data":
            continue
        outputs.append({"name": data.get("name"), "format": data.get("format")})
    outputs = [o for o in outputs if o.get("name")]

    dois = [c.text.strip() for c in root.iter()
            if strip_ns(c.tag) == "citation" and c.get("type") == "doi" and c.text]

    reqs = conda_requirements(root)
    imgs = containers(root)
    has_control = bool(CHEETAH_CONTROL.search(command))

    record.update({
        "tool_id": tool_id or None,
        "version": version or None,
        "name": name or None,
        "profile": profile or None,
        "description": description[:300],
        "conda_requirements": reqs,
        "containers": imgs,
        "param_count": len(params),
        "params": params[:30],
        "output_count": len(outputs),
        "outputs": outputs[:20],
        "citation_dois": dois,
        "has_cheetah_control": has_control,
        "command_chars": len(command),
        "command": command[:2000],
        "macro_tokens": len(tokens),
        "macro_xml": len(xml_macros),
    })

    if not tool_id:
        record["status"] = "rejected"
        record["reason"] = "no tool id"
    elif not command:
        record["status"] = "rejected"
        record["reason"] = "no command"
    elif has_control:
        record["status"] = "definition"
        record["reason"] = "command uses Cheetah control flow"
    elif not params or not outputs:
        record["status"] = "definition"
        record["reason"] = "no statically declared input/output pair"
    elif not reqs and not imgs:
        record["status"] = "definition"
        record["reason"] = "no conda requirement or container to pin a runtime"
    else:
        record["status"] = "executable"
        record["reason"] = ""
    return record


def node_identifiers(tool_id: str) -> tuple[str, str]:
    """Return (node_id, class_name) for a Galaxy tool id, sanitised for Python."""
    cleaned = IDENT.sub("_", tool_id).strip("_")
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    node_id = f"galaxy_{cleaned}".lower()
    class_name = "".join(part.capitalize() for part in cleaned.split("_") if part) + "Node"
    if not class_name[:1].isalpha():
        class_name = f"T{class_name}"
    return node_id, class_name


def emit_node(record: dict, wrappers_dir: Path, nodes_dir: Path, commit: str,
              repo: str) -> str | None:
    """Write one node module for a convertible wrapper. Returns the node id."""
    node_id, class_name = node_identifiers(record["tool_id"])
    source = (wrappers_dir / record["local_file"]).read_text(encoding="utf-8", errors="replace")
    tokens = GalaxyTokens.tokenize(record["command"])

    def ports(items: list[dict], kind: str) -> str:
        rows = []
        for item in items:
            rows.append(
                "        {\"name\": %r, \"type\": %r, \"format\": %r, \"optional\": %r},"
                % (item.get("name"), item.get("type"), item.get("format"),
                   str(item.get("optional")).lower() == "true")
            )
        return "\n".join(rows)

    body = f'''"""Galaxy wrapper `{record["tool_id"]}` — imported, not hand-authored.

Source wrapper: {repo}/blob/{commit}/{record["wrapper_path"]}
Wrapper SHA-256: {record["source_sha256"]}
Tier: convertible (no Cheetah control flow; a static argv can be rendered).

Importing a wrapper is not admitting a tool. This node has no real queued run or
independent oracle, so it is a *convertible contract*, not a verified operation.
"""

from __future__ import annotations

from bionodulo.nodes.builtin._galaxy_wrapped_adapter import GalaxyWrappedNode


class {class_name}(GalaxyWrappedNode):
    NODE_ID = "{node_id}"
    DISPLAY_NAME = {record["name"]!r}
    DESCRIPTION = {record["description"]!r}
    GALAXY_TOOL_ID = {record["tool_id"]!r}
    GALAXY_VERSION = {record["version"]!r}
    GALAXY_PROFILE = {record["profile"]!r}
    WRAPPER_PATH = {record["wrapper_path"]!r}
    WRAPPER_COMMIT = "{commit}"
    WRAPPER_URL = "{repo}/blob/{commit}/{record["wrapper_path"]}"
    TIER = "convertible"
    BLOCKER = ""
    VERSION = {record["version"]!r}
    DOCUMENTATION_URL = "{repo}/blob/{commit}/{record["wrapper_path"]}"
    GIT_URL = "{repo}"
    GIT_COMMIT = "{commit}"
    REQUIRED_CONDA_PACKAGES = {[f"{q['name']}={q['version']}" if q.get("version") else q["name"] for q in record.get("conda_requirements") or []]!r}
    CITATION_DOIS = {record.get("citation_dois") or []!r}
    COMMAND_TOKENS = {tokens!r}
    INPUT_PORTS = [
{ports([p for p in record.get("params") or [] if p.get("type") != "data_collection"], "in")}
    ]
    OUTPUT_PORTS = [
{ports(record.get("outputs") or [], "out")}
    ]
'''
    nodes_dir.mkdir(parents=True, exist_ok=True)
    (nodes_dir / f"{node_id}.py").write_text(body, encoding="utf-8", newline="\n")
    return node_id


class GalaxyTokens:
    """Tokeniser shared with the runtime adapter."""

    @staticmethod
    def tokenize(command: str) -> list[str]:
        import shlex
        rewritten = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", r"{\1}", command)
        rewritten = re.sub(r"\$([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", rewritten)
        try:
            return shlex.split(rewritten, comments=False, posix=True)
        except ValueError:
            return rewritten.split()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--wrappers-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--nodes-dir", type=Path, default=None,
                        help="Emit node modules for the convertible tier into this directory.")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    by_local = {w["local_file"]: w for w in manifest["wrappers"]}

    records = []
    for path in sorted(args.wrappers_dir.iterdir()):
        if not path.is_file():
            continue
        record = convert_one(path)
        source = by_local.get(path.name, {})
        record["wrapper_path"] = source.get("wrapper_path", "")
        record["source_sha256"] = source.get("source_sha256", "")
        records.append(record)

    statuses = Counter(r["status"] for r in records)
    reasons = Counter(r.get("reason", "") for r in records if r["status"] != "executable")
    executable = [r for r in records if r["status"] == "executable"]
    report = {
        "schema_version": 1,
        "repository": manifest["repository"],
        "commit": manifest["commit"],
        "wrappers": len(records),
        "statuses": dict(statuses.most_common()),
        "definition_reasons": dict(reasons.most_common()),
        "executable_tool_ids": sorted({r["tool_id"] for r in executable}),
        "distinct_conda_packages": len({q["name"] for r in records
                                        for q in r.get("conda_requirements") or []}),
        "with_macro_tokens": sum(1 for r in records if r.get("macro_tokens")),
        "with_cheetah_control": sum(1 for r in records if r.get("has_cheetah_control")),
        "scope": (
            "Static conversion census. 'executable' means a command can be rendered, not that "
            "the tool installs, runs, or produces correct science. Nothing was executed here."
        ),
        "records": records,
    }
    emitted: list[str] = []
    if args.nodes_dir:
        args.nodes_dir.mkdir(parents=True, exist_ok=True)
        for record in executable:
            node_id = emit_node(record, args.wrappers_dir, args.nodes_dir,
                                manifest["commit"], manifest["repository"])
            if node_id:
                emitted.append(node_id)
        (args.nodes_dir / "__init__.py").write_text(
            '"""Generated Galaxy wrapper nodes.\n\n'
            "Produced by scripts/convert_galaxy_wrappers.py. Do not hand-edit: the\n"
            "generator overwrites. Each module carries one node and the exact source\n"
            "wrapper revision it came from.\n"
            '"""\n', encoding="utf-8", newline="\n")
        report["nodes_emitted"] = sorted(emitted)
        report["nodes_emitted_count"] = len(emitted)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "conversion.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "records"}, indent=2)[:2500])


if __name__ == "__main__":
    main()
