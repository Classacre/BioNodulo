"""CRISPResso2 2.3.4 amplicon-editing analysis contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    CRISPRESSO2_COMMIT,
    CrisprCommandNode,
    crispresso_run_name,
    path_value,
    validate_integer_csv,
    validate_iupac_sequence,
)


class CRISPRESSO2Node(CrisprCommandNode):
    """Quantify editing outcomes from single- or paired-end amplicon reads."""

    NODE_ID = "crispresso2"
    DISPLAY_NAME = "CRISPRESSO2"
    DESCRIPTION = "Analyze CRISPR editing outcomes from amplicon sequencing with CRISPResso2."
    SEARCH_ALIASES = ["BioNodulo builtin", "CRISPResso", "CRISPResso2", "amplicon", "indel", "editing analysis"]
    RETURN_TYPES = ("HTML_REPORT", "DIRECTORY")
    RETURN_NAMES = ("report", "results_dir")
    REQUIRED_EXECUTABLES = ["CRISPResso"]
    REQUIRED_CONDA_PACKAGES = ["crispresso2"]
    CONDA_PACKAGE_CONSTRAINTS = {"crispresso2": "2.3.4"}
    VERSION = "2.3.4"
    GIT_URL = "https://github.com/pinellolab/CRISPResso2.git"
    GIT_COMMIT = CRISPRESSO2_COMMIT
    DOCUMENTATION_URL = "https://docs.crispresso.com/suite/core.html"
    CITATION_DOIS = ["10.1038/s41587-019-0032-3"]
    CITATION_URLS = ["https://doi.org/10.1038/s41587-019-0032-3"]
    CITATION_TEXT = "CRISPResso2 provides accurate and rapid genome editing sequence analysis."
    REQUIRED_PATH_INPUTS = ("r1",)
    UPSTREAM_SOURCE = "CRISPResso2/args.json; CRISPResso2/CRISPRessoCORE.py"
    EXIT_CODES = {
        0: "success",
        1: "invalid sequence alphabet",
        2: "invalid guide sequence",
        5: "read merging or trimming failure",
        6: "bad parameter",
        7: "no reads aligned",
        8: "autorun failure",
        9: "alignment failure",
        11: "coding-sequence failure",
        12: "duplicate FASTQ sequence ID",
        13: "no reads after filtering",
        14: "plot failure",
        -1: "unexpected failure",
    }
    EXIT_SEMANTICS = "CRISPResso2 reports typed non-zero failures; only exit code 0 is accepted."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "r1": ("FASTQ", {"description": "Forward FASTQ"}),
                "amplicon_seq": ("STRING", {"description": "Reference amplicon sequence(s)"}),
                "name": ("STRING", {"default": "crispresso_run", "description": "CRISPResso analysis name"}),
            },
            "optional": {
                "r2": ("FASTQ", {"description": "Reverse FASTQ"}),
                "guide_seq": ("STRING", {"default": "", "description": "Comma-separated guide sequence(s)"}),
                "quant_window_center": (
                    "STRING",
                    {"default": "-3", "description": "Comma-separated offsets from each guide's 3' end"},
                ),
                "quant_window_size": (
                    "STRING",
                    {"default": "1", "description": "Comma-separated quantification half-window sizes"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        run_dir = node_dir / f"CRISPResso_on_{crispresso_run_name(inputs)}"
        return [Path(f"{run_dir}.html"), run_dir]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_iupac_sequence(inputs.get("amplicon_seq", ""), "amplicon_seq", comma_separated=True)
        if validation is not True:
            return validation
        guide = inputs.get("guide_seq", "")
        if guide not in (None, ""):
            validation = validate_iupac_sequence(guide, "guide_seq", comma_separated=True)
            if validation is not True:
                return validation
        name = str(inputs.get("name", "") or "")
        if not name:
            return "Input 'name' must be non-empty"
        validation = validate_integer_csv(inputs.get("quant_window_center", "-3"), "quant_window_center")
        if validation is not True:
            return validation
        return validate_integer_csv(inputs.get("quant_window_size", "1"), "quant_window_size", minimum=0)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(
            inputs,
            "CRISPResso",
            "-r1",
            path_value(inputs.get("r1")),
            "-a",
            str(inputs.get("amplicon_seq", "")),
            "-o",
            str(inputs.get("output", inputs.get("output_dir", "."))),
            "--name",
            str(inputs.get("name", "crispresso_run")),
        )
        if path_value(inputs.get("r2")):
            command.extend(["-r2", path_value(inputs["r2"])])
        if inputs.get("guide_seq") not in (None, ""):
            command.extend(["-g", str(inputs["guide_seq"])])
        command.extend(
            [
                "-wc",
                str(inputs.get("quant_window_center", "-3")),
                "-w",
                str(inputs.get("quant_window_size", "1")),
            ]
        )
        return command
