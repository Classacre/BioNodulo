"""Shared helpers and citation metadata for BioNodulo built-in wrapped tool nodes."""
# ruff: noqa: F401
from __future__ import annotations

import ast

import json

import shlex

from pathlib import Path

from re import sub

import re

from typing import Any

from bionodulo.nodes.base import BaseNode

from bionodulo.nodes.command_node import CommandNode, _shell_join

BIONODULO_BUILTIN_ALIAS = "BioNodulo builtin"

DOI_URL = "https://doi.org/"

def _out(inputs: dict[str, Any]) -> str:
    return str(inputs.get("output", inputs.get("output_dir", ".")))

def _add_if_value(cmd: list[str], flag: str, value: Any) -> None:
    if value is not None and str(value) != "":
        cmd.extend([flag, str(value)])

def _add_shell_redirect(cmd: list[str], output_path: str) -> None:
    cmd.extend([">", output_path])

def _as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v) != ""]
    return [str(value)]

def _safe_name(value: str) -> str:
    return sub(r"[^\w\-.]", "_", Path(value).name)

def _safe_label(value: str) -> str:
    return sub(r"[^\w\-.]", "_", value)

def _safe_identifier(value: str) -> str:
    return sub(r"[^\w\-.]", "_", value.strip())

def _safe_element_identifier(value: str) -> str:
    return sub(r"[^\w\-_.]", "_", Path(value).name)

def _bedtools_ext(path: Any, default: str = "bed") -> str:
    suffixes = Path(str(path or "")).suffixes
    if not suffixes:
        return default
    if len(suffixes) >= 2 and suffixes[-2:] == [".gff", ".gz"]:
        return "gff"
    ext = suffixes[-1].lstrip(".").lower()
    return {"gff3": "gff", "bg": "bedgraph"}.get(ext, ext or default)

BEDTOOLS_CITATION_DOI = "10.1093/bioinformatics/btq033"

BEDTOOLS_CITATION_TEXT = "BEDTools: a flexible suite of utilities for comparing genomic features."

BEDOPS_CITATION_DOI = "10.1093/bioinformatics/bts277"

BEDOPS_CITATION_TEXT = "BEDOPS: high-performance genomic feature operations."

BCFTOOLS_CITATION_DOIS = ["10.1093/gigascience/giab008", "10.1093/bioinformatics/btp352"]

BCFTOOLS_CITATION_URLS = [f"{DOI_URL}{doi}" for doi in BCFTOOLS_CITATION_DOIS]

BCFTOOLS_CITATION_TEXT = (
    "Twelve years of SAMtools and BCFtools; "
    "The Sequence Alignment/Map format and SAMtools."
)

CNVKIT_CITATION_DOI = "10.1371/journal.pcbi.1004873"

CNVKIT_CITATION_TEXT = (
    "CNVkit: Genome-Wide Copy Number Detection and Visualization from Targeted DNA Sequencing."
)

FREEBAYES_CITATION_DOIS = ["10.48550/arXiv.1207.3907"]

FREEBAYES_CITATION_URLS = [
    "https://doi.org/10.48550/arXiv.1207.3907",
    "http://arxiv.org/abs/1207.3907",
]

FREEBAYES_CITATION_TEXT = "Haplotype-based variant detection from short-read sequencing."

BWA_MEM2_CITATION_DOIS = [
    "10.1109/IPDPS.2019.00041",
    "10.1093/bioinformatics/btp324",
    "10.1093/bioinformatics/btp698",
]

BWA_MEM2_CITATION_URLS = [f"{DOI_URL}{doi}" for doi in BWA_MEM2_CITATION_DOIS] + [
    "http://arxiv.org/abs/1303.3997",
]

BWA_MEM2_CITATION_TEXT = (
    "BWA-MEM2 acceleration of the BWA-MEM algorithm; "
    "Fast and accurate short read alignment with Burrows-Wheeler Transform; "
    "Fast and accurate long-read alignment with Burrows-Wheeler Transform; "
    "Aligning sequence reads, clone sequences and assembly contigs with BWA-MEM."
)

BWA_CITATION_DOIS = ["10.1093/bioinformatics/btp324", "10.1093/bioinformatics/btp698"]

BWA_CITATION_URLS = [f"{DOI_URL}{doi}" for doi in BWA_CITATION_DOIS]

BWA_CITATION_TEXT = (
    "Fast and accurate short read alignment with Burrows-Wheeler Transform; "
    "Fast and accurate long-read alignment with Burrows-Wheeler Transform."
)

BWA_METH_CITATION_DOIS = ["10.48550/arXiv.1401.1129"]

BWA_METH_CITATION_URLS = [f"{DOI_URL}{BWA_METH_CITATION_DOIS[0]}", "http://arxiv.org/abs/1401.1129"]

BWA_METH_CITATION_TEXT = "Fast and accurate alignment of long bisulfite-seq reads."

BWA_METH_DOCUMENTATION_URL = "https://github.com/brentp/bwa-meth"

BOWTIE2_CITATION_DOI = "10.1038/nmeth.1923"

BOWTIE2_CITATION_TEXT = "Fast gapped-read alignment with Bowtie 2."

BARRNAP_CITATION_URL = "https://github.com/tseemann/barrnap"

BARRNAP_CITATION_TEXT = "barrnap: rapid ribosomal RNA prediction."

FASTA_STATS_CITATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/fasta_stats"

FASTA_STATS_CITATION_TEXT = "Fasta Statistics: Display summary statistics for a fasta file."

ANNDATA2RI_CITATION_URL = "https://github.com/theislab/anndata2ri"

ANNDATA2RI_CITATION_TEXT = "Convert between AnnData and SingleCellExperiment objects."

ANNDATA_SCANPY_CITATION_DOI = "10.1186/s13059-017-1382-0"

ANNDATA_SCANPY_CITATION_TEXT = (
    "Scanpy and AnnData provide scalable analysis and annotated data matrices for single-cell gene expression data."
)

CELLTYPIST_CITATION_DOI = "10.1126/science.abl5197"

CELLTYPIST_CITATION_TEXT = (
    "CellTypist provides automated cell type annotation for scRNA-seq datasets, "
    "with a focus on immune populations."
)

CEMITOOL_CITATION_DOIS = ["10.1186/s12859-018-2053-1", "10.18129/B9.bioc.CEMiTool"]

CEMITOOL_CITATION_TEXT = (
    "CEMiTool identifies and analyzes co-expression modules from expression data and provides "
    "publication-ready reports for downstream enrichment analyses."
)

CHARTS_CITATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/charts"

CHARTS_CITATION_TEXT = "Galaxy Chart Utilities generate tabular chart data with R chart modules."

CHERRI_CITATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/cherri"

CHERRI_DOCUMENTATION_URL = "https://github.com/BackofenLab/CheRRI"

CHERRI_CITATION_TEXT = (
    "CheRRI evaluates RNA-RNA interaction sites and filters predicted or experimentally detected "
    "interactions with a trained model."
)

CHIRA_DOCUMENTATION_URL = "https://github.com/BackofenLab/ChiRA"

CHIRA_CITATION_DOI = "10.1093/gigascience/giaa158"

CHIRA_CITATION_TEXT = (
    "ChiRA: an integrated framework for chimeric read analysis from RNA-RNA interactome and structurome data."
)

CHEWBBACA_CITATION_DOI = "10.1099/mgen.0.000166"

CHEWBBACA_CITATION_TEXT = (
    "chewBBACA enables gene-by-gene allele calling and cgMLST/wgMLST schema-based bacterial typing."
)

ARGNORM_CITATION_DOI = "10.1093/bioinformatics/btaf173"

ARGNORM_CITATION_TEXT = (
    "argNorm: a tool to normalize antibiotic resistance gene annotation across different databases."
)

AUTOBIGS_CLI_CITATION_URL = "https://github.com/Syph-and-VPD-Lab/autoBIGS.cli"

AUTOBIGS_CLI_CITATION_TEXT = "Syph-and-VPD-Lab/autoBIGS.cli: automated MLST typing against BIGSdb databases."

MLST_CITATION_URL = "https://github.com/tseemann/mlst"

MLST_CITATION_TEXT = "MLST: Scan contig files against PubMLST typing schemes."

B2BTOOLS_CITATION_DOIS = [
    "10.1093/bioinformatics/btae543",
    "10.1038/ncomms3741",
    "10.1101/2020.05.25.115253",
    "10.1038/s41598-017-08366-3",
    "10.1093/bioinformatics/btz912",
]

B2BTOOLS_CITATION_TEXT = (
    "Bio2Byte Tools: a suite of protein sequence-based predictors; "
    "DynaMine backbone dynamics prediction; "
    "AgMata beta-aggregation prediction; "
    "EFoldMine early folding prediction; "
    "DisoMine protein disorder prediction."
)

BP_GENBANK2GFF3_CITATION_DOI = "10.1101/gr.361602"

BP_GENBANK2GFF3_CITATION_TEXT = (
    "BioPerl GenBank-to-GFF3 converter using Bio::SeqFeature::Tools::Unflattener and Bio::Tools::GFF."
)

