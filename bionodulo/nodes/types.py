BIO_TYPES = {
    "FASTQ",
    "FASTQ_LIST",
    "BAM",
    "CRAM",
    "SAM",
    "VCF",
    "BCF",
    "GFF",
    "GTF",
    "BED",
    "FASTA",
    "INDEX_DIR",
    "QC_REPORT_DIR",
    "HTML_REPORT",
    "JSON_REPORT",
    "MULTIQC_REPORT",
    "DIRECTORY",
    "FILE",
    "STRING",
    "INT",
    "FLOAT",
    "BOOLEAN",
    "SAMPLE_SHEET",
    "COUNT_MATRIX",
    "ANNOTATION_TABLE",
}


def is_compatible(source_type: str, target_type: str) -> bool:
    if source_type == target_type:
        return True
    if target_type == "FILE" and source_type in {"FASTQ", "FASTA", "BAM", "CRAM", "SAM", "VCF", "BCF", "GFF", "GTF", "BED", "HTML_REPORT", "JSON_REPORT"}:
        return True
    if target_type == "DIRECTORY" and source_type in {"QC_REPORT_DIR", "INDEX_DIR"}:
        return True
    return False
