#!/usr/bin/env python
"""Generate BioNodulo nodes for vcflib from each tool's own ``--help`` output.

vcflib is not one binary with subcommands. It ships ~121 separate executables, so
the "subcommand" is the binary name and the flat mode of the shared node emitter is
used. The emitter itself lives in ``generate_subcommand_nodes.py``; this module
supplies the parsers, because vcflib's help output is not cobra.

Four dialects appear, in rough order of usefulness:

``INFO`` blocks (GPAT++ tools, 14 of them)
    ::

        INFO: required: t,target     -- a zero based comma separated list of ...
        INFO: optional, r,region     -- a tabix compliant genomic region ...

    Machine-readable, and the only vcflib dialect that states which flags are
    required. Boolean flags are recognised by checking the tool's own ``INFO:
    usage:`` line: a flag that appears there without a value is a switch.

``options:`` tables (args.hxx tools, 26)
    ::

        -f, --fasta-reference  FASTA reference file to use to obtain primer sequences.
        -l, --compress-level INT   Compression level to use when compressing; 0 to 9

    A metavar is an all-uppercase token; anything else starts the description. That
    distinction matters, because the separator is only one space when the flag names
    are long (``--exclude-failures If a record fails``).

``Params:`` blocks (2)
    ::

        required: t,target  <STRING>  A zero base comma separated list of target
                                      individuals corresponding to VCF columns

    The metavar is explicit, and continuation lines are indented to the description
    column.

No declaration (46)
    Positional-only tools, or tools whose options exist but are not printed by
    ``--help`` (``vcfbreakmulti`` says ``usage: vcfbreakmulti [options] [file]`` and
    then lists nothing). Those nodes declare the data ports and stdout, and no
    parameters. Inventing a flag set for them is not an option.

Usage:
    python scripts/generate_vcflib_nodes.py \
        --help-dir artifacts/vcflib-help \
        --family bionodulo/nodes/builtin/vcflib_family \
        --manifest reports/node-expansion/vcflib-generated.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_subcommand_nodes import build_node  # noqa: E402
from dump_tool_help import probe_value_flags  # noqa: E402

VERSION = "1.0.15"
DOCUMENTATION_URL = "https://github.com/vcflib/vcflib"
IMAGE = ("quay.io/biocontainers/vcflib@sha256:"
         "838ddab39b0af484f51c1b08f032f47e4ca9e402a8d36d1d4c6f7c46e031d034")

# `INFO: required: t,target  -- desc` and `INFO: optional, r,region -- desc`.
# The separator after required/optional is a colon for some tools and a comma for
# others, in the same file.
INFO_FLAG = re.compile(
    r"^INFO:\s*(?P<kind>required|optional)[:,]\s*"
    r"(?P<short>[A-Za-z0-9]),(?P<long>[A-Za-z0-9][A-Za-z0-9-]*)\s+--\s*(?P<desc>.*)$"
)
# Some GPAT tools declare the short name only: `INFO: required: -f   -- desc`.
# There is no long form, so the node has to render the single-dash token.
INFO_FLAG_SHORT = re.compile(
    r"^INFO:\s*(?P<kind>required|optional)[:,]\s*"
    r"-(?P<short>[A-Za-z0-9])\s+--\s*(?P<desc>.*)$"
)
INFO_USAGE = re.compile(r"^INFO:\s*usage:\s*(?P<usage>.*)$", re.I)
# `-f, --fasta-reference  desc` with an optional all-uppercase metavar. The comma
# after the short name is optional: vcfcombine and vcfsamplediff print `-h --help`.
ARGS_FLAG = re.compile(
    r"^\s+(?:-(?P<short>[A-Za-z0-9]),?\s+)?--(?P<long>[a-z0-9][a-z0-9-]*)"
    r"(?:\s+(?P<type>[A-Z][A-Z0-9_]*))?\s+(?P<desc>.*)$"
)
ARGS_SECTION = re.compile(r"^\s*(?:options|Options):\s*$")
# `required: t,target  <STRING>  desc`
PARAMS_FLAG = re.compile(
    r"^\s*(?P<kind>required|optional):\s*(?P<short>[A-Za-z0-9]),"
    r"(?P<long>[A-Za-z0-9][A-Za-z0-9-]*)\s+<(?P<type>[A-Za-z0-9_]+)>\s+(?P<desc>.*)$"
)
PARAMS_SECTION = re.compile(r"^\s*Params:\s*$")
USAGE_LINE = re.compile(r"^\s*usage:\s*(?P<usage>.*)$", re.I)
TYPE_LINE = re.compile(r"^\s*Type:\s*(?P<kind>\w+)", re.I)
# Input redirection, as opposed to a metavariable. `<vcf file>` is vcflib's
# placeholder for a positional argument (vcffilter accepts one and works); a `<`
# followed by whitespace and a bracket is a real redirect, and those tools read
# stdin only, so a node that passes a path positionally cannot run them.
STDIN_REDIRECT = re.compile(r"\s<\s*[\[<]|<\[")
# Lines that are not a description. Tool errors, and the BusyBox applet banners that
# appear when a shell wrapper forwards --help to the command it wraps.
NOT_A_DESCRIPTION = re.compile(
    r"(invalid option|unrecognized option|command not found|no such file|"
    r"cannot open|cannot execute|BusyBox|"
    r"Usage:\s*(head|mkdir|cat|sort|awk|sed|cut|tail|uniq|grep)\b)", re.I)
# Tools whose output shape the node contract cannot express honestly yet. Kept as
# an explicit, reviewable list rather than a heuristic.
UNREPRESENTABLE = {
    "bgziptabix": (
        "shell wrapper prints concatenated bgzip and tabix help; its output and "
        "input contract cannot be inferred from either help page. Use the "
        "dedicated bgzip_compress and tabix_index nodes instead"
    ),
    "vcf2fasta": (
        "writes one FASTA per sample (sample_seq:N.fa) and has no output flag that "
        "names them; the node contract declares a single output"
    ),
    "vcfsort": (
        "a shell wrapper that forwards --help to the BusyBox applet it invokes, so it "
        "prints BusyBox's `head` help and documents no interface of its own; running it "
        "with no arguments prints nothing"
    ),
    "vcfmultiwayscripts": (
        "a shell wrapper that forwards --help to the BusyBox applet it invokes, so it "
        "prints BusyBox's `mkdir` help and documents no interface of its own"
    ),
}
# Metavar to node parameter type. Anything unrecognised is a string.
METAVAR_TYPES = {
    "INT": "INT", "INTEGER": "INT", "LONG": "INT", "NUM": "FLOAT",
    "FLOAT": "FLOAT", "DOUBLE": "FLOAT",
}
# Sections that end the options table. A blank line must NOT end it: several tools
# put a blank line immediately after `options:` and then the flags, and treating the
# blank line as a terminator silently produced flagless nodes for vcfcheck,
# vcfleftalign, vcfcombine and vcfcreatemulti.
STOP_SECTIONS = re.compile(r"^\s*(Type:|Version|Contact|Notes|Support|Contribution|"
                           r"Example|Output\s*:|---)", re.I)
# The GPAT++ tools take their input through a flag rather than a positional argument
# (`abba-baba --tree 0,1,2,3 --file my.vcf --type PL`). When a required flag carries
# one of these names it becomes the node's input port, so the command names the input
# once instead of twice. Verified against the pinned image: with the flag the tools
# exit 0, and a trailing positional is ignored rather than rejected, so the earlier
# form worked too but said the same thing twice.
INPUT_FLAG_NAMES = ("file", "input", "infile", "vcf-file")
# A trailing `[0.01]` or `(150)` in a description is the default value.
TRAILING_DEFAULT = re.compile(r"[\[(](?P<value>[^\]()]{1,24})[\])]\s*\.?\s*$")


def _split_default(desc: str) -> tuple[str, str | None]:
    match = TRAILING_DEFAULT.search(desc)
    if not match:
        return desc, None
    value = match.group("value").strip()
    # Only treat it as a default if it looks like one, not prose in brackets.
    if not re.fullmatch(r"-?[\w.*+/ ]{1,20}", value):
        return desc, None
    return desc[:match.start()].strip(), value


def _describe(text: str) -> str:
    """First meaningful sentence of the page, skipping the tool's own banners.

    Two kinds of line are not a description and were being captured as one:

    - **Tool errors.** ``normalize-iHS --help`` prints
      ``normalize-iHS: invalid option -- '-'`` to stderr before its real
      ``INFO: description:`` block, and the error line came first.
    - **BusyBox banners.** ``vcfsort`` and ``vcfmultiwayscripts`` are shell wrappers
      that forward ``--help`` to the applet they invoke, so the page is BusyBox's
      ``head`` or ``mkdir`` help. Their own usage is not printed at all.
    """
    from_info = _info_description(text)
    if from_info:
        return from_info
    in_warning = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("WARNING:"):
            in_warning = True
            continue
        if in_warning:
            if not stripped:
                in_warning = False
            continue
        if not stripped or len(stripped) < 12:
            continue
        if stripped.startswith(("INFO:", "usage:", "Usage:", "Type:", "-----",
                                "-", "=", "*")):
            continue
        if NOT_A_DESCRIPTION.search(stripped):
            continue
        return stripped[:200]
    return ""


def _info_description(text: str) -> str:
    """The text after an ``INFO: description:`` header, which is the tool's summary."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower().startswith("info: description"):
            collected: list[str] = []
            for follow in lines[index + 1:]:
                stripped = follow.strip()
                if not stripped:
                    if collected:
                        break
                    continue
                if stripped.lower().startswith("usage:"):
                    continue
                if stripped.startswith(("INFO:", "Usage:", "usage:")):
                    break
                if stripped.startswith(("-", "=", "*")):
                    break
                collected.append(stripped)
                if len(" ".join(collected)) > 60:
                    break
            if collected:
                return " ".join(collected)[:200]
    return ""