BASIL_CITATION_DOI = "10.1093/bioinformatics/btv051"

BASIL_CITATION_TEXT = (
    "BASIL is a method to detect breakpoints for structural variants, including insertion breakpoints, "
    "from aligned paired high-throughput sequencing reads."
)

BAREDSC_CITATION_DOI = "10.1186/s12859-021-04507-8"

BAREDSC_DOCUMENTATION_URL = "https://baredsc.readthedocs.io/en/latest/index.html"

BAREDSC_CITATION_TEXT = (
    "BARED (Bayesian Approach to Retrieve Expression Distribution of) Single Cell estimates confidence "
    "intervals on one- or two-gene single-cell expression probability density functions."
)

BBG_TO_BIGWIG_CITATION_DOI = "10.1093/bioinformatics/btq351"

BBG_TO_BIGWIG_CITATION_TEXT = (
    "BigWig and BigBed enable browsing of large distributed datasets in genome browsers."
)

BEROKKA_CITATION_URL = "https://github.com/tseemann/berokka"

BEROKKA_CITATION_TEXT = "Berokka: Faster Trim, circularise and orient long read bacterial genome assemblies."

BAX2BAM_CITATION_URL = "https://github.com/pacificbiosciences/bax2bam/"

BAX2BAM_CITATION_TEXT = "bax2bam converts the legacy PacBio basecall format (bax.h5) into BAM."

BAM_TO_SCIDX_CITATION_URL = (
    "http://www.huck.psu.edu/content/research/independent-centers-excellence/center-for-eukaryotic-gene-regulation"
)

BAM_TO_SCIDX_CITATION_TEXT = (
    "Convert BAM data to ScIdx, the Strand-specific coordinate count format used by ChIP-exo tools."
)

BIOEXT_CITATION_URL = "http://hyphy.org/"

BIOEXT_CITATION_TEXT = "HyPhy: Hypothesis Testing using Phylogenies."

BIOEXT_DOCUMENTATION_URL = "https://github.com/veg/BioExt"

BIOEXT_SANITIZE_PIPE = (
    "| gawk '{ if ($0 ~ \"^[^>]\") {a = gensub(/[^ACGTURYKMSWBDHVNacgturykmswbdhvn?-]/, \"\", \"g\"); } "
    "else {a=gensub(/[^>A-Za-z0-9_]/, \"_\", \"g\"); }; print a } ' | sed 's,_\\+,_,g' >"
)

CD_HIT_CITATION_DOIS = ["10.1093/bioinformatics/btl158", "10.1093/bioinformatics/bts565"]

CD_HIT_CITATION_TEXT = (
    "CD-HIT: a fast program for clustering and comparing large sets of protein or nucleotide sequences; "
    "CD-HIT Suite: a web server for clustering and comparing biological sequences."
)

FASTA_REGEX_FINDER_CITATION_URL = "https://github.com/dariober/bioinformatics-cafe/tree/master/fastaRegexFinder"

FASTA_REGEX_FINDER_CITATION_TEXT = "fastaRegexFinder: search FASTA files for regular-expression matches."

CHOPPER_CITATION_DOI = "10.1093/bioinformatics/btad311"

CHOPPER_CITATION_TEXT = "NanoPack2: population-scale evaluation of long-read sequencing data."

CHOPIN2_CITATION_DOI = "10.3390/a13090233"

CHOPIN2_CITATION_TEXT = "A Brain-Inspired Hyperdimensional Computing Approach for Classifying Massive DNA Methylation Data of Cancer."

CITE_SEQ_COUNT_CITATION_DOI = "10.5281/zenodo.2585469"

CITE_SEQ_COUNT_CITATION_TEXT = (
    "CITE-seq-Count outputs UMI and read counts from raw FASTQ CITE-seq or cell-hashing data."
)

SCIPY_CITATION_DOI = "10.1038/s41592-019-0686-2"

SCIPY_CITATION_TEXT = "SciPy 1.0: fundamental algorithms for scientific computing in Python."

CIALIGN_CITATION_DOI = "10.7717/peerj.12983"

CIALIGN_CITATION_TEXT = (
    "CIAlign: A highly customisable command line tool to clean, interpret and visualise multiple sequence alignments."
)

CHROMAP_CITATION_DOI = "10.1038/s41467-021-26865-w"

CHROMAP_CITATION_TEXT = "Fast alignment and preprocessing of chromatin profiles with Chromap."

CIRCEXPLORER2_CITATION_DOI = "10.1101/gr.202895.115"

CIRCEXPLORER2_CITATION_TEXT = (
    "Diverse alternative back-splicing and alternative splicing landscape of circular RNAs."
)

CIRCOS_CITATION_DOIS = ["10.1093/gigascience/giaa065", "10.1101/gr.092759.109"]

CIRCOS_CITATION_TEXT = (
    "Galactic Circos: User-friendly Circos plots within the Galaxy platform; "
    "Circos: an information aesthetic for comparative genomics."
)

FILTLONG_CITATION_URL = "https://github.com/rrwick/Filtlong"

FILTLONG_CITATION_TEXT = "Filtlong: quality filtering tool for long reads."

GFA_TO_FA_CITATION_URL = "http://gfa-spec.github.io/GFA-spec/GFA1.html"

GFA_TO_FA_CITATION_TEXT = "GFA v1 specification for Graphical Fragment Assembly files."

SEQTK_CITATION_URL = "https://github.com/lh3/seqtk"

SEQTK_CITATION_TEXT = "SeqTK FASTA/Q toolkit by Heng Li, distributed from the lh3/seqtk GitHub repository."

ADD_INPUT_NAME_AS_COLUMN_CITATION_URL = (
    "https://github.com/galaxyproject/tools-iuc/tree/main/tools/add_input_name_as_column"
)

ADD_INPUT_NAME_AS_COLUMN_CITATION_TEXT = "Add input name as column on an existing tabular file."

COLUMN_REMOVE_BY_HEADER_CITATION_URL = (
    "https://github.com/galaxyproject/tools-iuc/tree/main/tools/column_remove_by_header"
)

COLUMN_REMOVE_BY_HEADER_CITATION_TEXT = "Removes or keeps columns based upon user provided values."

COLUMN_ORDER_HEADER_SORT_CITATION_URL = (
    "https://github.com/galaxyproject/tools-iuc/tree/main/tools/column_order_header_sort"
)

COLUMN_ORDER_HEADER_SORT_CITATION_TEXT = "Reorders a file's columns by sorted value of header fields."

DATAMASH_CITATION_URL = "https://www.gnu.org/software/datamash/"

DATAMASH_DOCUMENTATION_URL = "https://www.gnu.org/software/datamash/manual/"

DATAMASH_CITATION_TEXT = "GNU Datamash: command-line calculations on tabular data."

FALCO_CITATION_DOI = "10.12688/f1000research.21142.2"

FALCO_DOCUMENTATION_URL = "https://falco.readthedocs.io"

FALCO_CITATION_TEXT = "Falco: high-speed FastQC emulation for quality control of sequencing data."

HAPPY_CITATION_URL = "https://github.com/Illumina/hap.py"

HAPPY_CITATION_TEXT = "Illumina hap.py: haplotype VCF comparison and som.py allele-matching tools."

CROSSMAP_CITATION_DOI = "10.1093/bioinformatics/btt730"

CROSSMAP_CITATION_TEXT = "CrossMap: a versatile tool for coordinate conversion between genome assemblies."

FEATURECOUNTS_CITATION_DOI = "10.1093/bioinformatics/btt656"

FEATURECOUNTS_CITATION_TEXT = (
    "featureCounts: an efficient general purpose program for assigning sequence reads to genomic features."
)

ROARY_CITATION_DOI = "10.1093/bioinformatics/btv421"

ROARY_CITATION_TEXT = "Roary: rapid large-scale prokaryote pan genome analysis."

COLUMN_MAKER_CITATION_DOI = "10.1093/nar/gkae410"

COLUMN_MAKER_CITATION_TEXT = (
    "The Galaxy platform for accessible, reproducible, and collaborative data analyses: 2024 update."
)

CALCULATE_NUMERIC_PARAM_CITATION_URL = (
    "https://github.com/galaxyproject/tools-iuc/tree/main/tools/calculate_numeric_param"
)

CALCULATE_NUMERIC_PARAM_CITATION_TEXT = (
    "Galaxy calculate_numeric_param expression tool for deriving integer or floating-point parameter values."
)

COMPOSE_TEXT_PARAM_CITATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/compose_text_param"

COMPOSE_TEXT_PARAM_CITATION_TEXT = "This tool concatenates each parameter value to a string."

COMPRESS_FILE_CITATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/compress_file"

COMPRESS_FILE_CITATION_TEXT = (
    "Compress files with gzip. If compressing a collection, all elements within that collection will be compressed."
)

COLLECTION_ELEMENT_IDENTIFIERS_CITATION_URL = (
    "https://github.com/galaxyproject/tools-iuc/tree/main/tools/collection_element_identifiers"
)

