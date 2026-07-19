"""Biopython 1.87 sequence operations for BioNodulo.

Wraps common BioPython functionality into workflow nodes for sequence
manipulation, format conversion, and analysis.
"""
from __future__ import annotations

import json
import re
import struct
import zlib
from binascii import crc32
from html import escape
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode


class BiopythonNode(BaseNode):
    """Shared authority and environment contract for in-process Biopython nodes."""

    CATEGORY = "biopython"
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["biopython"]
    VERSION = "1.87"
    GIT_URL = "https://github.com/biopython/biopython.git"
    GIT_COMMIT = "7a9c76cce8c6a58db791be2b12a135af210cedf2"
    DOCUMENTATION_URL = "https://biopython.org/docs/1.87/api/"
    SOURCE_URL = "https://github.com/biopython/biopython/tree/biopython-187"
    UPSTREAM_SOURCE = "Bio/SeqIO; Bio/AlignIO; Bio/Seq.py; Bio/SeqUtils/__init__.py"
    EXIT_SEMANTICS = "Invalid formats, malformed records, and unreadable inputs raise without partial success."

    @classmethod
    def require_valid_inputs(cls, inputs: dict[str, Any]) -> None:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))


def _validate_path(value: Any, key: str) -> bool | str:
    if not str(value or "").strip():
        return f"Input '{key}' must be a non-empty path"
    return True


def _validate_choice(value: Any, key: str, choices: tuple[str, ...]) -> bool | str:
    if str(value) not in choices:
        return f"Input '{key}' must be one of: {', '.join(choices)}"
    return True


def _validate_output_name(value: Any) -> bool | str:
    name = str(value or "")
    if not name or Path(name).name != name or name in {".", ".."}:
        return "Input 'output_name' must be a filename without directory components"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        return "Input 'output_name' contains unsupported filename characters"
    return True


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc32(kind + data) & 0xFFFFFFFF)


def _write_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    scanlines = bytearray()
    row_bytes = width * 3
    for row in range(height):
        scanlines.append(0)
        start = row * row_bytes
        scanlines.extend(pixels[start:start + row_bytes])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(scanlines), level=6))
        + _png_chunk(b"IEND", b"")
    )


def _render_alignment_png(alignment: Any, path: Path) -> None:
    columns = min(alignment.get_alignment_length(), 200)
    rows = len(alignment)
    cell_width = 4
    cell_height = 8
    width = max(1, columns * cell_width)
    height = max(1, rows * cell_height)
    pixels = bytearray([255, 255, 255]) * (width * height)
    colours = {
        "A": (239, 68, 68),
        "T": (16, 185, 129),
        "U": (16, 185, 129),
        "G": (245, 158, 11),
        "C": (59, 130, 246),
        "-": (226, 232, 240),
        "N": (148, 163, 184),
    }
    for row_index, record in enumerate(alignment):
        for column_index in range(columns):
            colour = colours.get(str(record.seq[column_index]).upper(), (255, 255, 255))
            for y in range(row_index * cell_height, (row_index + 1) * cell_height):
                for x in range(column_index * cell_width, (column_index + 1) * cell_width):
                    offset = (y * width + x) * 3
                    pixels[offset:offset + 3] = bytes(colour)
    _write_png(path, width, height, pixels)


def _write_summary_preview(
    context: Any,
    out_dir: Path,
    *,
    title: str,
    columns: list[str],
    rows: list[list[Any]],
    note: str = "",
    label: str = "Summary",
) -> Path:
    """Render a small HTML summary table and register it as a node preview.

    Gives terminal sequence nodes (translate, BLAST, SeqIO) something to show
    inline instead of producing an output that goes nowhere.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    thead = "".join(f"<th>{escape(str(c))}</th>" for c in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in row) + "</tr>"
        for row in rows
    )
    note_html = f"<p class='note'>{escape(note)}</p>" if note else ""
    html_path = out_dir / "summary.html"
    html_path.write_text(
        f"""<!doctype html><meta charset=utf-8><title>{escape(title)}</title>
