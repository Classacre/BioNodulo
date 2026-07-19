"""Stable owner for ``seqkit_head``."""

from pathlib import Path
from typing import Any

from .legacy import _SeqKitHeadContract


class SeqKitHeadNode(_SeqKitHeadContract):
    NODE_ID = "seqkit_head"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return super().PLAN_OUTPUTS(inputs, output_dir)
