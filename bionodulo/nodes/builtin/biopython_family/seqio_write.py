"""Biopython SeqIO writing from BioNodulo's reduced JSON record schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapter import (
    BiopythonNode,
    atomic_seqio_write,
    node_output_dir,
    validate_choice,
    validate_output_name,
    validate_path,
    write_summary_preview,
)


def _load_records(path: str, molecule_type: str) -> list[Any]:
    from Bio.Seq import Seq
    from Bio.SeqRecord import SeqRecord

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "_value" in payload:
        payload = payload["_value"]
    if not isinstance(payload, list) or not payload:
        raise ValueError("Input 'sequences_json' must contain a non-empty list of sequence records")

    records: list[SeqRecord] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Sequence record {index} must be a JSON object")
        record_id = item.get("id")
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError(f"Sequence record {index} requires a non-empty string 'id'")
        description = item.get("description", "")
        if not isinstance(description, str):
            raise ValueError(f"Sequence record {index} field 'description' must be a string")
        if "seq_full" in item:
            sequence = item["seq_full"]
        elif "seq_preview" in item:
            sequence = item["seq_preview"]
        else:
            raise ValueError(f"Sequence record {index} requires 'seq_full' or 'seq_preview'")
        if not isinstance(sequence, str):
            raise ValueError(f"Sequence record {index} sequence must be a string")
        records.append(
            SeqRecord(
                Seq(sequence),
                id=record_id,
                description=description,
                annotations={"molecule_type": molecule_type},
            )
        )
    return records


class SeqIOWriteNode(BiopythonNode):
    """Write reduced JSON sequence records through Bio.SeqIO.write."""

    NODE_ID = "bp_seqio_write"
    DISPLAY_NAME = "SeqIO Write"
    DESCRIPTION = (
        "Write reduced sequence-record JSON as FASTA, GenBank, EMBL, Clustal, or Stockholm."
    )
    SEARCH_ALIASES = ["BioNodulo builtin", "Biopython", "SeqIO", "write sequences", "format conversion"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_file",)
    FORMATS = ("fasta", "genbank", "embl", "clustal", "stockholm")
    MOLECULE_TYPES = ("DNA", "RNA", "protein")
    SOURCE_PATHS = (
        "Bio/SeqIO/__init__.py",
        "Bio/SeqIO/InsdcIO.py",
        "Bio/AlignIO/__init__.py",
        "Bio/AlignIO/ClustalIO.py",
        "Bio/AlignIO/StockholmIO.py",
    )
    UPSTREAM_SOURCE = "; ".join(SOURCE_PATHS)
    INPUT_SCHEMA = (
        "A non-empty JSON list of objects with non-empty id, optional string description, "
        "and string seq_full (preferred) or seq_preview."
    )
    FORMAT_BEHAVIOR = (
        "GenBank and EMBL receive the declared molecule_type; Clustal and Stockholm require "
        "equal-length sequences. Source annotations, features, and qualities are not reconstructed."
    )
    EXIT_SEMANTICS = (
        "Invalid JSON or a Biopython writer error fails the node; the declared output is atomically published only after all records write."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sequences_json": (
                    "JSON",
                    {
                        "label": "Sequences JSON",
                        "description": cls.INPUT_SCHEMA,
                    },
                ),
                "output_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": list(cls.FORMATS),
                        "label": "Output Format",
                    },
                ),
                "output_name": (
                    "STRING",
                    {"default": "output.fasta", "label": "Output Filename"},
                ),
            },
            "optional": {
                "molecule_type": (
                    "STRING",
                    {
                        "default": "DNA",
                        "options": list(cls.MOLECULE_TYPES),
                        "description": "Required by GenBank and EMBL writers and recorded on every output record",
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
        validation = validate_path(inputs.get("sequences_json"), "sequences_json")
        if validation is not True:
            return validation
        validation = validate_choice(
            inputs.get("output_format", "fasta"),
            "output_format",
            cls.FORMATS,
        )
        if validation is not True:
            return validation
        validation = validate_choice(
            inputs.get("molecule_type", "DNA"),
            "molecule_type",
            cls.MOLECULE_TYPES,
        )
        if validation is not True:
            return validation
        return validate_output_name(inputs.get("output_name", "output.fasta"))

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop("context", None)
        self.__class__.require_valid_inputs(kwargs)
        output_dir = node_output_dir(self.NODE_ID, context)

        format_name = str(kwargs.get("output_format", "fasta"))
        molecule_type = str(kwargs.get("molecule_type", "DNA"))
        output_path = output_dir / str(kwargs.get("output_name", "output.fasta"))
        records = _load_records(str(kwargs["sequences_json"]), molecule_type)
        atomic_seqio_write(records, output_path, format_name)

        unit = "aa" if molecule_type == "protein" else "bp"
        write_summary_preview(
            context,
            output_dir,
            title=f"SeqIO Write — {len(records)} record(s) → {format_name}",
            note=f"Wrote {output_path.name} ({output_path.stat().st_size:,} bytes)",
            columns=["ID", "Description", f"Length ({unit})"],
            rows=[[record.id, record.description, len(record.seq)] for record in records[:50]],
            label=f"{format_name} output",
        )
        return (str(output_path),)
