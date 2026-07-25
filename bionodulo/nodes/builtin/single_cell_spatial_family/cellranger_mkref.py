"""10x Genomics Cell Ranger 9.0.1 reference-builder contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from bionodulo.nodes.command_node import CommandNode

from .adapter import path_value, validate_int


class CellRangerMkrefNode(CommandNode):
    """Build one Cell Ranger reference from a matched FASTA and GTF pair."""

    NODE_ID = "cellranger_mkref"
    DISPLAY_NAME = "Cell Ranger mkref"
    CATEGORY = "single_cell"
    DESCRIPTION = "Build a Cell Ranger 9.0.1 reference transcriptome from matched FASTA and GTF inputs."
    SEARCH_ALIASES = ["BioNodulo builtin", "Cell Ranger", "mkref", "10x", "reference", "transcriptome"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("reference",)
    REQUIRED_EXECUTABLES = ["cellranger"]
    REQUIRED_CONDA_PACKAGES: list[str] = []
    VERSION = "9.0.1"
    GIT_URL = "https://github.com/10XGenomics/cellranger.git"
    GIT_COMMIT = "6ebad209b8354353b4a9ee3eed1cb248d102af88"
    SOURCE_TAG = "cellranger-9.0.1"
    DOCUMENTATION_URL = "https://www.10xgenomics.com/support/software/cell-ranger/9.0/analysis/inputs/cr-3p-references"
    RELEASE_NOTES_URL = "https://www.10xgenomics.com/support/software/cell-ranger/9.0/release-notes"
    UPSTREAM_SOURCE = "lib/rust/cr_wrap/src/mkref.rs; lib/rust/cr_wrap/src/mrp_args.rs"
    PACKAGE_CONSTRAINT = "external Cell Ranger 9.0.1 binary; unavailable from conda-forge and Bioconda"
    DISTRIBUTION = "Restricted 10x Genomics source/binary distribution; worker provisioning is external."
    ENVIRONMENT = {
        "provisioning": "external_worker_binary",
        "executable": "cellranger",
        "version": "9.0.1",
        "platform": "linux-64",
        "telemetry": "disabled with TENX_DISABLE_TELEMETRY=1",
    }
    ENV_VARS = {"TENX_DISABLE_TELEMETRY": "1"}
    RUN_IN_NODE_OUTPUT_DIR = True
    SHELL = False
    EXPERIMENTAL = True
    EXIT_SEMANTICS = (
        "Cell Ranger exit code 0 plus the genome-named reference directory is success; "
        "invalid identifiers, mismatched inputs, indexing errors, and missing output fail the node."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fasta": ("FASTA", {"description": "Uncompressed reference genome FASTA"}),
                "gtf": ("GTF", {"description": "Gene annotation GTF matched to the FASTA"}),
                "genome_name": ("STRING", {"default": "custom_ref"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1, "description": "STAR index threads"}),
                "memory": ("INT", {"default": 16, "min": 1, "description": "Maximum memory in GiB"}),
                "ref_version": (
                    "STRING",
                    {"default": "", "advanced": True, "description": "Reference version stored in metadata"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / str(inputs.get("genome_name", "custom_ref"))]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("fasta", "gtf"):
            if not path_value(inputs.get(key)):
                return f"Input '{key}' must be a non-empty path-like value"
        genome_name = str(inputs.get("genome_name", ""))
        if not genome_name:
            return "Input 'genome_name' must not be empty"
        if any(not (char.isascii() and (char.isalnum() or char in "_-")) for char in genome_name):
            return "Input 'genome_name' may only contain ASCII letters, numbers, underscores, and hyphens"
        validation = validate_int(inputs.get("threads", 1), "threads", minimum=1)
        if validation is not True:
            return validation
        return validate_int(inputs.get("memory", 16), "memory", minimum=1)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = [
            "cellranger",
            "mkref",
            "--genome",
            str(inputs.get("genome_name", "custom_ref")),
            "--fasta",
            path_value(inputs.get("fasta")),
            "--genes",
            path_value(inputs.get("gtf")),
            "--nthreads",
            str(inputs.get("threads", 1)),
            "--memgb",
            str(inputs.get("memory", 16)),
            "--disable-ui",
        ]
        ref_version = str(inputs.get("ref_version", "") or "").strip()
        if ref_version:
            command.extend(["--ref-version", ref_version])
        return command

    @classmethod
    def reference_cache_id(cls, inputs: dict[str, Any]) -> Optional[str]:
        from bionodulo.execution import reference_cache as reference_cache

        return reference_cache.compute_ref_id(
            "cellranger",
            [
                reference_cache.file_identity(inputs.get("fasta", "")),
                reference_cache.file_identity(inputs.get("gtf", "")),
                str(inputs.get("genome_name", "custom_ref")),
                str(inputs.get("ref_version", "") or ""),
                f"cellranger-{cls.VERSION}",
            ],
        )
