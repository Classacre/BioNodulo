"""Example data download manager for workflow templates.

Maps every file the templates expect under ``examples/data/`` to a REAL public
source URL (nothing is committed to the repo). The input node materialises these
on demand — downloading the URL (and decompressing when ``gunzip`` is set) — so a
fresh clone fetches its example data from the internet instead of carrying it.

Directory inputs (e.g. a 10x ``visium_outs/`` or an ONT ``pod5/`` folder) are
expressed as several entries whose ``filename`` includes the sub-path; the
resolver materialises every entry under the referenced directory.

Every entry is a real public URL — no synthetic data. (The spatial count/
coordinate CSVs are derived at run time from the real Visium ``.h5`` by the
``scanpy_spatial`` node, not generated here.)
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
# Download orchestration
# ---------------------------------------------------------------------------

def download_example_data(
    project_root: Path,
    emit: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    """Download all example data files from public sources.

    Returns a summary dict with downloaded, skipped, failed file lists.
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

        _emit(f"[{idx}/{total}] {spec.category}/{spec.filename} — {spec.description}", "info")

        if dest.exists():
            skipped.append(str(dest.relative_to(project_root)))
            _emit("  skipped (already exists)", "info")
            continue

        try:
            if spec.url:
                _download_url(spec.url, dest, gunzip=spec.gunzip)
                downloaded.append(str(dest.relative_to(project_root)))
                _emit("  downloaded OK", "success")
            elif spec.generator is not None:
                spec.generator(dest)
                downloaded.append(str(dest.relative_to(project_root)))
                _emit("  generated OK", "success")
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
    dest.parent.mkdir(parents=True, exist_ok=True)

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
        tmp_path.replace(dest)


# ---------------------------------------------------------------------------
# Manifest — every file templates reference under examples/data/, sourced from
# a real public URL (raw GitHub test-data repos, NCBI/EBI/Ensembl, BioModels,
# Cello, ProteoWizard, 10x). `gunzip=True` decompresses a .gz source into a
# plain target.
# ---------------------------------------------------------------------------