def _usage(text: str) -> str:
    for line in text.splitlines():
        match = USAGE_LINE.match(line) or INFO_USAGE.match(line)
        if match:
            return match.group("usage").strip()
    return ""


def _boolean_flags(usage: str) -> set[str]:
    """Long flags that appear in a usage line without a following value.

    ``--snp`` at the end of a usage line, or followed by another ``--flag``, is a
    switch. ``--type PL`` is not.
    """
    switches: set[str] = set()
    tokens = usage.split()
    for index, token in enumerate(tokens):
        if not token.startswith("--"):
            continue
        name = token[2:].strip(",=")
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        if following is None or following.startswith("-"):
            switches.add(name)
    return switches


def parse_info(text: str) -> dict | None:
    flags: list[dict] = []
    usage = _usage(text)
    switches = _boolean_flags(usage)
    for line in text.splitlines():
        stripped = line.strip()
        match = INFO_FLAG.match(stripped)
        short_only = False
        if match:
            long_name = match.group("long")
            short = match.group("short")
        else:
            match = INFO_FLAG_SHORT.match(stripped)
            if not match:
                continue
            # No long form declared. The node still has to invoke it, so the token
            # stays single-dash and the parameter is named after the letter.
            short = match.group("short")
            long_name = short
            short_only = True
        desc, default = _split_default(match.group("desc").strip())
        is_switch = long_name in switches or short in switches
        flags.append({
            "short": short,
            "long": long_name,
            "type": "bool" if is_switch else "string",
            "description": desc[:200],
            "default": default,
            "global": False,
            "required": match.group("kind") == "required",
            "short_only": short_only,
        })
    if not flags:
        return None
    return {"description": _describe(text), "usage": usage, "flags": flags}


