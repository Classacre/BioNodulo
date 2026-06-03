"""BioNodulo type system for node ports and file formats.

Defines all bioinformatics data types used as node port types, along with
compatibility checking logic for workflow validation.
"""
from __future__ import annotations

from typing import Any
from enum import Enum


class BioType(str, Enum):
    """Core bioinformatics data types for node ports."""

    # Generic types
    STRING = "STRING"
    INT = "INT"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"
    FILE = "FILE"
    DIRECTORY = "DIRECTORY"
    ANY = "ANY"

    # Sequencing data
    FASTQ = "FASTQ"
    FASTQ_LIST = "FASTQ_LIST"
    FASTA = "FASTA"
    FASTA_INDEX = "FASTA_INDEX"

    # Alignment
    SAM = "SAM"
    BAM = "BAM"
    BAI = "BAI"
    CRAM = "CRAM"
    INDEX_DIR = "INDEX_DIR"

    # Variants
    VCF = "VCF"
    VCF_GZ = "VCF_GZ"
    BCF = "BCF"
    VCF_INDEX = "VCF_INDEX"

    # Annotation
    GFF = "GFF"
    GTF = "GTF"
    GFF_GTF = "GFF_GTF"
    BED = "BED"

    # Assembly
    ASSEMBLY = "ASSEMBLY"
    CONTIGS = "CONTIGS"
    SCAFFOLDS = "SCAFFOLDS"

    # Pangenomics
    GFA = "GFA"
    ODGI = "ODGI"

    # Quantification
    COUNTS = "COUNTS"
    TPM_MATRIX = "TPM_MATRIX"
    ABUNDANCE = "ABUNDANCE"

    # QC / Reports
    QC_REPORT_DIR = "QC_REPORT_DIR"
    MULTIQC_REPORT = "MULTIQC_REPORT"
    HTML_REPORT = "HTML_REPORT"
    PDF_REPORT = "PDF_REPORT"
    STATS_FILE = "STATS_FILE"

    # RNA-seq specific
    TRANSCRIPTS = "TRANSCRIPTS"
    GENE_EXPRESSION = "GENE_EXPRESSION"
    TX_EXPRESSION = "TX_EXPRESSION"

    # Metagenomics
    KRAKEN_REPORT = "KRAKEN_REPORT"
    KRAKEN_OUTPUT = "KRAKEN_OUTPUT"
    METAPHLAN_PROFILE = "METAPHLAN_PROFILE"
    HUMANN_OUTPUT = "HUMANN_OUTPUT"
    BINS = "BINS"

    # Phylogeny
    ALIGNMENT = "ALIGNMENT"
    PHYLOGENY_TREE = "PHYLOGENY_TREE"

    # ChIP-seq
    PEAKS = "PEAKS"
    BIGWIG = "BIGWIG"
    NARROW_PEAK = "NARROW_PEAK"
    BROAD_PEAK = "BROAD_PEAK"

    # Single-cell
    SAMPLE_SHEET = "SAMPLE_SHEET"
    CELL_RANGER_OUT = "CELL_RANGER_OUT"
    H5AD = "H5AD"
    SEURAT_OBJ = "SEURAT_OBJ"

    # Phenomics / Other
    PAML_RESULTS = "PAML_RESULTS"
    IMAGE = "IMAGE"
    JSON = "JSON"
    YAML = "YAML"
    CSV = "CSV"
    TSV = "TSV"


