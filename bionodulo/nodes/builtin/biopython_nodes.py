"""BioPython integration nodes for BioNodulo.

Wraps common BioPython functionality into workflow nodes for sequence
manipulation, format conversion, and analysis.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode


class SeqIOReadNode(BaseNode):
    """Read sequence files using BioPython SeqIO."""

    NODE_ID = "bp_seqio_read"
    DISPLAY_NAME = "SeqIO Read"
    CATEGORY = "biopython"
    DESCRIPTION = "Read sequences from FASTA, GenBank, EMBL, etc."
    RETURN_TYPES = ("FILE", "FILE")
    RETURN_NAMES = ("sequences_json", "stats_json")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FILE", {"label": "Sequence File"}),
                "format": ("STRING", {
                    "default": "fasta",
                    "options": ["fasta", "fastq", "genbank", "embl", "swiss", "stockholm", "clustal", "phylip", "nexus"],
                    "label": "Format",
                }),
            },
            "optional": {
                "alphabet": ("STRING", {"default": "", "options": ["", "dna", "rna", "protein"], "label": "Alphabet Hint", "advanced": True}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        from Bio import SeqIO

        context = kwargs.pop("context", None)
        output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)

        input_file = kwargs["input_file"]
        fmt = kwargs.get("format", "fasta")

        records = list(SeqIO.parse(str(input_file), fmt))
        sequences = []
        total_len = 0
        gc_sum = 0.0

        for rec in records:
            seq_str = str(rec.seq)
            sequences.append({
                "id": rec.id,
                "description": rec.description,
                "length": len(seq_str),
                "seq_preview": seq_str[:100],
                "seq_full": seq_str,
            })
            total_len += len(seq_str)
            gc = seq_str.count("G") + seq_str.count("C")
            gc_sum += gc / len(seq_str) * 100 if seq_str else 0

        stats = {
            "count": len(records),
            "total_length": total_len,
            "average_length": total_len / len(records) if records else 0,
            "average_gc": gc_sum / len(records) if records else 0,
        }

        seq_path = out_dir / "sequences.json"
        stats_path = out_dir / "stats.json"
        seq_path.write_text(json.dumps(sequences, indent=2), encoding="utf-8")
        stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

        return (str(seq_path), str(stats_path))


class SeqIOWriteNode(BaseNode):
    """Write sequences to a file using BioPython SeqIO."""

    NODE_ID = "bp_seqio_write"
    DISPLAY_NAME = "SeqIO Write"
    CATEGORY = "biopython"
    DESCRIPTION = "Write sequences to FASTA, GenBank, FASTQ, etc."
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_file",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sequences_json": ("FILE", {"label": "Sequences JSON"}),
                "output_format": ("STRING", {
                    "default": "fasta",
                    "options": ["fasta", "fastq", "genbank", "embl", "swiss", "stockholm"],
                    "label": "Output Format",
                }),
                "output_name": ("STRING", {"default": "output.fasta", "label": "Output Filename"}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        from Bio import SeqIO
        from Bio.Seq import Seq
        from Bio.SeqRecord import SeqRecord

        context = kwargs.pop("context", None)
        output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)

        seq_json = kwargs["sequences_json"]
        fmt = kwargs.get("output_format", "fasta")
        name = kwargs.get("output_name", "output.fasta")

        data = json.loads(Path(seq_json).read_text(encoding="utf-8"))
        if isinstance(data, dict) and "_value" in data:
            data = data["_value"]
        records = []
        for item in data:
            seq = item.get("seq_full") or item.get("seq_preview", "")
            rec = SeqRecord(
                Seq(seq),
                id=item.get("id", "unknown"),
                description=item.get("description", ""),
                annotations={"molecule_type": "DNA"},
            )
            records.append(rec)

        out_path = out_dir / name
        SeqIO.write(records, str(out_path), fmt)
        return (str(out_path),)


class SequenceTranslateNode(BaseNode):
    """Translate DNA sequences to protein using BioPython."""

    NODE_ID = "bp_translate"
    DISPLAY_NAME = "Translate DNA"
    CATEGORY = "biopython"
    DESCRIPTION = "Translate nucleotide sequences to protein"
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("protein_fasta",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FILE", {"label": "DNA FASTA"}),
            },
            "optional": {
                "table": ("STRING", {
                    "default": "Standard",
                    "options": ["Standard", "Vertebrate Mitochondrial", "Bacterial", "Alternative Yeast Nuclear", "Ciliate Nuclear"],
                    "label": "Translation Table",
                    "advanced": True,
                }),
                "to_stop": ("BOOLEAN", {"default": True, "label": "Stop at first STOP codon", "advanced": True}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        from Bio import SeqIO
        from Bio.SeqRecord import SeqRecord

        context = kwargs.pop("context", None)
        output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)

        input_file = kwargs["input_file"]
        table = kwargs.get("table", "Standard")
        to_stop = kwargs.get("to_stop", True)

        table_map = {
            "Standard": 1,
            "Vertebrate Mitochondrial": 2,
            "Bacterial": 11,
            "Alternative Yeast Nuclear": 12,
            "Ciliate Nuclear": 6,
        }
        table_num = table_map.get(table, 1)

        records = []
        for rec in SeqIO.parse(str(input_file), "fasta"):
            protein = rec.seq.translate(table=table_num, to_stop=to_stop)
            records.append(SeqRecord(protein, id=rec.id, description=f"{rec.description} [translated]"))

        out_path = out_dir / "protein.fasta"
        SeqIO.write(records, str(out_path), "fasta")
        return (str(out_path),)


class SequenceStatsNode(BaseNode):
    """Compute sequence statistics (GC%, length, molecular weight)."""

    NODE_ID = "bp_seq_stats"
    DISPLAY_NAME = "Sequence Stats"
    CATEGORY = "biopython"
    DESCRIPTION = "Compute GC content, length, and molecular weight"
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("stats_json",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FILE", {"label": "Sequence File"}),
            },
            "optional": {
                "format": ("STRING", {"default": "fasta", "options": ["fasta", "fastq", "genbank"], "label": "Format", "advanced": True}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        from Bio import SeqIO
        from Bio.SeqUtils import molecular_weight, gc_fraction

        context = kwargs.pop("context", None)
        output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)

        input_file = kwargs["input_file"]
        fmt = kwargs.get("format", "fasta")

        results = []
        for rec in SeqIO.parse(str(input_file), fmt):
            seq_str = str(rec.seq)
            gc = gc_fraction(rec.seq) * 100
            try:
                mw = molecular_weight(rec.seq)
            except Exception:
                mw = None
            results.append({
                "id": rec.id,
                "length": len(seq_str),
                "gc_content": round(gc, 2),
                "molecular_weight": round(mw, 2) if mw else None,
            })

        out_path = out_dir / "stats.json"
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        return (str(out_path),)


class BLASTSearchNode(BaseNode):
    """Run a local BLAST search using BioPython's NCBIStandalone wrappers."""

    NODE_ID = "bp_blast"
    DISPLAY_NAME = "BLAST Search"
    REQUIRED_CONDA_PACKAGES = ['blast']
    CATEGORY = "biopython"
    DESCRIPTION = "Run local BLAST (requires blast+ installed)"
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("blast_xml",)
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ["blastn"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("FILE", {"label": "Query FASTA"}),
                "subject": ("FILE", {"label": "Subject/DB FASTA"}),
                "program": ("STRING", {
                    "default": "blastn",
                    "options": ["blastn", "blastp", "blastx", "tblastn", "tblastx"],
                    "label": "BLAST Program",
                }),
            },
            "optional": {
                "evalue": ("FLOAT", {"default": 0.001, "min": 0.0, "max": 100.0, "step": 0.001, "label": "E-value threshold", "advanced": True}),
                "max_hits": ("INT", {"default": 10, "min": 1, "max": 500, "label": "Max Hits", "advanced": True}),
                "outfmt": ("STRING", {"default": "5", "options": ["5", "6", "7"], "label": "Output Format", "advanced": True}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop("context", None)
        output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)

        query = kwargs["query"]
        subject = kwargs["subject"]
        program = kwargs.get("program", "blastn")
        evalue = kwargs.get("evalue", 0.001)
        max_hits = kwargs.get("max_hits", 10)
        outfmt = kwargs.get("outfmt", "5")

        out_path = out_dir / ("blast_result.xml" if outfmt == "5" else "blast_result.tsv")

        cmd = [
            program,
            "-query", str(query),
            "-subject", str(subject),
            "-evalue", str(evalue),
            "-max_target_seqs", str(max_hits),
            "-outfmt", str(outfmt),
            "-out", str(out_path),
        ]

        if context is not None and hasattr(context, "run_command"):
            result = await context.run_command(cmd, cwd=str(out_dir))
        else:
            import asyncio
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()
            result = {"returncode": proc.returncode}

        if result.get("returncode", 0) != 0:
            raise RuntimeError(f"BLAST failed: {result.get('stderr', '')}")

        return (str(out_path),)


class MSAViewNode(BaseNode):
    """View a multiple sequence alignment using BioPython's AlignIO."""

    NODE_ID = "bp_msa_view"
    DISPLAY_NAME = "MSA View"
    CATEGORY = "biopython"
    DESCRIPTION = "Read and summarize a multiple sequence alignment"
    RETURN_TYPES = ("FILE", "FILE")
    RETURN_NAMES = ("alignment_json", "consensus_fasta")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment_file": ("FILE", {"label": "Alignment File"}),
                "format": ("STRING", {
                    "default": "clustal",
                    "options": ["clustal", "stockholm", "phylip", "fasta", "nexus"],
                    "label": "Format",
                }),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        from Bio import AlignIO, SeqIO
        from Bio.Align import MultipleSeqAlignment
        from Bio.Seq import Seq
        from Bio.SeqRecord import SeqRecord

        context = kwargs.pop("context", None)
        output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)

        aln_file = kwargs["alignment_file"]
        fmt = kwargs.get("format", "clustal")

        alignment = AlignIO.read(str(aln_file), fmt)
        summary = {
            "num_sequences": len(alignment),
            "alignment_length": alignment.get_alignment_length(),
            "ids": [rec.id for rec in alignment],
        }

        # Simple majority-rule consensus
        consensus = []
        for i in range(alignment.get_alignment_length()):
            col = alignment[:, i]
            counts = {}
            for char in col.upper():
                if char != "-":
                    counts[char] = counts.get(char, 0) + 1
            consensus.append(max(counts, key=counts.get) if counts else "-")

        consensus_rec = SeqRecord(Seq("".join(consensus)), id="consensus", description="majority rule consensus")
        consensus_path = out_dir / "consensus.fasta"
        AlignIO.write([alignment], str(out_dir / "alignment.fasta"), "fasta")
        SeqIO.write([consensus_rec], str(consensus_path), "fasta")

        summary_path = out_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        return (str(summary_path), str(consensus_path))
