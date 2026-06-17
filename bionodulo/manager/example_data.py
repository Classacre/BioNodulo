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


def _generate_pangenomics_haplotypes(path: Path) -> None:
    """Generate a tiny two-haplotype FASTA for PGGB/ODGI template smoke runs."""
    sequences = {
        "haplotype_A": (
            "Synthetic haplotype A",
            "ACGTTGCAACGTTGCAACGTTGCAACGTTGCAGGATCCGATCGATCGATCGTTACGATCGATCGATCGATCGGCTA",
        ),
        "haplotype_B": (
            "Synthetic haplotype B",
            "ACGTTGCAACGTTGCAACGTTGCAACGTTGCAGGATCCGATCGATCGATCGTTACGATCGATCGTTCGATCGGCTA",
        ),
    }
    lines: list[str] = []
    for name, (description, sequence) in sequences.items():
        lines.append(f">{name} {description}")
        for index in range(0, len(sequence), 70):
            lines.append(sequence[index : index + 70])
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
# Synthetic FASTQ generators
#
# These cover datasets whose original public URLs have rotted out from under
# us (Zenodo records purged, GitHub test folders restructured, etc.). They
# emit small but well-formed FASTQ payloads so the example pipelines still
# have something realistic to chew on. We trade biological fidelity for never
# 404-ing — anyone needing real reads can drop them into the same paths.
# ---------------------------------------------------------------------------

def _write_fastq(path: Path, *, num_reads: int, read_len: int, seed: int, prefix: str) -> None:
    import random

    rng = random.Random(seed)
    bases = "ACGT"
    lines: list[str] = []
    for idx in range(num_reads):
        seq = "".join(rng.choice(bases) for _ in range(read_len))
        qual = "".join(chr(33 + rng.randint(25, 40)) for _ in range(read_len))
        lines.append(f"@{prefix}_{idx + 1}/{1 if 'R1' in path.name or 'read1' in path.name else 2}")
        lines.append(seq)
        lines.append("+")
        lines.append(qual)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _generate_chip_seq_read1(path: Path) -> None:
    _write_fastq(path, num_reads=2000, read_len=50, seed=1324070, prefix="chipseq_h3k4me3_R1")


def _generate_chip_seq_read2(path: Path) -> None:
    _write_fastq(path, num_reads=2000, read_len=50, seed=1324071, prefix="chipseq_h3k4me3_R2")


def _generate_metagenomics_forward(path: Path) -> None:
    _write_fastq(path, num_reads=2500, read_len=150, seed=17661262, prefix="meta_coffee_fwd")


def _generate_metagenomics_reverse(path: Path) -> None:
    _write_fastq(path, num_reads=2500, read_len=150, seed=17661263, prefix="meta_coffee_rev")


def _make_tinygex_generator(lane: int, kind: str, seed_offset: int):
    """Build a closure that generates one 10x-style tinygex FASTQ."""

    # I1 = sample-index, R1 = cell-barcode+UMI (~26 bp), R2 = transcript read.
    if kind == "I1":
        read_len = 8
    elif kind == "R1":
        read_len = 26
    else:
        read_len = 90
    prefix = f"tinygex_L00{lane}_{kind}"

    def _gen(path: Path) -> None:
        _write_fastq(path, num_reads=1500, read_len=read_len, seed=1000 + seed_offset, prefix=prefix)

    return _gen


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
        dest.parent.mkdir(parents=True, exist_ok=True)  # support nested filenames

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

# ---------------------------------------------------------------------------
# Additional generators for the remaining template categories (crispr, wgbs,
# proteomics, spatial, synthetic biology, long-read, chip-seq controls). Same
# philosophy: small, well-formed, never-404. Files whose real public source is
# stable use a URL instead (see manifest below).
# ---------------------------------------------------------------------------

_COMPLEMENT = str.maketrans("ACGTNacgtn", "TGCANtgcan")


def _revcomp(seq: str) -> str:
    return seq.translate(_COMPLEMENT)[::-1]


def _write_fastq_gz(
    path: Path,
    *,
    reads: list[str] | None = None,
    num_reads: int = 0,
    read_len: int = 0,
    seed: int = 0,
    prefix: str = "read",
    mate: int = 1,
) -> None:
    """Write a gzip-compressed FASTQ. Either pass explicit *reads* or generate
    *num_reads* random reads of *read_len*."""
    import random

    rng = random.Random(seed)
    if reads is None:
        reads = ["".join(rng.choice("ACGT") for _ in range(read_len)) for _ in range(num_reads)]
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for idx, seq in enumerate(reads, start=1):
            qual = "".join(chr(33 + rng.randint(25, 40)) for _ in range(len(seq)))
            fh.write(f"@{prefix}_{idx}/{mate}\n{seq}\n+\n{qual}\n")


