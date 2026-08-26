"""ViennaRNA ``RNAfold -p`` partition-function node."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapter import (
    RNAStructureCommandNode,
    ensemble_free_energy,
    parse_fold_stdout,
    validate_int,
    validate_number,
)


class RNAfoldPartitionNode(RNAStructureCommandNode):
    """Compute ensemble properties: centroid structure, MFE frequency, diversity."""

    NODE_ID = "rnafold_partition"
    DISPLAY_NAME = "RNAfold Partition"
    DESCRIPTION = "Compute RNAfold base-pair partition functions, centroid structures, and ensemble statistics."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "ViennaRNA",
        "RNAfold -p",
        "partition function",
        "ensemble diversity",
        "centroid structure",
        "pairing probabilities",
    ]
    RETURN_TYPES = ("STRING", "STRING", "JSON")
    RETURN_NAMES = ("structure", "raw_output", "ensemble")
    OUTPUT_FILENAMES = ("fold_stdout.txt", "structure.dbn", "ensemble.json")
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
        command = cls.checked_command(inputs, "RNAfold", "--noPS", "-p")
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
        context = kwargs.get("context")
        output_dir = kwargs.get("output_dir")
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        outputs = [Path(path) for path in await super().run(**kwargs)]
        stdout_text = outputs[0].read_text(encoding="utf-8")
        stderr_text = ""
        stderr_path = Path(str(output_dir)) / "stderr.log" if output_dir else None
        if stderr_path is not None and stderr_path.is_file():
            stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
        records = parse_fold_stdout(stdout_text, partition=True)
        free_energy = ensemble_free_energy(stdout_text, stderr_text)
        dbn_lines: list[str] = []
        json_records: list[dict[str, Any]] = []
        for record in records:
            mfe = record["mfe"]
            centroid = record["centroid"]
            dbn_lines.extend([f">{record['id']}", record["sequence"], mfe["structure"], centroid["structure"]])
            json_records.append(
                {
                    "id": record["id"],
                    "length": len(record["sequence"]),
                    "mfe": {"structure": mfe["structure"], "energy_kcal_mol": mfe["energy"]},
                    "centroid": {
                        "structure": centroid["structure"],
                        "energy_kcal_mol": centroid["energy"],
                        "distance": centroid.get("energy_centroid"),
                        "correction": centroid.get("energy_correction"),
                    },
                    "frequency_of_mfe": record.get("frequency_of_mfe"),
                    "ensemble_diversity": record.get("ensemble_diversity"),
                }
            )
        outputs[1].write_text("\n".join(dbn_lines) + "\n", encoding="utf-8")
        payload = {
            "tool": "RNAfold",
            "mode": "partition",
            "temperature_c": float(kwargs.get("temperature", 37.0)),
            "ensemble_free_energy_kcal_mol": free_energy,
            "record_count": len(json_records),
            "records": json_records,
        }
        outputs[2].write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return tuple(str(path) for path in outputs)
