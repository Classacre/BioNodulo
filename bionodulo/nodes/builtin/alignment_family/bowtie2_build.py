"""Build a complete Bowtie2 index bundle from one FASTA reference."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .bowtie2_adapter import BOWTIE2_SUFFIX_FAMILIES, Bowtie2CommandNode
from .fm_index_bundle import find_index_bundle, path_value


class Bowtie2BuildNode(Bowtie2CommandNode):
    """Build Bowtie2's six-file small or large index sibling set."""

    NODE_ID = "bowtie2_build"
    DISPLAY_NAME = "Bowtie2 Build"
    DESCRIPTION = "Build a complete Bowtie2 index bundle from a reference FASTA"
    SEARCH_ALIASES = ["bowtie2", "build", "index", "fm-index"]
    RETURN_TYPES = ("INDEX_DIR",)
    RETURN_NAMES = ("index",)
    REQUIRED_EXECUTABLES = ["bowtie2-build"]
    UPSTREAM_WRAPPER = "bowtie2-build"
    UPSTREAM_SOURCE = "bt2_build.cpp"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "Reference FASTA to index"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        index_dir = Path(output_dir) / cls.NODE_ID / "index"
        index_dir.mkdir(parents=True, exist_ok=True)
        return [index_dir]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation

        reference = path_value(inputs.get("reference"))
        if reference is None:
            return "Input 'reference' must be a non-empty path-like value"
        if not Path(reference).is_file():
            return f"Reference FASTA not found: {reference}"

        threads = inputs.get("threads", 1)
        if isinstance(threads, bool) or not isinstance(threads, int):
            return "threads must be an integer"
        if not 1 <= threads <= 64:
            return "threads must be between 1 and 64"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        outputs[0].mkdir(parents=True, exist_ok=True)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        prefix = output / "index" / "index"
        return [
            "bowtie2-build",
            "--threads",
            str(inputs.get("threads", 1)),
            str(inputs.get("reference", "")),
            str(prefix),
        ]

    async def run(self, **kwargs: Any) -> Any:
        result = await super().run(**kwargs)
        if isinstance(result, tuple) and result:
            find_index_bundle(
                result[0],
                label="Bowtie2",
                suffix_families=BOWTIE2_SUFFIX_FAMILIES,
            )
        return result

    @classmethod
    def reference_cache_id(cls, inputs: dict[str, Any]) -> Optional[str]:
        from bionodulo.execution import reference_cache as _rc

        return _rc.compute_ref_id(
            "bowtie2",
            [
                _rc.file_identity(inputs.get("reference", "")),
                f"bowtie2-{cls.VERSION}",
            ],
        )
