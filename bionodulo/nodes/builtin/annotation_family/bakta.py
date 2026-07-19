"""Focused Bakta owner."""

from .evidence import attach_evidence
from .legacy import BaktaNode as _LegacyBaktaNode


@attach_evidence
class BaktaNode(_LegacyBaktaNode):
    NODE_ID = "bakta"
    REQUIRED_EXECUTABLES = ["bakta", "ln", "mkdir", "cp", "tee"]
    REQUIRED_CONDA_PACKAGES = ["bakta", "coreutils"]

    OUTPUT_PREFIX = "bakta_output"
    OUTPUT_FILES = {
        "file_tsv": ("annotation_tsv.tsv", f"bakta_output/{OUTPUT_PREFIX}.tsv"),
        "file_gff3": ("annotation_gff3.gff3", f"bakta_output/{OUTPUT_PREFIX}.gff3"),
        "file_gbff": ("annotation_gbff.gbff", f"bakta_output/{OUTPUT_PREFIX}.gbff"),
        "file_embl": ("annotation_embl.embl", f"bakta_output/{OUTPUT_PREFIX}.embl"),
        "file_fna": ("annotation_fna.fasta", f"bakta_output/{OUTPUT_PREFIX}.fna"),
        "file_ffn": ("annotation_ffn.fasta", f"bakta_output/{OUTPUT_PREFIX}.ffn"),
        "file_faa": ("annotation_faa.fasta", f"bakta_output/{OUTPUT_PREFIX}.faa"),
        "hypo_tsv": (
            "hypotheticals_tsv.tsv",
            f"bakta_output/{OUTPUT_PREFIX}.hypotheticals.tsv",
        ),
        "hypo_fa": (
            "hypotheticals_faa.fasta",
            f"bakta_output/{OUTPUT_PREFIX}.hypotheticals.faa",
        ),
        "sum_txt": ("summary_txt.txt", f"bakta_output/{OUTPUT_PREFIX}.txt"),
        "file_json": ("annotation_json.json", f"bakta_output/{OUTPUT_PREFIX}.json"),
        "file_plot": ("annotation_plot.svg", f"bakta_output/{OUTPUT_PREFIX}.svg"),
        "log_txt": ("logfile.txt", "logfile.txt"),
    }
