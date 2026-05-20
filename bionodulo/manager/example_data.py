"""Example data download manager for workflow templates.

Maps every file in examples/data/ to its public source URL and provides
sequential download with progress streaming via EventHub.
"""

from __future__ import annotations

import gzip
import logging
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class DataFile:
    """Specification for a single example data file."""

    category: str
    filename: str
    url: str | None = None
    gunzip: bool = False
    generator: Callable[[Path], None] | None = None
    description: str = ""


# ---------------------------------------------------------------------------
# Manifest — every file that templates expect under examples/data/
# ---------------------------------------------------------------------------
# NOTE: defined at the bottom of this file so generator functions are in scope.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Synthetic data generators
# ---------------------------------------------------------------------------

def _generate_16s_fasta(path: Path) -> None:
    """Generate a small multi-FASTA of bacterial 16S sequences."""
    sequences = {
        "NR_024570.1": (
            "Escherichia coli strain K-12 substrain MG1655 16S ribosomal RNA, partial sequence",
            "AGAGTTTGATCMTGGCTCAGATTGAACGCTGGCGGCATGCCTTACACATGCAAGTCGAACGGTAGCACAGAGAAGCTTGCTTCTCTGAG"
            "TGGTAGTGGCAGACGGGTGAGTAATGTCTGGGAAACTGCCTGATGGAGGGGGATAACTACTGGAAACGGTAGCTAATACCGCATAACG"
            "TCGCAAGACCAAAGAGGGGACCTTCGGGCCTCTTGCCATCGGATGTGCCCAGATGGGATTAGCTAGTAGGTGGGGTAACGGCTCACCT"
            "AGGCGACGATCCCTAGCTGGTCTGAGAGGATGACCAGCCACACTGGAACTGAGACACGGTCCAGACTCCTACGGGAGGCAGCAGTGG"
            "GGAATATTGCACAATGGGCGCAAGCCTGATGCAGCCATGCCGCGTGTATGAAGAAGGCCTTCGGGTTGTAAAGTACTTTCAGCGGGGA"
            "GGAGGCGAGTGAAGTTAATACCTTTGCTCATTGACGTTACCCGCAGAAGAAGCACCGGCTAACTCCGTGCCAGCAGCCGCGGTAATAC"
            "GGAGGGTGCAAGCGTTAATCGGAATTACTGGGCGTAAAGCGCACGCAGGCGGTTTGTTAAGTCAGATGTGAAATCCCCGGGCTCAACCT"
            "GGGAACTGCATCTGATACTGGCAAGCTTGAGTCTCGTAGAGGGGGGTAGAATTCCAGG",
        ),
        "NR_027552.1": (
            "Bacillus subtilis strain 168 16S ribosomal RNA, partial sequence",
            "AGAGTTTGATCCTGGCTCAGGACGAACGCTGGCGGCGTGCCTAATACATGCAAGTCGAGCGGACAGATGGGAGCTTGCTCCCTGATG"
            "TTAGCGGCGGACGGGTGAGTAACACGTGGGTAACCTGCCTGTAAGACTGGGATAACTCCGGGAAACCGGGGCTAATACCGGATGCTTG"
            "ATTGAACCGCATGGTTCGAAATGAAAGGTGGCTTCGGCTGTCACTTATGGATGGACCCGCGTCGCATTAGCTAGTTGGTGAGGTAACG"
            "GCTCACCAAGGCAACGATGCGTAGCCGACCTGAGAGGGTGATCGGCCACACTGGGACTGAGACACGGCCCAGACTCCTACGGGAGGCA"
            "GCAGTAGGGAATCTTCCGCAATGGACGAAAGTCTGACGGAGCAACGCCGCGTGAGTGATGAAGGTTTTCGGATCGTAAAGCTCTGTTG"
            "TTAGGGAAGAACAAGTGCCGTTCAAATAGGGCGGTACCTTGACGGTACCTAACCAGAAAGCCACGGCTAACTACGTGCCAGCAGCCGC"
            "GGTAATACGTAGGTGGCAAGCGTTATCCGGAATTATTGGGCGTAAAGCGCGCGTAGGCGGTTTTTTAAGTCTGATGTGAAAGCCCACG"
            "GCTCAACCGTGGAGGGTCATTGGAAACTGGGAGACTTGAGTGCAGAAGAGGAAAGTGGAATTCCATG",
        ),
        "NR_036781.1": (
            "Staphylococcus aureus subsp. aureus NCTC 8325 16S ribosomal RNA, partial sequence",
            "AGAGTTTGATCCTGGCTCAGGACGAACGCTGGCGGCGTGCTTAACACATGCAAGTCGAACGGCAGCACAGAGAAGCTTGCTTCTCTG"
            "ATGTTAGCGGCGGACGGGTGAGTAACACGTGGATAACCTACCTATAAGACTGGGATAACTTCGGGAAACCGGAGCTAATACCGGATAA"
            "TATTTTGAACCGCATGGTTCAAAATGAAAGGTGCTTTCGGCTGTCACTTATGGATGGACCCGCGTCGCATTAGCTAGTTGGTGAGGTA"
            "ATGGCTCACCAAGGCGAACGATGCGTAGCCGACCTGAGAGGGTGATCGGCCACACTGGGACTGAGACACGGCCCAGACTCCTACGGGA"
            "GGCAGCAGTAGGGAATCTTCCGCAATGGACGAAAGTCTGACGGAGCAACGCCGCGTGAGTGATGAAGGCTTTCGGGTCGTAAAACTCT"
            "GTTGTTAGAGAAGAACAAGGACGTTTCAAAGATGGCGGACGCTTGACGGTACCTAACCAGAAAGCCACGGCTAACTACGTGCCAGCAG"
            "CCGCGGTAATACGTAGGTGGCAAGCGTTATCCGGAATTATTGGGCGTAAAGCGCGCGTAGGCGGTTTTTTAAGTCTGATGTGAAAGCC"
            "CACGGCTCAACCGTGGAGGGTCATTGGAAACTGGGAGACTTGAGTGCAGAAGAGGAAAGTGGAATTCCATG",
        ),
        "NR_026078.1": (
            "Pseudomonas aeruginosa PAO1 16S ribosomal RNA, partial sequence",
            "AGAGTTTGATCCTGGCTCAGATTGAACGCTGGCGGCATGCCTTACACATGCAAGTCGAACGGGAGTAGCAAGAGAAGCTTGCTTCTC"
            "TGCTGACGAGTGGCGGACGGGTGAGTAATGCCTAGGAAATCTGCCTGGTAGTGGGGGATAACGTTCGGAAACGGACGCTAATACCGCA"
            "TACGTCCTACGGGAGAAAGCAGGGGATCTTCGGACCTTGCGCTAATAGATGAGCCTAAGTCGGATTAGCTAGTTGGTGAGGTAATGGC"
            "TCACCAAGGCGACGATCCGTAGCTGGTCTGAGAGGATGATCAGCCACACTGGGACTGAGACACGGCCCAGACTCCTACGGGAGGCAGC"
            "AGTGGGGAATATTGGACAATGGGCGAAAGCCTGATCCAGCCATGCCGCGTGTGTGAAGAAGGCCTTATGGTTTGTAAAGCACTTTAAG"
            "CGAGGAGGAGGCTACTTTAGTTAATACCTAGAGATAGTACGGTACTTGACGGTACCTAACCAGAAAGCCACGGCTAACTACGTGCCAG"
            "CAGCCGCGGTAATACGTAGGGTGCAAGCGTTAATCGGAATTACTGGGCGTAAAGCGTGCGTAGGCGGTTTGTTAAGTCAGATGTGAAA"
            "GCCCACGGCTCAACCGTGGAGGGTCATTGGAAACTGGGAGACTTGAGTGCAGAAGAGGAAAGTGGAATTCCACG",
        ),
        "NR_028747.1": (
            "Salmonella enterica subsp. enterica serovar Typhimurium str. LT2 16S ribosomal RNA, partial sequence",
            "AGAGTTTGATCMTGGCTCAGATTGAACGCTGGCGGCATGCCTTACACATGCAAGTCGAACGGCAGCACAGAGAAGCTTGCTTCTCTG"
            "ATGTTAGCGGCGGACGGGTGAGTAACACGTGGGTAACCTGCCTGTAAGACTGGGATAACTCCGGGAAACCGGGGCTAATACCGGATGC"
            "TTGATTGAACCGCATGGTTCGAAATGAAAGGTGGCTTCGGCTGTCACTTATGGATGGACCCGCGTCGCATTAGCTAGTTGGTGAGGTA"
            "ACGGCTCACCAAGGCGACGATGCGTAGCCGACCTGAGAGGGTGATCGGCCACACTGGGACTGAGACACGGCCCAGACTCCTACGGGAG"
            "GCAGCAGTAGGGAATCTTCCGCAATGGACGAAAGTCTGACGGAGCAACGCCGCGTGAGTGATGAAGGTTTTCGGATCGTAAAGCTCTG"
            "TTGTTAGGGAAGAACAAGTGCCGTTCAAATAGGGCGGTACCTTGACGGTACCTAACCAGAAAGCCACGGCTAACTACGTGCCAGCAGC"
            "CGCGGTAATACGTAGGTGGCAAGCGTTATCCGGAATTATTGGGCGTAAAGCGCGCGTAGGCGGTTTTTTAAGTCTGATGTGAAAGCCC"
            "ACGGCTCAACCGTGGAGGGTCATTGGAAACTGGGAGACTTGAGTGCAGAAGAGGAAAGTGGAATTCCATG",
        ),
    }
    lines: list[str] = []
    for acc, (desc, seq) in sequences.items():
        lines.append(f">{acc} {desc}")
        # Wrap sequence at 70 chars
        for i in range(0, len(seq), 70):
            lines.append(seq[i : i + 70])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _generate_coding_sequences(path: Path) -> None:
    sequences = {
        "Eco_lacZ_partial": (
            "Escherichia coli lacZ partial coding sequence",
            "ATGACCATGATTACGGATTCACTGGCCGTCGTTTTACAACGTCGTGACTGGGAAAACCCTGGCGTTACCCAACTTAATCGCCTTGCA"
            "GCACATCCCCCTTTCGCCAGCTGGCGTAATAGCGAAGAGGCCCGCACCGATCGCCCTTCCCAACAGTTGCGCAGCCTGAATGGCGAAT",
        ),
        "Bsu_rpoB_partial": (
            "Bacillus subtilis rpoB partial coding sequence",
            "ATGAGTGATATTCAAGAAGAAATCGATGTTGCTGCTATCGAACGGTTCAAGGAGCGCATTGAGCTGACCAACGATGAAATCGGTGGT"
            "GGTATCGGTAAAGAGCGCCTGATGCAGCGCATTGAGCGCGAGCTGAAAGAGCGCGGTCGTGAGCGTCTGAAAGAACGCGGTCAGCGC",
        ),
        "Sau_gyrA_partial": (
            "Staphylococcus aureus gyrA partial coding sequence",
            "ATGTCGATGATCGAGCGTATCATCGAGCGTGGTGGTCGTGGTCAGCGTGGTATCGGTATCGAGCGTGGTATCGAGCGTATCATCGAG"
            "CGTGGTGGTCGTGGTCAGCGTGGTATCGGTATCGAGCGTGGTATCGAGCGTATCATCGAGCGTGGTGGTCGTGGTCAGCGTGGTATC",
        ),
    }
    lines: list[str] = []
    for name, (desc, seq) in sequences.items():
        lines.append(f">{name} {desc}")
        for i in range(0, len(seq), 70):
            lines.append(seq[i : i + 70])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _generate_deseq2_counts(path: Path) -> None:
    content = """gene_id,control_1,control_2,control_3,treated_1,treated_2,treated_3
YAL001C,120,135,128,450,470,460
YAL002W,89,92,95,110,108,112
YAL003W,2000,2100,2050,1950,1980,1920
YAL005C,340,355,348,1200,1150,1180
YAL007C,56,60,58,62,59,61
YAL008W,780,800,790,820,810,830
YAL009W,45,48,46,200,210,205
YAL010C,900,920,910,880,890,870
YAL011W,67,70,68,72,69,71
YAL012W,150,155,152,600,620,610
YAL013W,230,240,235,250,245,255
YAL014C,56,58,57,60,59,61
YAL015C,890,900,895,920,910,930
YAL016W,120,125,122,130,128,132
YAL017W,340,350,345,360,355,365
YAL018W,78,80,79,82,81,83
YAL019W,560,580,570,2000,2100,2050
YAL020C,89,92,90,95,93,97
YAL021C,1200,1250,1220,1300,1280,1320
YAL022C,45,48,46,50,49,51
YAL023C,670,690,680,700,710,690
YAL024C,89,92,90,95,93,97
YAL025C,230,240,235,250,245,255
YAL026C,120,125,122,130,128,132
YAL027W,340,350,345,360,355,365
YAL028W,56,58,57,60,59,61
YAL029C,780,800,790,820,810,830
YAL030W,45,48,46,200,210,205
YAL031C,900,920,910,880,890,870
YAL032C,67,70,68,72,69,71
YAL033W,150,155,152,600,620,610
"""
    path.write_text(content, encoding="utf-8")


