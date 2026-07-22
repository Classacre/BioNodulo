"""Deterministic summary, consensus, and bounded rendering for sequence alignments."""

from __future__ import annotations

import json
import struct
import zlib
from binascii import crc32
from collections import Counter
from pathlib import Path
from typing import Any

from .adapter import (
    BiopythonNode,
    atomic_seqio_write,
    node_output_dir,
    validate_choice,
    validate_path,
)


MAX_RENDER_COLUMNS = 200
MAX_RENDER_ROWS = 100
GAP_CHARACTERS = frozenset("-.")
NUCLEOTIDE_CHARACTERS = frozenset("ACGTRYSWKMBDHVNU")
NUCLEOTIDE_COLOURS = {
    "A": (239, 68, 68),
    "T": (16, 185, 129),
    "U": (16, 185, 129),
    "G": (245, 158, 11),
    "C": (59, 130, 246),
    "N": (100, 116, 139),
}
PROTEIN_COLOURS = {
    "A": (96, 165, 250),
    "V": (96, 165, 250),
    "I": (96, 165, 250),
    "L": (96, 165, 250),
    "M": (96, 165, 250),
    "F": (96, 165, 250),
    "W": (96, 165, 250),
    "Y": (96, 165, 250),
    "K": (248, 113, 113),
    "R": (248, 113, 113),
    "H": (248, 113, 113),
    "D": (244, 114, 182),
    "E": (244, 114, 182),
    "S": (74, 222, 128),
    "T": (74, 222, 128),
    "N": (74, 222, 128),
    "Q": (74, 222, 128),
    "C": (250, 204, 21),
    "G": (251, 146, 60),
    "P": (192, 132, 252),
    "X": (100, 116, 139),
}


def _alignment_type(alignment: Any) -> str:
    residues = {
        character.upper()
        for record in alignment
        for character in str(record.seq)
        if character not in GAP_CHARACTERS
    }
    return "nucleotide" if residues <= NUCLEOTIDE_CHARACTERS else "protein"


def _strict_majority_consensus(alignment: Any, sequence_type: str) -> str:
    ambiguous = "N" if sequence_type == "nucleotide" else "X"
    consensus: list[str] = []
    for column_index in range(alignment.get_alignment_length()):
        characters = [
            character.upper()
            for character in alignment[:, column_index]
            if character not in GAP_CHARACTERS
        ]
        if not characters:
            consensus.append("-")
            continue
        residue, count = Counter(characters).most_common(1)[0]
        consensus.append(residue if count * 2 > len(characters) else ambiguous)
    return "".join(consensus)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def _write_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    scanlines = bytearray()
    row_bytes = width * 3
    for row_index in range(height):
        scanlines.append(0)
        start = row_index * row_bytes
        scanlines.extend(pixels[start : start + row_bytes])
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(scanlines), level=6))
        + _png_chunk(b"IEND", b"")
    )


def _render_alignment_png(alignment: Any, path: Path, sequence_type: str) -> None:
    columns = min(alignment.get_alignment_length(), MAX_RENDER_COLUMNS)
    rows = min(len(alignment), MAX_RENDER_ROWS)
    cell_width = 4
    cell_height = 8
    width = max(1, columns * cell_width)
    height = max(1, rows * cell_height)
    pixels = bytearray([255, 255, 255]) * (width * height)
    colours = NUCLEOTIDE_COLOURS if sequence_type == "nucleotide" else PROTEIN_COLOURS

    for row_index, record in enumerate(alignment[:rows]):
        for column_index in range(columns):
            residue = str(record.seq[column_index]).upper()
            if residue in GAP_CHARACTERS:
                colour = (226, 232, 240)
            else:
                colour = colours.get(residue, (148, 163, 184))
            for y_position in range(row_index * cell_height, (row_index + 1) * cell_height):
                for x_position in range(
                    column_index * cell_width,
                    (column_index + 1) * cell_width,
                ):
                    offset = (y_position * width + x_position) * 3
                    pixels[offset : offset + 3] = bytes(colour)
    _write_png(path, width, height, pixels)