_COMPATIBILITY: dict[BioType, set[BioType]] = {
    BioType.ANY: set(),
    BioType.FILE: {BioType.STRING},
    BioType.DIRECTORY: {BioType.STRING},
    BioType.FASTQ: {BioType.FILE, BioType.STRING},
    BioType.FASTQ_LIST: {BioType.FILE, BioType.STRING},
    BioType.FASTA: {BioType.FILE, BioType.STRING, BioType.ASSEMBLY, BioType.CONTIGS, BioType.TRANSCRIPTS},
    BioType.FASTA_INDEX: {BioType.FILE, BioType.STRING},
    BioType.SAM: {BioType.FILE, BioType.STRING},
    BioType.BAM: {BioType.FILE, BioType.STRING, BioType.SAM},
    BioType.BAI: {BioType.FILE, BioType.STRING},
    BioType.CRAM: {BioType.FILE, BioType.STRING, BioType.BAM},
    BioType.INDEX_DIR: {BioType.DIRECTORY, BioType.STRING},
    BioType.VCF: {BioType.FILE, BioType.STRING},
    BioType.VCF_GZ: {BioType.FILE, BioType.STRING, BioType.VCF},
    BioType.BCF: {BioType.FILE, BioType.STRING, BioType.VCF, BioType.VCF_GZ},
    BioType.VCF_INDEX: {BioType.FILE, BioType.STRING},
    BioType.GFF: {BioType.FILE, BioType.STRING, BioType.GFF_GTF},
    BioType.GTF: {BioType.FILE, BioType.STRING, BioType.GFF_GTF},
    BioType.GFF_GTF: {BioType.FILE, BioType.STRING},
    BioType.BED: {BioType.FILE, BioType.STRING},
    BioType.ASSEMBLY: {BioType.FILE, BioType.STRING, BioType.FASTA, BioType.CONTIGS},
    BioType.CONTIGS: {BioType.FILE, BioType.STRING, BioType.FASTA, BioType.ASSEMBLY},
    BioType.SCAFFOLDS: {BioType.FILE, BioType.STRING, BioType.FASTA, BioType.ASSEMBLY, BioType.CONTIGS},
    BioType.GFA: {BioType.FILE, BioType.STRING},
    BioType.ODGI: {BioType.FILE, BioType.STRING},
    BioType.COUNTS: {BioType.FILE, BioType.STRING, BioType.TSV, BioType.CSV},
    BioType.TPM_MATRIX: {BioType.FILE, BioType.STRING, BioType.TSV, BioType.CSV},
    BioType.ABUNDANCE: {BioType.FILE, BioType.STRING, BioType.TSV, BioType.CSV},
    BioType.GENE_EXPRESSION: {BioType.FILE, BioType.STRING, BioType.TSV, BioType.CSV, BioType.COUNTS, BioType.TPM_MATRIX},
    BioType.TX_EXPRESSION: {BioType.FILE, BioType.STRING, BioType.TSV, BioType.CSV},
    BioType.QC_REPORT_DIR: {BioType.DIRECTORY, BioType.STRING},
    BioType.MULTIQC_REPORT: {BioType.HTML_REPORT, BioType.FILE, BioType.STRING},
    BioType.HTML_REPORT: {BioType.FILE, BioType.STRING},
    BioType.PDF_REPORT: {BioType.FILE, BioType.STRING},
    BioType.STATS_FILE: {BioType.FILE, BioType.STRING, BioType.TSV, BioType.CSV},
    BioType.KRAKEN_REPORT: {BioType.FILE, BioType.STRING},
    BioType.KRAKEN_OUTPUT: {BioType.FILE, BioType.STRING},
    BioType.METAPHLAN_PROFILE: {BioType.FILE, BioType.STRING, BioType.TSV},
    BioType.HUMANN_OUTPUT: {BioType.DIRECTORY, BioType.STRING},
    BioType.BINS: {BioType.DIRECTORY, BioType.STRING},
    BioType.ALIGNMENT: {BioType.FILE, BioType.STRING, BioType.FASTA},
    BioType.PHYLOGENY_TREE: {BioType.FILE, BioType.STRING},
    BioType.PEAKS: {BioType.FILE, BioType.STRING, BioType.BED},
    BioType.BIGWIG: {BioType.FILE, BioType.STRING},
    BioType.NARROW_PEAK: {BioType.FILE, BioType.STRING, BioType.PEAKS, BioType.BED},
    BioType.BROAD_PEAK: {BioType.FILE, BioType.STRING, BioType.PEAKS, BioType.BED},
    BioType.SAMPLE_SHEET: {BioType.FILE, BioType.STRING, BioType.CSV},
    BioType.CELL_RANGER_OUT: {BioType.DIRECTORY, BioType.STRING},
    BioType.H5AD: {BioType.FILE, BioType.STRING},
    BioType.SEURAT_OBJ: {BioType.FILE, BioType.STRING},
    BioType.STRING: set(),
    BioType.INT: set(),
    BioType.FLOAT: set(),
    BioType.BOOLEAN: set(),
    BioType.JSON: {BioType.FILE, BioType.STRING},
    BioType.YAML: {BioType.FILE, BioType.STRING},
    BioType.CSV: {BioType.FILE, BioType.STRING, BioType.TSV},
    BioType.TSV: {BioType.FILE, BioType.STRING, BioType.CSV},
    BioType.IMAGE: {BioType.FILE, BioType.STRING},
    BioType.PAML_RESULTS: {BioType.FILE, BioType.STRING},
    BioType.TRANSCRIPTS: {BioType.FILE, BioType.STRING, BioType.FASTA},
}