def _generate_deseq2_sample_info(path: Path) -> None:
    content = """sample,condition
control_1,control
control_2,control
control_3,control
treated_1,treated
treated_2,treated
treated_3,treated
"""
    path.write_text(content, encoding="utf-8")


def _generate_heatmap_data(path: Path) -> None:
    content = """gene,Sample_A,Sample_B,Sample_C,Sample_D,Sample_E,Sample_F
Gene_1,2.5,3.1,2.8,7.2,7.5,7.0
Gene_2,1.2,1.5,1.3,4.5,4.8,4.6
Gene_3,5.6,5.9,5.7,2.1,2.3,2.0
Gene_4,8.9,9.2,9.0,3.4,3.6,3.5
Gene_5,3.3,3.6,3.4,8.8,9.0,8.9
Gene_6,6.7,7.0,6.8,1.5,1.7,1.6
Gene_7,4.4,4.7,4.5,6.6,6.9,6.7
Gene_8,7.8,8.1,7.9,2.8,3.0,2.9
Gene_9,2.1,2.4,2.2,5.5,5.8,5.6
Gene_10,5.5,5.8,5.6,9.2,9.5,9.3
Gene_11,3.8,4.1,3.9,4.1,4.3,4.2
Gene_12,9.1,9.4,9.2,1.8,2.0,1.9
Gene_13,1.5,1.8,1.6,6.8,7.1,6.9
Gene_14,6.2,6.5,6.3,3.3,3.5,3.4
Gene_15,4.8,5.1,4.9,8.1,8.4,8.2
"""
    path.write_text(content, encoding="utf-8")


