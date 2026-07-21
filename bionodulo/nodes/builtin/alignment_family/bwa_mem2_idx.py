"""Build and validate a native BWA-MEM2 2.3 reference bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import stage_file
from .bwa_mem2_adapter import (
    BWA_MEM2_PREFIX,
    BwaMem2CommandNode,
    bwa_mem2_source_urls,
    find_index_prefix,
)
from .legacy_adapter import path_value


class BWAMem2IndexNode(BwaMem2CommandNode):
    """Build the five native BWA-MEM2 index siblings under one prefix."""

    NODE_ID = "bwa_mem2_idx"
    DISPLAY_NAME = "BWA-MEM2 Indexer"
    DESCRIPTION = "Build and validate a complete BWA-MEM2 2.3 reference index bundle."
    SEARCH_ALIASES = ["bwa-mem2", "index", "reference index"]
    RETURN_TYPES = ("BWA_MEM2_INDEX",)
    RETURN_NAMES = ("index",)
    UPSTREAM_SOURCE = "src/bwtindex.cpp"
    SOURCE_PATHS = ("README.md", "src/bwtindex.cpp", "src/FMI_search.cpp", "src/bntseq.cpp")
    SOURCE_URLS = bwa_mem2_source_urls(*SOURCE_PATHS)
    OUTPUT_DIRECTORY = "index"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"reference": ("FASTA", {"description": "Reference FASTA to index"})},
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        index_dir = Path(output_dir) / cls.NODE_ID / cls.OUTPUT_DIRECTORY
        index_dir.mkdir(parents=True, exist_ok=True)
        return [index_dir]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if path_value(inputs.get("reference")) is None:
            return "reference must be a non-empty path"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        staged_reference = outputs[0] / "reference.fa"
        stage_file(Path(str(inputs["reference"])), staged_reference)
        inputs["reference"] = str(staged_reference)
        inputs["index_prefix"] = str(outputs[0] / BWA_MEM2_PREFIX)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return [
            "bwa-mem2",
            "index",
            "-p",
            str(
                inputs.get(
                    "index_prefix", Path(str(inputs.get("output", "."))) / cls.OUTPUT_DIRECTORY / BWA_MEM2_PREFIX
                )
            ),
            str(inputs.get("reference", "")),
        ]

    async def run(self, **kwargs: Any) -> Any:
        result = await super().run(**kwargs)
        if isinstance(result, tuple) and result:
            find_index_prefix(result[0])
        return result
