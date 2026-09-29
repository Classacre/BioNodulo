#!/usr/bin/env python
"""Generate nodes for subcommand-style CLIs from their own ``--help`` output.

Many bioinformatics tools ship one binary with dozens of subcommands (``csvtk``,
``seqkit``, ``seqfu``) and document them with Go's cobra flag tables:

    Flags:
      -w, --decimal-width int    limit floats to N decimal points (default 2)
      -f, --fields strings       operations on these fields. e.g -f 1:count,1:sum

That table is a declaration, not prose: it gives every flag's short name, long
name, value type and default. This reads it and emits one node per subcommand, the
same way ``generate_emboss_nodes.py`` reads ACD files.

The help text comes from a digest-pinned image, so the parameter set is tied to the
same build the nodes declare.

Generation is not admission. A generated node renders a command; it is not evidence
that the command installs, runs, or produces correct science.

Usage:
    python scripts/generate_subcommand_nodes.py \
        --help-dir artifacts/csvtk-help \
        --binary csvtk \
        --family bionodulo/nodes/builtin/csvtk_family \
        --manifest reports/node-expansion/csvtk-generated.json \
        --snapshot reports/biotools_registry/current/registry.jsonl
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re

GENERATED_MARKER = "Generated from the tool's own --help output"

FLAG_LINE = re.compile(
    r"^\s+(?:-(?P<short>[A-Za-z0-9]),?\s+)?--(?P<long>[A-Za-z0-9][A-Za-z0-9-]*)"
    r"(?:=(?P<eqtype>[A-Za-z][A-Za-z0-9_]*))?"
    r"(?:\s+(?P<type>[A-Za-z][A-Za-z0-9]*))?"
    r"\s{2,}(?P<desc>.*)$"
)
# Go's cobra writes "(default X)"; seqfu's Nim parser writes "[default: X]".
DEFAULT_IN_DESC = re.compile(r"(?:\(default (?P<paren>.*?)\)|\[default: (?P<bracket>[^\]]*)\])\s*$")
# Cobra sections its flags under "Flags:"; seqfu uses "Options:".
FLAG_SECTIONS = ("Flags:", "Options:")
# Flags every subcommand inherits from the root. Exposed separately or not at all,
# because they are global concerns rather than this subcommand's contract.
GLOBAL_FLAGS = {
    "help", "out-file", "out-tabs", "tabs", "delimiter", "out-delimiter",
    "comment-char", "delete-header", "ignore-empty-row", "ignore-illegal-row",
    "infile-list", "lazy-quotes", "no-header-row", "num-cpus", "quiet",
    "show-row-number", "help", "version", "verbose",
}
# How a tool names its output varies per subcommand, and the differences are not
# cosmetic. ``unikmer count`` takes ``-o/--out-prefix`` (a prefix), ``unikmer
# encode`` takes ``-o/--out-file`` (a file), ``unikmer split`` takes
# ``-O/--out-dir`` (a directory). Rendering one flag for all three produced nodes
# whose declared output file the tool never writes. Detection order prefers the
# container (``out-dir``) over the name inside it, because a tool declaring both
# (``unikmer tsplit``) writes files *into* the directory.
OUTPUT_FLAG_PRIORITY = ("out-dir", "outdir", "out-file", "out-prefix", "output", "out")

# Help tables describe flags but do not specify how positional files map to node
# ports. These exceptions are taken from the pinned help pages' Usage sections.
# A path-taking flag is reserved below so it cannot also become a string control.
INPUT_OVERRIDES = {
    ("seqfu", "amplicheck"): (("read1", "FILE", ""), ("read2", "FILE", "")),
    ("seqfu", "lanes"): (("input_dir", "DIRECTORY", ""),),
    ("seqfu", "metadata"): (("input_dir", "DIRECTORY", ""),),
    ("seqfu", "subtract"): (("file1", "FILE", ""), ("file2", "FILE", "")),
    ("seqkit", "pair"): (("read1", "FILE", "--read1"), ("read2", "FILE", "--read2")),
}
OUTPUT_OVERRIDES = {
    ("seqfu", "amplicheck"): {"kind": "dir", "flag": "--outdir"},
    ("seqfu", "lanes"): {"kind": "dir", "flag": "--outdir"},
    ("seqkit", "pair"): {"kind": "dir", "flag": "--out-dir"},
    ("seqkit", "split"): {"kind": "dir", "flag": "--out-dir"},
}
# Cobra writes `("-" for stdout)` in the flag description when a file flag accepts
# the dash. That is what makes stdout capture legal instead of an invented path.
STDOUT_MARKERS = ('"-" for stdout', "for stdout")
TYPE_MAP = {
    "int": "INT", "int32": "INT", "int64": "INT",
    "INT": "INT", "INTEGER": "INT",
    "float": "FLOAT", "float32": "FLOAT", "float64": "FLOAT",
    "FLOAT": "FLOAT", "NUM": "FLOAT", "NUMBER": "FLOAT",
    "string": "STRING", "strings": "STRING", "stringSlice": "STRING",
    "duration": "STRING", "bool": "BOOLEAN", "BOOL": "BOOLEAN",
    "MIN_SIZE": "INT", "MIN_LENGTH": "INT", "MAX_LENGTH": "INT",
    "LINE_WIDTH": "INT",
}

DESCRIPTION_OVERRIDES = {
    ("seqfu", "amplicheck"): "Inspect paired-end amplicon FASTQ files and write QC recommendations",
    ("seqfu", "derep"): "Dereplicate identical sequences and report cluster sizes",
    ("seqfu", "lanes"): "Merge Illumina FASTQ lane files into uncompressed output files",
    ("seqfu", "metadata"): "Prepare mapping files from a directory containing FASTQ files",
    ("seqfu", "tabcheck"): "Inspect TSV and CSV files for valid columns",
    ("seqfu", "trim"): "Trim and quality-filter FASTQ reads",
}


def parse_required(directory: Path) -> dict[str, list[str]]:
    """Read the empirical required-flag probe.

    Cobra does not mark required flags in its help output, so the only reliable
    source is the tool itself: run the subcommand with no flags and read
    ``flag -n (--name) needed`` from stderr, iterating because it reports one at a
    time. Probing beats guessing here — 7 of 24 sampled csvtk nodes failed purely
    because a required flag was declared optional.
    """
    required: dict[str, list[str]] = {}
    if not directory.is_dir():
        return required
    for path in sorted(directory.glob("*.txt")):
        sub = ""
        flags: list[str] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("SUB="):
                sub = line[4:].strip()
            elif line.startswith("REQUIRED="):
                flags = [token[2:] for token in line[9:].split() if token.startswith("--")]
        if sub:
            required[sub] = flags
    return required


def parse_subcommands(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def parse_help(text: str) -> dict:
    """Return {description, usage, flags: [...]} from a cobra help page."""
    lines = text.splitlines()
    description = ""
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith(("Usage:", "Flags:", "Aliases:", "Examples:")):
            description = stripped
            break

    usage = ""
    for index, line in enumerate(lines):
        if line.strip().startswith("Usage:"):
            for follow in lines[index + 1:]:
                if follow.strip():
                    usage = follow.strip()
                    break
            break

    flags: list[dict] = []
    # Do not require a known section header. cobra writes "Flags:" and seqfu writes
    # "Options:", but seqfu also groups flags under arbitrary headings such as
    # "Name and comment search:" and "Input files:". Gating on a header silently
    # dropped every flag in those groups. FLAG_LINE is specific enough to match on
    # its own, so parsing starts immediately. Flags under "Global Flags:" are still
    # parsed but tagged, because for most tools they are inherited noise (csvtk's
    # --out-file) while for a few they are the operation's whole premise (taxonkit's
    # --data-dir points at the NCBI taxonomy dump, without which nothing works).
    in_flags = True
    in_global = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Global Flags:"):
            in_flags = True
            in_global = True
            continue
        if stripped.startswith(("Use ", "Aliases:", "Examples:")):
            in_flags = False
            continue
        if stripped in FLAG_SECTIONS:
            in_flags = True
            in_global = False
            continue
        if not in_flags:
            continue
        match = FLAG_LINE.match(line)
        if match:
            desc = match.group("desc").strip()
            default = None
            found = DEFAULT_IN_DESC.search(desc)
            if found:
                default = (found.group("paren") or found.group("bracket") or "").strip().strip('"')
                desc = DEFAULT_IN_DESC.sub("", desc).strip()
            flags.append({
                "short": match.group("short"),
                "long": match.group("long"),
                "type": (match.group("eqtype") or match.group("type") or "bool").strip(),
                "description": desc[:160],
                "default": default,
                "global": in_global,
            })
        elif flags and line.startswith(" " * 20):
            # Continuation of the previous flag's description.
            flags[-1]["description"] = (flags[-1]["description"] + " " + stripped)[:200]
    return {"description": description, "usage": usage, "flags": flags}


def python_literal(value) -> str:
    return repr(value)


def detect_output(parsed: dict, fallback_flag: str, mode: str) -> dict:
    """Work out how this subcommand names its output.

    Returns ``{"kind", "flag"}`` where kind is one of:

    ``stdout``  the flag accepts ``-``, so the run writes to stdout and the
                executor captures it into the planned file
    ``file``    the flag names one output file
    ``dir``     the flag names a directory the tool fills
    ``none``    no output flag is declared; the tool writes to stdout by default
    """
    if mode == "none":
        return {"kind": "none", "flag": ""}
    if mode == "flag":
        return {"kind": "file", "flag": fallback_flag} if fallback_flag else \
            {"kind": "none", "flag": ""}
    by_long = {flag["long"]: flag for flag in parsed["flags"]}
    for name in OUTPUT_FLAG_PRIORITY:
        flag = by_long.get(name)
        if flag is None:
            continue
        accepts_stdout = any(marker in flag["description"] for marker in STDOUT_MARKERS)
        if name in ("out-dir", "outdir"):
            return {"kind": "dir", "flag": f"--{name}"}
        if name in ("out-prefix", "output-prefix"):
            # A prefix cannot be a declared filename: `-o out` writes `out.unik`, not
            # `out`. Use the dash when the tool offers it and let the executor capture
            # stdout into the planned file. When it does not, the flag still names a
            # location inside the output directory (seqfu shred writes two files,
            # `<prefix>_1.fq` and `<prefix>_2.fq`), so declare a directory rather than
            # promising a filename the tool never creates.
            return {"kind": "stdout" if accepts_stdout else "dir", "flag": f"--{name}"}
        # out-file / output name a real path. Write to it directly rather than through
        # stdout capture: fewer moving parts, and the declared file exists because the
        # tool made it. This is also what the csvtk and seqkit nodes already do.
        return {"kind": "file", "flag": f"--{name}"}
    return {"kind": "none", "flag": ""}


def build_node(binary: str, sub: str, parsed: dict, source_sha: str, commit: str,
               family_module: str, required_longs: frozenset[str] = frozenset(),
               options: dict | None = None) -> tuple[str, dict]:
    options = options or {}
    base_class = options.get("base_class", "CsvtkBase")
    input_port = options.get("input_port", "table")
    input_description = options.get("input_description", "Input table file")
    output_flag = options.get("output_flag", "--out-file")
    output = options.get("output")
    if output is None:
        output = detect_output(parsed, output_flag, options.get("output_mode", "flag"))
    output = OUTPUT_OVERRIDES.get((binary, sub), output)
    parsed = {**parsed, "description": DESCRIPTION_OVERRIDES.get(
        (binary, sub), parsed["description"])}
    documentation_url = options.get("documentation_url", "https://github.com/shenwei356/csvtk")
    tabular = options.get("tabular", True)
    # A flat family ships one binary per operation (vcflib: vcfcheck, vcf2tsv, ...)
    # rather than one binary with subcommands. ``sub`` is then empty and the binary
    # name is the operation. ``id_prefix`` groups the family in the UI without
    # changing the argv, which must stay the real binary name.
    id_prefix = options.get("id_prefix", "")
    stem = sub if sub else binary
    safe_stem = re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_").lower()
    # Subcommand families are named <binary>_<sub> (seqfu_head). Flat families, where
    # the binary is the operation, take an explicit prefix so the family still groups
    # (vcflib_ + vcfcheck). Getting this wrong silently renames every node.
    node_id = f"{id_prefix}{binary}_{safe_stem}" if sub else f"{id_prefix}{safe_stem}"
    camel = "".join(part.capitalize() for part in safe_stem.split("_"))
    if sub:
        # Unchanged for every subcommand family: csvtk + add-header -> CsvtkAddHeaderNode.
        class_name = binary.capitalize() + camel + "Node"
    else:
        prefix_camel = "".join(
            part.capitalize() for part in id_prefix.strip("_").split("_")) if id_prefix else ""
        class_name = prefix_camel + camel + "Node"

    usable: list[dict] = []
    skipped: list[str] = []
    # The detected output flag must not also be exposed as an ordinary parameter,
    # or render_command emits it twice.
    reserved = {output["flag"][2:] for _ in (0,) if output["flag"]}
    # Some tools take their input through a flag rather than a positional argument
    # (vcflib's GPAT tools all use --file). That flag becomes the node's input port,
    # so it must not also appear as a parameter, or the command names the input twice.
    input_flag = options.get("input_flag") or ""
    if input_flag:
        reserved.add(input_flag.lstrip("-"))
    input_ports = INPUT_OVERRIDES.get((binary, sub))
    if input_ports:
        reserved.update(flag.lstrip("-") for _, _, flag in input_ports if flag)
    if (binary, sub) == ("unikmer", "grep"):
        # Its default out-prefix is "-", which streams to stdout even when an
        # out-dir is supplied. Give it a basename within the planned directory.
        reserved.add("out-prefix")
    promote = options.get("promote_global") or frozenset()
    for flag in parsed["flags"]:
        if flag["long"] == "help":
            skipped.append(flag["long"])
            continue
        if flag["long"] in GLOBAL_FLAGS and flag["long"] not in promote:
            skipped.append(flag["long"])
            continue
        if flag.get("global") and flag["long"] not in promote:
            skipped.append(flag["long"])
            continue
        if flag["long"] in reserved:
            skipped.append(flag["long"])
            continue
        usable.append(flag)

    info = {
        "node_id": node_id,
        "subcommand": sub,
        "description": parsed["description"],
        "flags_total": len(parsed["flags"]),
        "flags_exposed": [f["long"] for f in usable],
        "flags_skipped_global": skipped,
        "output_kind": output["kind"],
        "output_flag": output["flag"],
        "source_sha256": source_sha,
    }

    # Every subcommand reads a positional file (or stdin). Output goes to the
    # inherited -o flag, or stdout when the subcommand has no -o of its own.
    req_lines, opt_lines = [], []
    # Flags with no long form (some vcflib GPAT tools declare `-f` only) need their
    # literal token recorded, because the default renderer would emit `--f`.
    flag_tokens: dict[str, str] = {}
    # A tool flag can be named `output`. The generator owns
    # that name for its own output-directory port, and a collision makes
    # render_command read the user's chosen file path as the run directory. Rename
    # the tool's parameter and remember the token it maps back to.
    reserved_names = {"output", "output_dir", input_port}
    renamed: dict[str, str] = {}
    for flag in usable:
        name = flag["long"].replace("-", "_")
        if flag.get("short_only"):
            flag_tokens[name] = f"-{flag['short']}"
        if name in reserved_names:
            flag_tokens[f"{name}_flag"] = (
                f"-{flag['short']}" if flag.get("short_only") else f"--{flag['long']}")
            renamed[flag["long"]] = f"{name}_flag"
            name = f"{name}_flag"
        declared = TYPE_MAP.get(flag["type"], "STRING")
        meta: dict = {"description": flag["description"]}
        # This path is the pinned container's home directory, not a portable
        # project default. An explicit data_dir still renders --data-dir.
        if (binary, flag["long"]) == ("taxonkit", "data-dir"):
            pass
        elif flag["default"] is not None:
            if declared == "INT":
                try:
                    meta["default"] = int(float(flag["default"]))
                except (ValueError, OverflowError):
                    meta["default"] = 0
            elif declared == "FLOAT":
                # A help table can print "(default nan)" or "inf". float() accepts
                # those, but repr() emits bare `nan`, which is not valid Python and
                # breaks the module on import.
                try:
                    parsed_default = float(flag["default"])
                except (ValueError, OverflowError):
                    parsed_default = 0.0
                meta["default"] = parsed_default if math.isfinite(parsed_default) else 0.0
            elif declared == "BOOLEAN":
                meta["default"] = flag["default"].strip().lower() in ("true", "yes", "1")
            else:
                meta["default"] = flag["default"]
        else:
            meta["default"] = False if declared == "BOOLEAN" else ""
        line = f'                "{name}": ({declared!r}, {meta!r}),'
        if flag["long"] in required_longs:
            req_lines.append(line)
        else:
            opt_lines.append(line)
    info["flags_renamed"] = renamed

    # Delimited-text tools get a delimiter parameter; sequence tools do not.
    delimiter_block = (
        '                "delimiter": (\n'
        '                    "STRING",\n'
        '                    {\n'
        '                        "default": "tab",\n'
        '                        "options": ["tab", "comma"],\n'
        '                        "description": "Input delimiter",\n'
        '                    },\n'
        '                ),\n'
    ) if tabular else ""
    tabs_block = (
        '        mode = str(inputs.get("delimiter", "tab") or "tab")\n'
        '        if mode == "tab":\n'
        '            command.append("--tabs")\n'
    ) if tabular else ""
    skip_names = '("delimiter", ' + repr(input_port) + ')' if tabular else '(' + repr(input_port) + ',)'
    # How the run reports its output. ``stdout`` passes the flag's own dash value
    # and lets the executor capture stdout into the planned file; ``dir`` declares a
    # directory the tool fills, so no filename can be promised in advance.
    output_kind = output["kind"]
    if output_kind == "stdout":
        output_block = f'        command.extend([{output["flag"]!r}, "-"])\n'
        stdout_line = "    STDOUT_OUTPUT_INDEX = 0\n"
        return_types, return_names = '("FILE",)', '("output",)'
        output_filenames = python_literal((f"{node_id}.out",))
    elif output_kind == "dir":
        # CommandNode.run injects output_dir as the node's own planned directory.
        # A prefix needs a basename inside it; an out-dir flag names it directly.
        target = 'output_dir' if output["flag"] in ("--out-dir", "--outdir", "--output-dir") \
            else 'output_dir / "output"'
        output_block = (f'        command.extend([{output["flag"]!r}, '
                        f'str({target})])\n')
        if (binary, sub) == ("unikmer", "grep"):
            output_block += '        command.extend(["--out-prefix", str(output_dir / "output")])\n'
        stdout_line = ""
        return_types, return_names = '("DIRECTORY",)', '("output_dir",)'
        output_filenames = "()"
    elif output_kind == "file":
        output_block = (f'        command.extend([{output["flag"]!r}, '
                        f'str(output_dir / cls.OUTPUT_FILENAMES[0])])\n')
        stdout_line = ""
        return_types, return_names = '("FILE",)', '("output",)'
        output_filenames = python_literal((f"{node_id}.out",))
    else:
        # No output flag declared: the tool writes to stdout by default (seqfu).
        output_block = ""
        stdout_line = "    STDOUT_OUTPUT_INDEX = 0\n"
        return_types, return_names = '("FILE",)', '("output",)'
        output_filenames = python_literal((f"{node_id}.out",))

    path_import = "from pathlib import Path\n" if output_kind in ("dir", "file") else ""
    output_dir_line = (
        '        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))\n'
        if path_import else ""
    )

    # Flat families invoke the binary itself; subcommand families invoke
    # ``<binary> <sub>``. Everything below adapts to the difference.
    display_name = f"{binary} {sub}".strip() if sub else binary
    subcommand_line = f"    SUBCOMMAND = {sub!r}\n" if sub else ""
    aliases = [binary] + ([sub] if sub else [])
    command_head = (f"[{binary!r}, cls.SUBCOMMAND]" if sub else f"[{binary!r}]")
    if input_ports:
        input_append = "".join(
            (f'        command.extend([{flag!r}, str(inputs.get({name!r}, ""))])\n'
             if flag else f'        command.append(str(inputs.get({name!r}, "")))\n')
            for name, _, flag in input_ports
        )
    elif input_flag:
        input_append = (f'        command.extend([{input_flag!r}, '
                        f'str(inputs.get({input_port!r}, ""))])\n')
    else:
        input_append = f'        command.append(str(inputs.get({input_port!r}, "")))\n'
    # The conda package that provides the executable is not always the executable
    # name (vcflib ships vcfcheck, vcf2tsv, ...).
    conda_package = options.get("conda_package") or binary
    flag_tokens_line = f"    FLAG_TOKENS = {flag_tokens!r}\n" if flag_tokens else ""
    input_lines = (
        "\n".join(f'                {name!r}: ({kind!r}, {{"description": "Input {name.replace("_", " ")}"}}),'
                  for name, kind, _ in input_ports)
        if input_ports else f'                {input_port!r}: ("FILE", {{"description": {input_description!r}}}),'
    )
    skip_ports = tuple(name for name, _, _ in input_ports) if input_ports else (input_port,)
    skip_names = repr(("delimiter", *skip_ports) if tabular else skip_ports)

    body = f'''"""``{binary} {sub}``: {parsed["description"][:80]}.