def is_compatible(source_type: str | BioType, target_type: str | BioType) -> bool:
    """Check if a connection from source_type to target_type is valid."""
    source = _coerce_to_biotype(source_type)
    target = _coerce_to_biotype(target_type)
    if source is None or target is None:
        return str(source_type) == str(target_type)
    if source == target:
        return True
    if source == BioType.ANY or target == BioType.ANY:
        return True
    compatible_targets = _COMPATIBILITY.get(source, set())
    if target in compatible_targets:
        return True
    return False


def get_common_type(types: list[str | BioType]) -> BioType | None:
    """Find the most specific common type among a list of types."""
    if not types:
        return None
    biotypes = [_coerce_to_biotype(t) for t in types]
    if None in biotypes:
        return None
    first = biotypes[0]
    assert first is not None
    common: set[BioType] = {first}
    for bt in biotypes[1:]:
        if bt is None:
            return None
        new_common: set[BioType] = set()
        for c in common:
            if c == bt:
                new_common.add(c)
            elif bt in _COMPATIBILITY.get(c, set()):
                new_common.add(c)
            elif c in _COMPATIBILITY.get(bt, set()):
                new_common.add(bt)
        common = new_common
        if not common:
            return BioType.ANY
    return min(common, key=lambda x: len(_COMPATIBILITY.get(x, set())))


def _coerce_to_biotype(value: str | BioType | Any) -> BioType | None:
    """Coerce a string or enum value to a BioType enum member."""
    if isinstance(value, BioType):
        return value
    if isinstance(value, str):
        try:
            return BioType(value.upper())
        except ValueError:
            return None
    return None


def file_extension_for(biotype: str | BioType) -> str:
    """Get the canonical file extension for a BioType."""
    mapping: dict[BioType, str] = {
        BioType.FASTQ: ".fastq.gz",
        BioType.FASTQ_LIST: ".fastq.gz",
        BioType.FASTA: ".fasta",
        BioType.FASTA_INDEX: ".fai",
        BioType.SAM: ".sam",
        BioType.BAM: ".bam",
        BioType.BAI: ".bam.bai",
        BioType.CRAM: ".cram",
        BioType.VCF: ".vcf",
        BioType.VCF_GZ: ".vcf.gz",
        BioType.BCF: ".bcf",
        BioType.VCF_INDEX: ".csi",
        BioType.GFF: ".gff3",
        BioType.GTF: ".gtf",
        BioType.GFF_GTF: ".gff3",
        BioType.BED: ".bed",
        BioType.ASSEMBLY: ".fasta",
        BioType.CONTIGS: ".fasta",
        BioType.SCAFFOLDS: ".fasta",
        BioType.GFA: ".gfa",
        BioType.ODGI: ".odgi",
        BioType.COUNTS: ".counts.tsv",
        BioType.TPM_MATRIX: ".tpm.tsv",
        BioType.ABUNDANCE: ".abundance.tsv",
        BioType.GENE_EXPRESSION: ".expression.tsv",
        BioType.TX_EXPRESSION: ".tx_expression.tsv",
        BioType.HTML_REPORT: ".html",
        BioType.PDF_REPORT: ".pdf",
        BioType.STATS_FILE: ".stats.txt",
        BioType.KRAKEN_REPORT: ".kreport",
        BioType.KRAKEN_OUTPUT: ".kraken",
        BioType.METAPHLAN_PROFILE: ".metaphlan.tsv",
        BioType.ALIGNMENT: ".aln.fasta",
        BioType.PHYLOGENY_TREE: ".nwk",
        BioType.PEAKS: ".peaks.bed",
        BioType.BIGWIG: ".bw",
        BioType.NARROW_PEAK: ".narrowPeak",
        BioType.BROAD_PEAK: ".broadPeak",
        BioType.SAMPLE_SHEET: ".csv",
        BioType.H5AD: ".h5ad",
        BioType.SEURAT_OBJ: ".rds",
        BioType.JSON: ".json",
        BioType.YAML: ".yaml",
        BioType.CSV: ".csv",
        BioType.TSV: ".tsv",
        BioType.IMAGE: ".png",
        BioType.TRANSCRIPTS: ".transcripts.fasta",
    }
    bt = _coerce_to_biotype(biotype)
    if bt is None:
        return ".out"
    return mapping.get(bt, ".out")
