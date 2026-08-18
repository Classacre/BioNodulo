"""Modkit 0.6.4 per-read modified-base extraction with explicit BAM index."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin._bam_index import validate_colocated_bam_index
from bionodulo.nodes.builtin._reference_sidecars import (
    validate_colocated_reference_index,
)

from .adapter import (
    LongReadCommandNode,
    option_value,
    stage_file,
    validate_int,
)

MODES = ("full", "calls")


def parse_motifs(value: Any) -> list[tuple[str, int]]:
    """Parse 'CG,0;DRACH,2'-style motif/offset pairs for repeated --motif flags."""
    raw = str(value or "").strip()
    if not raw:
        return []
    motifs: list[tuple[str, int]] = []
    for token in raw.replace(";", " ").split():
        name, separator, offset_text = token.partition(",")
        if not separator:
            name, separator, offset_text = token.partition(":")
        if not separator or not name:
            raise ValueError(f"malformed motif token: {token}")
        try:
            offset = int(offset_text)
        except ValueError as exc:
            raise ValueError(f"motif offset must be an integer: {token}") from exc
        motifs.append((name, offset))
    return motifs


class ModkitExtractNode(LongReadCommandNode):
    """Emit per-read per-position modified-base calls from an indexed modBAM."""

    NODE_ID = "modkit_extract"
    DISPLAY_NAME = "Modkit Extract"
    DESCRIPTION = (
        "Run modkit extract on an indexed modBAM to emit per-read modified-base records: "
        "mode 'full' outputs mod_qual probabilities per base per read, mode 'calls' outputs "
        "thresholded call_prob/call_code records using the modkit pileup thresholding algorithm"
    )
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "modkit",
        "extract",
        "modified bases",
        "modBAM",
        "m6A",
        "per-read calls",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("extracted",)
    OUTPUT_FILENAMES = ("extracted.tsv",)
    REQUIRED_PATH_INPUTS = ("bam", "bam_index")
    REQUIRED_EXECUTABLES = ["modkit"]
    REQUIRED_CONDA_PACKAGES = ["ont-modkit"]
    PACKAGE_CONSTRAINT = "ont-modkit = 0.6.4"
    VERSION = "0.6.4"
    GIT_URL = "https://github.com/nanoporetech/modkit.git"
    GIT_COMMIT = "cd85862f71d3bfc289f12adc1052a2e574c95e0f"
    SOURCE_TAG = "v0.6.4"
    DOCUMENTATION_URL = "https://nanoporetech.github.io/modkit/intro_extract.html"
    UPSTREAM_SOURCE = "src/extract/subcommand.rs; src/bin/main.rs"
    SOURCE_AUTHORITIES = {
        "argv_parser": "src/extract/subcommand.rs:ModBamExtract",
        "bam_index_discovery": "src/extract/subcommand.rs:region extraction requires input.bam.bai",
        "native_output": "src/extract/subcommand.rs:extract full/calls table writer",
    }
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    EXIT_SEMANTICS = (
        "Clap rejects invalid option combinations; extract errors print their cause "
        "chain and exit 1. Successful execution returns 0."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": (
                    "BAM",
                    {"description": "modBAM carrying MM/ML modified-base tags"},
                ),
                "bam_index": (
                    "BAI",
                    {"description": "Exact colocated <bam>.bai index required for --region parallelism"},
                ),
            },
            "optional": {
                "mode": (
                    "STRING",
                    {
                        "default": "full",
                        "options": list(MODES),
                        "description": (
                            "'full' emits mod_qual probabilities; 'calls' emits thresholded "
                            "call_prob/call_code records"
                        ),
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 256}),
                "region": (
                    "STRING",
                    {"default": "", "description": "Region string such as 'chr20' or 'chr1:1-1000'"},
                ),
                "num_reads": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Limit reads processed to manage output size; 0 omits the flag"},
                ),
                "motif": (
                    "STRING",
                    {
                        "default": "",
                        "description": (
                            "Motif:offset pairs separated by spaces or ';' (e.g. 'CG,0;DRACH,2'); "
                            "each pair appends '--motif <name> <offset>' and enables the motifs column"
                        ),
                    },
                ),
                "cpg": (
                    "BOOLEAN",
                    {"default": False, "description": "Only output records at CpG motifs (requires reference)"},
                ),
                "reference": (
                    "FASTA",
                    {"default": "", "description": "Reference FASTA for ref_position/chrom, kmer context, and motifs"},
                ),
                "reference_index": (
                    "FASTA_INDEX",
                    {"default": "", "description": "Exact colocated <reference>.fai index"},
                ),
                "filter_threshold": (
                    "STRING",
                    {
                        "default": "",
                        "description": (
                            "calls-mode threshold, global ('0.7') or per-canonical-base ('A:0.8'); "
                            "empty omits the flag"
                        ),
                    },
                ),
                "mod_threshold": (
                    "STRING",
                    {
                        "default": "",
                        "description": "calls-mode per-modification threshold such as 'a:0.9'; empty omits the flag",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_colocated_bam_index(inputs)
        if validation is not True:
            return validation
        for key, default, minimum, maximum in (
            ("threads", 4, 1, 256),
            ("num_reads", 0, 0, 2_147_483_646),
        ):
            validation = validate_int(
                option_value(inputs, key, default),
                key,
                minimum=minimum,
                maximum=maximum,
            )
            if validation is not True:
                return validation
        mode = str(option_value(inputs, "mode", "full") or "full")
        if mode not in MODES:
            return f"Input 'mode' must be one of: {', '.join(MODES)}"
        for key in ("filter_threshold", "mod_threshold"):
            if option_value(inputs, key, "") and mode != "calls":
                return f"Input '{key}' is only valid with mode 'calls'"
        try:
            motifs = parse_motifs(option_value(inputs, "motif", ""))
        except ValueError as exc:
            return f"Input 'motif' must be motif:offset pairs separated by spaces or ';' ({exc})"
        reference_supplied = inputs.get("reference") not in (None, "")
        index_supplied = inputs.get("reference_index") not in (None, "")
        needs_reference = bool(option_value(inputs, "cpg", False)) or bool(motifs)
        if needs_reference and not (reference_supplied and index_supplied):
            return "Inputs 'reference' and 'reference_index' are required for motif annotation"
        if reference_supplied or index_supplied:
            validation = validate_colocated_reference_index(inputs)
            if validation is not True:
                return validation
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Any]) -> None:
        """Stage each implicit sidecar beside the file Modkit will open."""
        node_dir = outputs[0].parent
        bam_dir = node_dir / "inputs" / "bam"
        bam_target = bam_dir / Path(str(inputs["bam"])).name
        bam_index_target = Path(f"{bam_target}.bai")
        stage_file(str(inputs["bam"]), bam_target)
        stage_file(str(inputs["bam_index"]), bam_index_target)
        inputs["bam"] = str(bam_target)
        inputs["bam_index"] = str(bam_index_target)

        if inputs.get("reference"):
            reference_dir = node_dir / "inputs" / "reference"
            reference_target = reference_dir / Path(str(inputs["reference"])).name
            reference_index_target = Path(f"{reference_target}.fai")
            stage_file(str(inputs["reference"]), reference_target)
            stage_file(str(inputs["reference_index"]), reference_index_target)
            inputs["reference"] = str(reference_target)
            inputs["reference_index"] = str(reference_index_target)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        mode = str(option_value(inputs, "mode", "full") or "full")
        command = cls.checked_command(
            inputs,
            "modkit",
            "extract",
            mode,
            str(inputs["bam"]),
            f"{output}/extracted.tsv",
            "--threads",
            str(option_value(inputs, "threads", 4)),
        )
        num_reads = option_value(inputs, "num_reads", 0)
        if num_reads:
            command.extend(["--num-reads", str(num_reads)])
        if inputs.get("region"):
            command.extend(["--region", str(inputs["region"])])
        if inputs.get("reference"):
            command.extend(["--reference", str(inputs["reference"])])
        for name, offset in parse_motifs(option_value(inputs, "motif", "")):
            command.extend(["--motif", name, str(offset)])
        if option_value(inputs, "cpg", False):
            command.append("--cpg")
        filter_threshold = str(option_value(inputs, "filter_threshold", "") or "").strip()
        if filter_threshold:
            command.extend(["--filter-threshold", filter_threshold])
        mod_threshold = str(option_value(inputs, "mod_threshold", "") or "").strip()
        if mod_threshold:
            command.extend(["--mod-threshold", mod_threshold])
        return command
