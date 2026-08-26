"""ViennaRNA ``RNAfold`` minimum free energy node."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapter import (
    RNAStructureCommandNode,
    parse_fold_stdout,
    validate_int,
    validate_number,
)


class RNAfoldMFENode(RNAStructureCommandNode):
    """Predict minimum free energy secondary structures for RNA records."""

    NODE_ID = "rnafold_mfe"
    DISPLAY_NAME = "RNAfold MFE"
    DESCRIPTION = "Fold RNA sequences into minimum free energy (MFE) dot-bracket structures with RNAfold."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "ViennaRNA",
        "RNAfold",
        "minimum free energy",
        "secondary structure",
        "dot-bracket",
        "mRNA structure",
    ]
    RETURN_TYPES = ("STRING", "STRING", "JSON", "TSV")
    RETURN_NAMES = ("structure", "raw_output", "energies", "per_record")
    OUTPUT_FILENAMES = ("fold_stdout.txt", "structure.dbn", "energies.json", "per_record.tsv")
    STDOUT_OUTPUT_INDEX = 0
    REQUIRED_SEQUENCE_INPUTS = ("fasta", "sequence")
    REQUIRED_EXECUTABLES = ["RNAfold"]
    DOCUMENTATION_URL = "https://www.tbi.univie.ac.at/RNA/RNAfold.1.html"
    RUN_IN_NODE_OUTPUT_DIR = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "fasta": ("FASTA", {"description": "Input FASTA with one or more RNA records"}),
                "sequence": (
                    "STRING",
                    {"multiline": True, "default": "", "description": "Inline RNA/DNA sequence used when no FASTA is given"},
                ),
                "temperature": ("FLOAT", {"default": 37.0, "min": 0.0, "max": 100.0}),
                "no_lp": ("BOOLEAN", {"default": False, "description": "Disallow lonely pairs"}),
                "max_bp_span": ("INT", {"default": None, "min": 1, "description": "Maximum base pair distance"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 256}),
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
        validation = validate_number(inputs.get("temperature", 37.0), "temperature", minimum=0.0, maximum=100.0)
        if validation is not True:
            return validation
        if not isinstance(inputs.get("no_lp", False), bool):
            return "Input 'no_lp' must be a boolean"
        if inputs.get("max_bp_span") is not None:
            validation = validate_int(inputs["max_bp_span"], "max_bp_span", minimum=1)
            if validation is not True:
                return validation
        return validate_int(inputs.get("threads", 1), "threads", minimum=1, maximum=256)

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        cls.stage_input(inputs, outputs)

    @classmethod
    def REQUIRED_OUTPUT_PATHS(cls, inputs: dict[str, Any], outputs: list[Path]) -> list[Path]:
        return [outputs[cls.STDOUT_OUTPUT_INDEX]]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "RNAfold", "--noPS")
        if inputs.get("no_lp", False):
            command.append("--noLP")
        if inputs.get("max_bp_span") is not None:
            command.extend(["--maxBPspan", str(inputs["max_bp_span"])])
        threads = inputs.get("threads", 1)
        if threads not in (None, 1):
            command.extend([f"--jobs={threads}"])
        command.extend(["-T", str(inputs.get("temperature", 37.0)), "-i", str(cls.staged_input_path(inputs))])
        return command

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        outputs = [Path(path) for path in await super().run(**kwargs)]
        records = parse_fold_stdout(outputs[0].read_text(encoding="utf-8"), partition=False)
        dbn_lines: list[str] = []
        json_records: list[dict[str, Any]] = []
        for record in records:
            mfe = record["mfe"]
            dbn_lines.extend([f">{record['id']}", record["sequence"], mfe["structure"]])
            json_records.append(
                {
                    "id": record["id"],
                    "length": len(record["sequence"]),
                    "sequence": record["sequence"],
                    "structure": mfe["structure"],
                    "mfe_kcal_mol": mfe["energy"],
                }
            )
        outputs[1].write_text("\n".join(dbn_lines) + "\n", encoding="utf-8")
        payload = {
            "tool": "RNAfold",
            "mode": "mfe",
            "temperature_c": float(kwargs.get("temperature", 37.0)),
            "record_count": len(json_records),
            "records": json_records,
        }
        outputs[2].write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        per_record_lines = ["id\tmfe"]
        per_record_lines.extend(f"{record['id']}\t{record['mfe_kcal_mol']}" for record in json_records)
        outputs[3].write_text("\n".join(per_record_lines) + "\n", encoding="utf-8")
        return tuple(str(path) for path in outputs)
