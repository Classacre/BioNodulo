"""Biopython SeqIO parsing into BioNodulo's reduced JSON record schema."""

from __future__ import annotations

import json
from typing import Any

from .adapter import (
    BiopythonNode,
    node_output_dir,
    validate_choice,
    validate_path,
    write_summary_preview,
)


def _annotation_sequence_type(record: Any) -> str | None:
    value = str(record.annotations.get("molecule_type", "")).lower()
    if "protein" in value:
        return "protein"
    if "rna" in value:
        return "RNA"
    if "dna" in value:
        return "DNA"
    return None


def _resolve_sequence_type(records: list[Any], requested: str) -> str:
    if requested != "auto":
        return requested
    annotations = {_annotation_sequence_type(record) for record in records}
    annotations.discard(None)
    if len(annotations) == 1 and len(annotations) == len(
        {_annotation_sequence_type(record) for record in records}
    ):
        return annotations.pop()
    if annotations:
        return "mixed"
    # FASTA and FASTQ do not encode molecule type. Retain the historical
    # nucleotide assumption while exposing an explicit override.
    return "DNA"


class SeqIOReadNode(BiopythonNode):
    """Read supported sequence or alignment formats with Bio.SeqIO.parse."""

    NODE_ID = "bp_seqio_read"
    DISPLAY_NAME = "SeqIO Read"
    DESCRIPTION = (
        "Parse sequence records into reduced JSON containing ID, description, length, "
        "and sequence text; source annotations and qualities are not preserved."
    )
    SEARCH_ALIASES = ["BioNodulo builtin", "Biopython", "SeqIO", "parse sequences"]
    RETURN_TYPES = ("JSON", "JSON")
    RETURN_NAMES = ("sequences_json", "stats_json")
    FORMATS = (
        "fasta",
        "fastq",
        "genbank",
        "embl",
        "swiss",
        "stockholm",
        "clustal",
        "phylip",
        "nexus",
    )
    SEQUENCE_TYPES = ("auto", "DNA", "RNA", "protein")
    SOURCE_PATHS = ("Bio/SeqIO/__init__.py", "Bio/SeqUtils/__init__.py")
    UPSTREAM_SOURCE = "Bio/SeqIO/__init__.py; Bio/SeqUtils/__init__.py"
    OUTPUT_SEMANTICS = (
        "average_gc is the arithmetic mean of per-record gc_fraction(..., ambiguous='remove') "
        "for nucleotide records and null for protein or mixed records."
    )
    EXIT_SEMANTICS = (
        "Unsupported formats, malformed records, unreadable inputs, and inputs with no records fail before outputs are returned."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FILE", {"label": "Sequence File"}),
                "format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": list(cls.FORMATS),
                        "label": "Format",
                    },
                ),
            },
            "optional": {
                "sequence_type": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": list(cls.SEQUENCE_TYPES),
                        "description": (
                            "Controls GC interpretation; auto uses source annotations and otherwise assumes DNA"
                        ),
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
            inputs.get("sequence_type", "auto"),
            "sequence_type",
            cls.SEQUENCE_TYPES,
        )

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        from Bio import SeqIO
        from Bio.SeqUtils import gc_fraction

        context = kwargs.pop("context", None)
        self.__class__.require_valid_inputs(kwargs)
        output_dir = node_output_dir(self.NODE_ID, context)

        input_file = str(kwargs["input_file"])
        format_name = str(kwargs.get("format", "fasta"))
        records = list(SeqIO.parse(input_file, format_name))
        if not records:
            raise ValueError(f"No sequence records found in {input_file}")

        sequence_type = _resolve_sequence_type(
            records,
            str(kwargs.get("sequence_type", "auto")),
        )
        sequences: list[dict[str, Any]] = []
        total_length = 0
        gc_values: list[float] = []
        for record in records:
            sequence = str(record.seq)
            sequences.append(
                {
                    "id": record.id,
                    "description": record.description,
                    "length": len(sequence),
                    "seq_preview": sequence[:100],
                    "seq_full": sequence,
                }
            )
            total_length += len(sequence)
            if sequence_type in {"DNA", "RNA"}:
                gc_values.append(gc_fraction(record.seq, ambiguous="remove") * 100)

        average_gc = sum(gc_values) / len(gc_values) if gc_values else None
        stats = {
            "count": len(records),
            "total_length": total_length,
            "average_length": total_length / len(records),
            "sequence_type": sequence_type,
            "average_gc": average_gc,
            "gc_ambiguous_mode": "remove" if average_gc is not None else None,
        }

        sequences_path = output_dir / "sequences.json"
        stats_path = output_dir / "stats.json"
        sequences_path.write_text(json.dumps(sequences, indent=2), encoding="utf-8")
        stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

        gc_note = (
            f"avg GC {average_gc:.1f}%"
            if average_gc is not None
            else f"GC not applicable ({sequence_type})"
        )
        unit = "aa" if sequence_type == "protein" else "bp"
        write_summary_preview(
            context,
            output_dir,
            title=f"SeqIO Read — {stats['count']} record(s) parsed",
            note=(
                f"total {stats['total_length']:,} {unit} · "
                f"avg length {stats['average_length']:.0f} {unit} · {gc_note}"
            ),
            columns=["ID", "Description", f"Length ({unit})", "Sequence preview"],
            rows=[
                [item["id"], item["description"], item["length"], item["seq_preview"]]
                for item in sequences[:50]
            ],
            label="Parsed Sequences",
        )
        return (str(sequences_path), str(stats_path))
