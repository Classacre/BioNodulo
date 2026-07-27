"""BWA index node with a complete, colocated reference bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .adapter import (
    BWA_INDEX_DIRECTORY,
    BWA_INDEX_FASTA,
    BwaCommandNode,
    bwa_source_urls,
    find_index_prefix,
    path_value,
    stage_file,
)


class BWAIndexNode(BwaCommandNode):
    """Stage a reference FASTA and build its complete BWA index sibling set."""

    NODE_ID = "bwa_index"
    DISPLAY_NAME = "BWA Index"
    DESCRIPTION = "Stage a reference FASTA and build its complete BWA index bundle"
    SEARCH_ALIASES = ["bwa", "index", "reference index", "fm-index"]
    RETURN_TYPES = ("INDEX_DIR",)
    RETURN_NAMES = ("indexed_reference",)
    UPSTREAM_SOURCE = "bwtindex.c"
    SOURCE_PATHS = ("bwa.1", "bwtindex.c", "bwa.c", "bntseq.c")
    SOURCE_URLS = bwa_source_urls(*SOURCE_PATHS)
    ALGORITHMS = ("auto", "is", "bwtsw", "rb2")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "Reference FASTA to index"}),
            },
            "optional": {
                "algorithm": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": list(cls.ALGORITHMS),
                        "description": "BWT construction algorithm; auto lets BWA choose by reference size",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / BWA_INDEX_DIRECTORY]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if path_value(inputs.get("reference")) is None:
            return "Input 'reference' must be a non-empty path-like value"
        algorithm = inputs.get("algorithm", "auto")
        if algorithm not in cls.ALGORITHMS:
            return f"algorithm must be one of: {', '.join(cls.ALGORITHMS)}"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        source = Path(path_value(inputs["reference"]) or "")
        index_dir = outputs[0]
        index_dir.mkdir(parents=True, exist_ok=True)
        staged_reference = index_dir / BWA_INDEX_FASTA
        stage_file(source, staged_reference)
        inputs["reference"] = str(staged_reference)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        reference = str(inputs.get("reference", ""))
        command = ["bwa", "index"]
        algorithm = inputs.get("algorithm", "auto")
        if algorithm != "auto":
            command.extend(["-a", str(algorithm)])
        command.extend(["-p", reference, reference])
        return command

    @classmethod
    def VERIFY_OUTPUTS(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        """Verify before the shared cache is written, not after run() returns."""
        if outputs:
            find_index_prefix(outputs[0])

    @classmethod
    def reference_cache_id(cls, inputs: dict[str, Any]) -> Optional[str]:
        from bionodulo.execution import reference_cache as _rc

        return _rc.compute_ref_id(
            "bwa",
            [
                _rc.file_identity(inputs.get("reference", "")),
                f"bwa-{cls.VERSION}",
                str(inputs.get("algorithm", "auto")),
            ],
        )
