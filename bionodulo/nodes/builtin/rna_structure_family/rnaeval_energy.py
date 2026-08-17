"""ViennaRNA ``RNAeval`` structure-energy node."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .adapter import (
    RNAStructureCommandNode,
    normalize_sequence,
    validate_number,
    validate_sequence_string,
)


STRUCTURE_ALPHABET = frozenset(".()[]{}&")
TRAILING_ENERGY_RE = re.compile(r"\(\s*(-?\d+(?:\.\d+)?)\s*(?:=\s*(-?\d+(?:\.\d+)?)\s*\+\s*(-?\d+(?:\.\d+)?)\s*)?\)\s*$")
STAGED_EVAL_FILENAME = "input.txt"


def validate_structure_string(value: Any, key: str) -> bool | str:
    """Validate one dot-bracket structure parameter."""
    if not isinstance(value, str) or not value.strip():
        return f"Input '{key}' must be a non-empty dot-bracket structure"
    structure = "".join(value.split())
    if not structure:
        return f"Input '{key}' must be a non-empty dot-bracket structure"
    invalid = set(structure) - STRUCTURE_ALPHABET
    if invalid:
        return f"Input '{key}' contains non dot-bracket characters: {''.join(sorted(invalid))}"
    return True


class RNAevalEnergyNode(RNAStructureCommandNode):
    """Score one provided sequence and dot-bracket structure pair."""

    NODE_ID = "rnaeval_energy"
    DISPLAY_NAME = "RNAeval Energy"
    DESCRIPTION = "Evaluate the free energy of one provided RNA sequence and dot-bracket structure pair."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "ViennaRNA",
        "RNAeval",
        "energy evaluation",
        "score structure",
        "free energy",
    ]
    RETURN_TYPES = ("STRING", "JSON")
    RETURN_NAMES = ("raw_output", "energy")
    OUTPUT_FILENAMES = ("eval_stdout.txt", "energy.json")
    STDOUT_OUTPUT_INDEX = 0
    REQUIRED_EXECUTABLES = ["RNAeval"]
    DOCUMENTATION_URL = "https://www.tbi.univie.ac.at/RNA/RNAeval.1.html"
    RUN_IN_NODE_OUTPUT_DIR = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sequence": (
                    "STRING",
                    {"multiline": True, "default": "", "description": "RNA/DNA sequence string"},
                ),
                "structure": (
                    "STRING",
                    {"multiline": True, "default": "", "description": "Dot-bracket structure for the sequence"},
                ),
            },
            "optional": {
                "temperature": ("FLOAT", {"default": 37.0, "min": 0.0, "max": 100.0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_sequence_string(inputs.get("sequence"), "sequence")
        if validation is not True:
            return validation
        validation = validate_structure_string(inputs.get("structure"), "structure")
        if validation is not True:
            return validation
        if len(normalize_sequence(inputs["sequence"])) != len("".join(str(inputs["structure"]).split())):
            return "Input 'structure' length must equal 'sequence' length"
        return validate_number(inputs.get("temperature", 37.0), "temperature", minimum=0.0, maximum=100.0)

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        del outputs
        sequence = normalize_sequence(inputs["sequence"])
        structure = "".join(str(inputs["structure"]).split())
        node_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        node_dir.mkdir(parents=True, exist_ok=True)
        staged = node_dir / STAGED_EVAL_FILENAME
        staged.write_text(f"{sequence}\n{structure}\n", encoding="utf-8")
        inputs["_staged_eval"] = str(staged)

    @classmethod
    def REQUIRED_OUTPUT_PATHS(cls, inputs: dict[str, Any], outputs: list[Path]) -> list[Path]:
        return [outputs[cls.STDOUT_OUTPUT_INDEX]]

    @classmethod
    def staged_eval_path(cls, inputs: dict[str, Any]) -> Path:
        staged = inputs.get("_staged_eval")
        if staged:
            return Path(str(staged))
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        return Path(output) / cls.NODE_ID / STAGED_EVAL_FILENAME

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "RNAeval")
        command.extend(["-T", str(inputs.get("temperature", 37.0)), "-i", str(cls.staged_eval_path(inputs))])
        return command

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        outputs = [Path(path) for path in await super().run(**kwargs)]
        stdout_text = outputs[0].read_text(encoding="utf-8")
        energy = None
        for line in reversed(stdout_text.splitlines()):
            match = TRAILING_ENERGY_RE.search(line)
            if match:
                energy = float(match.group(1))
                break
        if energy is None:
            raise ValueError("RNAeval produced no energy line")
        sequence = normalize_sequence(kwargs["sequence"])
        structure = "".join(str(kwargs["structure"]).split())
        payload = {
            "tool": "RNAeval",
            "temperature_c": float(kwargs.get("temperature", 37.0)),
            "sequence": sequence,
            "structure": structure,
            "length": len(sequence),
            "energy_kcal_mol": energy,
        }
        outputs[1].write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return tuple(str(path) for path in outputs)
