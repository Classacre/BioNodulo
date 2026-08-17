"""ViennaRNA ``RNAplfold`` local accessibility node."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .adapter import (
    RNAStructureCommandNode,
    parse_lunp,
    validate_int,
)


SOURCE_LUNP_FILENAME = "rnaplfold_0001_lunp"


class RNAplfoldAccessibilityNode(RNAStructureCommandNode):
    """Compute local pairing probabilities and per-position accessibility."""

    NODE_ID = "rnaplfold_accessibility"
    DISPLAY_NAME = "RNAplfold Accessibility"
    DESCRIPTION = (
        "Compute RNAplfold local base-pair probabilities and mean unpaired-region "
        "probabilities (accessibility) for one RNA record."
    )
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "ViennaRNA",
        "RNAplfold",
        "local folding",
        "accessibility",
        "unpaired probability",
        "lunp",
        "sliding window",
    ]
    RETURN_TYPES = ("STRING", "JSON")
    RETURN_NAMES = ("accessibility", "summary")
    OUTPUT_FILENAMES = ("accessibility.lunp", "accessibility.json")
    REQUIRED_SEQUENCE_INPUTS = ("fasta", "sequence")
    REQUIRED_EXECUTABLES = ["RNAplfold"]
    DOCUMENTATION_URL = "https://www.tbi.univie.ac.at/RNA/RNAplfold.1.html"
    RUN_IN_NODE_OUTPUT_DIR = True
    SINGLE_RECORD_INPUT = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "fasta": ("FASTA", {"description": "Input FASTA with exactly one RNA record"}),
                "sequence": (
                    "STRING",
                    {"multiline": True, "default": "", "description": "Inline RNA/DNA sequence used when no FASTA is given"},
                ),
                "window_size": ("INT", {"default": 120, "min": 1, "max": 5000}),
                "max_span": ("INT", {"default": 80, "min": 1, "description": "Maximum base pair span; at most window_size"}),
                "unpaired_length": ("INT", {"default": 25, "min": 1, "max": 100, "description": "Longest unpaired region tracked"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if inputs.get("fasta", "") in (None, "") and inputs.get("sequence", "") in (None, ""):
            return "Provide exactly one of 'fasta' or 'sequence'"
        validation = validate_int(inputs.get("window_size", 120), "window_size", minimum=1, maximum=5000)
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("max_span", 80), "max_span", minimum=1)
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("unpaired_length", 25), "unpaired_length", minimum=1, maximum=100)
        if validation is not True:
            return validation
        if int(inputs.get("max_span", 80)) > int(inputs.get("window_size", 120)):
            return "Input 'max_span' must not exceed 'window_size'"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        cls.stage_input(inputs, outputs)

    @classmethod
    def REQUIRED_OUTPUT_PATHS(cls, inputs: dict[str, Any], outputs: list[Path]) -> list[Path]:
        del inputs, outputs
        return []

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "RNAplfold")
        command.extend(
            [
                "-W",
                str(inputs.get("window_size", 120)),
                "-L",
                str(inputs.get("max_span", 80)),
                "-u",
                str(inputs.get("unpaired_length", 25)),
            ]
        )
        command.extend(["--auto-id", "--id-prefix=rnaplfold", str(cls.staged_input_path(inputs))])
        return command

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        outputs = [Path(path) for path in await super().run(**kwargs)]
        node_dir = outputs[0].parent
        source = node_dir / SOURCE_LUNP_FILENAME
        if not source.is_file():
            raise RuntimeError(f"RNAplfold completed but did not create expected output(s): {source}")
        os.replace(source, outputs[0])
        rows = parse_lunp(outputs[0])
        values = [row["p_unpaired"] for row in rows]
        payload = {
            "tool": "RNAplfold",
            "window_size": int(kwargs.get("window_size", 120)),
            "max_span": int(kwargs.get("max_span", 80)),
            "unpaired_length": int(kwargs.get("unpaired_length", 25)),
            "position_count": len(rows),
            "mean_p_unpaired": sum(values) / len(values),
            "min_p_unpaired": min(values),
            "max_p_unpaired": max(values),
            "per_position": rows,
        }
        outputs[1].write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return tuple(str(path) for path in outputs)
