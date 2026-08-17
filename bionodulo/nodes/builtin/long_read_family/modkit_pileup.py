"""Modkit 0.4.3 bedMethyl pileup with explicit BAM and FASTA indexes."""

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
    validate_number,
)


class ModkitPileupNode(LongReadCommandNode):
    """Tabulate modified-base calls from a sorted, indexed modBAM."""

    NODE_ID = "modkit_pileup"
    DISPLAY_NAME = "Modkit Pileup"
    DESCRIPTION = "Generate bedMethyl pileup from a sorted and indexed modified-base BAM"
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "modkit",
        "pileup",
        "bedMethyl",
        "modified bases",
        "methylation",
        "CpG",
    ]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("bedmethyl",)
    OUTPUT_FILENAMES = ("bedmethyl.bed",)
    REQUIRED_PATH_INPUTS = ("bam", "bam_index")
    REQUIRED_EXECUTABLES = ["modkit"]
    REQUIRED_CONDA_PACKAGES = ["ont-modkit"]
    PACKAGE_CONSTRAINT = "ont-modkit = 0.4.3"
    VERSION = "0.4.3"
    GIT_URL = "https://github.com/nanoporetech/modkit.git"
    GIT_COMMIT = "d13b97db2d221afc4a1db3616a7eccdc6858a313"
    SOURCE_TAG = "v0.4.3"
    DOCUMENTATION_URL = "https://nanoporetech.github.io/modkit/intro_pileup.html"
    UPSTREAM_SOURCE = "src/pileup/subcommand.rs; src/fasta.rs; src/bin/main.rs"
    SOURCE_AUTHORITIES = {
        "argv_parser": "src/pileup/subcommand.rs:ModBamPileup",
        "bam_index_discovery": "src/pileup/subcommand.rs:IndexedReader::from_path",
        "fasta_index_discovery": "src/fasta.rs:MotifLocationsLookup::from_paths",
        "native_output": "src/pileup/subcommand.rs:PileupWriter::new",
    }
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    EXIT_SEMANTICS = (
        "Clap rejects invalid option combinations; pileup errors print their cause "
        "chain and exit 1. Successful execution returns 0."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": (
                    "BAM",
                    {"description": "Coordinate-sorted BAM carrying MM/ML modified-base tags"},
                ),
                "bam_index": (
                    "BAI",
                    {"description": "Exact colocated <bam>.bai index required by modkit"},
                ),
            },
            "optional": {
                "reference": (
                    "FASTA",
                    {"default": "", "description": "Reference FASTA for CpG pileup"},
                ),
                "reference_index": (
                    "FASTA_INDEX",
                    {"default": "", "description": "Exact colocated <reference>.fai index"},
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 256}),
                "region": ("STRING", {"default": ""}),
                "max_depth": ("INT", {"default": 8000, "min": 1}),
                "cpg": ("BOOLEAN", {"default": False}),
                "combine_strands": ("BOOLEAN", {"default": False}),
                "no_filtering": ("BOOLEAN", {"default": False}),
                "filter_percentile": (
                    "FLOAT",
                    {"default": 0.1, "min": 0.0, "max": 1.0},
                ),
                "with_header": ("BOOLEAN", {"default": False}),
                "modified_bases": (
                    "STRING",
                    {
                        "default": "",
                        "description": (
                            "Comma-separated modified-base codes passed to --modified-bases "
                            "(e.g. 'm' for 5mC, 'a' for m6A). Empty omits the flag; non-5mC "
                            "mods are only reported when declared"
                        ),
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
            ("max_depth", 8000, 1, 2_147_483_646),
        ):
            validation = validate_int(
                option_value(inputs, key, default),
                key,
                minimum=minimum,
                maximum=maximum,
            )
            if validation is not True:
                return validation
        validation = validate_number(
            option_value(inputs, "filter_percentile", 0.1),
            "filter_percentile",
            minimum=0,
            maximum=1,
        )
        if validation is not True:
            return validation
        if option_value(inputs, "no_filtering", False) and float(
            option_value(inputs, "filter_percentile", 0.1)
        ) != 0.1:
            return (
                "Input 'filter_percentile' cannot be combined with 'no_filtering'; "
                "the pinned Modkit parser treats them as mutually exclusive"
            )
        reference_supplied = inputs.get("reference") not in (None, "")
        index_supplied = inputs.get("reference_index") not in (None, "")
        needs_reference = bool(option_value(inputs, "cpg", False) or option_value(inputs, "combine_strands", False))
        if needs_reference and not (reference_supplied and index_supplied):
            return "Inputs 'reference' and 'reference_index' are required for CpG strand handling"
        if reference_supplied or index_supplied:
            validation = validate_colocated_reference_index(inputs)
            if validation is not True:
                return validation
        if option_value(inputs, "combine_strands", False) and not option_value(inputs, "cpg", False):
            return "Input 'combine_strands' requires 'cpg' in this focused contract"
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
        command = cls.checked_command(
            inputs,
            "modkit",
            "pileup",
            str(inputs["bam"]),
            f"{output}/bedmethyl.bed",
            "--threads",
            str(option_value(inputs, "threads", 4)),
            "--max-depth",
            str(option_value(inputs, "max_depth", 8000)),
        )
        if option_value(inputs, "no_filtering", False):
            command.append("--no-filtering")
        else:
            command.extend(
                [
                    "--filter-percentile",
                    str(option_value(inputs, "filter_percentile", 0.1)),
                ]
            )
        if inputs.get("region"):
            command.extend(["--region", str(inputs["region"])])
        if inputs.get("reference"):
            command.extend(["--ref", str(inputs["reference"])])
        if option_value(inputs, "cpg", False):
            command.append("--cpg")
        if option_value(inputs, "combine_strands", False):
            command.append("--combine-strands")
        if option_value(inputs, "with_header", False):
            command.append("--header")
        modified_bases = str(option_value(inputs, "modified_bases", "") or "").strip()
        if modified_bases:
            command.extend(["--modified-bases", *modified_bases.replace(" ", "").split(",")])
        return command
