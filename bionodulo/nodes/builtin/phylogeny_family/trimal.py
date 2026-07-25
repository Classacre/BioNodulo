"""trimAl 1.4.1 alignment-trimming owner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import path_value, validate_choice
from .evidence import source_pinned
from .legacy import _TrimAlContract


@source_pinned("trimal")
class TrimAlNode(_TrimAlContract):
    NODE_ID = "trimal"
    REQUIRED_PATH_INPUTS = ("alignment",)
    AUTOMATED_MODES = ("automated1", "strict", "strictplus", "gappyout")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not path_value(inputs.get("alignment")):
            return "Input 'alignment' must be a non-empty path-like value"
        return validate_choice(
            inputs.get("automated", "automated1"),
            "automated",
            cls.AUTOMATED_MODES,
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        if not inputs:
            return [node_out / "trimmed.fasta", node_out / "stats.stats.txt"]
        outputs = [node_out / "trimmed.fasta"]
        if inputs.get("htmlout"):
            outputs.append(node_out / "stats.html")
        return outputs