# --- chip-seq input control + gene annotations ----------------------------

def _generate_chip_input_control_read1(path: Path) -> None:
    _write_fastq(path, num_reads=2000, read_len=50, seed=1324080, prefix="chipseq_input_control_read1")


def _generate_chip_input_control_read2(path: Path) -> None:
    _write_fastq(path, num_reads=2000, read_len=50, seed=1324081, prefix="chipseq_input_control_read2")


def _generate_chip_genes_bed(path: Path) -> None:
    rows = [
        ("chrX", 5000, 6500, "GeneA", "+"), ("chrX", 12000, 14000, "GeneB", "-"),
        ("chrX", 21000, 23000, "GeneC", "+"), ("chrX", 35000, 37000, "GeneD", "-"),
        ("chr1", 1000, 2500, "GeneE", "+"), ("chr2", 8000, 9500, "GeneF", "-"),
    ]
    rows.sort(key=lambda r: (r[0], r[1]))
    path.write_text(
        "".join(f"{c}\t{s}\t{e}\t{n}\t.\t{strand}\n" for c, s, e, n, strand in rows),
        encoding="utf-8",
    )


# --- crispr ----------------------------------------------------------------

def _crispr_library() -> list[tuple[str, str, str]]:
    """Deterministic sgRNA library shared by the .tsv and the screen reads."""
    import random

    rng = random.Random(7)
    lib: list[tuple[str, str, str]] = []
    for gene, n in (("GENEA", 3), ("GENEB", 3), ("GENEC", 2)):
        for k in range(1, n + 1):
            seq = "".join(rng.choice("ACGT") for _ in range(20))
            lib.append((f"sg_{gene}_{k}", seq, gene))
    return lib


def _generate_crispr_genome(path: Path) -> None:
    import random

    rng = random.Random(424242)
    seq = "".join(rng.choice("ACGT") for _ in range(1800))  # plenty of NGG PAMs by chance
    lines = "\n".join(seq[i:i + 70] for i in range(0, len(seq), 70))
    path.write_text(f">chr1 synthetic CRISPR target locus\n{lines}\n", encoding="utf-8")


