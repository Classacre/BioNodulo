"""Clustal Omega 1.2.4 alignment owner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import path_value, validate_choice, validate_int
from .evidence import source_pinned
from .legacy import _ClustalOContract


@source_pinned("clustalo")
class ClustalONode(_ClustalOContract):
    NODE_ID = "clustalo"
    REQUIRED_PATH_INPUTS = ("input",)
    OUTPUT_FORMATS = ("fasta", "clustal", "msf", "phylip", "selex", "stockholm", "vienna")
    OUTPUT_EXTENSIONS = {
        "fasta": ".fasta",
        "clustal": ".aln",
        "msf": ".msf",
        "phylip": ".phy",
        "selex": ".slx",
        "stockholm": ".stk",
        "vienna": ".vie",
    }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not path_value(inputs.get("input")):
            return "Input 'input' must be a non-empty path-like value"
        validation = validate_int(inputs.get("threads", 4), "threads", minimum=1, maximum=64)
        if validation is not True:
            return validation
        return validate_choice(inputs.get("outfmt", "fasta"), "outfmt", cls.OUTPUT_FORMATS)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        outfmt = str(inputs.get("outfmt", "fasta"))
        extension = cls.OUTPUT_EXTENSIONS.get(outfmt, ".fasta")
        return [node_out / f"alignment{extension}"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        outfmt = str(inputs.get("outfmt", "fasta"))
        extension = cls.OUTPUT_EXTENSIONS.get(outfmt, ".fasta")
        command = [
            "clustalo",
            "-i",
            str(inputs.get("input", "")),
            "-o",
            f"{inputs.get('output', '.')}/alignment{extension}",
            "--threads",
            str(inputs.get("threads", 4)),
            "--force",
        ]
        if inputs.get("outfmt"):
            command.extend(["--outfmt", outfmt])
        return command
