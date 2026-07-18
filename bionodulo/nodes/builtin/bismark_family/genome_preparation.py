"""Bismark Bowtie2 genome preparation with a self-contained output bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    PREPARED_GENOME_DIRECTORY,
    BismarkCommandNode,
    discover_fasta_files,
    path_value,
    stage_fasta_tier,
    validate_prepared_genome,
)


class BismarkGenomePreparationNode(BismarkCommandNode):
    """Copy the selected reference FASTAs and build both Bowtie2 bisulfite indexes."""

    NODE_ID = "bismark_genome_preparation"
    DISPLAY_NAME = "Bismark Genome Preparation"
    DESCRIPTION = "Stage reference FASTAs and build a complete CT/GA Bowtie2 genome bundle"
    SEARCH_ALIASES = ["bismark", "bisulfite", "genome preparation", "index", "wgbs", "prepare"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("genome_folder",)
    REQUIRED_EXECUTABLES = ["bismark_genome_preparation", "bowtie2-build"]
    REQUIRED_CONDA_PACKAGES = ["bismark", "bowtie2"]
    DOCUMENTATION_URL = "https://felixkrueger.github.io/Bismark/options/genome-preparation/"
    UPSTREAM_SOURCE = "rust/bismark/src/genome_prep"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genome_folder": (
                    "DIRECTORY",
                    {"description": "Folder containing top-level reference FASTA files"},
                ),
            },
            "optional": {
                "parallel": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "description": "Threads per indexer; values above 1 run two indexers concurrently",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / PREPARED_GENOME_DIRECTORY]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        genome_folder = path_value(inputs.get("genome_folder"))
        if genome_folder is None:
            return "Input 'genome_folder' must be a non-empty path-like value"
        try:
            discover_fasta_files(genome_folder)
        except (OSError, ValueError) as exc:
            return str(exc)
        parallel = inputs.get("parallel", 1)
        if isinstance(parallel, bool) or not isinstance(parallel, int):
            return "parallel must be an integer"
        if parallel < 1:
            return "parallel must be at least 1"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        source = Path(path_value(inputs.get("genome_folder")) or "")
        stage_fasta_tier(source, outputs[0])
        inputs["genome_folder"] = str(outputs[0])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        prepared = Path(str(inputs.get("output", inputs.get("output_dir", ".")))) / PREPARED_GENOME_DIRECTORY
        command = ["bismark_genome_preparation", "--bowtie2"]
        parallel = inputs.get("parallel", 1)
        if isinstance(parallel, int) and not isinstance(parallel, bool) and parallel > 1:
            command.extend(["--parallel", str(parallel)])
        command.append(str(prepared))
        return command

    async def run(self, **kwargs: Any) -> Any:
        result = await super().run(**kwargs)
        if isinstance(result, tuple) and result:
            validate_prepared_genome(result[0])
        return result
