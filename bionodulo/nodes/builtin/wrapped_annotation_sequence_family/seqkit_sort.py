"""Stable owner for ``seqkit_sort``."""

from pathlib import Path
from typing import Any

from .legacy import _SeqKitSortContract


class SeqKitSortNode(_SeqKitSortContract):
    NODE_ID = "seqkit_sort"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return super().PLAN_OUTPUTS(inputs, output_dir)
