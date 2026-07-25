"""Samtools index node with explicit colocated BAM and BAI outputs."""

from __future__ import annotations

import errno
import os
import shutil
from pathlib import Path
from typing import Any

from .adapter import SamtoolsCommandNode


_LINK_FALLBACK_ERRNOS = {errno.EXDEV, errno.EPERM, errno.ENOSYS}
for _errno_name in ("ENOTSUP", "EOPNOTSUPP"):
    _errno_value = getattr(errno, _errno_name, None)
    if _errno_value is not None:
        _LINK_FALLBACK_ERRNOS.add(_errno_value)


class SamtoolsIndexNode(SamtoolsCommandNode):
    """Create a BAI for the input coordinate-sorted BAM."""

    NODE_ID = "samtools_index"
    DISPLAY_NAME = "Samtools Index"
    DESCRIPTION = "Create a BAI index for a coordinate-sorted BAM"
    SEARCH_ALIASES = ["samtools", "index", "bai"]
    RETURN_TYPES = ("BAM", "BAI")
    RETURN_NAMES = ("indexed_bam", "bai")
    OUTPUT_FILENAMES = ("indexed_bam.bam", "indexed_bam.bam.bai")
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-index.html"
    UPSTREAM_MANPAGE = "doc/samtools-index.1"
    UPSTREAM_SOURCE = "bam_index.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": (
                    "BAM",
                    {"description": "Coordinate-sorted BAM file to index"},
                ),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        return [
            "samtools",
            "index",
            "-@",
            str(inputs.get("threads", 2)),
            "-b",
            "-o",
            str(output / cls.OUTPUT_FILENAMES[1]),
            str(inputs.get("bam", "")),
        ]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        source = Path(os.fsdecode(os.fspath(inputs["bam"])))
        staged_bam = outputs[0]
        staged_bam.parent.mkdir(parents=True, exist_ok=True)

        source_lexical = os.path.abspath(os.path.normpath(os.fspath(source)))
        staged_lexical = os.path.abspath(os.path.normpath(os.fspath(staged_bam)))
        if source_lexical == staged_lexical:
            inputs["bam"] = str(staged_bam)
            return
        if (
            not staged_bam.is_symlink()
            and staged_bam.exists()
            and os.path.samefile(source, staged_bam)
        ):
            inputs["bam"] = str(staged_bam)
            return

        if staged_bam.exists() or staged_bam.is_symlink():
            staged_bam.unlink()
        try:
            os.link(source, staged_bam)
        except OSError as exc:
            if exc.errno not in _LINK_FALLBACK_ERRNOS:
                raise
            shutil.copy2(source, staged_bam)
        inputs["bam"] = str(staged_bam)