<style>body{{font-family:system-ui,sans-serif;padding:12px;color:#0f172a}}
h1{{font-size:13px;margin:0 0 8px;color:#475569}}
.note{{font-size:11px;color:#64748b;margin:0 0 8px}}
table{{border-collapse:collapse;font-size:12px;width:100%}}
th,td{{border:1px solid #e2e8f0;padding:4px 8px;text-align:left;vertical-align:top}}
th{{background:#f1f5f9;position:sticky;top:0}}
tr:nth-child(even) td{{background:#f8fafc}}</style>
<h1>{escape(title)}</h1>{note_html}
<table><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>""",
        encoding="utf-8",
    )
    if context is not None and hasattr(context, "register_preview"):
        context.register_preview(html_path, label=label)
    return html_path


class SeqIOReadNode(BiopythonNode):
    """Read sequence files using BioPython SeqIO."""

    NODE_ID = "bp_seqio_read"
    DISPLAY_NAME = "SeqIO Read"
    CATEGORY = "biopython"
    DESCRIPTION = "Read sequences from FASTA, GenBank, EMBL, etc."
    RETURN_TYPES = ("FILE", "FILE")
    RETURN_NAMES = ("sequences_json", "stats_json")
    REQUIRES_EXTERNAL_TOOLS = False
    FORMATS = ("fasta", "fastq", "genbank", "embl", "swiss", "stockholm", "clustal", "phylip", "nexus")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FILE", {"label": "Sequence File"}),
                "format": ("STRING", {
                    "default": "fasta",
                    "options": list(cls.FORMATS),
                    "label": "Format",
                }),
            },
            "optional": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = _validate_path(inputs.get("input_file"), "input_file")
        if validation is not True:
            return validation
        return _validate_choice(inputs.get("format", "fasta"), "format", cls.FORMATS)

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        from Bio import SeqIO

        context = kwargs.pop("context", None)
        self.__class__.require_valid_inputs(kwargs)
        output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)

        input_file = kwargs["input_file"]
        fmt = kwargs.get("format", "fasta")

        records = list(SeqIO.parse(str(input_file), fmt))
        if not records:
            raise ValueError(f"No sequence records found in {input_file}")
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

        _write_summary_preview(
            context,
            out_dir,
            title=f"SeqIO Read — {stats['count']} record(s) parsed",
            note=(
                f"total {stats['total_length']:,} bp · "
                f"avg length {stats['average_length']:.0f} bp · "
                f"avg GC {stats['average_gc']:.1f}%"
            ),
            columns=["ID", "Description", "Length (bp)", "Sequence preview"],
            rows=[
                [s["id"], s["description"], s["length"], s["seq_preview"]]
                for s in sequences[:50]
            ],
            label="Parsed Sequences",
        )

        return (str(seq_path), str(stats_path))


class SeqIOWriteNode(BiopythonNode):
    """Write sequences to a file using BioPython SeqIO."""

    NODE_ID = "bp_seqio_write"
    DISPLAY_NAME = "SeqIO Write"
    CATEGORY = "biopython"
    DESCRIPTION = "Write sequences to FASTA, GenBank, FASTQ, etc."
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_file",)
    REQUIRES_EXTERNAL_TOOLS = False
    FORMATS = ("fasta", "genbank", "embl", "clustal", "stockholm")
    MOLECULE_TYPES = ("DNA", "RNA", "protein")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sequences_json": ("FILE", {"label": "Sequences JSON"}),
                "output_format": ("STRING", {
                    "default": "fasta",
                    "options": list(cls.FORMATS),
                    "label": "Output Format",
                }),
                "output_name": ("STRING", {"default": "output.fasta", "label": "Output Filename"}),
            },
            "optional": {
                "molecule_type": (
                    "STRING",
                    {"default": "DNA", "options": list(cls.MOLECULE_TYPES), "advanced": True},
                ),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = _validate_path(inputs.get("sequences_json"), "sequences_json")
        if validation is not True:
            return validation
        validation = _validate_choice(inputs.get("output_format", "fasta"), "output_format", cls.FORMATS)
        if validation is not True:
            return validation
        validation = _validate_choice(inputs.get("molecule_type", "DNA"), "molecule_type", cls.MOLECULE_TYPES)
        if validation is not True:
            return validation
        return _validate_output_name(inputs.get("output_name", "output.fasta"))

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        from Bio import SeqIO
        from Bio.Seq import Seq
        from Bio.SeqRecord import SeqRecord

        context = kwargs.pop("context", None)
        self.__class__.require_valid_inputs(kwargs)
        output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)

        seq_json = kwargs["sequences_json"]
        fmt = kwargs.get("output_format", "fasta")
        name = kwargs.get("output_name", "output.fasta")
        molecule_type = kwargs.get("molecule_type", "DNA")

        data = json.loads(Path(seq_json).read_text(encoding="utf-8"))
        if isinstance(data, dict) and "_value" in data:
            data = data["_value"]
        if not isinstance(data, list) or not data:
            raise ValueError("Input 'sequences_json' must contain a non-empty list of sequence records")
        records = []
        for item in data:
            seq = item.get("seq_full") or item.get("seq_preview", "")
            rec = SeqRecord(
                Seq(seq),
                id=item.get("id", "unknown"),
                description=item.get("description", ""),
                annotations={"molecule_type": molecule_type},
            )
            records.append(rec)

        out_path = out_dir / name
        SeqIO.write(records, str(out_path), fmt)

        _write_summary_preview(
            context,
            out_dir,
            title=f"SeqIO Write — {len(records)} record(s) → {fmt}",
            note=f"Wrote {out_path.name} ({out_path.stat().st_size:,} bytes)",
            columns=["ID", "Description", "Length (bp)"],
            rows=[[r.id, r.description, len(r.seq)] for r in records[:50]],
            label=f"{fmt} output",
        )
        return (str(out_path),)


class SequenceTranslateNode(BiopythonNode):
    """Translate DNA sequences to protein using BioPython."""

    NODE_ID = "bp_translate"
    DISPLAY_NAME = "Translate DNA"
    CATEGORY = "biopython"
    DESCRIPTION = "Translate nucleotide sequences to protein"
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("protein_fasta",)
    REQUIRES_EXTERNAL_TOOLS = False
    TABLES = (
        "Standard",
        "Vertebrate Mitochondrial",
        "Bacterial",
        "Alternative Yeast Nuclear",
        "Ciliate Nuclear",
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FILE", {"label": "DNA FASTA"}),
            },
            "optional": {
                "table": ("STRING", {
                    "default": "Standard",
                    "options": list(cls.TABLES),
                    "label": "Translation Table",
                    "advanced": True,
                }),
                "to_stop": ("BOOLEAN", {"default": True, "label": "Stop at first STOP codon", "advanced": True}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = _validate_path(inputs.get("input_file"), "input_file")
        if validation is not True:
            return validation
        return _validate_choice(inputs.get("table", "Standard"), "table", cls.TABLES)

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        from Bio import SeqIO
        from Bio.SeqRecord import SeqRecord

        context = kwargs.pop("context", None)
        self.__class__.require_valid_inputs(kwargs)
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
        proteins: list[tuple[str, str]] = []
        for rec in SeqIO.parse(str(input_file), "fasta"):
            protein = rec.seq.translate(table=table_num, to_stop=to_stop)
            records.append(SeqRecord(protein, id=rec.id, description=f"{rec.description} [translated]"))
            proteins.append((rec.id, str(protein)))

        if not records:
            raise ValueError(f"No FASTA records found in {input_file}")

        out_path = out_dir / "protein.fasta"
        SeqIO.write(records, str(out_path), "fasta")

        _write_summary_preview(
            context,
            out_dir,
            title=f"Translate DNA — {len(records)} protein(s)",
            note=f"Translation table: {table} · to_stop={bool(to_stop)}",
            columns=["ID", "Length (aa)", "Protein sequence"],
            rows=[
                [pid, len(seq), (seq[:80] + "…") if len(seq) > 80 else seq]
                for pid, seq in proteins[:50]
            ],
            label="Translated Proteins",
        )
        return (str(out_path),)


class SequenceStatsNode(BiopythonNode):
    """Compute sequence statistics (GC%, length, molecular weight)."""

    NODE_ID = "bp_seq_stats"
    DISPLAY_NAME = "Sequence Stats"
    CATEGORY = "biopython"
    DESCRIPTION = "Compute GC content, length, and molecular weight"
    RETURN_TYPES = ("FILE", "FILE", "FILE")
    RETURN_NAMES = ("stats_json", "stats_tsv", "stats_csv")
    REQUIRES_EXTERNAL_TOOLS = False
    FORMATS = ("fasta", "fastq", "genbank")
    SEQUENCE_TYPES = ("DNA", "RNA", "protein")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FILE", {"label": "Sequence File"}),
            },
            "optional": {
                "format": ("STRING", {"default": "fasta", "options": list(cls.FORMATS), "label": "Format", "advanced": True}),
                "sequence_type": (
                    "STRING",
                    {"default": "DNA", "options": list(cls.SEQUENCE_TYPES), "advanced": True},
                ),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = _validate_path(inputs.get("input_file"), "input_file")
        if validation is not True:
            return validation
        validation = _validate_choice(inputs.get("format", "fasta"), "format", cls.FORMATS)
        if validation is not True:
            return validation
        return _validate_choice(inputs.get("sequence_type", "DNA"), "sequence_type", cls.SEQUENCE_TYPES)

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        from Bio import SeqIO
        from Bio.SeqUtils import molecular_weight, gc_fraction

        context = kwargs.pop("context", None)
        self.__class__.require_valid_inputs(kwargs)
        output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)

        input_file = kwargs["input_file"]
        fmt = kwargs.get("format", "fasta")
        sequence_type = kwargs.get("sequence_type", "DNA")

        results = []
        for rec in SeqIO.parse(str(input_file), fmt):
            seq_str = str(rec.seq)
            gc = gc_fraction(rec.seq) * 100 if sequence_type != "protein" else None
            try:
                mw = molecular_weight(rec.seq, seq_type=sequence_type)
            except Exception:
                mw = None
            results.append({
                "id": rec.id,
                "length": len(seq_str),
                "gc_content": round(gc, 2) if gc is not None else None,
                "molecular_weight": round(mw, 2) if mw else None,
            })

        if not results:
            raise ValueError(f"No sequence records found in {input_file}")

        out_path = out_dir / "stats.json"
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

        # Also emit a TSV alongside the JSON. Lets the user wire the stats
        # into a generic table_preview node without hand-rolling HTML — the
        # table view can stream just the head if the dataset is large.
        tsv_path = out_dir / "stats.tsv"
        with tsv_path.open("w", encoding="utf-8") as fh:
            fh.write("id\tlength\tgc_content\tmolecular_weight\n")
            for r in results:
                gc = r["gc_content"] if r["gc_content"] is not None else ""
                mw = r["molecular_weight"] if r["molecular_weight"] is not None else ""
                fh.write(f"{r['id']}\t{r['length']}\t{gc}\t{mw}\n")

        # And a CSV, so charting nodes that expect comma-separated input
        # (e.g. the ggplot2-based r_plot node) can consume the stats directly.
        csv_path = out_dir / "stats.csv"
        with csv_path.open("w", encoding="utf-8") as fh:
            fh.write("id,length,gc_content,molecular_weight\n")
            for r in results:
                gc = r["gc_content"] if r["gc_content"] is not None else ""
                mw = r["molecular_weight"] if r["molecular_weight"] is not None else ""
                fh.write(f"{r['id']},{r['length']},{gc},{mw}\n")

        return (str(out_path), str(tsv_path), str(csv_path))


class BLASTSearchNode(BiopythonNode):
    """Run a local BLAST search using BioPython's NCBIStandalone wrappers."""

    NODE_ID = "bp_blast"
    DISPLAY_NAME = "BLAST Search"
    REQUIRED_CONDA_PACKAGES = ["biopython", "blast"]
    CATEGORY = "biopython"
    DESCRIPTION = "Run local BLAST (requires blast+ installed)"
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("blast_xml",)
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ["blastn", "blastp", "blastx", "tblastn", "tblastx"]
    VERSION = "2.17.0"
    GIT_URL = "https://www.ncbi.nlm.nih.gov/books/NBK279684/"
    GIT_COMMIT = "898be99790d620053991c7761797f5328281fffc6ed2ca0c95504e619be8f68a"
    DOCUMENTATION_URL = "https://www.ncbi.nlm.nih.gov/books/NBK279684/"
    SOURCE_URL = "https://www.ncbi.nlm.nih.gov/books/NBK279684/?report=xml"
    SOURCE_SHA256 = "898be99790d620053991c7761797f5328281fffc6ed2ca0c95504e619be8f68a"
    UPSTREAM_SOURCE = "BLAST+ command-line applications: -query, -subject, -evalue, -max_target_seqs, -outfmt, -out"
    EXIT_SEMANTICS = "Any non-zero BLAST+ exit is fatal; the selected output file must be produced."
    PROGRAMS = ("blastn", "blastp", "blastx", "tblastn", "tblastx")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("FILE", {"label": "Query FASTA"}),
                "subject": ("FILE", {"label": "Subject/DB FASTA"}),
                "program": ("STRING", {
                    "default": "blastn",
                    "options": list(cls.PROGRAMS),
                    "label": "BLAST Program",
                }),
            },
            "optional": {
                "evalue": ("FLOAT", {"default": 0.001, "min": 0.0, "max": 100.0, "step": 0.001, "label": "E-value threshold", "advanced": True}),
                "max_hits": ("INT", {"default": 10, "min": 1, "max": 500, "label": "Max Hits", "advanced": True}),
                "outfmt": ("STRING", {"default": "5", "options": ["5"], "label": "XML Output Format", "advanced": True}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("query", "subject"):
            validation = _validate_path(inputs.get(key), key)
            if validation is not True:
                return validation
        validation = _validate_choice(inputs.get("program", "blastn"), "program", cls.PROGRAMS)
        if validation is not True:
            return validation
        if str(inputs.get("outfmt", "5")) != "5":
            return "Input 'outfmt' must be 5 because this node exposes BLAST XML"
        try:
            evalue = float(inputs.get("evalue", 0.001))
            max_hits = int(inputs.get("max_hits", 10))
        except (TypeError, ValueError):
            return "Inputs 'evalue' and 'max_hits' must be numeric"
        if evalue < 0:
            return "Input 'evalue' must be non-negative"
        if not 1 <= max_hits <= 500:
            return "Input 'max_hits' must be between 1 and 500"
        return True

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop("context", None)
        self.__class__.require_valid_inputs(kwargs)
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
        if not out_path.is_file():
            raise RuntimeError(f"BLAST completed without producing {out_path.name}")

        self._register_hits_preview(context, out_dir, out_path, outfmt, program)
        return (str(out_path),)

    @staticmethod
    def _register_hits_preview(
        context: Any, out_dir: Path, out_path: Path, outfmt: str, program: str
    ) -> None:
        """Summarise BLAST output so the node shows hits instead of ending blank."""
        rows: list[list[Any]] = []
        try:
            if str(outfmt) == "5":
                from Bio.Blast import NCBIXML

                with out_path.open(encoding="utf-8") as handle:
                    for record in NCBIXML.parse(handle):
                        query = record.query.split()[0] if record.query else "query"
                        for alignment in record.alignments:
                            for hsp in alignment.hsps:
                                ident = (
                                    100.0 * hsp.identities / hsp.align_length
                                    if hsp.align_length
                                    else 0.0
                                )
                                rows.append([
                                    query,
                                    alignment.hit_id or alignment.hit_def.split()[0],
                                    f"{ident:.1f}%",
                                    f"{hsp.expect:.1e}",
                                    f"{hsp.score:g}",
                                ])
            else:
                # Tabular outfmt 6/7 — show the head verbatim.
                for line in out_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("#") or not line.strip():
                        continue
                    rows.append(line.split("\t")[:5])
        except Exception:  # noqa: BLE001 — a preview must never fail the run
            rows = []

        _write_summary_preview(
            context,
            out_dir,
            title=f"BLAST ({program}) — {len(rows)} hit(s)",
            note=f"Output format {outfmt} · {out_path.name}",
            columns=["Query", "Subject", "% identity", "E-value", "Score"],
            rows=rows[:50],
            label="BLAST Hits",
        )


class MSAViewNode(BiopythonNode):
    """View a multiple sequence alignment using BioPython's AlignIO."""

    NODE_ID = "bp_msa_view"
    DISPLAY_NAME = "MSA View"
    CATEGORY = "biopython"
    DESCRIPTION = "Read and summarize a multiple sequence alignment, render a PNG view"
    RETURN_TYPES = ("FILE", "FILE", "IMAGE")
    RETURN_NAMES = ("alignment_json", "consensus_fasta", "alignment_image")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["biopython"]
    FORMATS = ("clustal", "stockholm", "phylip", "fasta", "nexus")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment_file": ("FILE", {"label": "Alignment File"}),
                "format": ("STRING", {
                    "default": "clustal",
                    "options": list(cls.FORMATS),
                    "label": "Format",
                }),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = _validate_path(inputs.get("alignment_file"), "alignment_file")
        if validation is not True:
            return validation
        return _validate_choice(inputs.get("format", "clustal"), "format", cls.FORMATS)

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        from Bio import AlignIO, SeqIO
        from Bio.Seq import Seq
        from Bio.SeqRecord import SeqRecord

        context = kwargs.pop("context", None)
        self.__class__.require_valid_inputs(kwargs)
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
            counts: dict[str, int] = {}
            for char in col.upper():
                if char != "-":
                    counts[char] = counts.get(char, 0) + 1
            consensus.append(max(counts, key=lambda k: counts[k]) if counts else "-")

        consensus_rec = SeqRecord(Seq("".join(consensus)), id="consensus", description="majority rule consensus")
        consensus_path = out_dir / "consensus.fasta"
        AlignIO.write([alignment], str(out_dir / "alignment.fasta"), "fasta")
        SeqIO.write([consensus_rec], str(consensus_path), "fasta")

        summary_path = out_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        # Render a deterministic dependency-free alignment grid. The full
        # alignment remains available in alignment.fasta.
        image_path = out_dir / "alignment.png"
        _render_alignment_png(alignment, image_path)

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(image_path, label="MSA View")

        return (str(summary_path), str(consensus_path), str(image_path))
