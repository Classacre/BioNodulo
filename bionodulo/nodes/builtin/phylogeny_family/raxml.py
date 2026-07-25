"""RAxML 8.2.12 tree-inference owner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import path_value, validate_int
from .evidence import source_pinned
from .legacy import _RAxMLContract


@source_pinned("raxml")
class RAxMLNode(_RAxMLContract):
    NODE_ID = "raxml"
    REQUIRED_PATH_INPUTS = ("alignment",)
    REQUIRED_EXECUTABLES = ["raxmlHPC-PTHREADS"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not path_value(inputs.get("alignment")):
            return "Input 'alignment' must be a non-empty path-like value"
        validation = validate_int(inputs.get("threads", 4), "threads", minimum=1, maximum=64)
        if validation is not True:
            return validation
        if not str(inputs.get("model", "GTRGAMMA")).strip():
            return "Input 'model' must be non-empty"
        if not str(inputs.get("prefix", "tree")).strip():
            return "Input 'prefix' must be non-empty"
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        prefix = str(inputs.get("prefix", "tree"))
        result = "RAxML_bipartitions" if inputs.get("bootstrap") else "RAxML_bestTree"
        return [node_out / f"{result}.{prefix}"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = [
            "raxmlHPC-PTHREADS",
            "-s",
            str(inputs.get("alignment", "")),
            "-n",
            str(inputs.get("prefix", "tree")),
            "-m",
            str(inputs.get("model", "GTRGAMMA")),
            "-p",
            "12345",
            "-T",
            str(inputs.get("threads", 4)),
            "-w",
            str(Path(str(inputs.get("output", "."))).resolve()),
        ]
        if inputs.get("bootstrap"):
            command.extend(["-f", "a", "-x", "12345", "-#", "100"])
        return command
