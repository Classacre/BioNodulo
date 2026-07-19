"""FastTree 2.1.11 tree-inference owner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .adapter import path_value
from .evidence import source_pinned
from .legacy import _FastTreeContract


@source_pinned("fasttree")
class FastTreeNode(_FastTreeContract):
    NODE_ID = "fasttree"
    REQUIRED_PATH_INPUTS = ("alignment",)
    STDOUT_OUTPUT_INDEX = 0

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not path_value(inputs.get("alignment")):
            return "Input 'alignment' must be a non-empty path-like value"
        if inputs.get("gtr") and not inputs.get("nucleotide"):
            return "Input 'gtr' requires nucleotide mode"
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "tree.nwk"]

    async def run(self, **kwargs: Any) -> Any:
        return await CommandNode.run(self, **kwargs)