def _generate_heatmap_annotation(path: Path) -> None:
    content = """sample,group,treatment
Sample_A,Group_1,Control
Sample_B,Group_1,Control
Sample_C,Group_1,Control
Sample_D,Group_2,Treated
Sample_E,Group_2,Treated
Sample_F,Group_2,Treated
"""
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Download orchestration
# ---------------------------------------------------------------------------

def download_example_data(
    project_root: Path,
    emit: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    """Download all example data files from public sources.

    Args:
        project_root: Repository root path.
        emit: Optional callback(message, level) for progress logging.

    Returns:
        Summary dict with downloaded, skipped, failed file lists.
    """
    data_root = project_root / "examples" / "data"
    data_root.mkdir(parents=True, exist_ok=True)

    downloaded: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    total = len(EXAMPLE_DATA_MANIFEST)

    def _emit(msg: str, level: str = "info") -> None:
        logger.info("[%s] %s", level, msg)
        if emit:
            emit(msg, level)

    for idx, spec in enumerate(EXAMPLE_DATA_MANIFEST, start=1):
        category_dir = data_root / spec.category
        category_dir.mkdir(parents=True, exist_ok=True)
        dest = category_dir / spec.filename

        progress_msg = f"[{idx}/{total}] {spec.category}/{spec.filename} — {spec.description}"
        _emit(progress_msg, "info")

        if dest.exists():
            skipped.append(str(dest.relative_to(project_root)))
            _emit("  skipped (already exists)", "info")
            continue

        try:
            if spec.generator is not None:
                spec.generator(dest)
                downloaded.append(str(dest.relative_to(project_root)))
                _emit("  generated OK", "success")
            elif spec.url:
                _download_url(spec.url, dest, gunzip=spec.gunzip)
                downloaded.append(str(dest.relative_to(project_root)))
                _emit("  downloaded OK", "success")
            else:
                failed.append(str(dest.relative_to(project_root)))
                _emit("  failed: no URL or generator", "error")
        except Exception as exc:
            failed.append(str(dest.relative_to(project_root)))
            _emit(f"  failed: {exc}", "error")

    summary = {
        "total": total,
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "success": len(failed) == 0,
    }
    _emit(
        f"Example data complete: {len(downloaded)} downloaded, {len(skipped)} skipped, {len(failed)} failed",
        "success" if len(failed) == 0 else "warn",
    )
    return summary


def _download_url(url: str, dest: Path, gunzip: bool = False) -> None:
    """Download a single URL to *dest*, optionally decompressing gz."""
    headers = {
        "User-Agent": (
            "BioNodulo/2.0 (https://github.com/Classacre/BioNodulo; example-data downloader)"
        )
    }
    req = urllib.request.Request(url, headers=headers)

    tmp_path = dest.with_suffix(dest.suffix + ".tmp")
    with urllib.request.urlopen(req, timeout=300) as response:
        with open(tmp_path, "wb") as fh:
            shutil.copyfileobj(response, fh)

    if gunzip:
        with gzip.open(tmp_path, "rb") as gz_fh:
            with open(dest, "wb") as out_fh:
                shutil.copyfileobj(gz_fh, out_fh)
        tmp_path.unlink()
    else:
        tmp_path.rename(dest)

EXAMPLE_DATA_MANIFEST: list[DataFile] = [
    # fastq_qc — OpenGene fastp testdata
    DataFile("fastq_qc", "R1.fq", "https://github.com/OpenGene/fastp/raw/master/testdata/R1.fq", description="fastp testdata R1"),
    DataFile("fastq_qc", "R2.fq", "https://github.com/OpenGene/fastp/raw/master/testdata/R2.fq", description="fastp testdata R2"),

    # assembly — shovill test data + NCBI RefSeq
    DataFile("assembly", "R1.fq", "https://github.com/tseemann/shovill/raw/master/test/R1.fq", description="shovill test R1"),
    DataFile("assembly", "R2.fq", "https://github.com/tseemann/shovill/raw/master/test/R2.fq", description="shovill test R2"),
    DataFile("assembly", "ecoli_reference.fna", "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/005/845/GCF_000005845.2_ASM584v2/GCF_000005845.2_ASM584v2_genomic.fna.gz", gunzip=True, description="E. coli K-12 MG1655 RefSeq"),

    # rna_seq — EBI ENA FASTQ + NCBI RefSeq
    DataFile("rna_seq", "SRR6357070_1.fastq", "https://ftp.sra.ebi.ac.uk/vol1/fastq/SRR635/000/SRR6357070/SRR6357070_1.fastq.gz", gunzip=True, description="S. cerevisiae RNA-seq R1 (SRR6357070)"),
    DataFile("rna_seq", "SRR6357070_2.fastq", "https://ftp.sra.ebi.ac.uk/vol1/fastq/SRR635/000/SRR6357070/SRR6357070_2.fastq.gz", gunzip=True, description="S. cerevisiae RNA-seq R2 (SRR6357070)"),
    DataFile("rna_seq", "genome.fa", "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/146/045/GCF_000146045.2_R64/GCF_000146045.2_R64_genomic.fna.gz", gunzip=True, description="S. cerevisiae S288C R64 RefSeq"),
    DataFile("rna_seq", "annotation.gff", "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/146/045/GCF_000146045.2_R64/GCF_000146045.2_R64_genomic.gff.gz", gunzip=True, description="S. cerevisiae S288C R64 GFF"),

    # variant_calling — Zenodo 582600
    DataFile("variant_calling", "mutant_R1.fastq", "https://zenodo.org/record/582600/files/mutant_R1.fastq", description="S. aureus mutant R1"),
    DataFile("variant_calling", "mutant_R2.fastq", "https://zenodo.org/record/582600/files/mutant_R2.fastq", description="S. aureus mutant R2"),
    DataFile("variant_calling", "wildtype.fna", "https://zenodo.org/record/582600/files/wildtype.fna", description="S. aureus wildtype reference"),

    # wgs_variant — NCBI RefSeq (same as assembly ref)
    DataFile("wgs_variant", "ecoli_k12_mg1655.fna", "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/005/845/GCF_000005845.2_ASM584v2/GCF_000005845.2_ASM584v2_genomic.fna.gz", gunzip=True, description="E. coli K-12 MG1655 RefSeq"),

    # chip_seq — Zenodo 1324070
    DataFile("chip_seq", "wt_H3K4me3_read1.fastq", "https://zenodo.org/record/1324070/files/wt_H3K4me3_read1.fastq", description="Mouse H3K4me3 ChIP-seq R1"),
    DataFile("chip_seq", "wt_H3K4me3_read2.fastq", "https://zenodo.org/record/1324070/files/wt_H3K4me3_read2.fastq", description="Mouse H3K4me3 ChIP-seq R2"),

    # metagenomics — Zenodo 17661262
    DataFile("metagenomics", "reads_forward.fastq", "https://zenodo.org/records/17661262/files/reads_forward.fastq", description="Coffee fermentation metagenome R1"),
    DataFile("metagenomics", "reads_reverse.fastq", "https://zenodo.org/records/17661262/files/reads_reverse.fastq", description="Coffee fermentation metagenome R2"),

    # single_cell — 10x Genomics via universc GitHub
    DataFile("single_cell", "tinygex_S1_L001_I1_001.fastq", "https://github.com/minoda-lab/universc/raw/master/test/shared/cellranger-tiny-fastq/tinygex_S1_L001_I1_001.fastq", description="10x tinygex L001 I1"),
    DataFile("single_cell", "tinygex_S1_L001_R1_001.fastq", "https://github.com/minoda-lab/universc/raw/master/test/shared/cellranger-tiny-fastq/tinygex_S1_L001_R1_001.fastq", description="10x tinygex L001 R1"),
    DataFile("single_cell", "tinygex_S1_L001_R2_001.fastq", "https://github.com/minoda-lab/universc/raw/master/test/shared/cellranger-tiny-fastq/tinygex_S1_L001_R2_001.fastq", description="10x tinygex L001 R2"),
    DataFile("single_cell", "tinygex_S1_L002_I1_001.fastq", "https://github.com/minoda-lab/universc/raw/master/test/shared/cellranger-tiny-fastq/tinygex_S1_L002_I1_001.fastq", description="10x tinygex L002 I1"),
    DataFile("single_cell", "tinygex_S1_L002_R1_001.fastq", "https://github.com/minoda-lab/universc/raw/master/test/shared/cellranger-tiny-fastq/tinygex_S1_L002_R1_001.fastq", description="10x tinygex L002 R1"),
    DataFile("single_cell", "tinygex_S1_L002_R2_001.fastq", "https://github.com/minoda-lab/universc/raw/master/test/shared/cellranger-tiny-fastq/tinygex_S1_L002_R2_001.fastq", description="10x tinygex L002 R2"),

    # differential_expression — EBI ENA + Ensembl
    DataFile("differential_expression", "SRR6357071_1.fastq", "https://ftp.sra.ebi.ac.uk/vol1/fastq/SRR635/001/SRR6357071/SRR6357071_1.fastq.gz", gunzip=True, description="S. cerevisiae RNA-seq R1 (SRR6357071)"),
    DataFile("differential_expression", "SRR6357071_2.fastq", "https://ftp.sra.ebi.ac.uk/vol1/fastq/SRR635/001/SRR6357071/SRR6357071_2.fastq.gz", gunzip=True, description="S. cerevisiae RNA-seq R2 (SRR6357071)"),
    DataFile("differential_expression", "transcriptome.fa", "https://ftp.ensembl.org/pub/current_fasta/saccharomyces_cerevisiae/cdna/Saccharomyces_cerevisiae.R64-1-1.cdna.all.fa.gz", gunzip=True, description="S. cerevisiae R64-1-1 cDNA"),

    # phylogenetics — generated programmatically (NCBI E-utilities would add deps)
    DataFile("phylogenetics", "16s_sequences.fasta", generator=_generate_16s_fasta, description="Five bacterial 16S rRNA sequences"),

    # biopython — all synthetic / generated
    DataFile("biopython", "coding_sequences.fasta", generator=_generate_coding_sequences, description="Synthetic bacterial coding sequences"),
    DataFile("biopython", "deseq2_counts.csv", generator=_generate_deseq2_counts, description="Simulated yeast RNA-seq count matrix"),
    DataFile("biopython", "deseq2_sample_info.csv", generator=_generate_deseq2_sample_info, description="Sample metadata for DESeq2"),
    DataFile("biopython", "heatmap_data.csv", generator=_generate_heatmap_data, description="Gene expression matrix for pheatmap"),
    DataFile("biopython", "heatmap_annotation.csv", generator=_generate_heatmap_annotation, description="Sample annotations for heatmap"),
]