COLLECTION_ELEMENT_IDENTIFIERS_CITATION_TEXT = (
    "Extracts the element identifiers from a list collection and writes them to a plain text file."
)

COLLECTION_COLUMN_JOIN_CITATION_URL = (
    "https://github.com/galaxyproject/tools-iuc/tree/main/tools/collection_column_join"
)

COLLECTION_COLUMN_JOIN_CITATION_TEXT = "Joins lists of tabular datasets together on a field."

CALCULATE_CONTRAST_THRESHOLD_DOCUMENTATION_URL = (
    "https://github.com/CEGRcode/ChIP-QC-tools/tree/master/calculate_contrast_threshold"
)

CALCULATE_CONTRAST_THRESHOLD_CITATION_URLS = [
    CALCULATE_CONTRAST_THRESHOLD_DOCUMENTATION_URL,
    "https://github.com/galaxyproject/tools-iuc/tree/main/tools/calculate_contrast_threshold",
    "http://www.pughlab.psu.edu/",
]

CALCULATE_CONTRAST_THRESHOLD_CITATION_TEXT = (
    "calculate_contrast_threshold is an unpublished Pugh Lab / CEGR ChIP-QC helper for calculating "
    "heatmap contrast thresholds from tag pileup CDT matrices."
)

COVERAGE_REPORT_CITATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/coverage_report"

COVERAGE_REPORT_CITATION_TEXT = "Panel Coverage Report creates a coverage report for QC purposes."

EXTRACT_GENOMIC_DNA_CITATION_URL = (
    "https://github.com/galaxyproject/tools-iuc/tree/main/tools/extract_genomic_dna"
)

EXTRACT_GENOMIC_DNA_CITATION_TEXT = (
    "Extract Genomic DNA fetches genomic DNA in FASTA or interval format from assembled or unassembled genomes."
)

BARCODE_SPLITTER_CITATION_DOI = "10.5281/zenodo.2566616"

BARCODE_SPLITTER_CITATION_URL = "https://bitbucket.org/princeton_genomics/barcode_splitter/"

BARCODE_SPLITTER_CITATION_TEXT = (
    "Barcode Splitter: split sequence files using multiple sets of barcodes."
)

BCTOOLS_CITATION_DOI = "10.1016/j.molcel.2013.07.001"

BCTOOLS_CITATION_URL = "https://github.com/dmaticzka/bctools"

BCTOOLS_CITATION_TEXT = (
    "bctools handles barcodes and UMIs in NGS data, including binary RY-space barcodes used with uvCLAP and FLASH."
)

BLASTXML_TO_GAPPED_GFF3_CITATION_URL = (
    "https://github.com/galaxyproject/tools-iuc/tree/main/tools/blastxml_to_gapped_gff3"
)

BLASTXML_TO_GAPPED_GFF3_CITATION_TEXT = (
    "BlastXML to gapped GFF3 converts BLAST XML alignments into GFF3 with match_part features and Gap attributes."
)

MAGICBLAST_CITATION_DOI = "10.1186/s12859-019-2996-x"

MAGICBLAST_CITATION_TEXT = "Magic-BLAST, an accurate RNA-seq aligner for long and short reads."

BMTAGGER_CITATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/bmtagger"

BMTAGGER_CITATION_TEXT = "BMTagger: Best Match Tagger for removing human reads from metagenomics datasets."

CAT_CITATION_DOIS = [
    "10.1101/072868",
    "10.1186/s13059-019-1817-x",
    "10.1038/nmeth.3176",
    "10.1186/1471-2105-11-119",
]

CAT_CITATION_URL = "https://github.com/dutilh/CAT"

CAT_CITATION_TEXT = (
    "CAT and BAT classify contigs and metagenome-assembled genomes taxonomically; "
    "the Galaxy wrappers also cite DIAMOND protein alignment and Prodigal prokaryotic gene recognition."
)

CAWLIGN_CITATION_URL = "https://github.com/veg/cawlign"

CAWLIGN_CITATION_TEXT = "cawlign: a C++ port of bealign for codon-aware, nucleotide, and protein alignments."

AEGEAN_CITATION_URL = "https://github.com/BrendelGroup/AEGeAn"

AEGEAN_CITATION_TEXT = "AEGeAn genome annotation toolkit."

LOCUSPOCUS_CITATION_DOI = "10.1093/nargab/lqac013"

LOCUSPOCUS_CITATION_TEXT = (
    "Interval locus concepts and associated LocusPocus/Fidibus software for comparative genome annotation."
)

PARSEVAL_CITATION_DOI = "10.1186/1471-2105-13-187"

PARSEVAL_CITATION_TEXT = "ParsEval: parallel comparison and analysis of gene structure annotations."

AUGUSTUS_CITATION_DOIS = [
    "10.1093/bioinformatics/btg1080",
    "10.1093/bioinformatics/btr010",
    "10.1093/bioinformatics/btn013",
]

AUGUSTUS_CITATION_TEXT = (
    "AUGUSTUS predicts genes in eukaryotic genomic sequences, supports alternative transcripts and UTRs, "
    "and can incorporate extrinsic evidence hints."
)

AUGUSTUS_DOCUMENTATION_URL = "https://bioinf.uni-greifswald.de/augustus/"

ARRIBA_CITATION_DOI = "10.1101/gr.257246.119"

ARRIBA_CITATION_TEXT = "Arriba detects gene fusions and other aberrant transcripts from STAR-aligned RNA-Seq data."

ARRIBA_DOCUMENTATION_URL = "https://github.com/suhrig/arriba/wiki"

ARTIC_CITATION_URL = "https://github.com/artic-network/fieldbioinformatics"

ARTIC_CITATION_TEXT = "ARTIC toolkit by the ARTIC network for field bioinformatics workflows."

ARTIC_DOCUMENTATION_URL = "https://artic.readthedocs.io/en/latest/"

GFFREAD_CITATION_DOI = "10.12688/f1000research.23297.2"

GFFREAD_CITATION_TEXT = "GFF Utilities: GffRead and GffCompare."

def _bedtools_common_output(node_id: str, filename: str, output_dir: str | Path) -> Path:
    out = Path(output_dir) / node_id
    out.mkdir(parents=True, exist_ok=True)
    return out / filename

def _bedtools_add_genome(cmd: list[str], inputs: dict[str, Any]) -> None:
    _add_if_value(cmd, "-g", inputs.get("genome"))

def _bedtools_add_lr_or_b(cmd: list[str], inputs: dict[str, Any]) -> None:
    mode = str(inputs.get("addition_mode", inputs.get("addition_select", "b")))
    if mode == "lr":
        cmd.extend(["-l", str(inputs.get("left", inputs.get("l", 0)))])
        cmd.extend(["-r", str(inputs.get("right", inputs.get("r", 0)))])
    else:
        cmd.extend(["-b", str(inputs.get("both", inputs.get("b", 1)))])

def _bedtools_strand_flag(value: Any, *, same: str = "-s", opposite: str = "-S") -> str:
    strand = str(value or "")
    return {
        "same": same,
        "opposite": opposite,
        "-s": same,
        "-S": opposite,
        same: same,
        opposite: opposite,
    }.get(strand, "")

def _bcftools_common_output(node_id: str, filename: str, output_dir: str | Path) -> Path:
    out = Path(output_dir) / node_id
    out.mkdir(parents=True, exist_ok=True)
    return out / filename

def _bcftools_add_output_type(cmd: list[str], inputs: dict[str, Any]) -> None:
    output_type = str(inputs.get("output_type", "z"))
    if output_type and output_type != "__none__":
        cmd.extend(["--output-type", output_type])

def _bcftools_variant_suffix(inputs: dict[str, Any], default: str = ".vcf.gz") -> str:
    output_type = str(inputs.get("output_type", "z"))
    return {"b": ".bcf", "u": ".bcf", "z": ".vcf.gz", "v": ".vcf"}.get(output_type, default)

def _bcftools_add_restrict(cmd: list[str], inputs: dict[str, Any]) -> None:
    _add_if_value(cmd, "--collapse", inputs.get("collapse"))
    _add_if_value(cmd, "--regions", inputs.get("regions"))
    if not inputs.get("_skip_samples_restrict"):
        _add_if_value(cmd, "--samples", inputs.get("samples"))
    _add_if_value(cmd, "--targets", inputs.get("targets"))
    _add_if_value(cmd, "--include", inputs.get("include"))
    _add_if_value(cmd, "--exclude", inputs.get("exclude"))

def _bcftools_add_apply_filters(cmd: list[str], inputs: dict[str, Any]) -> None:
    _add_if_value(cmd, "--apply-filters", inputs.get("apply_filters"))

def _bcftools_add_region_targets(cmd: list[str], inputs: dict[str, Any]) -> None:
    _add_if_value(cmd, "--regions", inputs.get("regions"))
    _add_if_value(cmd, "--regions-overlap", inputs.get("regions_overlap"))
    _add_if_value(cmd, "--targets", inputs.get("targets"))
    _add_if_value(cmd, "--targets-overlap", inputs.get("targets_overlap"))

