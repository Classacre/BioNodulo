#!/usr/bin/env python
"""Dump a tool's own ``--help`` pages from a digest-pinned container.

``generate_subcommand_nodes.py`` reads help text as a declaration: the flag table
is the parameter grammar, and the pinned image is what ties that grammar to a
build. This script produces that input.

Two shapes are supported, because real tools come in both:

``subcommands``
    One binary, many subcommands (``csvtk stats``, ``vg filter``). Discovery reads
    the root help's command list, then dumps ``<binary> <sub> --help`` for each.

``flat``
    Many separate binaries in one package (``vcflib`` ships ~100 executables such
    as ``vcf2tsv`` and ``vcfallelicprimitives``). Here the "subcommand" is the
    binary name itself and the root help is not a command list but a binary list.

Every container is run with ``--network none``. Docker is invoked through
``subprocess`` rather than a shell, because Git Bash rewrites arguments that look
like POSIX paths and turns ``--entrypoint /bin/sh`` into a Windows path.

Usage:
    python scripts/dump_tool_help.py \
        --image quay.io/biocontainers/vcflib@sha256:838ddab3... \
        --binary vcflib --mode flat --out-dir artifacts/vcflib-help
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

# Cobra, click, and hand-rolled Go tools all section their command list under one
# of these. vg writes "commands:", odgi writes "Available commands:".
COMMAND_HEADERS = re.compile(
    r"^\s*(available commands|commands|subcommands|available subcommands|"
    r"sub-commands|command list)\s*:?\s*$",
    re.I,
)
# A command-list row: two-space indent, a bare token, then a description.
COMMAND_ROW = re.compile(r"^\s{2,}(?P<name>[a-z][a-z0-9_-]{1,40})\s{2,}\S")
# "flag -f (--fields) needed" / "required flag(s) \"name\" not set"
NEEDED_FLAG = re.compile(r'flag -[A-Za-z0-9] \(--(?P<long>[a-z0-9-]+)\) needed')
NEEDED_FLAG_ALT = re.compile(r'required flag\(s\) "(?P<long>[a-z0-9-]+)" not set')
# args.hxx (vcflib) does not print a metavar for every flag that takes a value, so
# the help table alone cannot separate `--keep-info` (a switch) from `--info-filter`
# (takes an expression). The tool itself says so when the flag is used bare:
# "vcffilter: option '--info-filter' requires an argument".
ARG_REQUIRED = re.compile(r"option '(?P<flag>--[a-z0-9-]+)' requires an argument")

NON_COMMANDS = {
    "help", "completion", "version", "man", "docs", "gen", "generate",
    "bash", "zsh", "fish", "powershell", "list", "manpage", "help-topic",
}
MAX_PROBE_ROUNDS = 12


def docker(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8", errors="replace")


def run_in_image(image: str, argv: list[str], timeout: int = 300) -> tuple[int, str]:
    """Run argv inside the image with no network. Returns (exit_code, combined output)."""
    try:
        proc = docker(["run", "--rm", "--network", "none", "--entrypoint", "sh",
                       image, "-c", _shell_quote(argv)], timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, ""
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _shell_quote(argv: list[str]) -> str:
    out = []
    for token in argv:
        if re.fullmatch(r"[A-Za-z0-9_./=:@+-]+", token):
            out.append(token)
        else:
            out.append("'" + token.replace("'", "'\\''") + "'")
    return " ".join(out)


def _looks_like_help(text: str) -> bool:
    """Decide whether a tool's output is a help page.

    Exit code is not the test. ``vcf2tsv --help`` exits 1 while
    ``vcfallelicprimitives --help`` exits 0, and both print help. Gate on the
    content instead.
    """
    low = text.lower()
    if len(text.strip()) < 60:
        return False
    return any(marker in low for marker in ("usage:", "options:", "flags:", "synopsis"))


def discover_subcommands(text: str) -> list[str]:
    lines = text.splitlines()
    found: list[str] = []
    for index, line in enumerate(lines):
        if not COMMAND_HEADERS.match(line):
            continue
        for follow in lines[index + 1:]:
            if not follow.strip():
                # A blank line ends the table only once rows have been seen.
                if found:
                    break
                continue
            match = COMMAND_ROW.match(follow)
            if match:
                found.append(match.group("name"))
            elif found:
                break
    if not found:
        for line in lines:
            match = COMMAND_ROW.match(line)
            if match:
                found.append(match.group("name"))
    ordered: list[str] = []
    for name in found:
        if name in NON_COMMANDS or name.startswith("-"):
            continue
        if name not in ordered:
            ordered.append(name)
    return ordered


def list_binaries(image: str) -> list[str]:
    """List executables the package installed, using conda's own manifest."""
    code, out = run_in_image(image, ["sh", "-c",
        "ls -1 /usr/local/bin /usr/bin 2>/dev/null | sort -u"], timeout=120)
    del code
    return [line.strip() for line in out.splitlines() if line.strip()]


def probe_required(image: str, binary: str, subcommands: list[str],
                   timeout: int) -> dict[str, list[str]]:
    """Run each subcommand bare and read which flags it demands.

    Neither cobra nor args.hxx marks required flags in help output, so the tool is
    the only authority. It reports one missing flag per run, so this iterates.
    """
    required: dict[str, list[str]] = {}
    for sub in subcommands:
        found: list[str] = []
        for _ in range(MAX_PROBE_ROUNDS):
            argv = [binary, sub] if sub else [binary]
            for flag in found:
                argv.extend([f"--{flag}", "x"])
            code, out = run_in_image(image, argv, timeout=timeout)
            if code == 0:
                break
            match = NEEDED_FLAG.search(out) or NEEDED_FLAG_ALT.search(out)
            if not match:
                break
            name = match.group("long")
            if name in found:
                break
            found.append(name)
        required[sub] = found
    return required