class MSAViewNode(BiopythonNode):
    """Read an MSA and emit deterministic summary, consensus, and PNG outputs."""

    NODE_ID = "bp_msa_view"
    DISPLAY_NAME = "MSA View"
    DESCRIPTION = (
        "Summarize a multiple sequence alignment, calculate a strict-majority "
        "consensus, and render a bounded deterministic PNG."
    )
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Biopython",
        "AlignIO",
        "multiple sequence alignment",
        "consensus",
    ]
    RETURN_TYPES = ("JSON", "FASTA", "IMAGE")
    RETURN_NAMES = ("alignment_json", "consensus_fasta", "alignment_image")
    FORMATS = ("clustal", "stockholm", "phylip", "fasta", "nexus")
    SOURCE_PATHS = (
        "Bio/AlignIO/__init__.py",
        "Bio/AlignIO/ClustalIO.py",
        "Bio/AlignIO/StockholmIO.py",
        "Bio/AlignIO/PhylipIO.py",
        "Bio/AlignIO/NexusIO.py",
        "Bio/SeqIO/__init__.py",
    )
    UPSTREAM_SOURCE = "; ".join(SOURCE_PATHS)
    CONSENSUS_SEMANTICS = (
        "Each non-gap column emits its residue only when that residue has more than "
        "half of non-gap observations. Otherwise nucleotide alignments emit N and "
        "protein alignments emit X; all-gap columns emit '-'. Alignment type is "
        "detected from the IUPAC nucleotide alphabet."
    )
    RENDER_SEMANTICS = (
        f"The PNG includes at most {MAX_RENDER_ROWS} rows and {MAX_RENDER_COLUMNS} "
        "columns, with visible deterministic nucleotide and protein colors."
    )
    EXIT_SEMANTICS = (
        "Unsupported formats, unreadable or malformed alignments, and writer errors "
        "fail the node; no undeclared copy of the source alignment is emitted."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment_file": ("FILE", {"label": "Alignment File"}),
                "format": (
                    "STRING",
                    {
                        "default": "clustal",
                        "options": list(cls.FORMATS),
                        "label": "Format",
                    },
                ),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_path(inputs.get("alignment_file"), "alignment_file")
        if validation is not True:
            return validation
        return validate_choice(inputs.get("format", "clustal"), "format", cls.FORMATS)

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        from Bio import AlignIO
        from Bio.Seq import Seq
        from Bio.SeqRecord import SeqRecord

        context = kwargs.pop("context", None)
        self.__class__.require_valid_inputs(kwargs)
        output_dir = node_output_dir(self.NODE_ID, context)

        alignment = AlignIO.read(
            str(kwargs["alignment_file"]),
            str(kwargs.get("format", "clustal")),
        )
        sequence_type = _alignment_type(alignment)
        alignment_length = alignment.get_alignment_length()
        consensus = _strict_majority_consensus(alignment, sequence_type)
        rendered_rows = min(len(alignment), MAX_RENDER_ROWS)
        rendered_columns = min(alignment_length, MAX_RENDER_COLUMNS)

        summary = {
            "num_sequences": len(alignment),
            "alignment_length": alignment_length,
            "ids": [record.id for record in alignment],
            "sequence_type": sequence_type,
            "consensus_rule": "strict majority among non-gap residues",
            "rendered_sequences": rendered_rows,
            "rendered_columns": rendered_columns,
            "render_truncated": (
                rendered_rows < len(alignment) or rendered_columns < alignment_length
            ),
        }
        summary_path = output_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        consensus_path = output_dir / "consensus.fasta"
        consensus_record = SeqRecord(
            Seq(consensus),
            id="consensus",
            description="strict majority consensus",
        )
        atomic_seqio_write([consensus_record], consensus_path, "fasta")

        image_path = output_dir / "alignment.png"
        _render_alignment_png(alignment, image_path, sequence_type)
        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(image_path, label="MSA View")

        return (str(summary_path), str(consensus_path), str(image_path))
