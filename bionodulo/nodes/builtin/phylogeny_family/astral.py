"""ASTRAL-III 5.7.8 species-tree owner."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .evidence import source_pinned
from .legacy import _ASTRALContract


@source_pinned("astral")
class ASTRALNode(_ASTRALContract):
    NODE_ID = "astral"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        if not inputs.get("_runtime_contract"):
            return super().render_command(inputs)

        output_dir = Path(str(inputs.get("output", ".")))
        command = (
            f"mkdir -p {shlex.quote(str(output_dir))} && "
            f"cd {shlex.quote(str(output_dir))} && "
            f"astral --input {shlex.quote(str(inputs.get('input', '')))} "
            f"--branch-annotate {shlex.quote(cls._branch_annotate(inputs))} "
            f"--output ./output.tre --lambda {shlex.quote(str(cls._lambda_value(inputs)))} "
            f"2> {shlex.quote(str(output_dir / 'log_output.txt'))}"
        )
        if cls._export_branch_annotations(inputs):
            command += (
                " && mv freqQuad.csv "
                f"{shlex.quote(str(output_dir / 'branch_annotations.tsv'))}"
            )
        return command

    async def run(self, **kwargs: Any) -> Any:
        kwargs["_runtime_contract"] = True
        return await CommandNode.run(self, **kwargs)
