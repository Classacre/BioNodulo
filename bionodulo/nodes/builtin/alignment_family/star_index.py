"""Build and validate a STAR genome-index directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .star_adapter import STAR_INDEX_MARKERS, STARCommandNode, path_value


class STARIndexNode(STARCommandNode):
    NODE_ID = "star_index"
    DISPLAY_NAME = "STAR Index"
    DESCRIPTION = "Build a STAR splice-aware genome index from FASTA and GTF"
    SEARCH_ALIASES = ["star", "index", "genome", "rna-seq"]
    RETURN_TYPES = ("INDEX_DIR",)
    RETURN_NAMES = ("index",)
    UPSTREAM_SOURCE = "source/Genome_genomeGenerate.cpp"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "Reference genome FASTA"}),
                "gtf": ("GTF", {"description": "Gene annotation GTF"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "genome_sa_index_nbases": ("INT", {"default": 14, "min": 1}),
                "sjdb_overhang": ("INT", {"default": 100, "min": 1, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        index_dir = Path(output_dir) / cls.NODE_ID / "index"
        index_dir.mkdir(parents=True, exist_ok=True)
        return [index_dir]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        outputs[0].mkdir(parents=True, exist_ok=True)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("reference", "gtf"):
            if path_value(inputs.get(key)) is None:
                return f"{key} must be a non-empty path-like value"
        validation = cls.validate_threads(inputs)
        if validation is not True:
            return validation
        for key, default in (("genome_sa_index_nbases", 14), ("sjdb_overhang", 100)):
            value = inputs.get(key, default)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                return f"{key} must be a positive integer"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        index_dir = cls.output_dir(inputs) / "index"
        return [
            "STAR",
            "--runMode",
            "genomeGenerate",
            "--genomeDir",
            str(index_dir),
            "--genomeFastaFiles",
            str(inputs.get("reference", "")),
            "--sjdbGTFfile",
            str(inputs.get("gtf", "")),
            "--runThreadN",
            str(inputs.get("threads", 8)),
            "--genomeSAindexNbases",
            str(inputs.get("genome_sa_index_nbases", 14)),
            "--sjdbOverhang",
            str(inputs.get("sjdb_overhang", 100)),
        ]

    @classmethod
    def VERIFY_OUTPUTS(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        """Verify before the shared cache is written, not after run() returns.

        STAR matters most here: this is the 30+ minute build the cache exists
        for, so a poisoned entry is both the costliest to have cached and the
        one every later run is most likely to stage instead of rebuilding.
        """
        if outputs:
            index_dir = Path(outputs[0])
            missing = [name for name in STAR_INDEX_MARKERS if not (index_dir / name).is_file()]
            if missing:
                raise RuntimeError(f"STAR index is incomplete; missing: {', '.join(missing)}")

    @classmethod
    def reference_cache_id(cls, inputs: dict[str, Any]) -> Optional[str]:
        from bionodulo.execution import reference_cache as _rc

        return _rc.compute_ref_id(
            "star",
            [
                _rc.file_identity(inputs.get("reference", "")),
                _rc.file_identity(inputs.get("gtf", "")),
                f"STAR{cls.VERSION}",
                f"sa{inputs.get('genome_sa_index_nbases', 14)}",
                f"oh{inputs.get('sjdb_overhang', 100)}",
            ],
        )


__all__ = ["STARIndexNode"]
