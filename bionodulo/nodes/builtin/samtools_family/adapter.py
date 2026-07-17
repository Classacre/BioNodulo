"""Shared runtime contract for the first-wave Samtools nodes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


class SamtoolsCommandNode(CommandNode):
    """Small adapter for metadata, output planning, and common validation."""

    CATEGORY = "samtools"
    REQUIRED_EXECUTABLES = ["samtools"]
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    VERSION = "1.23.1"
    GIT_URL = "https://github.com/samtools/samtools.git"
    GIT_COMMIT = "6efb9b6da35224cf804921dedecf9fb8f411365d"
    CITATION_DOIS = [
        "10.1093/gigascience/giab008",
        "10.1093/bioinformatics/btp352",
    ]
    CITATION_URLS = [f"https://doi.org/{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = (
        "Twelve years of SAMtools and BCFtools; "
        "The Sequence Alignment/Map format and SAMtools."
    )
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    UPSTREAM_MANPAGE: ClassVar[str] = ""
    UPSTREAM_SOURCE: ClassVar[str] = ""

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation

        for name, spec in cls.INPUT_TYPES().get("required", {}).items():
            declared_type = spec[0] if isinstance(spec, (list, tuple)) else spec
            declared_types = (
                (declared_type,)
                if isinstance(declared_type, str)
                else tuple(declared_type)
            )
            if not {"SAM", "BAM"}.intersection(declared_types):
                continue
            value = inputs.get(name)
            if not isinstance(value, (str, os.PathLike)):
                return f"Input '{name}' must be a path-like value"
            path_value = os.fspath(value)
            if not isinstance(path_value, str) or not path_value.strip():
                return f"Input '{name}' must be a non-empty path"

        threads = inputs.get("threads")
        if isinstance(threads, bool) or not isinstance(threads, int):
            return "threads must be an integer"
        if not 1 <= threads <= 64:
            return "threads must be between 1 and 64"
        return True
