"""Seqtk 1.4 ``seq`` node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqtkStdoutNode


class SeqTKSeqNode(SeqtkStdoutNode):
    """Apply Seqtk's common FASTA/Q transformations without post-processing."""

    NODE_ID = "seqtk_seq"
    DISPLAY_NAME = "SeqTK Seq"
    DESCRIPTION = "Transform, filter, mask, subsample, or reverse-complement FASTA/Q records."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "seq", "reverse complement", "quality mask"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("transformed_records",)
    REQUIRED_PATH_INPUTS = ("in_file",)
    UPSTREAM_FUNCTION = "stk_seq"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": (("FASTA", "FASTQ"), {"description": "Input FASTA/Q, optionally gzip-compressed"}),
            },
            "optional": {
                "q": ("INT", {"default": 0, "description": "Mask bases below this quality"}),
                "X": ("INT", {"default": 255, "description": "Mask bases above this quality"}),
                "n": ("STRING", {"default": "", "description": "Replacement character for masked bases"}),
                "l": ("INT", {"default": 0, "min": 0, "description": "Residues per output line; zero is unlimited"}),
                "Q": ("INT", {"default": 33, "description": "ASCII quality offset"}),
                "s": ("INT", {"default": 11, "description": "Random seed used by -f"}),
                "f": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "description": "Sequence sampling fraction"}),
                "M": ("FILE", {"default": "", "description": "BED or name-list regions to mask"}),
                "L": ("INT", {"default": 0, "min": 0, "description": "Drop sequences shorter than this length"}),
                "F": ("STRING", {"default": "", "description": "Create FASTQ using this fake quality character"}),
                "c": ("BOOLEAN", {"default": False, "description": "Mask the complement of -M regions"}),
                "r": ("BOOLEAN", {"default": False, "description": "Reverse-complement records"}),
                "A": ("BOOLEAN", {"default": False, "description": "Force FASTA and discard qualities"}),
                "C": ("BOOLEAN", {"default": False, "description": "Drop header comments"}),
                "N": ("BOOLEAN", {"default": False, "description": "Drop sequences containing ambiguous bases"}),
                "x1": ("BOOLEAN", {"default": False, "description": "Output odd-numbered records only (-1)"}),
                "x2": ("BOOLEAN", {"default": False, "description": "Output even-numbered records only (-2)"}),
                "V": ("BOOLEAN", {"default": False, "description": "Shift qualities from -Q to Phred+33"}),
                "U": ("BOOLEAN", {"default": False, "description": "Convert all bases to uppercase"}),
                "x": ("BOOLEAN", {"default": False, "description": "Convert lowercase bases to -n character"}),
                "S": ("BOOLEAN", {"default": False, "description": "Strip whitespace within sequences"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        if inputs.get("A"):
            extension = ".fasta"
        elif inputs.get("F"):
            extension = ".fastq"
        else:
            extension = cls.sequence_extension(inputs.get("in_file"))
        return [node_dir / f"transformed{extension}"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.reject_legacy(inputs, ("input_ext", "direction", "fastqillumina"))
        if validation is not True:
            return validation
        for key, default, minimum, maximum in (
            ("q", 0, None, None),
            ("X", 255, None, None),
            ("l", 0, 0, None),
            ("Q", 33, None, None),
            ("s", 11, None, None),
            ("L", 0, 0, None),
        ):
            validation = cls.validate_int(
                inputs.get(key, default),
                key,
                minimum=minimum,
                maximum=maximum,
            )
            if validation is not True:
                return validation
        validation = cls.validate_number(inputs.get("f", 1.0), "f", minimum=0.0, maximum=1.0)
        if validation is not True:
            return validation
        # Seqtk reads the first byte, but BioNodulo keeps the documented CHAR contract;
        # -F also determines whether the planned artifact is FASTQ.
        for key in ("n", "F"):
            value = inputs.get(key, "")
            if value not in (None, "") and len(str(value)) != 1:
                return f"Input '{key}' must be exactly one character"
        if inputs.get("F") and not 33 <= ord(str(inputs["F"])) <= 127:
            return "Input 'F' must have an ASCII code between 33 and 127"
        if inputs.get("M"):
            validation = cls.require_path(inputs, "M")
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(
            inputs,
            "seqtk",
            "seq",
            "-q",
            str(inputs.get("q", 0)),
            "-X",
            str(inputs.get("X", 255)),
        )
        cls.add_value(command, "-n", inputs.get("n"))
        command.extend(
            [
                "-l",
                str(inputs.get("l", 0)),
                "-Q",
                str(inputs.get("Q", 33)),
                "-s",
                str(inputs.get("s", 11)),
                "-f",
                str(inputs.get("f", 1.0)),
            ]
        )
        cls.add_value(command, "-M", inputs.get("M"))
        command.extend(["-L", str(inputs.get("L", 0))])
        cls.add_value(command, "-F", inputs.get("F"))
        for key, flag in (
            ("c", "-c"),
            ("r", "-r"),
            ("A", "-A"),
            ("C", "-C"),
            ("N", "-N"),
            ("x1", "-1"),
            ("x2", "-2"),
            ("V", "-V"),
            ("U", "-U"),
            ("x", "-x"),
            ("S", "-S"),
        ):
            if inputs.get(key):
                command.append(flag)
        command.append(cls.path_value(inputs["in_file"]))
        return command