def parse_args_table(text: str) -> dict | None:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if ARGS_SECTION.match(line)), None)
    if start is None:
        return None
    flags: list[dict] = []
    for line in lines[start + 1:]:
        if STOP_SECTIONS.match(line):
            break
        match = ARGS_FLAG.match(line)
        if match:
            metavar = match.group("type")
            desc, default = _split_default(match.group("desc").strip())
            flags.append({
                "short": match.group("short"),
                "long": match.group("long"),
                "type": (METAVAR_TYPES.get(metavar, "string") if metavar else "bool"),
                "description": desc[:200],
                "default": default,
                "global": False,
                # No metavar in the help: the flag is either a switch or a value flag
                # the author left undocumented. Resolved by probing the tool.
                "metavar_missing": metavar is None,
            })
        elif flags and line.startswith(" " * 20):
            flags[-1]["description"] = (flags[-1]["description"] + " " +
                                        line.strip())[:240]
    if not flags:
        return None
    return {"description": _describe(text), "usage": _usage(text), "flags": flags}


def parse_params_block(text: str) -> dict | None:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if PARAMS_SECTION.match(line)), None)
    if start is None:
        return None
    flags: list[dict] = []
    for line in lines[start + 1:]:
        match = PARAMS_FLAG.match(line)
        if match:
            desc, default = _split_default(match.group("desc").strip())
            flags.append({
                "short": match.group("short"),
                "long": match.group("long"),
                "type": METAVAR_TYPES.get(match.group("type").upper(), "string"),
                "description": desc[:200],
                "default": default,
                "global": False,
                "required": match.group("kind") == "required",
            })
        elif flags and line.startswith(" " * 20):
            flags[-1]["description"] = (flags[-1]["description"] + " " +
                                        line.strip())[:240]
    if not flags:
        return None
    return {"description": _describe(text), "usage": _usage(text), "flags": flags}


