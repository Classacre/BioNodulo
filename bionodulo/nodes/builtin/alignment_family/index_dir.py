"""BioNodulo adapter for importing an existing complete BWA index bundle."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode

from .adapter import (
    BWA_INDEX_DIRECTORY,
    BWA_INDEX_FASTA,
    BWA_INDEX_SUFFIXES,
    find_index_prefix,
    path_value,
    staged_reference,
    stage_file,
)


class BWAIndexDirNode(BaseNode):
    """Validate and stage a complete existing BWA index directory.

    BWA has no ``index-dir`` subcommand. This stable node ID is a BioNodulo
    import adapter for the documented file set consumed by ``bwa mem``.
    """

    NODE_ID = "bwa_index_dir"
    DISPLAY_NAME = "BWA Index Directory"
    CATEGORY = "alignment"
    DESCRIPTION = "Validate and stage an existing complete BWA index bundle"
    SEARCH_ALIASES = ["bwa index dir", "index directory", "import bwa index"]
    RETURN_TYPES = ("INDEX_DIR",)
    RETURN_NAMES = ("index_dir",)
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: list[str] = []
    REQUIRED_CONDA_PACKAGES: list[str] = []
    DOCUMENTATION_URL = "https://github.com/lh3/bwa/blob/v0.7.19/bwa.1"
    VERSION = "0.7.19"
    GIT_URL = "https://github.com/lh3/bwa.git"
    GIT_COMMIT = "b92993c1161e73167181558856567ef2f367e3f0"
    CITATION_DOIS = ["10.1093/bioinformatics/btp324"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btp324"]
    CITATION_TEXT = "Fast and accurate short read alignment with Burrows-Wheeler transform."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "index_dir": (
                    "INDEX_DIR",
                    {"description": "Directory containing one staged FASTA and all five BWA index siblings"},
                ),
            },
            "optional": {},
            "hidden": {},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [Path(output_dir) / cls.NODE_ID / BWA_INDEX_DIRECTORY]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        index_dir = path_value(inputs.get("index_dir"))
        if index_dir is None:
            return "Input 'index_dir' must be a non-empty path-like value"
        try:
            find_index_prefix(index_dir)
        except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
            return str(exc)
        return True

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        output_dir = kwargs.pop("output_dir", None)
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        output_dir = output_dir or "."

        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")

        source_prefix = find_index_prefix(str(kwargs["index_dir"]))
        source_reference = staged_reference(source_prefix)
        assert source_reference is not None
        source_dir = source_prefix.parent
        target_dir = self.PLAN_OUTPUTS(kwargs, output_dir)[0]
        if os.path.abspath(source_dir) == os.path.abspath(target_dir):
            return (str(target_dir),)

        if target_dir.exists() or target_dir.is_symlink():
            if target_dir.is_dir() and not target_dir.is_symlink():
                shutil.rmtree(target_dir)
            else:
                target_dir.unlink()
        target_prefix = target_dir / BWA_INDEX_FASTA
        stage_file(source_reference, target_prefix)
        for suffix in BWA_INDEX_SUFFIXES:
            stage_file(Path(f"{source_prefix}{suffix}"), Path(f"{target_prefix}{suffix}"))
        source_alt = Path(f"{source_prefix}.alt")
        if source_alt.is_file():
            stage_file(source_alt, Path(f"{target_prefix}.alt"))

        find_index_prefix(target_dir)
        return (str(target_dir),)