{GENERATED_MARKER} in the pinned {binary} {commit} image.
Help page SHA-256: {source_sha}

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

{path_import}from typing import Any

from .adapter import {base_class}


class {class_name}({base_class}):
    """{parsed["description"][:150]}"""

    NODE_ID = {node_id!r}
    DISPLAY_NAME = {display_name!r}
{subcommand_line}    DESCRIPTION = {parsed["description"]!r}
    SEARCH_ALIASES = {aliases!r}
    RETURN_TYPES = {return_types}
    RETURN_NAMES = {return_names}
    OUTPUT_FILENAMES = {output_filenames}
{stdout_line}{flag_tokens_line}    DOCUMENTATION_URL = {documentation_url!r}
    REQUIRED_EXECUTABLES = [{binary!r}]
    REQUIRED_CONDA_PACKAGES = [{conda_package!r}]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {{
            "required": {{
{input_lines}
{chr(10).join(req_lines)}
            }},
            "optional": {{
{delimiter_block}{chr(10).join(opt_lines)}
            }},
            "hidden": {{"output": ("STRING", {{}})}},
        }}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
{output_dir_line}        command = {command_head}
{tabs_block}        # Required flags must be rendered too. Iterating only "optional" silently
        # dropped every empirically-required flag (csvtk mutate --name and friends).
        declared_types = cls.INPUT_TYPES()
        for category in ("required", "optional"):
            for name, spec in declared_types.get(category, {{}}).items():
                if name in {skip_names}:
                    continue
                value = inputs.get(name)
                if value in (None, ""):
                    continue
                declared = spec[0] if isinstance(spec, (list, tuple)) else spec
                default = spec[1].get("default") if isinstance(spec, tuple) and len(spec) > 1 else None
                token = getattr(cls, "FLAG_TOKENS", {{}}).get(name) or f"--{{name.replace('_', '-')}}"
                if declared == "BOOLEAN":
                    if bool(value):
                        command.append(token)
                    continue
                if value == default:
                    continue
                command.extend([token, str(value)])
{output_block}{input_append}        return command
'''
    info["status"] = "generated"
    return body, info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--help-dir", type=Path, required=True)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--family", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, default=None,
                        help="Retained for call-site compatibility. The generator no "
                             "longer reads the 107 MB registry snapshot: it parsed it "
                             "into an `accessions` set that nothing consumed.")
    parser.add_argument("--commit", default="")
    parser.add_argument("--required-dir", type=Path, default=None,
                        help="Directory of empirical required-flag probes (see parse_required).")
    parser.add_argument("--base-module", default=".adapter",
                        help="Relative import providing the family base class.")
    parser.add_argument("--base-class", default="CsvtkBase",
                        help="Family base class name every generated node subclasses.")
    parser.add_argument("--input-port", default="table",
                        help="Name of the primary file input port.")
    parser.add_argument("--input-description", default="Input table file")
    parser.add_argument("--output-flag", default="--out-file",
                        help="Flag that names the output file (used when "
                             "--output-mode is 'flag').")
    parser.add_argument("--output-mode", choices=("auto", "flag", "none"), default="auto",
                        help="'auto' reads the output flag from each subcommand's own "
                             "help page (a tool may use --out-file for one subcommand "
                             "and --out-prefix for the next); 'flag' forces "
                             "--output-flag; 'none' captures stdout.")
    parser.add_argument("--documentation-url", default="https://github.com/shenwei356/csvtk")
    parser.add_argument("--tabular", default="true",
                        help="'true' adds the delimiter parameter and --tabs flag "
                             "(delimited-text tools); 'false' for sequence tools.")
    parser.add_argument("--skip-subcommands", default="",
                        help="Comma-separated subcommands not to generate (non-data commands).")
    parser.add_argument("--promote-global", default="",
                        help="Comma-separated flags inherited from the root that this "
                             "family should still declare, because they are the "
                             "operation's premise rather than noise (e.g. taxonkit's "
                             "--data-dir, the NCBI taxonomy dump).")
    args = parser.parse_args()

    tabular = args.tabular.strip().lower() in ("true", "1", "yes")
    skip = {s.strip() for s in args.skip_subcommands.split(",") if s.strip()}
    promote_global = frozenset(s.strip() for s in args.promote_global.split(",") if s.strip())
    required = parse_required(args.required_dir) if args.required_dir else {}

    existing: set[str] = set()
    covered_subcommands: set[str] = set()
    # An existing hand-written node may be named differently from the subcommand it
    # drives: ``stats.py`` renders ``csvtk summary``. Matching on filename alone
    # therefore produced a duplicate ``csvtk_summary`` alongside ``csvtk_stats``.
    # Read the subcommand each hand-written node actually invokes instead.
    invoked = re.compile(r'["\']' + re.escape(args.binary) + r'["\']\s*,\s*["\']([a-z0-9][a-z0-9-]*)["\']')
    # A hand-written node may deliberately absorb several subcommands. ``convert.py``
    # declares COVERS_SUBCOMMANDS for the format-conversion cluster, which is one
    # operation with six encodings rather than six operations.
    covers = re.compile(r"COVERS_SUBCOMMANDS[^=]*=\s*\(([^)]*)\)", re.S)
    for path in args.family.glob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if GENERATED_MARKER in text:
            continue
        existing.add(path.stem)
        existing.add(f"{args.binary}_{path.stem}")
        for match in invoked.finditer(text):
            covered_subcommands.add(match.group(1))
        for match in covers.finditer(text):
            covered_subcommands.update(re.findall(r'["\']([a-z0-9][a-z0-9-]*)["\']', match.group(1)))

    subcommands = parse_subcommands(args.help_dir / "_subcommands.txt")
    results = []
    for sub in subcommands:
        page = args.help_dir / f"{sub}.txt"
        if not page.is_file():
            results.append({"subcommand": sub, "status": "skipped_no_help"})
            continue
        text = page.read_text(encoding="utf-8", errors="replace")
        import hashlib
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        parsed = parse_help(text)
        node_id = f"{args.binary}_{sub.replace('-', '_')}"
        if node_id in existing:
            results.append({"subcommand": sub, "node_id": node_id,
                            "status": "skipped_already_handwritten"})
            continue
        if sub in covered_subcommands:
            results.append({"subcommand": sub, "node_id": node_id,
                            "status": "skipped_subcommand_already_covered"})
            continue
        if not parsed["flags"]:
            results.append({"subcommand": sub, "node_id": node_id,
                            "status": "skipped_no_flags", "description": parsed["description"]})
            continue
        if sub in skip:
            results.append({"subcommand": sub, "node_id": node_id,
                            "status": "skipped_non_data_command"})
            continue
        body, info = build_node(args.binary, sub, parsed, sha, args.commit, args.family.name,
                                frozenset(required.get(sub, [])), {
                                    "base_module": args.base_module,
                                    "base_class": args.base_class,
                                    "input_port": args.input_port,
                                    "input_description": args.input_description,
                                    "output_flag": args.output_flag,
                                    "output": detect_output(parsed, args.output_flag,
                                                            args.output_mode),
                                    "documentation_url": args.documentation_url,
                                    "tabular": tabular,
                                    "promote_global": promote_global,
                                })
        info["required_flags"] = required.get(sub, [])
        (args.family / f"{node_id}.py").write_text(body, encoding="utf-8", newline="\n")
        results.append(info)

    statuses = Counter(r["status"] for r in results)
    manifest = {
        "schema_version": 1,
        "binary": args.binary,
        "subcommands_seen": len(subcommands),
        "statuses": dict(statuses.most_common()),
        "generated_node_ids": sorted(r["node_id"] for r in results if r["status"] == "generated"),
        "scope": (
            "Contracts generated from the tool's own --help output. No tool was executed "
            "and no scientific result was validated."
        ),
        "records": results,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "records"}, indent=2)[:2500])


if __name__ == "__main__":
    main()