_NFCORE = "https://raw.githubusercontent.com/nf-core/test-datasets"
_MAGECK = "https://raw.githubusercontent.com/davidliwei/mageck/master/demo/demo2"
# 10x tinygex (cellranger-tiny-fastq) — Git-LFS, must use the media host.
_TINYGEX = "https://media.githubusercontent.com/media/minoda-lab/universc/master/test/shared/cellranger-tiny-fastq/3.0.0"
_TINYREF_PATH = "minoda-lab/universc/7cbd039613b45c64f4b6d8219906aafda28dd5f9/test/cellranger_reference/cellranger-tiny-ref/1.2.0"
_TINYREF_RAW = f"https://raw.githubusercontent.com/{_TINYREF_PATH}"
_TINYREF_LFS = f"https://media.githubusercontent.com/media/{_TINYREF_PATH}"
_VISIUM = f"{_NFCORE}/spatialvi/testdata/human-brain-cancer-11-mm-capture-area-ffpe-2-standard_v2_ffpe_cytassist/outs"

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

    # wgs_variant — NCBI RefSeq
    DataFile("wgs_variant", "ecoli_k12_mg1655.fna", "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/005/845/GCF_000005845.2_ASM584v2/GCF_000005845.2_ASM584v2_genomic.fna.gz", gunzip=True, description="E. coli K-12 MG1655 RefSeq"),

    # differential_expression — EBI ENA + Ensembl
    DataFile("differential_expression", "SRR6357071_1.fastq", "https://ftp.sra.ebi.ac.uk/vol1/fastq/SRR635/001/SRR6357071/SRR6357071_1.fastq.gz", gunzip=True, description="S. cerevisiae RNA-seq R1 (SRR6357071)"),
    DataFile("differential_expression", "SRR6357071_2.fastq", "https://ftp.sra.ebi.ac.uk/vol1/fastq/SRR635/001/SRR6357071/SRR6357071_2.fastq.gz", gunzip=True, description="S. cerevisiae RNA-seq R2 (SRR6357071)"),
    DataFile("differential_expression", "transcriptome.fa", "https://ftp.ensembl.org/pub/current_fasta/saccharomyces_cerevisiae/cdna/Saccharomyces_cerevisiae.R64-1-1.cdna.all.fa.gz", gunzip=True, description="S. cerevisiae R64-1-1 cDNA"),

    # phylogenetics — real NCBI 16S accessions via E-utilities efetch
    DataFile("phylogenetics", "16s_sequences.fasta", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=NR_024570.1,NR_027552.1,NR_036781.1,NR_026078.1,NR_028747.1&rettype=fasta&retmode=text", description="Five bacterial 16S rRNA sequences (NCBI)"),

    # biopython — real CDS (NCBI) + airway counts/metadata (bioconnector workshops)
    DataFile("biopython", "coding_sequences.fasta", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=J01749.1&rettype=fasta_cds_na&retmode=text", description="pBR322 coding sequences (NCBI)"),
    DataFile("biopython", "deseq2_counts.csv", "https://raw.githubusercontent.com/bioconnector/workshops/master/data/airway_scaledcounts.csv", description="airway RNA-seq count matrix"),
    DataFile("biopython", "deseq2_sample_info.csv", "https://raw.githubusercontent.com/bioconnector/workshops/master/data/airway_metadata.csv", description="airway sample metadata"),
    DataFile("biopython", "heatmap_data.csv", "https://raw.githubusercontent.com/bioconnector/workshops/master/data/airway_scaledcounts.csv", description="airway expression matrix for heatmap"),
    DataFile("biopython", "heatmap_annotation.csv", "https://raw.githubusercontent.com/bioconnector/workshops/master/data/airway_metadata.csv", description="airway sample annotations"),

    # pangenomics — pggb HLA-DRB1 tutorial haplotypes
    DataFile("pangenomics", "haplotypes.fa", "https://raw.githubusercontent.com/pangenome/pggb/e25486b9b219877eca82631a13953129386c8b09/data/HLA/DRB1-3123.fa.gz", gunzip=True, description="pggb v0.7.4 HLA-DRB1 12-haplotype fixture"),

    # metagenomics — nf-core mag minigut shotgun reads
    DataFile("metagenomics", "reads_forward.fastq", f"{_NFCORE}/mag/test_data/test_minigut_R1.fastq.gz", gunzip=True, description="Shotgun metagenome R1 (nf-core mag)"),
    DataFile("metagenomics", "reads_reverse.fastq", f"{_NFCORE}/mag/test_data/test_minigut_R2.fastq.gz", gunzip=True, description="Shotgun metagenome R2 (nf-core mag)"),

    # single_cell — canonical 10x tinygex (cellranger-tiny-fastq 3.0.0)
    DataFile("single_cell", "tinygex_S1_L001_I1_001.fastq", f"{_TINYGEX}/tinygex_S1_L001_I1_001.fastq.gz", gunzip=True, description="10x tinygex L001 I1"),
    DataFile("single_cell", "tinygex_S1_L001_R1_001.fastq", f"{_TINYGEX}/tinygex_S1_L001_R1_001.fastq.gz", gunzip=True, description="10x tinygex L001 R1"),
    DataFile("single_cell", "tinygex_S1_L001_R2_001.fastq", f"{_TINYGEX}/tinygex_S1_L001_R2_001.fastq.gz", gunzip=True, description="10x tinygex L001 R2"),
    DataFile("single_cell", "tinygex_S1_L002_I1_001.fastq", f"{_TINYGEX}/tinygex_S1_L002_I1_001.fastq.gz", gunzip=True, description="10x tinygex L002 I1"),
    DataFile("single_cell", "tinygex_S1_L002_R1_001.fastq", f"{_TINYGEX}/tinygex_S1_L002_R1_001.fastq.gz", gunzip=True, description="10x tinygex L002 R1"),
    DataFile("single_cell", "tinygex_S1_L002_R2_001.fastq", f"{_TINYGEX}/tinygex_S1_L002_R2_001.fastq.gz", gunzip=True, description="10x tinygex L002 R2"),

    # single_cell reference — the cellranger-tiny-ref that MATCHES the tinygex
    # reads above (hg19 chr21, ~120 MB). The published refdata-gex-GRCh38 is
    # 11.4 GB and is a different genome from these reads entirely.
    DataFile("single_cell_ref", "fasta/genome.fa", f"{_TINYREF_RAW}/fasta/genome.fa", description="cellranger tiny reference FASTA"),
    DataFile("single_cell_ref", "genes/genes.gtf", f"{_TINYREF_RAW}/genes/genes.gtf", description="cellranger tiny reference GTF"),
    # reference.json is the one Git-LFS file here, so it needs the media host.
    DataFile("single_cell_ref", "reference.json", f"{_TINYREF_LFS}/reference.json", description="cellranger tiny reference metadata"),
    DataFile("single_cell_ref", "star/Genome", f"{_TINYREF_RAW}/star/Genome", description="cellranger tiny STAR index Genome"),
    DataFile("single_cell_ref", "star/SAindex", f"{_TINYREF_RAW}/star/SAindex", description="cellranger tiny STAR index SAindex"),
    DataFile("single_cell_ref", "star/SA", f"{_TINYREF_RAW}/star/SA", description="cellranger tiny STAR index SA"),
    DataFile("single_cell_ref", "star/chrName.txt", f"{_TINYREF_RAW}/star/chrName.txt", description="cellranger tiny STAR index chrName.txt"),
    DataFile("single_cell_ref", "star/chrLength.txt", f"{_TINYREF_RAW}/star/chrLength.txt", description="cellranger tiny STAR index chrLength.txt"),
    DataFile("single_cell_ref", "star/chrStart.txt", f"{_TINYREF_RAW}/star/chrStart.txt", description="cellranger tiny STAR index chrStart.txt"),
    DataFile("single_cell_ref", "star/chrNameLength.txt", f"{_TINYREF_RAW}/star/chrNameLength.txt", description="cellranger tiny STAR index chrNameLength.txt"),
    DataFile("single_cell_ref", "star/genomeParameters.txt", f"{_TINYREF_RAW}/star/genomeParameters.txt", description="cellranger tiny STAR index genomeParameters.txt"),
    DataFile("single_cell_ref", "star/exonInfo.tab", f"{_TINYREF_RAW}/star/exonInfo.tab", description="cellranger tiny STAR index exonInfo.tab"),
    DataFile("single_cell_ref", "star/geneInfo.tab", f"{_TINYREF_RAW}/star/geneInfo.tab", description="cellranger tiny STAR index geneInfo.tab"),
    DataFile("single_cell_ref", "star/sjdbInfo.txt", f"{_TINYREF_RAW}/star/sjdbInfo.txt", description="cellranger tiny STAR index sjdbInfo.txt"),
    DataFile("single_cell_ref", "star/sjdbList.out.tab", f"{_TINYREF_RAW}/star/sjdbList.out.tab", description="cellranger tiny STAR index sjdbList.out.tab"),
    DataFile("single_cell_ref", "star/sjdbList.fromGTF.out.tab", f"{_TINYREF_RAW}/star/sjdbList.fromGTF.out.tab", description="cellranger tiny STAR index sjdbList.fromGTF.out.tab"),
    DataFile("single_cell_ref", "star/transcriptInfo.tab", f"{_TINYREF_RAW}/star/transcriptInfo.tab", description="cellranger tiny STAR index transcriptInfo.tab"),
    DataFile("single_cell_ref", "star/exonGeTrInfo.tab", f"{_TINYREF_RAW}/star/exonGeTrInfo.tab", description="cellranger tiny STAR index exonGeTrInfo.tab"),
    DataFile("single_cell_ref", "star/Log.out", f"{_TINYREF_RAW}/star/Log.out", description="cellranger tiny STAR index Log.out"),

    # chip_seq — nf-core chipseq Spt5 IP/input pair + yeast reference + gene annotations
    DataFile("chip_seq", "genome.fa", f"{_NFCORE}/chipseq/reference/genome.fa", description="S. cerevisiae reference (nf-core chipseq)"),
    DataFile("chip_seq", "wt_Spt5_read1.fastq", f"{_NFCORE}/chipseq/testdata/SRR5204807_Spt5-ChIP_IP1_SacCer_ChIP-Seq_ss100k_R1.fastq.gz", gunzip=True, description="Spt5 ChIP IP R1 (nf-core)"),
    DataFile("chip_seq", "wt_Spt5_read2.fastq", f"{_NFCORE}/chipseq/testdata/SRR5204807_Spt5-ChIP_IP1_SacCer_ChIP-Seq_ss100k_R2.fastq.gz", gunzip=True, description="Spt5 ChIP IP R2 (nf-core)"),
    DataFile("chip_seq", "input_control_read1.fastq", f"{_NFCORE}/chipseq/testdata/SRR5204809_Spt5-ChIP_Input1_SacCer_ChIP-Seq_ss100k_R1.fastq.gz", gunzip=True, description="ChIP-seq input control R1 (nf-core)"),
    DataFile("chip_seq", "input_control_read2.fastq", f"{_NFCORE}/chipseq/testdata/SRR5204809_Spt5-ChIP_Input1_SacCer_ChIP-Seq_ss100k_R2.fastq.gz", gunzip=True, description="ChIP-seq input control R2 (nf-core)"),
    DataFile("chip_seq", "genes.bed", f"{_NFCORE}/chipseq/reference/genes.bed", description="Gene annotations BED (nf-core chipseq)"),

    # crispr — CRISPResso2 reference + MAGeCK demo screen + nf-core amplicon edits
    DataFile("crispr", "genome.fa", "https://raw.githubusercontent.com/pinellolab/CRISPResso2/master/tests/smallGenome/smallGenome.fa", description="CRISPResso2 small test genome"),
    DataFile("crispr", "sgrna_library.tsv", f"{_MAGECK}/library.txt", description="MAGeCK demo sgRNA library (sgRNA/sequence/gene)"),
    DataFile("crispr", "control.fastq", f"{_MAGECK}/test1.fastq", description="MAGeCK demo control reads"),
    DataFile("crispr", "treated.fastq", f"{_MAGECK}/test2.fastq", description="MAGeCK demo treated reads"),
    DataFile("crispr", "amplicon_R1.fastq.gz", f"{_NFCORE}/crisprseq/testdata-edition/hCas9-TRAC-a_R1.fastq.gz", description="CRISPResso2 amplicon R1 (nf-core)"),
    DataFile("crispr", "amplicon_R2.fastq.gz", f"{_NFCORE}/crisprseq/testdata-edition/hCas9-TRAC-a_R2.fastq.gz", description="CRISPResso2 amplicon R2 (nf-core)"),

    # epigenomics / WGBS — nf-core methylseq reference + bisulfite reads
    DataFile("epigenomics", "reference.fasta", f"{_NFCORE}/methylseq/reference/genome.fa", description="WGBS reference (nf-core methylseq)"),
    DataFile("epigenomics", "sample_R1.fastq.gz", f"{_NFCORE}/methylseq/testdata/Ecoli_10K_methylated_R1.fastq.gz", description="WGBS reads R1 (nf-core methylseq)"),
    DataFile("epigenomics", "sample_R2.fastq.gz", f"{_NFCORE}/methylseq/testdata/Ecoli_10K_methylated_R2.fastq.gz", description="WGBS reads R2 (nf-core methylseq)"),
    # bismark genome folder: the real reference; bismark_genome_preparation builds the indices.
    DataFile("epigenomics", "bismark_genome/genome.fa", f"{_NFCORE}/methylseq/reference/genome.fa", description="Bismark genome folder reference"),

    # proteomics — ProteoWizard mzML + nf-core quantms target-decoy FASTA
    DataFile("proteomics", "sample.mzML", "https://raw.githubusercontent.com/ProteoWizard/pwiz/master/example_data/tiny.pwiz.1.1.1.mzML", description="ProteoWizard tiny mzML (MS1+MS2)"),
    DataFile("proteomics", "target_decoy.fasta", f"{_NFCORE}/quantms/testdata/lfq_ci_phospho/pools_crap_targetdecoy.fasta", description="Target+decoy protein FASTA (DECOY_ prefix)"),

    # metabolomics — ProteoWizard mzML
    DataFile("metabolomics", "sample.mzML", "https://raw.githubusercontent.com/ProteoWizard/pwiz/master/example_data/tiny.pwiz.1.1.1.mzML", description="ProteoWizard tiny mzML"),
    DataFile("metabolomics", "sample_2.mzML", "https://raw.githubusercontent.com/ProteoWizard/pwiz/master/example_data/tiny.pwiz.1.1.1.mzML", description="Second local copy of the ProteoWizard tiny mzML for multi-file workflow wiring"),

    # long_read — nf-core nanoseq reference + a real tiny ONT pod5
    DataFile("long_read", "reference.fasta", f"{_NFCORE}/nanoseq/reference/chr22_23800000-23980000.fa", description="Nanopore reference (nf-core nanoseq)"),
    DataFile("long_read", "pod5/example.pod5", "https://media.githubusercontent.com/media/nanoporetech/pod5-file-format/master/test_data/multi_fast5_zip_v4.pod5", description="Real tiny ONT pod5"),
    DataFile("long_read", "demux/barcode01.fastq", "https://raw.githubusercontent.com/nanoporetech/dorado/0949eb8de80dce9a198c08c0e37e31ed1eb627fc/tests/data/barcode_demux/single_end/SQK-RBK114-96_BC01.fastq", description="Dorado 0.9.6 barcode-demultiplexing FASTQ fixture"),

    # spatial_transcriptomics — real Visium outs (scanpy_spatial derives the
    # count/coordinate CSVs from this .h5 at run time; squidpy reads it directly)
    # nf-core's filtered_feature_bc_matrix.h5 for this sample is a stub: 1 gene
    # x 10881 spots with every count zero, so ANY QC filter empties it and
    # squidpy_qc dies with "Too few spots or genes after filtering".
    # raw_feature_bc_matrix.h5 is the real (downsampled) matrix -- 19023 genes x
    # 11397 spots, 7089 non-empty -- so stage that under the filename the Space
    # Ranger readers look for. Counts top out at ~22/spot, which is why the
    # spatial template uses CI-sized min_counts/min_genes thresholds.
    DataFile("spatial_transcriptomics", "visium_outs/filtered_feature_bc_matrix.h5", f"{_VISIUM}/raw_feature_bc_matrix.h5", description="Visium matrix (nf-core spatialvi)"),
    DataFile("spatial_transcriptomics", "visium_outs/spatial/scalefactors_json.json", f"{_VISIUM}/spatial/scalefactors_json.json", description="Visium scalefactors"),
    DataFile("spatial_transcriptomics", "visium_outs/spatial/tissue_positions.csv", f"{_VISIUM}/spatial/tissue_positions.csv", description="Visium tissue positions"),
    DataFile("spatial_transcriptomics", "visium_outs/spatial/tissue_hires_image.png", f"{_VISIUM}/spatial/tissue_hires_image.png", description="Visium hires image"),
    DataFile("spatial_transcriptomics", "visium_outs/spatial/tissue_lowres_image.png", f"{_VISIUM}/spatial/tissue_lowres_image.png", description="Visium lowres image"),

    # synthetic_biology — Cello (UCF/options/netlist) + COPASI + BioModels toggle switch
    DataFile("synthetic_biology", "Eco1C1G1T1.UCF.json", "https://raw.githubusercontent.com/CIDARLAB/Cello-UCF/develop/files/v2/ucf/Eco/Eco1C1G1T1.UCF.json", description="Cello E. coli UCF"),
    DataFile("synthetic_biology", "cello_options.csv", "https://raw.githubusercontent.com/CIDARLAB/Cello-v2/develop/sample-input/DNACompiler/adder/options.csv", description="Cello runtime options"),
    DataFile("synthetic_biology", "toggle_netlist.v", "https://raw.githubusercontent.com/CIDARLAB/Cello-v2/develop/cello/cello-dnacompiler/src/test/resources/and.v", description="Cello Verilog netlist"),
    DataFile("synthetic_biology", "toggle_model.cps", "https://raw.githubusercontent.com/copasi/COPASI/master/COPASI_TestSuite/Tests/EventTest1/EventTest1.cps", description="COPASI model"),
    DataFile("synthetic_biology", "toggle_switch.xml", "https://www.ebi.ac.uk/biomodels/model/download/BIOMD0000000507?filename=BIOMD0000000507_url.xml", description="Gardner 2000 genetic toggle switch (SBML, BioModels)"),
    DataFile("synthetic_biology", "toggle_study.omex", "https://www.ebi.ac.uk/biomodels/model/download/BIOMD0000000507", description="Toggle switch COMBINE archive (BioModels)"),
]