def probe_value_flags(image: str, candidates: dict[str, list[str]], out_dir: Path,
                      timeout: int = 60) -> dict[str, dict[str, bool]]:
    """Ask each tool which of its flags take a value.

    ``candidates`` maps tool name to the flags whose help entry shows no metavar.
    Those are the ambiguous ones: a flag with a printed metavar is already known to
    take a value, while a bare flag is either a switch or a value flag the author
    did not document. Running the flag alone settles it, because args.hxx prints
    "option '--x' requires an argument".

    Results are cached under ``out_dir`` so a regeneration does not re-run 200
    containers.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, bool]] = {}
    for tool, flags in candidates.items():
        cache = out_dir / f"{tool}.json"
        if cache.is_file():
            results[tool] = json.loads(cache.read_text(encoding="utf-8"))
            continue
        verdicts: dict[str, bool] = {}
        for flag in flags:
            # The caller passes bare long names. The tool must be asked with the
            # dashes, or it treats the flag as a positional argument and says
            # nothing, which reads as "it's a switch" for every flag.
            token = flag if flag.startswith("-") else f"--{flag}"
            _code, out = run_in_image(image, [tool, token], timeout=timeout)
            match = ARG_REQUIRED.search(out)
            verdicts[flag] = bool(match and match.group("flag") == token)
        cache.write_text(json.dumps(verdicts, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
        results[tool] = verdicts
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", required=True, help="Digest-pinned image reference.")
    parser.add_argument("--binary", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("subcommands", "flat"), default="subcommands")
    parser.add_argument("--subcommands", default="",
                        help="Explicit comma-separated list; skips discovery.")
    parser.add_argument("--skip", default="", help="Subcommands to exclude.")
    parser.add_argument("--timeout", type=int, default=120, help="Per-invocation seconds.")
    parser.add_argument("--probe", default="true",
                        help="'true' runs the empirical required-flag probe.")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    # Only create the probe directory when probing. Creating it unconditionally left
    # an empty artifacts/vcflib-help-required behind on a run with --probe false.
    probe_enabled = args.probe.strip().lower() in ("true", "1", "yes")
    required_dir = args.out_dir.parent / f"{args.out_dir.name}-required"
    if probe_enabled:
        required_dir.mkdir(parents=True, exist_ok=True)

    code, root_help = run_in_image(args.image, [args.binary, "--help"], args.timeout)
    (args.out_dir / "_root.txt").write_text(root_help, encoding="utf-8", newline="\n")

    if args.subcommands.strip():
        subcommands = [s.strip() for s in args.subcommands.split(",") if s.strip()]
    elif args.mode == "flat":
        # Each executable is its own tool; the package's own bin listing is the
        # authority, filtered to the ones that answer --help.
        subcommands = list_binaries(args.image)
    else:
        subcommands = discover_subcommands(root_help)

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    subcommands = [s for s in subcommands if s not in skip]
    print(f"root help exit={code}  discovered={len(subcommands)}")

    usable: list[str] = []
    if args.mode == "flat":
        # Flat mode: the binary *is* the tool, so the help page is `<name> --help`.
        for name in subcommands:
            _exit_code, text = run_in_image(args.image, [name, "--help"], args.timeout)
            if _looks_like_help(text):
                (args.out_dir / f"{name}.txt").write_text(text, encoding="utf-8",
                                                          newline="\n")
                usable.append(name)
    else:
        for sub in subcommands:
            _exit_code, text = run_in_image(args.image, [args.binary, sub, "--help"],
                                            args.timeout)
            if _looks_like_help(text):
                (args.out_dir / f"{sub}.txt").write_text(text, encoding="utf-8",
                                                         newline="\n")
                usable.append(sub)

    (args.out_dir / "_subcommands.txt").write_text("\n".join(usable) + "\n",
                                                   encoding="utf-8", newline="\n")

    required: dict[str, list[str]] = {}
    if probe_enabled and args.mode == "subcommands":
        required = probe_required(args.image, args.binary, usable, args.timeout)
        for sub, flags in required.items():
            (required_dir / f"{sub}.txt").write_text(
                f"SUB={sub}\nREQUIRED={' '.join('--' + f for f in flags)}\n",
                encoding="utf-8", newline="\n")
    elif probe_enabled and args.mode == "flat":
        # Flat mode: each binary takes its own flags, so "required" is per binary.
        for name in usable:
            found: list[str] = []
            for _ in range(MAX_PROBE_ROUNDS):
                argv = [name] + [x for f in found for x in (f"--{f}", "x")]
                exit_code, out = run_in_image(args.image, argv, args.timeout)
                if exit_code == 0:
                    break
                match = NEEDED_FLAG.search(out) or NEEDED_FLAG_ALT.search(out)
                if not match or match.group("long") in found:
                    break
                found.append(match.group("long"))
            required[name] = found
            (required_dir / f"{name}.txt").write_text(
                f"SUB={name}\nREQUIRED={' '.join('--' + f for f in found)}\n",
                encoding="utf-8", newline="\n")

    summary = {
        "image": args.image,
        "binary": args.binary,
        "mode": args.mode,
        "root_help_exit": code,
        "discovered": len(subcommands),
        "help_pages": len(usable),
        "with_required_flags": sum(1 for f in required.values() if f),
        "subcommands": usable,
        "required": required,
    }
    (args.out_dir / "_summary.json").write_text(json.dumps(summary, indent=2) + "\n",
                                                encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("subcommands", "required")}, indent=2))


if __name__ == "__main__":
    main()
