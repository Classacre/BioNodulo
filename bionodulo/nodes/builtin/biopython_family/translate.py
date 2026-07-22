"""Biopython nucleotide translation."""

from __future__ import annotations

from typing import Any

from .adapter import (
    BiopythonNode,
    atomic_seqio_write,
    node_output_dir,
    validate_choice,
    validate_path,
    write_summary_preview,
)


class SequenceTranslateNode(BiopythonNode):
    """Translate FASTA nucleotide records with Bio.Seq.translate."""

    NODE_ID = "bp_translate"
    DISPLAY_NAME = "Translate DNA"
    DESCRIPTION = "Translate DNA or RNA FASTA records with a selected NCBI codon table."
    SEARCH_ALIASES = ["BioNodulo builtin", "Biopython", "translate", "codon table", "protein FASTA"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("protein_fasta",)
    TABLE_IDS = {
        "Standard": 1,
        "Vertebrate Mitochondrial": 2,
        "Bacterial": 11,
        "Alternative Yeast Nuclear": 12,
        "Ciliate Nuclear": 6,
    }
    TABLES = tuple(TABLE_IDS)
    SOURCE_PATHS = ("Bio/Seq.py", "Bio/Data/CodonTable.py", "Bio/SeqIO/__init__.py")
    UPSTREAM_SOURCE = "; ".join(SOURCE_PATHS)
    UPSTREAM_DEFAULTS = {"table": "Standard", "to_stop": False, "cds": False}
    WRAPPER_DEFAULTS = {
        "table": "Standard",
        "to_stop": True,
        "cds": False,
    }
    TRANSLATION_SEMANTICS = (
        "The stable node translates from frame zero with cds=False. to_stop=True truncates before the first in-frame stop; "
        "partial terminal codons follow Biopython's warning-and-ignore behavior."
    )
    EXIT_SEMANTICS = (
        "Malformed FASTA, invalid codons, invalid table combinations, and inputs with no records fail before protein.fasta is published."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FASTA", {"label": "Nucleotide FASTA"}),
            },
            "optional": {
                "table": (
                    "STRING",
                    {
                        "default": "Standard",
                        "options": list(cls.TABLES),
                        "label": "Translation Table",
                        "advanced": True,
                    },
                ),
                "to_stop": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label": "Stop at first STOP codon",
                        "description": "BioNodulo compatibility default; Biopython's function default is false",
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
        return validate_choice(inputs.get("table", "Standard"), "table", cls.TABLES)

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        from Bio import SeqIO
        from Bio.SeqRecord import SeqRecord

        context = kwargs.pop("context", None)
        self.__class__.require_valid_inputs(kwargs)
        output_dir = node_output_dir(self.NODE_ID, context)

        input_file = str(kwargs["input_file"])
        table = str(kwargs.get("table", "Standard"))
        to_stop = bool(kwargs.get("to_stop", True))
        table_id = self.TABLE_IDS[table]

        records: list[SeqRecord] = []
        proteins: list[tuple[str, str]] = []
        for record in SeqIO.parse(input_file, "fasta"):
            protein = record.seq.translate(table=table_id, to_stop=to_stop)
            records.append(
                SeqRecord(
                    protein,
                    id=record.id,
                    description=f"{record.description} [translated]",
                )
            )
            proteins.append((record.id, str(protein)))
        if not records:
            raise ValueError(f"No FASTA records found in {input_file}")

        output_path = output_dir / "protein.fasta"
        atomic_seqio_write(records, output_path, "fasta")
        write_summary_preview(
            context,
            output_dir,
            title=f"Translate DNA — {len(records)} protein(s)",
            note=f"NCBI translation table {table_id}: {table} · to_stop={to_stop}",
            columns=["ID", "Length (aa)", "Protein sequence"],
            rows=[
                [record_id, len(sequence), (sequence[:80] + "…") if len(sequence) > 80 else sequence]
                for record_id, sequence in proteins[:50]
            ],
            label="Translated Proteins",
        )
        return (str(output_path),)
