"""Stable owner for ``seqkit_translate``."""

from pathlib import Path
from typing import Any

from .legacy import _SeqKitTranslateContract


class SeqKitTranslateNode(_SeqKitTranslateContract):
    NODE_ID = "seqkit_translate"
    OUTPUT_NAME_BY_BASENAME = {
        "translated.fasta": "translated_fasta",
        "translated.fasta.gz": "translated_fasta",
        "translated.fastq": "translated_fastq",
        "translated.fastq.gz": "translated_fastq",
    }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return super().PLAN_OUTPUTS(inputs, output_dir)
