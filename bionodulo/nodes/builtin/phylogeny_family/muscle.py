"""MUSCLE 5.3 alignment owner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import path_value, validate_int
from .evidence import source_pinned
from .legacy import _MUSCLEContract


@source_pinned("muscle")
class MUSCLENode(_MUSCLEContract):
    NODE_ID = "muscle"
    REQUIRED_PATH_INPUTS = ("sequences",)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not path_value(inputs.get("sequences")):
            return "Input 'sequences' must be a non-empty path-like value"
        validation = validate_int(inputs.get("maxiters", 0), "maxiters", minimum=0)
        if validation is not True:
            return validation
        if inputs.get("diags"):
            return "Input 'diags' is not supported by the pinned MUSCLE 5.3 help contract"
        if inputs.get("stable"):
            return "Input 'stable' is not supported by the pinned MUSCLE 5.3 help contract"
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "alignment.aln.fasta"]
