"""Build one pangenome graph with PGGB 0.7.4."""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

from .pggb_adapter import PGGBCommandNode, path_value


_POA_TARGET_RE = re.compile(r"^[1-9][0-9]*(?:,[1-9][0-9]*)*$")


def _number(value: int | float) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)


class PGGBNode(PGGBCommandNode):
    """Run PGGB on one multi-sequence FASTA and normalize its final graph names."""

    NODE_ID = "pggb"
    DISPLAY_NAME = "PGGB Build"
    DESCRIPTION = "Build a reference-free pangenome graph from one indexed multi-sequence FASTA"
    SEARCH_ALIASES = ["pggb", "pangenome graph builder", "wga", "all-vs-all", "graph construction"]
    RETURN_TYPES = ("GFA", "ODGI")
    RETURN_NAMES = ("smooth_gfa", "smooth_odgi")
    GFA_FILENAME = "smooth_gfa.gfa"
    ODGI_FILENAME = "smooth_odgi.og"
    PREVIOUS_VERSIONS = ["0.7.3"]
    MIGRATIONS = [
        {
            "from_version": "0.7.3",
            "to_version": "0.7.4",
            "description": (
                "Replace graph_poas with poa_length_target; remove consensus_spec "
                "and do_layout; smooth_odgi replaces the undocumented consensus output."
            ),
        }
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Multi-sequence FASTA containing all haplotypes"}),
                "threads": ("INT", {"default": 1, "min": 1}),
            },
            "optional": {
                "num_haplotypes": (
                    "INT",
                    {"default": 0, "min": 0, "description": "0 lets PGGB infer PanSN haplotypes from the FASTA index"},
                ),
                "map_pct_id": ("FLOAT", {"default": 90.0, "min": 0.0, "max": 100.0}),
                "segment_length": ("INT", {"default": 5000, "min": 1}),
                "min_match_length": ("INT", {"default": 23, "min": 1}),
                "poa_length_target": (
                    "STRING",
                    {"default": "700,1100", "description": "Comma-separated smoothxg POA target lengths (-G)"},
                ),
                "do_viz": (
                    "BOOLEAN",
                    {"default": True, "description": "Render PGGB's default 1D and 2D diagnostics"},
                ),
                "stats": ("BOOLEAN", {"default": False, "description": "Generate ODGI statistics (-S)"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / cls.GFA_FILENAME, node_out / cls.ODGI_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation

        fasta_text = path_value(inputs.get("input_fasta"))
        if fasta_text is None:
            return "input_fasta must be a non-empty path-like value"
        fasta = Path(fasta_text)
        if not fasta.is_file():
            return f"input_fasta does not exist: {fasta_text}"
        if fasta.stat().st_size == 0:
            return f"input_fasta is empty: {fasta_text}"

        threads = inputs.get("threads", 1)
        if isinstance(threads, bool) or not isinstance(threads, int):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be at least 1"

        num_haplotypes = inputs.get("num_haplotypes", 0)
        if isinstance(num_haplotypes, bool) or not isinstance(num_haplotypes, int):
            return "num_haplotypes must be an integer"
        if num_haplotypes < 0:
            return "num_haplotypes must be zero or greater"

        map_pct_id = inputs.get("map_pct_id", 90.0)
        if isinstance(map_pct_id, bool) or not isinstance(map_pct_id, (int, float)):
            return "map_pct_id must be a number"
        if not 0 < float(map_pct_id) <= 100:
            return "map_pct_id must be greater than 0 and at most 100"

        for name, default in (("segment_length", 5000), ("min_match_length", 23)):
            value = inputs.get(name, default)
            if isinstance(value, bool) or not isinstance(value, int):
                return f"{name} must be an integer"
            if value < 1:
                return f"{name} must be at least 1"

        poa_target = str(inputs.get("poa_length_target", "700,1100") or "")
        if not _POA_TARGET_RE.fullmatch(poa_target):
            return "poa_length_target must be a comma-separated list of positive integers"

        if "graph_poas" in inputs:
            return "legacy graph_poas has no PGGB 0.7.4 equivalent; use poa_length_target for -G"
        if str(inputs.get("consensus_spec", "") or "").strip():
            return "consensus_spec is unavailable in PGGB 0.7.4; the upstream -C option is disabled"
        if "do_layout" in inputs:
            return "legacy do_layout is unavailable in PGGB 0.7.4"
        return True

    @classmethod
    def pggb_argv(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        command = ["pggb", "-i", str(inputs.get("input_fasta", "")), "-o", output]
        num_haplotypes = int(inputs.get("num_haplotypes", 0) or 0)
        if num_haplotypes:
            command.extend(["-n", str(num_haplotypes)])
        command.extend(
            [
                "-t",
                str(inputs.get("threads", 1)),
                "-p",
                _number(inputs.get("map_pct_id", 90.0)),
                "-s",
                str(inputs.get("segment_length", 5000)),
                "-k",
                str(inputs.get("min_match_length", 23)),
                "-G",
                str(inputs.get("poa_length_target", "700,1100")),
            ]
        )
        if not inputs.get("do_viz", True):
            command.append("-v")
        if inputs.get("stats", False):
            command.append("-S")
        return command

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        input_fasta = str(inputs.get("input_fasta", ""))
        stable_gfa = output / cls.GFA_FILENAME
        stable_odgi = output / cls.ODGI_FILENAME
        output_q = shlex.quote(str(output))
        stable_gfa_q = shlex.quote(str(stable_gfa))
        stable_odgi_q = shlex.quote(str(stable_odgi))
        script = "\n".join(
            [
                "set -euo pipefail",
                shlex.join(["samtools", "faidx", input_fasta]),
                shlex.join(cls.pggb_argv(inputs)),
                "gfas=()",
                f"mapfile -d '' gfas < <(find {output_q} -maxdepth 1 -type f -name '*.final.gfa' -print0)",
                'if (( ${#gfas[@]} != 1 )); then printf "[bionodulo::pggb] expected exactly one *.final.gfa, found %s\\n" "${#gfas[@]}" >&2; exit 1; fi',
                "odgis=()",
                f"mapfile -d '' odgis < <(find {output_q} -maxdepth 1 -type f -name '*.final.og' -print0)",
                'if (( ${#odgis[@]} != 1 )); then printf "[bionodulo::pggb] expected exactly one *.final.og, found %s\\n" "${#odgis[@]}" >&2; exit 1; fi',
                f'cp -- "${{gfas[0]}}" {stable_gfa_q}',
                f'cp -- "${{odgis[0]}}" {stable_odgi_q}',
                f"test -s {stable_gfa_q}",
                f"test -s {stable_odgi_q}",
            ]
        )
        return ["bash", "-o", "pipefail", "-c", script]
