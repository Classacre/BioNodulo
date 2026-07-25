"""RAxML-NG 1.2.2 tree-inference owner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import path_value, validate_int
from .evidence import source_pinned
from .legacy import _RAxMLNGContract


@source_pinned("raxml_ng")
class RAxMLNGNode(_RAxMLNGContract):
    NODE_ID = "raxml_ng"
    REQUIRED_PATH_INPUTS = ("alignment",)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not path_value(inputs.get("alignment")):
            return "Input 'alignment' must be a non-empty path-like value"
        validation = validate_int(inputs.get("threads", 4), "threads", minimum=1, maximum=64)
        if validation is not True:
            return validation
        if not str(inputs.get("model", "GTR+G")).strip():
            return "Input 'model' must be non-empty"
        validation = validate_int(
            inputs.get("bootstrap_replicates", 100),
            "bootstrap_replicates",
            minimum=0,
            maximum=10000,
        )
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("seed", 1), "seed", minimum=0)
        if validation is not True:
            return validation
        if inputs.get("tree_search", True) is False:
            return "RAxML-NG --evaluate requires a --tree input not exposed by this stable node"
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        prefix = Path(output_dir) / cls.NODE_ID / "raxml_ng"
        prefix.parent.mkdir(parents=True, exist_ok=True)
        if not inputs:
            return [
                Path(f"{prefix}.raxml.bestTree"),
                Path(f"{prefix}.raxml.bootstraps"),
            ]
        outputs = [Path(f"{prefix}.raxml.bestTree")]
        if inputs.get("bootstrap_replicates", 100):
            outputs.append(Path(f"{prefix}.raxml.bootstraps"))
        return outputs

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        prefix = f"{inputs.get('output', '.')}/raxml_ng"
        command = [
            "raxml-ng",
            "--msa",
            str(inputs.get("alignment", "")),
            "--model",
            str(inputs.get("model", "GTR+G")),
            "--prefix",
            prefix,
            "--threads",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("seed") not in (None, ""):
            command.extend(["--seed", str(inputs["seed"])])
        bootstrap_replicates = int(inputs.get("bootstrap_replicates", 100))
        if bootstrap_replicates:
            command.extend(["--all", "--bs-trees", str(bootstrap_replicates)])
        else:
            command.append("--search")
        if inputs.get("outgroup"):
            command.extend(["--outgroup", str(inputs["outgroup"])])
        return command