def _generate_crispr_sgrna_library(path: Path) -> None:
    lines = ["sgRNA\tsequence\tgene"]
    lines += [f"{sgid}\t{seq}\t{gene}" for sgid, seq, gene in _crispr_library()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _generate_crispr_control(path: Path) -> None:
    reads = [f"ACCG{seq}GTTT" for _, seq, _ in _crispr_library() for _ in range(80)]
    _write_fastq_gz(path, reads=reads, seed=11, prefix="crispr_control")


def _generate_crispr_treated(path: Path) -> None:
    # Deplete GENEA guides relative to control so mageck_test ranks hits.
    reads = [
        f"ACCG{seq}GTTT"
        for _, seq, gene in _crispr_library()
        for _ in range(10 if gene == "GENEA" else 80)
    ]
    _write_fastq_gz(path, reads=reads, seed=12, prefix="crispr_treated")


def _amplicon_reads(n: int, seed: int, revcomp: bool = False) -> list[str]:
    import random

    rng = random.Random(seed)
    amp = "ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT"  # matches template amplicon_seq
    out = []
    for _ in range(n):
        s = list(amp)
        if rng.random() < 0.3:  # synthetic edit so editing-quant is non-trivial
            p = rng.randint(15, 25)
            s[p] = rng.choice("ACGT")
        seq = "".join(s)
        out.append(_revcomp(seq) if revcomp else seq)
    return out


def _generate_crispr_amplicon_r1(path: Path) -> None:
    _write_fastq_gz(path, reads=_amplicon_reads(400, 21), seed=21, prefix="crispr_amp_R1", mate=1)


def _generate_crispr_amplicon_r2(path: Path) -> None:
    _write_fastq_gz(path, reads=_amplicon_reads(400, 21, revcomp=True), seed=22, prefix="crispr_amp_R2", mate=2)


# --- wgbs / epigenomics ----------------------------------------------------

def _epigenomics_reference_seq() -> str:
    import random

    rng = random.Random(55)
    return "".join(rng.choice("ACGTCGCG") for _ in range(5000))  # CpG-enriched


def _generate_epigenomics_reference(path: Path) -> None:
    s = _epigenomics_reference_seq()
    lines = "\n".join(s[i:i + 70] for i in range(0, len(s), 70))
    path.write_text(f">chr1 synthetic bisulfite reference\n{lines}\n", encoding="utf-8")


def _bisulfite_reads(seed: int, convert: str, num: int = 1500, read_len: int = 80) -> list[str]:
    import random

    rng = random.Random(seed)
    ref = _epigenomics_reference_seq()
    table = {"CT": str.maketrans("C", "T"), "GA": str.maketrans("G", "A")}[convert]
    out = []
    for _ in range(num):
        start = rng.randint(0, len(ref) - read_len)
        out.append(ref[start:start + read_len].translate(table))  # most C unmethylated
    return out


def _generate_epigenomics_r1(path: Path) -> None:
    _write_fastq_gz(path, reads=_bisulfite_reads(551, "CT"), seed=551, prefix="wgbs_R1", mate=1)


def _generate_epigenomics_r2(path: Path) -> None:
    _write_fastq_gz(path, reads=_bisulfite_reads(552, "GA"), seed=552, prefix="wgbs_R2", mate=2)


def _generate_bismark_genome_dir(path: Path) -> None:
    """Bismark --genome folder: the reference FASTA plus a placeholder
    Bisulfite_Genome/ (real bisulfite indices need bismark_genome_preparation;
    this keeps the directory valid and lets a prep step fill it in)."""
    path.mkdir(parents=True, exist_ok=True)
    _generate_epigenomics_reference(path / "genome.fa")
    bg = path / "Bisulfite_Genome"
    (bg / "CT_conversion").mkdir(parents=True, exist_ok=True)
    (bg / "GA_conversion").mkdir(parents=True, exist_ok=True)
    (bg / "README.txt").write_text(
        "Placeholder. Run `bismark_genome_preparation` on this folder to build "
        "the bisulfite indices before aligning.\n",
        encoding="utf-8",
    )


# --- proteomics ------------------------------------------------------------

def _generate_proteomics_fasta(path: Path) -> None:
    import random

    rng = random.Random(99)
    aa = "ACDEFGHIKLMNPQRSTVWY"
    targets = [(f"sp|TEST{i}|TEST{i}_YEAST Synthetic protein {i}",
                "".join(rng.choice(aa) for _ in range(120))) for i in range(1, 11)]
    lines: list[str] = []
    for name, seq in targets:  # target entries
        lines.append(f">{name}")
        lines += [seq[j:j + 60] for j in range(0, len(seq), 60)]
    for name, seq in targets:  # decoy entries (reversed, `decoy` prefix)
        lines.append(f">decoy_{name}")
        rseq = seq[::-1]
        lines += [rseq[j:j + 60] for j in range(0, len(rseq), 60)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --- long-read -------------------------------------------------------------

def _generate_long_read_reference(path: Path) -> None:
    import random

    rng = random.Random(303)
    s = "".join(rng.choice("ACGT") for _ in range(2000))
    lines = "\n".join(s[i:i + 70] for i in range(0, len(s), 70))
    path.write_text(f">chr_test synthetic long-read reference\n{lines}\n", encoding="utf-8")


_POD5_URL = "https://media.githubusercontent.com/media/nanoporetech/pod5-file-format/master/test_data/multi_fast5_zip_v4.pod5"


def _generate_long_read_pod5_dir(path: Path) -> None:
    """pod5 input is a directory of raw ONT signal. Download one real tiny pod5
    (Git-LFS media endpoint serves the binary, not a pointer)."""
    path.mkdir(parents=True, exist_ok=True)
    dest = path / "example.pod5"
    if not dest.exists():
        _download_url(_POD5_URL, dest)


# --- spatial transcriptomics ----------------------------------------------

def _spatial_barcodes() -> list[str]:
    return [f"spot_{i:03d}" for i in range(40)]


def _generate_spatial_counts(path: Path) -> None:
    import random

    rng = random.Random(808)
    barcodes = _spatial_barcodes()
    lines = ["gene," + ",".join(barcodes)]
    for g in range(400):  # gene-by-spot matrix; node transposes to spots x genes
        lines.append(f"GENE{g:04d}," + ",".join(str(rng.randint(0, 20)) for _ in barcodes))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _generate_spatial_coordinates(path: Path) -> None:
    import random

    rng = random.Random(809)
    lines = ["barcode,x,y"]
    for b in _spatial_barcodes():
        lines.append(f"{b},{rng.randint(0, 1000)},{rng.randint(0, 1000)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# 1x1 PNG so Space Ranger image readers have a valid (if tiny) image.
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da6360000002000001e221bc330000000049454e44ae426082"
)


def _generate_visium_outs_dir(path: Path) -> None:
    """Minimal Space Ranger `outs/` layout (MTX matrix + spatial/) so the input
    directory validates and read_visium has the expected files."""
    import json as _json

    barcodes = _spatial_barcodes()
    mat = path / "filtered_feature_bc_matrix"
    sp = path / "spatial"
    mat.mkdir(parents=True, exist_ok=True)
    sp.mkdir(parents=True, exist_ok=True)

    genes = [f"GENE{g:04d}" for g in range(50)]
    with gzip.open(mat / "barcodes.tsv.gz", "wt", encoding="utf-8") as fh:
        fh.write("\n".join(barcodes) + "\n")
    with gzip.open(mat / "features.tsv.gz", "wt", encoding="utf-8") as fh:
        fh.write("\n".join(f"{g}\t{g}\tGene Expression" for g in genes) + "\n")
    entries = [(gi + 1, bi + 1, (gi + bi) % 7 + 1)
               for gi in range(len(genes)) for bi in range(len(barcodes)) if (gi + bi) % 3 == 0]
    with gzip.open(mat / "matrix.mtx.gz", "wt", encoding="utf-8") as fh:
        fh.write("%%MatrixMarket matrix coordinate integer general\n%\n")
        fh.write(f"{len(genes)} {len(barcodes)} {len(entries)}\n")
        for g, b, v in entries:
            fh.write(f"{g} {b} {v}\n")

    pos = ["barcode,in_tissue,array_row,array_col,pxl_row_in_fullres,pxl_col_in_fullres"]
    for i, b in enumerate(barcodes):
        pos.append(f"{b},1,{i // 8},{i % 8},{100 + i * 5},{100 + i * 7}")
    (sp / "tissue_positions_list.csv").write_text("\n".join(pos) + "\n", encoding="utf-8")
    (sp / "scalefactors_json.json").write_text(
        _json.dumps({"spot_diameter_fullres": 89.0, "tissue_hires_scalef": 0.17,
                     "fiducial_diameter_fullres": 144.0, "tissue_lowres_scalef": 0.05}),
        encoding="utf-8",
    )
    (sp / "tissue_hires_image.png").write_bytes(_PNG_1x1)
    (sp / "tissue_lowres_image.png").write_bytes(_PNG_1x1)


# --- synthetic biology -----------------------------------------------------

def _generate_cello_options(path: Path) -> None:
    path.write_text(
        "name,value\n"
        "Eugene,true\n"
        "test_verbose,2\n"
        "print_iss,false\n"
        "print_part_uri,true\n",
        encoding="utf-8",
    )


def _generate_cello_netlist(path: Path) -> None:
    path.write_text(
        "module toggle (output out, input a, input b);\n"
        "  wire w1, w2;\n"
        "  nor (w1, a, w2);\n"
        "  nor (w2, b, w1);\n"
        "  assign out = w1;\n"
        "endmodule\n",
        encoding="utf-8",
    )


def _generate_copasi_cps(path: Path) -> None:
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<COPASI xmlns="http://www.copasi.org/static/schema" versionMajor="4" '
        'versionMinor="40" versionDevel="0">\n'
        '  <ListOfFunctions/>\n'
        '  <Model key="Model_0" name="Toggle Switch" timeUnit="s" '
        'volumeUnit="ml" quantityUnit="mmol" type="deterministic">\n'
        '    <ListOfMetabolites/>\n'
        '  </Model>\n'
        '</COPASI>\n',
        encoding="utf-8",
    )


def _generate_sbol3_toggle(path: Path) -> None:
    """Prefer a guaranteed-valid SBOL3 doc via pysbol3 when importable; fall
    back to a minimal RDF/XML literal otherwise."""
    try:
        import sbol3  # type: ignore

        sbol3.set_namespace("https://bionodulo.org/synbio")
        doc = sbol3.Document()
        comp = sbol3.Component("toggle_switch", sbol3.SBO_DNA)
        comp.roles.append("https://identifiers.org/SO:0000804")  # engineered region
        doc.add(comp)
        doc.write(str(path), sbol3.RDF_XML)
        return
    except Exception:
        pass
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:sbol="http://sbols.org/v3#">\n'
        '  <sbol:Component rdf:about="https://bionodulo.org/synbio/toggle_switch">\n'
        '    <sbol:displayId>toggle_switch</sbol:displayId>\n'
        '    <sbol:type rdf:resource="https://identifiers.org/SBO:0000251"/>\n'
        '    <sbol:role rdf:resource="https://identifiers.org/SO:0000804"/>\n'
        '  </sbol:Component>\n'
        '</rdf:RDF>\n',
        encoding="utf-8",
    )


