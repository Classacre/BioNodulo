"""BioNodulo adapter for importing an existing complete BWA index bundle."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode

from .adapter import (
    BWA_GIT_COMMIT,
    BWA_GIT_URL,
    BWA_INDEX_DIRECTORY,
    BWA_INDEX_FASTA,
    BWA_INDEX_SUFFIXES,
    BWA_SOURCE_ROOT,
    BWA_VERSION,
    bwa_source_urls,
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
    DESCRIPTION = "Validate and stage an existing complete native BWA index bundle"
    SEARCH_ALIASES = ["bwa index dir", "index directory", "import bwa index"]
    RETURN_TYPES = ("INDEX_DIR",)
    RETURN_NAMES = ("index_dir",)
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: list[str] = []
    REQUIRED_CONDA_PACKAGES: list[str] = []
    DOCUMENTATION_URL = f"{BWA_SOURCE_ROOT}/bwa.1"
    VERSION = BWA_VERSION
    GIT_URL = BWA_GIT_URL
    GIT_COMMIT = BWA_GIT_COMMIT
    GIT_TAG = "v0.7.19"
    SOURCE_REF = f"tag v0.7.19 at {BWA_GIT_COMMIT}"
    SOURCE_REVISION = BWA_GIT_COMMIT
    SOURCE_URL = f"https://github.com/lh3/bwa/tree/{BWA_GIT_COMMIT}"
    SOURCE_PATHS = ("bwa.1", "bwa.c", "bntseq.c")
    SOURCE_URLS = bwa_source_urls(*SOURCE_PATHS)
    UPSTREAM_SOURCE = "bwa.c; bntseq.c"
    AUDIT_STATUS = "contract-checked-no-external-execution"
    CITATION_DOIS = ["10.1093/bioinformatics/btp324"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btp324"]
    CITATION_TEXT = "Fast and accurate short read alignment with Burrows-Wheeler transform."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "index_dir": (
                    "INDEX_DIR",
                    {"description": "Directory containing exactly one complete five-file BWA index prefix"},
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
            find_index_prefix(index_dir, require_reference=False)
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

        source_prefix = find_index_prefix(str(kwargs["index_dir"]), require_reference=False)
        source_reference = staged_reference(source_prefix)
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
        if source_reference is not None:
            stage_file(source_reference, target_prefix)
        for suffix in BWA_INDEX_SUFFIXES:
            stage_file(Path(f"{source_prefix}{suffix}"), Path(f"{target_prefix}{suffix}"))
        source_alt = Path(f"{source_prefix}.alt")
        if source_alt.is_file():
            stage_file(source_alt, Path(f"{target_prefix}.alt"))

        find_index_prefix(target_dir, require_reference=False)
        return (str(target_dir),)
