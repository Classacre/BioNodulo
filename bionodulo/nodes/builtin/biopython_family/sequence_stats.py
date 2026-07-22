"""Biopython sequence length, GC, and molecular-weight statistics."""

from __future__ import annotations

import csv
import json
from typing import Any

from .adapter import BiopythonNode, node_output_dir, validate_choice, validate_path


class SequenceStatsNode(BiopythonNode):
    """Compute documented Bio.SeqUtils statistics for sequence records."""

    NODE_ID = "bp_seq_stats"
    DISPLAY_NAME = "Sequence Stats"
    DESCRIPTION = (
        "Compute sequence length, nucleotide GC content, and molecular weight; "
        "ambiguous molecular weights are reported explicitly rather than guessed."
    )
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Biopython",
        "SeqUtils",
        "GC content",
        "molecular weight",
    ]
    RETURN_TYPES = ("JSON", "TSV", "CSV")
    RETURN_NAMES = ("stats_json", "stats_tsv", "stats_csv")
    FORMATS = ("fasta", "fastq", "genbank")
    SEQUENCE_TYPES = ("DNA", "RNA", "protein")
    SOURCE_PATHS = ("Bio/SeqIO/__init__.py", "Bio/SeqUtils/__init__.py")
    UPSTREAM_SOURCE = "; ".join(SOURCE_PATHS)
    UPSTREAM_DEFAULTS = {
        "gc_fraction.ambiguous": "remove",
        "molecular_weight.seq_type": "DNA",
        "molecular_weight.double_stranded": False,
        "molecular_weight.circular": False,
        "molecular_weight.monoisotopic": False,
    }
    OUTPUT_SEMANTICS = (
        "gc_content is null for protein records and otherwise uses "
        "gc_fraction(..., ambiguous='remove'). molecular_weight accepts only "
        "unambiguous letters upstream; a rejected record receives null plus the "
        "documented ValueError message in molecular_weight_error."
    )
    EXIT_SEMANTICS = (
        "Malformed records, unreadable inputs, and inputs with no records fail the node. "
        "Only Bio.SeqUtils.molecular_weight ValueError is converted into a per-record null."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FILE", {"label": "Sequence File"}),
            },
            "optional": {
                "format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": list(cls.FORMATS),
                        "label": "Format",
                        "advanced": True,
                    },
                ),
                "sequence_type": (
                    "STRING",
                    {
                        "default": "DNA",
                        "options": list(cls.SEQUENCE_TYPES),
                        "label": "Sequence Type",
                        "advanced": True,
                    },
                ),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_path(inputs.get("input_file"), "input_file")
        if validation is not True:
            return validation
        validation = validate_choice(inputs.get("format", "fasta"), "format", cls.FORMATS)
        if validation is not True:
            return validation
        return validate_choice(
            inputs.get("sequence_type", "DNA"),
            "sequence_type",
            cls.SEQUENCE_TYPES,
        )

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        from Bio import SeqIO
        from Bio.SeqUtils import gc_fraction, molecular_weight

        context = kwargs.pop("context", None)
        self.__class__.require_valid_inputs(kwargs)
        output_dir = node_output_dir(self.NODE_ID, context)

        input_file = str(kwargs["input_file"])
        format_name = str(kwargs.get("format", "fasta"))
        sequence_type = str(kwargs.get("sequence_type", "DNA"))
        results: list[dict[str, Any]] = []
        for record in SeqIO.parse(input_file, format_name):
            gc_content = None
            if sequence_type != "protein":
                gc_content = gc_fraction(record.seq, ambiguous="remove") * 100

            molecular_weight_error = None
            try:
                weight = molecular_weight(record.seq, seq_type=sequence_type)
            except ValueError as error:
                weight = None
                molecular_weight_error = str(error)

            results.append(
                {
                    "id": record.id,
                    "length": len(record.seq),
                    "gc_content": (
                        round(gc_content, 2) if gc_content is not None else None
                    ),
                    "molecular_weight": round(weight, 2) if weight is not None else None,
                    "molecular_weight_error": molecular_weight_error,
                }
            )

        if not results:
            raise ValueError(f"No sequence records found in {input_file}")

        json_path = output_dir / "stats.json"
        json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

        fieldnames = (
            "id",
            "length",
            "gc_content",
            "molecular_weight",
            "molecular_weight_error",
        )
        tsv_path = output_dir / "stats.tsv"
        with tsv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
                delimiter="\t",
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(results)

        csv_path = output_dir / "stats.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(results)

        return (str(json_path), str(tsv_path), str(csv_path))