def _generate_omex_archive(path: Path) -> None:
    """Minimal COMBINE archive (.omex): a zip with manifest + SBML + SED-ML."""
    import zipfile

    sbml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sbml xmlns="http://www.sbml.org/sbml/level3/version2/core" level="3" version="2">\n'
        '  <model id="toggle_switch" name="Toggle Switch"/>\n'
        '</sbml>\n'
    )
    sedml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sedML xmlns="http://sed-ml.org/sed-ml/level1/version3" level="1" version="3"/>\n'
    )
    manifest = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<omexManifest xmlns="http://identifiers.org/combine.specifications/omex-manifest">\n'
        '  <content location="." format="http://identifiers.org/combine.specifications/omex"/>\n'
        '  <content location="./model.xml" format="http://identifiers.org/combine.specifications/sbml"/>\n'
        '  <content location="./simulation.sedml" format="http://identifiers.org/combine.specifications/sed-ml"/>\n'
        '</omexManifest>\n'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.xml", manifest)
        zf.writestr("model.xml", sbml)
        zf.writestr("simulation.sedml", sedml)


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

    # chip_seq — synthetic FASTQ (Zenodo record 1324070 was deprecated upstream)
    DataFile("chip_seq", "wt_H3K4me3_read1.fastq", generator=_generate_chip_seq_read1, description="Synthetic H3K4me3 ChIP-seq R1"),
    DataFile("chip_seq", "wt_H3K4me3_read2.fastq", generator=_generate_chip_seq_read2, description="Synthetic H3K4me3 ChIP-seq R2"),

    # metagenomics — synthetic FASTQ (Zenodo record 17661262 returned 404)
    DataFile("metagenomics", "reads_forward.fastq", generator=_generate_metagenomics_forward, description="Synthetic coffee fermentation metagenome R1"),
    DataFile("metagenomics", "reads_reverse.fastq", generator=_generate_metagenomics_reverse, description="Synthetic coffee fermentation metagenome R2"),

    # single_cell — synthetic 10x tinygex (upstream `minoda-lab/universc` test/
    # folder no longer ships the raw fastqs at the historical paths).
    DataFile("single_cell", "tinygex_S1_L001_I1_001.fastq", generator=_make_tinygex_generator(1, "I1", 1), description="Synthetic 10x tinygex L001 I1"),
    DataFile("single_cell", "tinygex_S1_L001_R1_001.fastq", generator=_make_tinygex_generator(1, "R1", 2), description="Synthetic 10x tinygex L001 R1"),
    DataFile("single_cell", "tinygex_S1_L001_R2_001.fastq", generator=_make_tinygex_generator(1, "R2", 3), description="Synthetic 10x tinygex L001 R2"),
    DataFile("single_cell", "tinygex_S1_L002_I1_001.fastq", generator=_make_tinygex_generator(2, "I1", 4), description="Synthetic 10x tinygex L002 I1"),
    DataFile("single_cell", "tinygex_S1_L002_R1_001.fastq", generator=_make_tinygex_generator(2, "R1", 5), description="Synthetic 10x tinygex L002 R1"),
    DataFile("single_cell", "tinygex_S1_L002_R2_001.fastq", generator=_make_tinygex_generator(2, "R2", 6), description="Synthetic 10x tinygex L002 R2"),

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

    # pangenomics — generated tiny haplotypes for template smoke runs
    DataFile("pangenomics", "haplotypes.fa", generator=_generate_pangenomics_haplotypes, description="Synthetic two-haplotype FASTA"),

    # chip_seq — input control reads + gene annotations (the H3K4me3 pair is above)
    DataFile("chip_seq", "input_control_read1.fastq", generator=_generate_chip_input_control_read1, description="Synthetic ChIP-seq input control R1"),
    DataFile("chip_seq", "input_control_read2.fastq", generator=_generate_chip_input_control_read2, description="Synthetic ChIP-seq input control R2"),
    DataFile("chip_seq", "genes.bed", generator=_generate_chip_genes_bed, description="Gene annotations for peak annotation"),

    # crispr — synthetic genome, sgRNA library, screen + amplicon reads
    DataFile("crispr", "genome.fa", generator=_generate_crispr_genome, description="Synthetic CRISPR target locus"),
    DataFile("crispr", "sgrna_library.tsv", generator=_generate_crispr_sgrna_library, description="Synthetic sgRNA library (sgRNA/sequence/gene)"),
    DataFile("crispr", "control.fastq.gz", generator=_generate_crispr_control, description="Synthetic CRISPR screen control reads"),
    DataFile("crispr", "treated.fastq.gz", generator=_generate_crispr_treated, description="Synthetic CRISPR screen treated reads"),
    DataFile("crispr", "amplicon_R1.fastq.gz", generator=_generate_crispr_amplicon_r1, description="Synthetic CRISPResso2 amplicon R1"),
    DataFile("crispr", "amplicon_R2.fastq.gz", generator=_generate_crispr_amplicon_r2, description="Synthetic CRISPResso2 amplicon R2"),

    # epigenomics / WGBS — bisulfite reference, reads, and bismark genome folder
    DataFile("epigenomics", "reference.fasta", generator=_generate_epigenomics_reference, description="Synthetic bisulfite reference"),
    DataFile("epigenomics", "sample_R1.fastq.gz", generator=_generate_epigenomics_r1, description="Synthetic WGBS reads R1 (C->T)"),
    DataFile("epigenomics", "sample_R2.fastq.gz", generator=_generate_epigenomics_r2, description="Synthetic WGBS reads R2 (G->A)"),
    DataFile("epigenomics", "bismark_genome", generator=_generate_bismark_genome_dir, description="Bismark genome folder (reference + index placeholder)"),

    # proteomics — Sage/Percolator: real tiny mzML + synthetic target-decoy FASTA
    DataFile("proteomics", "sample.mzML", "https://raw.githubusercontent.com/ProteoWizard/pwiz/master/example_data/tiny.pwiz.1.1.1.mzML", description="ProteoWizard tiny example mzML (MS1+MS2)"),
    DataFile("proteomics", "target_decoy.fasta", generator=_generate_proteomics_fasta, description="Synthetic target+decoy protein FASTA"),

    # metabolomics — XCMS: same real tiny mzML
    DataFile("metabolomics", "sample.mzML", "https://raw.githubusercontent.com/ProteoWizard/pwiz/master/example_data/tiny.pwiz.1.1.1.mzML", description="ProteoWizard tiny example mzML"),

    # long_read — synthetic reference + a real tiny ONT pod5 directory
    DataFile("long_read", "reference.fasta", generator=_generate_long_read_reference, description="Synthetic long-read reference"),
    DataFile("long_read", "pod5", generator=_generate_long_read_pod5_dir, description="Real tiny ONT pod5 (downloaded into a directory)"),

    # spatial_transcriptomics — synthetic counts/coords + a minimal Visium outs dir
    DataFile("spatial_transcriptomics", "counts.csv", generator=_generate_spatial_counts, description="Synthetic gene-by-spot count matrix"),
    DataFile("spatial_transcriptomics", "coordinates.csv", generator=_generate_spatial_coordinates, description="Synthetic spot coordinates"),
    DataFile("spatial_transcriptomics", "visium_outs", generator=_generate_visium_outs_dir, description="Minimal Space Ranger outs/ layout"),

    # synthetic_biology — Cello UCF (real) + synthetic netlist/options/models
    DataFile("synthetic_biology", "Eco1C1G1T1.UCF.json", "https://raw.githubusercontent.com/CIDARLAB/Cello-UCF/develop/files/v2/ucf/Eco/Eco1C1G1T1.UCF.json", description="Cello E. coli user-constraints file"),
    DataFile("synthetic_biology", "cello_options.csv", generator=_generate_cello_options, description="Cello runtime options"),
    DataFile("synthetic_biology", "toggle_netlist.v", generator=_generate_cello_netlist, description="Synthetic Cello Verilog netlist"),
    DataFile("synthetic_biology", "toggle_model.cps", generator=_generate_copasi_cps, description="Minimal COPASI model"),
    DataFile("synthetic_biology", "toggle_switch.xml", generator=_generate_sbol3_toggle, description="Minimal SBOL3 component"),
    DataFile("synthetic_biology", "toggle_study.omex", generator=_generate_omex_archive, description="Minimal COMBINE archive"),
]
