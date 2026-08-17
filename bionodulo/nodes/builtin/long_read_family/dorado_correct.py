"""Dorado 0.9.6 HERRO correction with explicit local model input."""

from __future__ import annotations

import re
from typing import Any

from .adapter import (
    DoradoCommandNode,
    option_value,
    path_value,
    valid_dorado_device,
    validate_int,
)


_INDEX_SIZE = re.compile(r"^[0-9]+(?:[KMGTP]i?B?|[kmgpt])?$", re.IGNORECASE)


class DoradoCorrectNode(DoradoCommandNode):
    """Correct one ONT read file and capture Dorado's FASTA stdout."""

    NODE_ID = "dorado_correct"
    REQUIRES_GPU = True
    DISPLAY_NAME = "Dorado Correct"
    DESCRIPTION = "Correct Oxford Nanopore reads with HERRO and an explicit local model"
    SEARCH_ALIASES = [
        *DoradoCommandNode.SEARCH_ALIASES,
        "HERRO",
        "read correction",
        "corrected FASTA",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("corrected_reads",)
    OUTPUT_FILENAMES = ("corrected_reads.fasta",)
    STDOUT_OUTPUT_INDEX = 0
    REQUIRED_PATH_INPUTS = ("reads", "model")
    UPSTREAM_SOURCE = "dorado/cli/correct.cpp"
    DOCUMENTATION_URL = "https://github.com/nanoporetech/dorado/tree/v0.9.6#read-correction"
    EXIT_SEMANTICS = (
        "Argument, path, model, device, and pipeline failures return non-zero; "
        "successful correction writes FASTA records to stdout and returns zero."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ", {"description": "One FASTQ file containing ONT reads"}),
                "model": (
                    "DIRECTORY",
                    {
                        "description": (
                            "Staged local HERRO model directory; omitting --model-path would "
                            "make Dorado download herro-v1 at runtime"
                        )
                    },
                ),
            },
            "optional": {
                "threads": ("INT", {"default": 0, "min": 0, "description": "Zero uses all available threads"}),
                "infer_threads": ("INT", {"default": 1, "min": 1}),
                "device": (
                    "STRING",
                    {"default": "auto", "description": "auto, cpu, cuda:all, cuda:auto, or cuda:<ids>"},
                ),
                "from_paf": ("FILE", {"default": "", "description": "Existing all-vs-all PAF alignments"}),
                "resume_from": (
                    "FILE",
                    {"default": "", "description": "Read IDs already corrected, one first-column ID per row"},
                ),
                "batch_size": ("INT", {"default": 0, "min": 0}),
                "index_size": ("STRING", {"default": "8G"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key, default, minimum in (
            ("threads", 0, 0),
            ("infer_threads", 1, 1),
            ("batch_size", 0, 0),
        ):
            validation = validate_int(option_value(inputs, key, default), key, minimum=minimum)
            if validation is not True:
                return validation
        device = str(option_value(inputs, "device", "auto"))
        if not valid_dorado_device(device):
            return "Input 'device' must be auto, cpu, cuda:all, cuda:auto, or cuda:<ids>"
        index_size = str(option_value(inputs, "index_size", "8G")).strip()
        if not _INDEX_SIZE.fullmatch(index_size):
            return "Input 'index_size' must be an integer optionally followed by a size suffix"
        for key in ("from_paf", "resume_from"):
            value = inputs.get(key)
            if value not in (None, "") and not path_value(value):
                return f"Input '{key}' must be a non-empty path-like value"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(
            inputs,
            "dorado",
            "correct",
            path_value(inputs["reads"]),
            "--model-path",
            path_value(inputs["model"]),
            "--threads",
            str(option_value(inputs, "threads", 0)),
            "--infer-threads",
            str(option_value(inputs, "infer_threads", 1)),
            "--device",
            str(option_value(inputs, "device", "auto")),
            "--batch-size",
            str(option_value(inputs, "batch_size", 0)),
            "--index-size",
            str(option_value(inputs, "index_size", "8G")),
        )
        if inputs.get("from_paf"):
            command.extend(["--from-paf", path_value(inputs["from_paf"])])
        if inputs.get("resume_from"):
            command.extend(["--resume-from", path_value(inputs["resume_from"])])
        return command