def _bcftools_add_af_file(cmd: list[str], inputs: dict[str, Any]) -> None:
    _add_if_value(cmd, "--AF-file", inputs.get("AF_file", inputs.get("af_file")))

def _bcftools_plugin_base_cmd(plugin: str, inputs: dict[str, Any]) -> list[str]:
    cmd = ["bcftools", "plugin", plugin]
    _add_if_value(cmd, "--include", inputs.get("include"))
    _add_if_value(cmd, "--exclude", inputs.get("exclude"))
    _bcftools_add_region_targets(cmd, inputs)
    return cmd

def _bcftools_add_plugin_separator(cmd: list[str], plugin_args: list[str]) -> None:
    if plugin_args:
        cmd.append("--")
        cmd.extend(plugin_args)

def _bcftools_add_plugin_vcf_output(cmd: list[str], inputs: dict[str, Any]) -> None:
    cmd.extend(["--output-type", "z"])
    _add_if_value(cmd, "--threads", inputs.get("threads"))

def _bcftools_join_mode(value: Any, default: str = "a") -> str:
    parts = _as_list(value)
    if not parts:
        return default
    return "".join(str(part).replace(",", "") for part in parts)

def _bcftools_convert_from_outputs(inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
    out = Path(output_dir) / "bcftools_convert_from_vcf"
    out.mkdir(parents=True, exist_ok=True)
    mode = str(inputs.get("convert_to", "gen_sample"))
    if mode == "hap_legend_sample":
        return [out / "converted.hap", out / "converted.legend", out / "converted.samples"]
    if mode == "hap_sample":
        return [out / "converted.hap", out / "converted.samples"]
    return [out / "converted.gen", out / "converted.samples"]

AMRFINDERPLUS_ORGANISMS = [
    "Acinetobacter_baumannii",
    "Burkholderia_cepacia",
    "Burkholderia_pseudomallei",
    "Campylobacter",
    "Citrobacter_freundii",
    "Clostridioides_difficile",
    "Enterobacter_cloacae",
    "Enterococcus_faecalis",
    "Enterococcus_faecium",
    "Escherichia",
    "Klebsiella_aerogenes",
    "Klebsiella_oxytoca",
    "Klebsiella_pneumoniae",
    "Neisseria_gonorrhoeae",
    "Neisseria_meningitidis",
    "Pseudomonas_aeruginosa",
    "Salmonella",
    "Serratia_marcescens",
    "Staphylococcus_aureus",
    "Staphylococcus_pseudintermedius",
    "Streptococcus_agalactiae",
    "Streptococcus_pneumoniae",
    "Streptococcus_pyogenes",
    "Vibrio_cholerae",
]

AMRFINDERPLUS_ANNOTATION_FORMATS = [
    "bakta",
    "genbank",
    "microscope",
    "patric",
    "prokka",
    "pseudomonasdb",
    "rast",
    "standard",
    "prodigal",
]

AMRFINDERPLUS_TRANSLATION_TABLES = [
    "",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
    "16",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "33",
]

def _amrfinderplus_out(output_dir: str | Path, filename: str) -> Path:
    out = Path(output_dir) / "amrfinderplus"
    out.mkdir(parents=True, exist_ok=True)
    return out / filename

RAVEN_CITATION_DOI = "10.1038/s43588-021-00073-4"

RAVEN_CITATION_TEXT = "Time- and memory-efficient genome assembly with Raven."

RAVEN_DOCUMENTATION_URL = "https://github.com/lbcb-sci/raven"

SHOVILL_CITATION_URL = "https://github.com/tseemann/shovill"

SHOVILL_CITATION_TEXT = "Shovill: Faster SPAdes assembly of Illumina reads."

SNIPPY_CITATION_URL = "https://github.com/tseemann/snippy"

SNIPPY_CITATION_TEXT = "snippy: fast bacterial variant calling from NGS reads."

ABRICATE_CITATION_TEXT = "ABRicate: mass screening of contigs for antibiotic resistance genes."

ABRICATE_CITATION_URL = "https://github.com/tseemann/abricate"

PLASMIDFINDER_CITATION_DOI = "10.1007/978-1-4939-9877-7_20"

PLASMIDFINDER_CITATION_TEXT = (
    "PlasmidFinder and In Silico pMLST: Identification and Typing of Plasmid Replicons in "
    "Whole-Genome Sequencing (WGS)."
)

PLASMIDFINDER_DOCUMENTATION_URL = "https://bitbucket.org/genomicepidemiology/plasmidfinder"

STARAMR_CITATION_DOI = "10.3390/microorganisms10020292"

STARAMR_CITATION_TEXT = (
    "Correlation between Phenotypic and In Silico Detection of Antimicrobial Resistance in "
    "Salmonella enterica in Canada Using Staramr."
)

STARAMR_DOCUMENTATION_URL = "https://github.com/phac-nml/staramr"

CHECKM2_TRANSLATION_TABLES = [
    "",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
    "16",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "33",
]

BANDAGE_CITATION_DOI = "10.1093/bioinformatics/btv383"

BANDAGE_CITATION_TEXT = "Bandage: interactive visualization of de novo genome assemblies."

def _bandage_prefix(inputs: dict[str, Any], node_out: str) -> list[str]:
    return [
        "ln",
        "-sf",
        str(inputs.get("input_file", "")),
        f"{node_out}/input.gfa",
        "&&",
        "export",
        "QT_QPA_PLATFORM=offscreen",
        "&&",
    ]

ASSEMBLY_STATS_CITATION_DOI = "10.5281/zenodo.322347"

ASSEMBLY_STATS_CITATION_TEXT = "rjchallis/assembly-stats 17.02."

AMAS_CITATION_DOI = "10.7717/peerj.1660"

AMAS_CITATION_TEXT = "AMAS: a fast tool for alignment manipulation and computing of summary statistics."

CLUSTALW_CITATION_DOI = "10.1093/bioinformatics/btm404"

CLUSTALW_CITATION_TEXT = "Clustal W and Clustal X version 2.0."

QUICKTREE_CITATION_DOI = "10.1093/oxfordjournals.molbev.a040454"

QUICKTREE_CITATION_TEXT = "The neighbor-joining method: a new method for reconstructing phylogenetic trees."

RAPIDNJ_CITATION_DOI = "10.1007/978-3-540-87361-7_10"

RAPIDNJ_CITATION_TEXT = "Rapid Neighbour Joining: high-performance neighbour-joining phylogenetic inference."

PHYML_CITATION_DOI = "10.1093/sysbio/syq010"

PHYML_CITATION_TEXT = (
    "New Algorithms and Methods to Estimate Maximum-Likelihood Phylogenies: "
    "Assessing the Performance of PhyML 3.0."
)

FLASH_CITATION_DOI = "10.1093/bioinformatics/btr507"

FLASH_CITATION_TEXT = "FLASH: fast length adjustment of short reads to improve genome assemblies."

PEAR_CITATION_DOI = "10.1093/bioinformatics/btt593"

PEAR_CITATION_TEXT = "PEAR: a fast and accurate Illumina Paired-End reAd mergeR."

FRAGGENESCAN_CITATION_DOI = "10.1093/nar/gkq747"

FRAGGENESCAN_CITATION_TEXT = (
    "FragGeneScan: predicting genes in short and error-prone reads."
)

PRODIGAL_CITATION_DOI = "10.1186/1471-2105-11-119"

PRODIGAL_CITATION_TEXT = "Prodigal: prokaryotic gene recognition and translation initiation site identification."

EUKREP_CITATION_DOI = "10.1101/gr.228429.117"

EUKREP_CITATION_TEXT = "Genome-reconstruction for eukaryotes from complex natural microbial communities."

GAMMA_CITATION_DOI = "10.1093/bioinformatics/btab607"

GAMMA_CITATION_TEXT = (
    "GAMMA: a tool for the rapid identification, classification and annotation of translated gene matches "
    "from sequencing data."
)

RED_CITATION_DOI = "10.1186/s12859-015-0654-5"

RED_CITATION_TEXT = "Red: an intelligent, rapid, accurate tool for detecting repeats de-novo on the genomic scale."

ABRITAMR_CITATION_DOI = "10.5281/zenodo.7370627"

ABRITAMR_CITATION_TEXT = "MDU-PHL/abritamr: AMR gene detection and reporting pipeline."

NONPAREIL_CITATION_DOI = "10.1093/bioinformatics/btt584"

NONPAREIL_CITATION_TEXT = "Nonpareil: a redundancy-based approach to assess the level of coverage in metagenomic datasets."

BBTOOLS_CITATION_DOI = "10.1371/journal.pone.0185056"

BBTOOLS_CITATION_TEXT = "BBMerge - Accurate paired shotgun read merging via overlap."

PLASCLASS_CITATION_DOI = "10.1371/journal.pcbi.1007781"

PLASCLASS_CITATION_TEXT = "PlasClass improves plasmid sequence classification."

PLASFLOW_CITATION_DOI = "10.1093/nar/gkx1321"

PLASFLOW_CITATION_TEXT = "PlasFlow: predicting plasmid sequences in metagenomic data using genome signatures."

MINIA_CITATION_DOI = "10.1186/1748-7188-8-22"

MINIA_CITATION_TEXT = "Space-efficient and exact de Bruijn graph representation based on a Bloom filter."

GENOMESCOPE_CITATION_DOIS = ["10.1093/bioinformatics/btx153", "10.1038/s41467-020-14998-3"]

GENOMESCOPE_CITATION_TEXT = (
    "GenomeScope: fast reference-free genome profiling from short reads; "
    "GenomeScope 2.0 and Smudgeplot for reference-free profiling of polyploid genomes."
)

ART_CITATION_DOI = "10.1093/bioinformatics/btr708"

ART_CITATION_TEXT = "ART: a next-generation sequencing read simulator."

AMPLICAN_CITATION_DOI = "10.1101/gr.244293.118"

AMPLICAN_CITATION_TEXT = "Accurate analysis of genuine CRISPR editing events with ampliCan. Genome Research."

ALLEGRO_CITATION_DOIS = ["10.1038/ng1005-1015", "10.1038/75514"]

ALLEGRO_CITATION_TEXT = (
    "Allegro version 2; "
    "Allegro, a new computer program for multipoint linkage analysis."
)

ALPHAGENOME_CITATION_DOI = "10.1038/s41586-025-10014-0"

ALPHAGENOME_CITATION_TEXT = "Advancing regulatory variant effect prediction with AlphaGenome."

AMPVIS2_CITATION_DOIS = ["10.1101/299537", "10.1371/journal.pcbi.1003531"]

AMPVIS2_CITATION_TEXT = (
    "ampvis2: an R package to analyse and visualise 16S rRNA amplicon data; "
    "Waste Not, Want Not: Why Rarefying Microbiome Data Is Inadmissible."
)

ALDEX2_CITATION_DOIS = [
    "10.1371/journal.pone.0067019",
    "10.1186/2049-2618-2-15",
    "10.1080/10618600.2015.1131161",
]

ALDEX2_CITATION_TEXT = (
    "ANOVA-Like Differential Expression (ALDEx) Analysis for Mixed Population RNA-Seq; "
    "Unifying the analysis of high-throughput sequencing datasets: characterizing RNA-seq, 16S rRNA gene "
    "sequencing and selective growth experiments by compositional data analysis; "
    "Displaying Variation in Large Datasets: Plotting a Visual Summary of Effect Sizes."
)

ANCOMBC_CITATION_DOIS = ["10.1038/s41467-020-17041-7", "10.3402/mehd.v26.27663"]

ANCOMBC_CITATION_TEXT = (
    "Analysis of compositions of microbiomes with bias correction; "
    "Analysis of composition of microbiomes: a novel method for studying microbial composition."
)

ANGSD_CITATION_DOIS = ["10.1186/s12859-014-0356-4", "10.7717/peerj.10947"]

ANGSD_CITATION_TEXT = (
    "ANGSD: Analysis of Next Generation Sequencing Data; "
    "Reproducible, portable, and efficient ancient genome reconstruction with nf-core/eager."
)

MINIASM_CITATION_DOI = "10.1093/bioinformatics/btw152"

MINIASM_CITATION_TEXT = "Minimap and miniasm: fast mapping and de novo assembly for noisy long sequences."

MEGAHIT_CITATION_DOI = "10.1093/bioinformatics/btv033"

MEGAHIT_CITATION_TEXT = (
    "MEGAHIT: an ultra-fast single-node solution for large and complex metagenomics assembly "
    "via succinct de Bruijn graph."
)

PRINSEQ_CITATION_DOI = "10.1093/bioinformatics/btr026"

PRINSEQ_CITATION_TEXT = "Quality control and preprocessing of metagenomic datasets."

ADAPTER_REMOVAL_CITATION_DOI = "10.1186/s13104-016-1900-2"

ADAPTER_REMOVAL_CITATION_TEXT = "AdapterRemoval v2: rapid adapter trimming, identification, and read merging."

ADAPTER_REMOVAL_ADAPTER1 = "AGATCGGAAGAGCACACGTCTGAACTCCAGTCACNNNNNNATCTCGTATGCCGTCTTCTGCTTG"

ADAPTER_REMOVAL_ADAPTER2 = "AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGTAGATCTCGGTGGTCGCCGTATCATT"

TRIMN_CITATION_DOIS = ["10.1101/2020.05.22.110833", "10.1101/2020.06.30.177956"]

TRIMN_CITATION_TEXT = "Vertebrate Genomes Project assembly pipeline methods for bionano hybrid scaffolds."

DIAMOND_CITATION_DOI = "10.1038/s41592-021-01101-x"

DIAMOND_CITATION_TEXT = "Sensitive protein alignments at tree-of-life scale using DIAMOND."

DIAMOND_OUTPUT_FORMATS = {
    "0": ("TXT", "blast_pairwise", "blast_pairwise.txt"),
    "5": ("XML", "blast_xml", "blast.xml"),
    "6": ("TSV", "blast_tabular", "blast_tabular.tsv"),
    "100": ("FILE", "daa_output", "output.daa"),
    "101": ("SAM", "sam_output", "output.sam"),
    "102": ("TSV", "tax_output", "taxonomic_classification.tsv"),
    "104": ("JSON", "json_output", "output.json"),
}

DIAMOND_DEFAULT_FIELDS = [
    "qseqid",
    "sseqid",
    "pident",
    "length",
    "mismatch",
    "gapopen",
    "qstart",
    "qend",
    "sstart",
    "send",
    "evalue",
    "bitscore",
]

DIAMOND_FIELD_OPTIONS = [
    "qseqid",
    "qlen",
    "sseqid",
    "sallseqid",
    "slen",
    "qstart",
    "qend",
    "sstart",
    "send",
    "qseq",
    "sseq",
    "evalue",
    "bitscore",
    "score",
    "length",
    "pident",
    "nident",
    "mismatch",
    "positive",
    "gapopen",
    "gaps",
    "ppos",
    "qframe",
    "btop",
    "stitle",
    "salltitles",
    "qcovhsp",
    "qtitle",
    "full_sseq",
    "qqual",
    "qnum",
    "snum",
    "scovhsp",
    "full_qqual",
    "full_qseq",
    "qseq_gapped",
    "sseq_gapped",
    "qstrand",
    "cigar",
    "full_qseq_mate",
    "qseq_translated",
    "hspnum",
    "normalized_bitscore",
    "normalized_nident",
    "approx_pident",
    "corrected_bitscore",
    "staxids",
    "sscinames",
    "sskingdoms",
    "skingdoms",
    "sphylums",
    "slineages",
]

DIAMOND_SENSITIVITY_OPTIONS = [
    "--faster",
    "--fast",
    "",
    "--mid-sensitive",
    "--sensitive",
    "--more-sensitive",
    "--very-sensitive",
    "--ultra-sensitive",
]

KRAKENTOOLS_DOI = "10.1038/s41596-022-00738-y"

KRAKENTOOLS_CITATION_TEXT = "Metagenome analysis using the Kraken software suite."

BRACKEN_DOI = "10.7717/peerj-cs.104"

BRACKEN_CITATION_TEXT = "Bracken: estimating species abundance in metagenomics data."

MOTHUR_DOI = "10.1128/AEM.01541-09"

MOTHUR_CITATION_TEXT = (
    "Introducing mothur: open-source, platform-independent, community-supported software for "
    "describing and comparing microbial communities."
)

KRONA_CITATION_DOIS = ["10.1186/1471-2105-12-385", "10.1093/bioinformatics/btu135"]

KRONA_CITATION_TEXT = (
    "Interactive metagenomic visualization in a Web browser; "
    "Orione, a web-based framework for NGS analysis in microbiology."
)

BEACON2_DOI = "10.1093/bioinformatics/btac568"

BEACON2_CITATION_TEXT = (
    "Beacon v2 Reference Implementation: a toolkit to enable federated sharing of genomic and phenotypic data."
)

BEACON2_IMPORT_DOI = "10.1002/humu.24369"

BEACON2_IMPORT_CITATION_TEXT = (
    "Beacon v2 provides a standardized framework for querying genomic and phenotypic data discovery services."
)

BIOM_FORMAT_DOI = "10.1186/2047-217X-1-7"

BIOM_FORMAT_CITATION_TEXT = "The Biological Observation Matrix (BIOM) format."

QQMAN_CITATION_DOIS = ["10.1101/005165", "10.21105/joss.00731"]

QQMAN_CITATION_TEXT = "qqman: an R package for visualizing GWAS results using Q-Q and manhattan plots."

HEINZ_CITATION_DOIS = ["10.1093/bioinformatics/btn161", "10.1093/bioinformatics/btg148"]

HEINZ_CITATION_TEXT = (
    "Heinz identifies optimal scoring subnetworks; "
    "Beta-Uniform Mixture models support p-value distribution scoring."
)

HEINZ_BUM_CITATION_DOIS = ["10.1093/bioinformatics/btq089", "10.1093/bioinformatics/btn161"]

HEINZ_BUM_CITATION_TEXT = (
    "BioNet provides Beta-Uniform Mixture modeling for p-value distributions; "
    "Heinz identifies optimal scoring subnetworks."
)

BREW3R_R_CITATION_URL = "https://github.com/lldelisle/BREW3R.r"

BREW3R_R_CITATION_TEXT = "BREW3R.r extends GTF annotations at 3' ends while preventing new gene overlaps."

UCSC_UTILS_CITATION_DOI = "10.1093/bib/bbs038"

UCSC_UTILS_CITATION_TEXT = "The UCSC genome browser and associated tools."

UCSC_GENOME_BROWSER_CITATION_DOI = "10.1101/gr.229102"

UCSC_GENOME_BROWSER_CITATION_TEXT = "The Human Genome Browser at UCSC."

TAXPASTA_DOI = "10.21105/joss.05627"

TAXPASTA_CITATION_TEXT = "TAXPASTA: TAXonomic Profile Aggregation and STAndardisation."

HUMANN_CITATION_DOIS = ["10.7554/eLife.65088", "10.1371/journal.pcbi.1002358"]

HUMANN_CITATION_TEXT = (
    "bioBakery 3: a platform for analyzing meta'omic datasets; "
    "HUMAnN: the HMP Unified Metabolic Analysis Network."
)

METAPHLAN_DOI = "10.1038/s41587-023-01688-w"

METAPHLAN_CITATION_TEXT = (
    "Extending and improving metagenomic taxonomic profiling with uncharacterized species using MetaPhlAn 4."
)

HYBPIPER_CITATION_DOI = "10.3732/apps.1600016"

HYBPIPER_CITATION_TEXT = (
    "HybPiper: Extracting coding sequence and introns for phylogenetics from "
    "high-throughput sequencing reads using target enrichment."
)

HYPHY_ABSREL_CITATION_DOIS = ["10.1093/molbev/msz197", "10.1093/molbev/msv022"]

HYPHY_ABSREL_CITATION_TEXT = (
    "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
    "Less Is More: an adaptive branch-site random effects model for efficient detection of "
    "episodic diversifying selection."
)

HYPHY_CITATION_DOI = "10.1093/molbev/msz197"

HYPHY_CITATION_TEXT = "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies."

HYPHY_FUBAR_CITATION_DOI = "10.1093/molbev/mst030"

HYPHY_B_STILL_CITATION_DOIS = [HYPHY_CITATION_DOI, HYPHY_FUBAR_CITATION_DOI]

HYPHY_B_STILL_CITATION_TEXT = (
    "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
    "FUBAR: A Fast, Unconstrained Bayesian AppRoximation for Inferring Selection."
)

HYPHY_BGM_CITATION_DOIS = [
    HYPHY_CITATION_DOI,
    "10.1093/bioinformatics/btn313",
    "10.1371/journal.pcbi.0030231",
]

HYPHY_BGM_CITATION_TEXT = (
    "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
    "Spidermonkey: rapid detection of co-evolving sites using Bayesian graphical models; "
    "An evolutionary-network model reveals stratified interactions in the V3 loop of the HIV-1 envelope."
)

HYPHY_FADE_CITATION_DOIS = [HYPHY_CITATION_DOI, HYPHY_FUBAR_CITATION_DOI]

HYPHY_FADE_CITATION_TEXT = (
    "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
    "FUBAR: A Fast, Unconstrained Bayesian AppRoximation for Inferring Selection."
)

HYPHY_FEL_CITATION_DOIS = [HYPHY_CITATION_DOI, "10.1093/molbev/msi105"]

HYPHY_FEL_CITATION_TEXT = (
    "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
    "Not So Different After All: A Comparison of Methods for Detecting Amino Acid Sites Under Selection."
)

HYPHY_FUBAR_CITATION_DOIS = [HYPHY_CITATION_DOI, HYPHY_FUBAR_CITATION_DOI]

HYPHY_FUBAR_CITATION_TEXT = (
    "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
    "FUBAR: A Fast, Unconstrained Bayesian AppRoximation for Inferring Selection."
)

HYPHY_GARD_CITATION_DOIS = [HYPHY_CITATION_DOI, "10.1093/molbev/msl051"]

HYPHY_GARD_CITATION_TEXT = (
    "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
    "Automated Phylogenetic Detection of Recombination Using a Genetic Algorithm."
)

HYPHY_MEME_CITATION_DOIS = [HYPHY_CITATION_DOI, "10.1371/journal.pgen.1002764"]

HYPHY_MEME_CITATION_TEXT = (
    "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
    "Detecting Individual Sites Subject to Episodic Diversifying Selection."
)

HYPHY_PRIME_CITATION_DOIS = [HYPHY_CITATION_DOI, "10.64898/2026.03.09.710461"]

HYPHY_PRIME_CITATION_TEXT = (
    "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
    "Characterizing Physicochemical Selection in Protein Evolution with Property-Informed Models (PRIME)."
)

HYPHY_RELAX_CITATION_DOIS = [HYPHY_CITATION_DOI, "10.1093/molbev/msu400"]

HYPHY_RELAX_CITATION_TEXT = (
    "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
    "RELAX: Detecting Relaxed Selection in a Phylogenetic Framework."
)

HYPHY_SLAC_CITATION_DOIS = [HYPHY_CITATION_DOI, "10.1093/molbev/msi105"]

HYPHY_SLAC_CITATION_TEXT = (
    "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
    "Not So Different After All: A Comparison of Methods for Detecting Amino Acid Sites Under Selection."
)

HYPHY_SM19_CITATION_DOIS = [HYPHY_CITATION_DOI, "10.1093/genetics/123.3.603"]

HYPHY_SM19_CITATION_TEXT = (
    "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
    "A cladistic measure of gene flow inferred from the phylogenies of alleles."
)

HYPHY_STRIKE_AMBIGS_CITATION_DOIS = [HYPHY_CITATION_DOI, "10.1093/bioinformatics/bti079"]

HYPHY_STRIKE_AMBIGS_CITATION_TEXT = (
    "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
    "HyPhy: hypothesis testing using phylogenies."
)

HYPHY_BUSTED_CITATION_DOIS = [
    HYPHY_CITATION_DOI,
    "10.1093/molbev/msv035",
    "10.1093/molbev/msaa037",
    "10.1093/molbev/msaf068",
]

HYPHY_BUSTED_CITATION_TEXT = (
    "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
    "Gene-Wide Identification of Episodic Selection; "
    "Synonymous Site-to-Site Substitution Rate Variation Dramatically Inflates False Positive Rates of "
    "Selection Analyses: Ignore at Your Own Peril; "
    "A New Comparative Framework for Estimating Selection on Synonymous Substitutions."
)

HYPHY_CFEL_CITATION_DOIS = [HYPHY_CITATION_DOI, "10.1093/molbev/msaa263"]

HYPHY_CFEL_CITATION_TEXT = (
    "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
    "Contrast-FEL: A Test for Differences in Selective Pressures at Individual Sites among Clades and "
    "Sets of Branches."
)

DREP_CITATION_DOI = "10.1038/ismej.2017.126"

DREP_CITATION_TEXT = "dRep: a tool for fast and accurate genomic comparisons that enables improved genome recovery from metagenomes through de-replication."


# Explicit, not `[name for name in globals() ...]`: mypy evaluates __all__
# statically, so a comprehension over globals() made `import *` export
# nothing as far as the type checker was concerned, and every name in every
# consuming module became an undefined-name error. That one line accounted
# for roughly 8000 of the repository's 8535 mypy errors. The contents below
# are exactly what the comprehension produced at import time.
__all__ = [
    "ABRICATE_CITATION_TEXT",
    "ABRICATE_CITATION_URL",
    "ABRITAMR_CITATION_DOI",
    "ABRITAMR_CITATION_TEXT",
    "ADAPTER_REMOVAL_ADAPTER1",
    "ADAPTER_REMOVAL_ADAPTER2",
    "ADAPTER_REMOVAL_CITATION_DOI",
    "ADAPTER_REMOVAL_CITATION_TEXT",
    "ADD_INPUT_NAME_AS_COLUMN_CITATION_TEXT",
    "ADD_INPUT_NAME_AS_COLUMN_CITATION_URL",
    "AEGEAN_CITATION_TEXT",
    "AEGEAN_CITATION_URL",
    "ALDEX2_CITATION_DOIS",
    "ALDEX2_CITATION_TEXT",
    "ALLEGRO_CITATION_DOIS",
    "ALLEGRO_CITATION_TEXT",
    "ALPHAGENOME_CITATION_DOI",
    "ALPHAGENOME_CITATION_TEXT",
    "AMAS_CITATION_DOI",
    "AMAS_CITATION_TEXT",
    "AMPLICAN_CITATION_DOI",
    "AMPLICAN_CITATION_TEXT",
    "AMPVIS2_CITATION_DOIS",
    "AMPVIS2_CITATION_TEXT",
    "AMRFINDERPLUS_ANNOTATION_FORMATS",
    "AMRFINDERPLUS_ORGANISMS",
    "AMRFINDERPLUS_TRANSLATION_TABLES",
    "ANCOMBC_CITATION_DOIS",
    "ANCOMBC_CITATION_TEXT",
    "ANGSD_CITATION_DOIS",
    "ANGSD_CITATION_TEXT",
    "ANNDATA2RI_CITATION_TEXT",
    "ANNDATA2RI_CITATION_URL",
    "ANNDATA_SCANPY_CITATION_DOI",
    "ANNDATA_SCANPY_CITATION_TEXT",
    "ARGNORM_CITATION_DOI",
    "ARGNORM_CITATION_TEXT",
    "ARRIBA_CITATION_DOI",
    "ARRIBA_CITATION_TEXT",
    "ARRIBA_DOCUMENTATION_URL",
    "ARTIC_CITATION_TEXT",
    "ARTIC_CITATION_URL",
    "ARTIC_DOCUMENTATION_URL",
    "ART_CITATION_DOI",
    "ART_CITATION_TEXT",
    "ASSEMBLY_STATS_CITATION_DOI",
    "ASSEMBLY_STATS_CITATION_TEXT",
    "AUGUSTUS_CITATION_DOIS",
    "AUGUSTUS_CITATION_TEXT",
    "AUGUSTUS_DOCUMENTATION_URL",
    "AUTOBIGS_CLI_CITATION_TEXT",
    "AUTOBIGS_CLI_CITATION_URL",
    "Any",
    "B2BTOOLS_CITATION_DOIS",
    "B2BTOOLS_CITATION_TEXT",
    "BAM_TO_SCIDX_CITATION_TEXT",
    "BAM_TO_SCIDX_CITATION_URL",
    "BANDAGE_CITATION_DOI",
    "BANDAGE_CITATION_TEXT",
    "BARCODE_SPLITTER_CITATION_DOI",
    "BARCODE_SPLITTER_CITATION_TEXT",
    "BARCODE_SPLITTER_CITATION_URL",
    "BAREDSC_CITATION_DOI",
    "BAREDSC_CITATION_TEXT",
    "BAREDSC_DOCUMENTATION_URL",
    "BARRNAP_CITATION_TEXT",
    "BARRNAP_CITATION_URL",
    "BASIL_CITATION_DOI",
    "BASIL_CITATION_TEXT",
    "BAX2BAM_CITATION_TEXT",
    "BAX2BAM_CITATION_URL",
    "BBG_TO_BIGWIG_CITATION_DOI",
    "BBG_TO_BIGWIG_CITATION_TEXT",
    "BBTOOLS_CITATION_DOI",
    "BBTOOLS_CITATION_TEXT",
    "BCFTOOLS_CITATION_DOIS",
    "BCFTOOLS_CITATION_TEXT",
    "BCFTOOLS_CITATION_URLS",
    "BCTOOLS_CITATION_DOI",
    "BCTOOLS_CITATION_TEXT",
    "BCTOOLS_CITATION_URL",
    "BEACON2_CITATION_TEXT",
    "BEACON2_DOI",
    "BEACON2_IMPORT_CITATION_TEXT",
    "BEACON2_IMPORT_DOI",
    "BEDOPS_CITATION_DOI",
    "BEDOPS_CITATION_TEXT",
    "BEDTOOLS_CITATION_DOI",
    "BEDTOOLS_CITATION_TEXT",
    "BEROKKA_CITATION_TEXT",
    "BEROKKA_CITATION_URL",
    "BIOEXT_CITATION_TEXT",
    "BIOEXT_CITATION_URL",
    "BIOEXT_DOCUMENTATION_URL",
    "BIOEXT_SANITIZE_PIPE",
    "BIOM_FORMAT_CITATION_TEXT",
    "BIOM_FORMAT_DOI",
    "BIONODULO_BUILTIN_ALIAS",
    "BLASTXML_TO_GAPPED_GFF3_CITATION_TEXT",
    "BLASTXML_TO_GAPPED_GFF3_CITATION_URL",
    "BMTAGGER_CITATION_TEXT",
    "BMTAGGER_CITATION_URL",
    "BOWTIE2_CITATION_DOI",
    "BOWTIE2_CITATION_TEXT",
    "BP_GENBANK2GFF3_CITATION_DOI",
    "BP_GENBANK2GFF3_CITATION_TEXT",
    "BRACKEN_CITATION_TEXT",
    "BRACKEN_DOI",
    "BREW3R_R_CITATION_TEXT",
    "BREW3R_R_CITATION_URL",
    "BWA_CITATION_DOIS",
    "BWA_CITATION_TEXT",
    "BWA_CITATION_URLS",
    "BWA_MEM2_CITATION_DOIS",
    "BWA_MEM2_CITATION_TEXT",
    "BWA_MEM2_CITATION_URLS",
    "BWA_METH_CITATION_DOIS",
    "BWA_METH_CITATION_TEXT",
    "BWA_METH_CITATION_URLS",
    "BWA_METH_DOCUMENTATION_URL",
    "BaseNode",
    "CALCULATE_CONTRAST_THRESHOLD_CITATION_TEXT",
    "CALCULATE_CONTRAST_THRESHOLD_CITATION_URLS",
    "CALCULATE_CONTRAST_THRESHOLD_DOCUMENTATION_URL",
    "CALCULATE_NUMERIC_PARAM_CITATION_TEXT",
    "CALCULATE_NUMERIC_PARAM_CITATION_URL",
    "CAT_CITATION_DOIS",
    "CAT_CITATION_TEXT",
    "CAT_CITATION_URL",
    "CAWLIGN_CITATION_TEXT",
    "CAWLIGN_CITATION_URL",
    "CD_HIT_CITATION_DOIS",
    "CD_HIT_CITATION_TEXT",
    "CELLTYPIST_CITATION_DOI",
    "CELLTYPIST_CITATION_TEXT",
    "CEMITOOL_CITATION_DOIS",
    "CEMITOOL_CITATION_TEXT",
    "CHARTS_CITATION_TEXT",
    "CHARTS_CITATION_URL",
    "CHECKM2_TRANSLATION_TABLES",
    "CHERRI_CITATION_TEXT",
    "CHERRI_CITATION_URL",
    "CHERRI_DOCUMENTATION_URL",
    "CHEWBBACA_CITATION_DOI",
    "CHEWBBACA_CITATION_TEXT",
    "CHIRA_CITATION_DOI",
    "CHIRA_CITATION_TEXT",
    "CHIRA_DOCUMENTATION_URL",
    "CHOPIN2_CITATION_DOI",
    "CHOPIN2_CITATION_TEXT",
    "CHOPPER_CITATION_DOI",
    "CHOPPER_CITATION_TEXT",
    "CHROMAP_CITATION_DOI",
    "CHROMAP_CITATION_TEXT",
    "CIALIGN_CITATION_DOI",
    "CIALIGN_CITATION_TEXT",
    "CIRCEXPLORER2_CITATION_DOI",
    "CIRCEXPLORER2_CITATION_TEXT",
    "CIRCOS_CITATION_DOIS",
    "CIRCOS_CITATION_TEXT",
    "CITE_SEQ_COUNT_CITATION_DOI",
    "CITE_SEQ_COUNT_CITATION_TEXT",
    "CLUSTALW_CITATION_DOI",
    "CLUSTALW_CITATION_TEXT",
    "CNVKIT_CITATION_DOI",
    "CNVKIT_CITATION_TEXT",
    "COLLECTION_COLUMN_JOIN_CITATION_TEXT",
    "COLLECTION_COLUMN_JOIN_CITATION_URL",
    "COLLECTION_ELEMENT_IDENTIFIERS_CITATION_TEXT",
    "COLLECTION_ELEMENT_IDENTIFIERS_CITATION_URL",
    "COLUMN_MAKER_CITATION_DOI",
    "COLUMN_MAKER_CITATION_TEXT",
    "COLUMN_ORDER_HEADER_SORT_CITATION_TEXT",
    "COLUMN_ORDER_HEADER_SORT_CITATION_URL",
    "COLUMN_REMOVE_BY_HEADER_CITATION_TEXT",
    "COLUMN_REMOVE_BY_HEADER_CITATION_URL",
    "COMPOSE_TEXT_PARAM_CITATION_TEXT",
    "COMPOSE_TEXT_PARAM_CITATION_URL",
    "COMPRESS_FILE_CITATION_TEXT",
    "COMPRESS_FILE_CITATION_URL",
    "COVERAGE_REPORT_CITATION_TEXT",
    "COVERAGE_REPORT_CITATION_URL",
    "CROSSMAP_CITATION_DOI",
    "CROSSMAP_CITATION_TEXT",
    "CommandNode",
    "DATAMASH_CITATION_TEXT",
    "DATAMASH_CITATION_URL",
    "DATAMASH_DOCUMENTATION_URL",
    "DIAMOND_CITATION_DOI",
    "DIAMOND_CITATION_TEXT",
    "DIAMOND_DEFAULT_FIELDS",
    "DIAMOND_FIELD_OPTIONS",
    "DIAMOND_OUTPUT_FORMATS",
    "DIAMOND_SENSITIVITY_OPTIONS",
    "DOI_URL",
    "DREP_CITATION_DOI",
    "DREP_CITATION_TEXT",
    "EUKREP_CITATION_DOI",
    "EUKREP_CITATION_TEXT",
    "EXTRACT_GENOMIC_DNA_CITATION_TEXT",
    "EXTRACT_GENOMIC_DNA_CITATION_URL",
    "FALCO_CITATION_DOI",
    "FALCO_CITATION_TEXT",
    "FALCO_DOCUMENTATION_URL",
    "FASTA_REGEX_FINDER_CITATION_TEXT",
    "FASTA_REGEX_FINDER_CITATION_URL",
    "FASTA_STATS_CITATION_TEXT",
    "FASTA_STATS_CITATION_URL",
    "FEATURECOUNTS_CITATION_DOI",
    "FEATURECOUNTS_CITATION_TEXT",
    "FILTLONG_CITATION_TEXT",
    "FILTLONG_CITATION_URL",
    "FLASH_CITATION_DOI",
    "FLASH_CITATION_TEXT",
    "FRAGGENESCAN_CITATION_DOI",
    "FRAGGENESCAN_CITATION_TEXT",
    "FREEBAYES_CITATION_DOIS",
    "FREEBAYES_CITATION_TEXT",
    "FREEBAYES_CITATION_URLS",
    "GAMMA_CITATION_DOI",
    "GAMMA_CITATION_TEXT",
    "GENOMESCOPE_CITATION_DOIS",
    "GENOMESCOPE_CITATION_TEXT",
    "GFA_TO_FA_CITATION_TEXT",
    "GFA_TO_FA_CITATION_URL",
    "GFFREAD_CITATION_DOI",
    "GFFREAD_CITATION_TEXT",
    "HAPPY_CITATION_TEXT",
    "HAPPY_CITATION_URL",
    "HEINZ_BUM_CITATION_DOIS",
    "HEINZ_BUM_CITATION_TEXT",
    "HEINZ_CITATION_DOIS",
    "HEINZ_CITATION_TEXT",
    "HUMANN_CITATION_DOIS",
    "HUMANN_CITATION_TEXT",
    "HYBPIPER_CITATION_DOI",
    "HYBPIPER_CITATION_TEXT",
    "HYPHY_ABSREL_CITATION_DOIS",
    "HYPHY_ABSREL_CITATION_TEXT",
    "HYPHY_BGM_CITATION_DOIS",
    "HYPHY_BGM_CITATION_TEXT",
    "HYPHY_BUSTED_CITATION_DOIS",
    "HYPHY_BUSTED_CITATION_TEXT",
    "HYPHY_B_STILL_CITATION_DOIS",
    "HYPHY_B_STILL_CITATION_TEXT",
    "HYPHY_CFEL_CITATION_DOIS",
    "HYPHY_CFEL_CITATION_TEXT",
    "HYPHY_CITATION_DOI",
    "HYPHY_CITATION_TEXT",
    "HYPHY_FADE_CITATION_DOIS",
    "HYPHY_FADE_CITATION_TEXT",
    "HYPHY_FEL_CITATION_DOIS",
    "HYPHY_FEL_CITATION_TEXT",
    "HYPHY_FUBAR_CITATION_DOI",
    "HYPHY_FUBAR_CITATION_DOIS",
    "HYPHY_FUBAR_CITATION_TEXT",
    "HYPHY_GARD_CITATION_DOIS",
    "HYPHY_GARD_CITATION_TEXT",
    "HYPHY_MEME_CITATION_DOIS",
    "HYPHY_MEME_CITATION_TEXT",
    "HYPHY_PRIME_CITATION_DOIS",
    "HYPHY_PRIME_CITATION_TEXT",
    "HYPHY_RELAX_CITATION_DOIS",
    "HYPHY_RELAX_CITATION_TEXT",
    "HYPHY_SLAC_CITATION_DOIS",
    "HYPHY_SLAC_CITATION_TEXT",
    "HYPHY_SM19_CITATION_DOIS",
    "HYPHY_SM19_CITATION_TEXT",
    "HYPHY_STRIKE_AMBIGS_CITATION_DOIS",
    "HYPHY_STRIKE_AMBIGS_CITATION_TEXT",
    "KRAKENTOOLS_CITATION_TEXT",
    "KRAKENTOOLS_DOI",
    "KRONA_CITATION_DOIS",
    "KRONA_CITATION_TEXT",
    "LOCUSPOCUS_CITATION_DOI",
    "LOCUSPOCUS_CITATION_TEXT",
    "MAGICBLAST_CITATION_DOI",
    "MAGICBLAST_CITATION_TEXT",
    "MEGAHIT_CITATION_DOI",
    "MEGAHIT_CITATION_TEXT",
    "METAPHLAN_CITATION_TEXT",
    "METAPHLAN_DOI",
    "MINIASM_CITATION_DOI",
    "MINIASM_CITATION_TEXT",
    "MINIA_CITATION_DOI",
    "MINIA_CITATION_TEXT",
    "MLST_CITATION_TEXT",
    "MLST_CITATION_URL",
    "MOTHUR_CITATION_TEXT",
    "MOTHUR_DOI",
    "NONPAREIL_CITATION_DOI",
    "NONPAREIL_CITATION_TEXT",
    "PARSEVAL_CITATION_DOI",
    "PARSEVAL_CITATION_TEXT",
    "PEAR_CITATION_DOI",
    "PEAR_CITATION_TEXT",
    "PHYML_CITATION_DOI",
    "PHYML_CITATION_TEXT",
    "PLASCLASS_CITATION_DOI",
    "PLASCLASS_CITATION_TEXT",
    "PLASFLOW_CITATION_DOI",
    "PLASFLOW_CITATION_TEXT",
    "PLASMIDFINDER_CITATION_DOI",
    "PLASMIDFINDER_CITATION_TEXT",
    "PLASMIDFINDER_DOCUMENTATION_URL",
    "PRINSEQ_CITATION_DOI",
    "PRINSEQ_CITATION_TEXT",
    "PRODIGAL_CITATION_DOI",
    "PRODIGAL_CITATION_TEXT",
    "Path",
    "QQMAN_CITATION_DOIS",
    "QQMAN_CITATION_TEXT",
    "QUICKTREE_CITATION_DOI",
    "QUICKTREE_CITATION_TEXT",
    "RAPIDNJ_CITATION_DOI",
    "RAPIDNJ_CITATION_TEXT",
    "RAVEN_CITATION_DOI",
    "RAVEN_CITATION_TEXT",
    "RAVEN_DOCUMENTATION_URL",
    "RED_CITATION_DOI",
    "RED_CITATION_TEXT",
    "ROARY_CITATION_DOI",
    "ROARY_CITATION_TEXT",
    "SCIPY_CITATION_DOI",
    "SCIPY_CITATION_TEXT",
    "SEQTK_CITATION_TEXT",
    "SEQTK_CITATION_URL",
    "SHOVILL_CITATION_TEXT",
    "SHOVILL_CITATION_URL",
    "SNIPPY_CITATION_TEXT",
    "SNIPPY_CITATION_URL",
    "STARAMR_CITATION_DOI",
    "STARAMR_CITATION_TEXT",
    "STARAMR_DOCUMENTATION_URL",
    "TAXPASTA_CITATION_TEXT",
    "TAXPASTA_DOI",
    "TRIMN_CITATION_DOIS",
    "TRIMN_CITATION_TEXT",
    "UCSC_GENOME_BROWSER_CITATION_DOI",
    "UCSC_GENOME_BROWSER_CITATION_TEXT",
    "UCSC_UTILS_CITATION_DOI",
    "UCSC_UTILS_CITATION_TEXT",
    "_add_if_value",
    "_add_shell_redirect",
    "_amrfinderplus_out",
    "_as_list",
    "_bandage_prefix",
    "_bcftools_add_af_file",
    "_bcftools_add_apply_filters",
    "_bcftools_add_output_type",
    "_bcftools_add_plugin_separator",
    "_bcftools_add_plugin_vcf_output",
    "_bcftools_add_region_targets",
    "_bcftools_add_restrict",
    "_bcftools_common_output",
    "_bcftools_convert_from_outputs",
    "_bcftools_join_mode",
    "_bcftools_plugin_base_cmd",
    "_bcftools_variant_suffix",
    "_bedtools_add_genome",
    "_bedtools_add_lr_or_b",
    "_bedtools_common_output",
    "_bedtools_ext",
    "_bedtools_strand_flag",
    "_out",
    "_safe_element_identifier",
    "_safe_identifier",
    "_safe_label",
    "_safe_name",
    "_shell_join",
    "annotations",
    "ast",
    "json",
    "re",
    "shlex",
    "sub",
]
