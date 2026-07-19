"""Dorado 0.9.6 barcode classification and demultiplexing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    DoradoCommandNode,
    option_value,
    path_value,
    validate_int,
)


class DoradoDemuxNode(DoradoCommandNode):
    """Emit Dorado's per-barcode files and native tab-delimited summary."""

    NODE_ID = "dorado_demux"
    DISPLAY_NAME = "Dorado Demux"
    DESCRIPTION = "Classify or split Dorado reads into source-native per-barcode files"
    SEARCH_ALIASES = [
        *DoradoCommandNode.SEARCH_ALIASES,
        "demux",
        "demultiplex",
        "barcoding",
        "barcode classification",
    ]
    RETURN_TYPES = ("DIRECTORY", "TSV")
    RETURN_NAMES = ("demux_dir", "barcode_summary")
    REQUIRED_PATH_INPUTS = ("reads",)
    UPSTREAM_SOURCE = "dorado/cli/demux.cpp; dorado/summary/summary.cpp"
    DOCUMENTATION_URL = "https://github.com/nanoporetech/dorado/tree/v0.9.6#barcode-classification"
    NATIVE_SUMMARY_FILENAME = "barcoding_summary.txt"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": (
                    ("BAM", "CRAM", "SAM", "FASTQ", "DIRECTORY"),
                    {"description": "One HTS file or a directory containing HTS files"},
                ),
            },
            "optional": {
                "kit_name": ("STRING", {"default": ""}),
                "no_classify": (
                    "BOOLEAN",
                    {"default": False, "description": "Split existing barcode classifications"},
                ),
                "sample_sheet": ("CSV", {"default": ""}),
                "barcode_arrangement": ("FILE", {"default": ""}),
                "barcode_sequences": ("FASTA", {"default": ""}),
                "emit_fastq": ("BOOLEAN", {"default": False}),
                "barcode_both_ends": ("BOOLEAN", {"default": False}),
                "no_trim": ("BOOLEAN", {"default": False}),
                "sort_bam": ("BOOLEAN", {"default": False}),
                "recursive": ("BOOLEAN", {"default": False}),
                "threads": ("INT", {"default": 0, "min": 0}),
                "max_reads": ("INT", {"default": 0, "min": 0}),
                "read_ids": ("FILE", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(
        cls,
        inputs: dict[str, Any],
        output_dir: str | Path,
    ) -> list[Path]:
        demux_dir = Path(output_dir) / cls.NODE_ID / "demux"
        demux_dir.mkdir(parents=True, exist_ok=True)
        return [demux_dir, demux_dir / cls.NATIVE_SUMMARY_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        kit_name = str(inputs.get("kit_name", "") or "").strip()
        no_classify = bool(option_value(inputs, "no_classify", False))
        if bool(kit_name) == no_classify:
            return "Specify exactly one of 'kit_name' or 'no_classify'"
        if no_classify and inputs.get("sample_sheet"):
            return "Input 'sample_sheet' cannot be used with 'no_classify'"
        if inputs.get("barcode_arrangement") and not kit_name:
            return "Input 'barcode_arrangement' requires 'kit_name'"
        if inputs.get("barcode_sequences") and not inputs.get("barcode_arrangement"):
            return "Input 'barcode_sequences' requires 'barcode_arrangement'"
        if option_value(inputs, "sort_bam", False) and not (option_value(inputs, "no_trim", False) or no_classify):
            return "Input 'sort_bam' requires 'no_trim' or 'no_classify'"
        for key, default in (("threads", 0), ("max_reads", 0)):
            validation = validate_int(option_value(inputs, key, default), key, minimum=0)
            if validation is not True:
                return validation
        for key in ("sample_sheet", "barcode_arrangement", "barcode_sequences", "read_ids"):
            value = inputs.get(key)
            if value not in (None, "") and not path_value(value):
                return f"Input '{key}' must be a non-empty path-like value"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", ".")))) / "demux"
        command = cls.checked_command(
            inputs,
            "dorado",
            "demux",
            "--output-dir",
            str(output),
        )
        if option_value(inputs, "no_classify", False):
            command.append("--no-classify")
        else:
            command.extend(["--kit-name", str(inputs["kit_name"]).strip()])
        for key, flag in (
            ("sample_sheet", "--sample-sheet"),
            ("barcode_arrangement", "--barcode-arrangement"),
            ("barcode_sequences", "--barcode-sequences"),
        ):
            if inputs.get(key):
                command.extend([flag, path_value(inputs[key])])
        if option_value(inputs, "emit_fastq", False):
            command.append("--emit-fastq")
        command.append("--emit-summary")
        if option_value(inputs, "barcode_both_ends", False):
            command.append("--barcode-both-ends")
        if option_value(inputs, "no_trim", False):
            command.append("--no-trim")
        if option_value(inputs, "sort_bam", False):
            command.append("--sort-bam")
        if option_value(inputs, "recursive", False):
            command.append("--recursive")
        threads = option_value(inputs, "threads", 0)
        if threads:
            command.extend(["--threads", str(threads)])
        max_reads = option_value(inputs, "max_reads", 0)
        if max_reads:
            command.extend(["--max-reads", str(max_reads)])
        if inputs.get("read_ids"):
            command.extend(["--read-ids", path_value(inputs["read_ids"])])
        command.append(path_value(inputs["reads"]))
        return command