def parse_vcflib(text: str) -> tuple[dict, str]:
    """Return (parsed, dialect)."""
    for dialect, parser in (("info", parse_info), ("params", parse_params_block),
                            ("args", parse_args_table)):
        parsed = parser(text)
        if parsed:
            return parsed, dialect
    return {"description": _describe(text), "usage": _usage(text), "flags": []}, \
        "no_declaration"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--help-dir", type=Path, required=True)
    parser.add_argument("--family", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--commit", default=VERSION)
    parser.add_argument("--documentation-url", default=DOCUMENTATION_URL)
    parser.add_argument("--input-port", default="input")
    parser.add_argument("--input-description",
                        default="Input VCF file (or the positional file the tool expects)")
    parser.add_argument("--skip", default="",
                        help="Comma-separated tool names to exclude (shell wrappers, "
                             "interactive viewers).")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--image", default=IMAGE, help="Digest-pinned image to probe.")
    parser.add_argument("--arg-probe-dir", type=Path,
                        default=Path("artifacts/vcflib-argprobe"),
                        help="Cache for the value-flag probe. Delete to re-probe.")
    parser.add_argument("--no-probe", action="store_true",
                        help="Skip the probe; metavar-less flags stay typed as switches.")
    args = parser.parse_args()

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    tools = [line.strip() for line in
             (args.help_dir / "_subcommands.txt").read_text(encoding="utf-8").splitlines()
             if line.strip()]

    # Work out which metavar-less flags actually take a value, before generating.
    parsed_pages: dict[str, tuple[dict, str]] = {}
    ambiguous: dict[str, list[str]] = {}
    for tool in tools:
        text = (args.help_dir / f"{tool}.txt").read_text(encoding="utf-8", errors="replace")
        parsed, dialect = parse_vcflib(text)
        parsed_pages[tool] = (parsed, dialect)
        if dialect == "args":
            bare = [f["long"] for f in parsed["flags"] if f.get("metavar_missing")]
            if bare:
                ambiguous[tool] = bare
    probe: dict[str, dict[str, bool]] = {}
    if ambiguous and not args.no_probe:
        print(f"probing {sum(len(v) for v in ambiguous.values())} flags across "
              f"{len(ambiguous)} tools for value-vs-switch", file=sys.stderr)
        probe = probe_value_flags(args.image, ambiguous, args.arg_probe_dir)
    for tool, (parsed, dialect) in parsed_pages.items():
        for flag in parsed["flags"]:
            if probe.get(tool, {}).get(flag["long"]):
                flag["type"] = "string"
                flag["value_probed"] = True

    results = []
    for tool in tools:
        parsed, dialect = parsed_pages[tool]
        sha = hashlib.sha256(
            (args.help_dir / f"{tool}.txt").read_text(encoding="utf-8",
                                                      errors="replace").encode("utf-8")
        ).hexdigest()
        if tool in skip:
            results.append({"tool": tool, "status": "skipped_by_request",
                            "dialect": dialect})
            continue
        if tool in UNREPRESENTABLE:
            status = ("skipped_unsupported_shell_wrapper" if tool == "bgziptabix"
                      else "skipped_unrepresentable_output")
            results.append({"tool": tool, "status": status,
                            "reason": UNREPRESENTABLE[tool], "dialect": dialect})
            continue
        if STDIN_REDIRECT.search(parsed["usage"]):
            results.append({
                "tool": tool, "status": "skipped_reads_stdin",
                "reason": ("usage line shows input redirection, so the tool reads "
                           "stdin and a positional file argument does not reach it"),
                "usage": parsed["usage"], "dialect": dialect,
            })
            continue
        if not parsed["description"]:
            results.append({"tool": tool, "status": "skipped_no_description",
                            "dialect": dialect})
            continue
        required = frozenset(f["long"] for f in parsed["flags"] if f.get("required"))
        # Promote a required file-named flag to the node's input port.
        input_flag = ""
        for flag in parsed["flags"]:
            if flag.get("required") and flag["long"] in INPUT_FLAG_NAMES:
                input_flag = (f"-{flag['short']}" if flag.get("short_only")
                              else f"--{flag['long']}")
                break
        body, info = build_node(tool, "", parsed, sha, args.commit, args.family.name,
                                required, {
                                    "base_class": "VcflibBase",
                                    "input_port": args.input_port,
                                    "input_description": args.input_description,
                                    "input_flag": input_flag,
                                    "output_mode": "none",
                                    "documentation_url": args.documentation_url,
                                    "tabular": False,
                                    "id_prefix": "vcflib_",
                                    "conda_package": "vcflib",
                                })
        info["dialect"] = dialect
        info["tool"] = tool
        info["input_flag"] = input_flag
        info["status"] = "generated"
        results.append(info)
        if not args.dry_run:
            (args.family / f"{info['node_id']}.py").write_text(
                body, encoding="utf-8", newline="\n")

    dialects = Counter(r["dialect"] for r in results)
    statuses = Counter(r["status"] for r in results)
    manifest = {
        "schema_version": 1,
        "binary": "vcflib",
        "source": f"vcflib --help output from quay.io/biocontainers/vcflib:{VERSION}",
        "tools_seen": len(tools),
        "statuses": dict(statuses.most_common()),
        "dialects": dict(dialects.most_common()),
        "generated_node_ids": sorted(r["node_id"] for r in results
                                     if r["status"] == "generated"),
        "scope": (
            "Contracts generated from each tool's own --help output. No tool was "
            "executed and no scientific result was validated."
        ),
        "records": results,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "records"}, indent=2))


if __name__ == "__main__":
    main()
