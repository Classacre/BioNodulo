"""Stable owner for ``seqkit_split2``."""

from pathlib import Path
from typing import Any

from .legacy import _SeqKitSplit2Contract


class SeqKitSplit2Node(_SeqKitSplit2Contract):
    NODE_ID = "seqkit_split2"
    OUTPUT_NAME_BY_BASENAME = {
        "split_files": "split_files",
        "paired_split_files": "paired_split_files",
    }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return super().PLAN_OUTPUTS(inputs, output_dir)
