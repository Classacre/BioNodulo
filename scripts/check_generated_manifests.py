#!/usr/bin/env python
"""Check generated node files against the manifest that produced them.

Why this exists: regenerating a family overwrites files in place, and a change to
the generator can silently alter them. On 2026-09-28 a template edit renamed every
node (``seqfu_head`` became ``head``) and nothing caught it, because a regenerated
file has no previous version to diff against. Hash comparison only works if you
thought to record hashes first.

The manifest does record the contract: ``flags_exposed``, ``required_flags`` and the
help-page SHA. This compares the node module on disk to its manifest record, so a
silent rename or a dropped parameter fails loudly.

Usage:
    python scripts/check_generated_manifests.py reports/node-expansion
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# family directory -> manifest file, for the generated families.
FAMILY_MANIFESTS = {
    "csvtk_family": "csvtk-generated.json",
    "seqkit_family": "seqkit-generated.json",
    "seqfu_family": "seqfu-generated.json",
    "emboss_family": "emboss-generated.json",
    "unikmer_family": "unikmer-generated.json",
    "taxonkit_family": "taxonkit-generated.json",
    "vcflib_family": "vcflib-generated.json",
}
PACKAGE = "bionodulo.nodes.builtin"
# Scalar flag types. Anything else a node declares (FILE, FASTA, SEQUENCE,
# DIRECTORY, LIST variants) is a data port, not a command-line flag, so it never
# appears in a manifest's flag list.
FLAG_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN"}


def is_generator_port(name: str, decl) -> bool:
    """True for a port the generator injects rather than one the tool declares.

    Only the tabular delimiter qualifies, and it is recognised by its own shape:
    ``options ["tab", "comma"]`` with default ``"tab"``. Matching on the name alone
    wrongly excluded EMBOSS ``infoseq``, whose ACD file declares a real ``delimiter``
    parameter with default ``|``.
    """
    if name in ("output", "output_dir"):
        return True
    if name == "delimiter" and isinstance(decl, tuple) and len(decl) > 1 \
            and isinstance(decl[1], dict):
        return decl[1].get("options") == ["tab", "comma"]
    return False


def declared_parameters(node_cls) -> list[str]:
    spec = node_cls.INPUT_TYPES()
    names: list[str] = []
    for section in ("required", "optional"):
        for name, decl in (spec.get(section, {}) or {}).items():
            if is_generator_port(name, decl):
                continue
            declared = decl[0] if isinstance(decl, (list, tuple)) and decl else decl
            if isinstance(declared, (list, tuple)):
                continue  # a port accepting several types is a data port
            if str(declared).upper() not in FLAG_TYPES:
                continue
            names.append(name)
    return names


def expected_parameters(record: dict) -> list[str] | None:
    """Read the parameter list out of whichever manifest schema produced it.

    The cobra generator writes ``flags_exposed``; the ACD generator behind the
    EMBOSS family writes ``tunable_params`` and ``required_params`` instead. Return
    None when a record carries neither, so the caller reports it as unverifiable
    rather than as a mismatch.
    """
    if "flags_exposed" in record:
        names = [str(name) for name in record["flags_exposed"]]
    elif "tunable_params" in record or "required_params" in record:
        # The ACD schema lists file declarations alongside real flags, in
        # required_params. It also lists the file ports and the graph outputs
        # separately, so subtract them. Graph outputs are not tunable parameters:
        # the generated node drives them through its own -graph/-goutfile pair.
        ports = {str(p) for p in record.get("input_files", [])} | \
            {str(p) for p in record.get("output_files", [])} | \
            {str(p) for p in record.get("graphs", [])}
        names = [str(name) for name in
                 list(record.get("tunable_params", [])) +
                 list(record.get("required_params", []))
                 if str(name) not in ports]
    else:
        return None
    # The flag the node uses to name its output is consumed by the output mechanism
    # rather than exposed as a parameter, so it is not expected in INPUT_TYPES. The
    # same goes for a flag promoted to the node's input port.
    consumed = {str(record.get("output_flag") or ""), str(record.get("input_flag") or "")}
    consumed = {name.lstrip("-").replace("-", "_") for name in consumed if name.strip("-")}
    if consumed:
        names = [name for name in names if name.replace("-", "_") not in consumed]
    # A tool flag whose name collides with one of the generator's own ports is
    # renamed in the node; the manifest records the mapping.
    renamed = {str(k): str(v) for k, v in (record.get("flags_renamed") or {}).items()}
    return [renamed.get(name, name).replace("-", "_") for name in names]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest_dir", type=Path)
    args = parser.parse_args()

    problems: list[str] = []
    unverifiable: list[str] = []
    checked = 0
    for family, filename in sorted(FAMILY_MANIFESTS.items()):
        path = args.manifest_dir / filename
        if not path.is_file():
            problems.append(f"missing family manifest: {path}")
            continue
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for record in manifest.get("records", []):
            if record.get("status") != "generated":
                continue
            node_id = record["node_id"]
            module = f"{PACKAGE}.{family}.{node_id}"
            try:
                imported = importlib.import_module(module)
            except ModuleNotFoundError:
                problems.append(f"{node_id}: manifest lists it but {module} does not exist")
                continue
            # One node class per module, named after the module.
            classes = [obj for name, obj in vars(imported).items()
                       if isinstance(obj, type) and obj.__module__ == module
                       and hasattr(obj, "NODE_ID")]
            if len(classes) != 1:
                problems.append(f"{node_id}: module defines {len(classes)} node classes")
                continue
            node_cls = classes[0]
            checked += 1
            if node_cls.NODE_ID != node_id:
                problems.append(
                    f"{node_id}: NODE_ID on disk is {node_cls.NODE_ID!r} "
                    f"(manifest says {node_id!r})")
            expected = expected_parameters(record)
            if expected is None:
                unverifiable.append(node_id)
                problems.append(f"{node_id}: manifest has no parameter contract to verify")
                continue
            actual = declared_parameters(node_cls)
            missing = [n for n in expected if n not in actual]
            extra = [n for n in actual if n not in expected]
            if missing:
                problems.append(f"{node_id}: parameters missing vs manifest: {missing}")
            if extra:
                problems.append(f"{node_id}: parameters not in manifest: {extra}")

    print(f"checked {checked} generated nodes against their manifests")
    if checked == 0:
        problems.append("no generated nodes were checked")
    if unverifiable:
        print(f"{len(unverifiable)} node(s) had no parameter list in the manifest "
              f"(not verifiable this way): {unverifiable[:8]}")
    if problems:
        print(f"{len(problems)} problem(s):")
        for problem in problems[:60]:
            print(f"  {problem}")
        return 1
    print("all generated nodes agree with their manifests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
