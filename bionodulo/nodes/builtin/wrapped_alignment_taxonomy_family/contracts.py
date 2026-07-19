"""Pinned Tools-IUC evidence for alignment, utility, BCtools, and CAT contracts."""

from __future__ import annotations

from dataclasses import dataclass

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode


TOOLS_IUC_REPO_URL = "https://github.com/galaxyproject/tools-iuc"
TOOLS_IUC_GIT_COMMIT = "8eb66da1f6f16fde92688ee6c500d2bcdc924a47"


@dataclass(frozen=True)
class WrapperEvidence:
    wrapper_path: str
    wrapper_version: str
    package_constraints: tuple[str, ...]
    commit: str = TOOLS_IUC_GIT_COMMIT

    @property
    def source_url(self) -> str:
        return f"{TOOLS_IUC_REPO_URL}/blob/{self.commit}/{self.wrapper_path}"


CROSSMAP_PACKAGES = ("crossmap==0.7.3",)
BCTOOLS_PACKAGES = ("bctools==0.2.2",)
CAT_PACKAGES = ("cat==5.2.3",)

NODE_EVIDENCE = {
    "som.py": WrapperEvidence("tools/happy/hap.py.xml", "0.3.15+galaxy1", ("hap.py==0.3.15",)),
    "bwameth": WrapperEvidence("tools/bwameth/bwameth.xml", "0.2.9+galaxy0", ("bwameth==0.2.9",)),
    "crossmap_bed": WrapperEvidence(
        "tools/crossmap/crossmap_bed.xml",
        "0.7.3+galaxy0",
        CROSSMAP_PACKAGES,
    ),
    "crossmap_bam": WrapperEvidence(
        "tools/crossmap/crossmap_bam.xml",
        "0.7.3+galaxy0",
        CROSSMAP_PACKAGES,
    ),
    "crossmap_bw": WrapperEvidence(
        "tools/crossmap/crossmap_bigwig.xml",
        "0.7.3+galaxy0",
        CROSSMAP_PACKAGES,
    ),
    "crossmap_gff": WrapperEvidence(
        "tools/crossmap/crossmap_gff.xml",
        "0.7.3+galaxy0",
        CROSSMAP_PACKAGES,
    ),
    "crossmap_region": WrapperEvidence(
        "tools/crossmap/crossmap_region.xml",
        "0.7.3+galaxy0",
        CROSSMAP_PACKAGES,
    ),
    "crossmap_vcf": WrapperEvidence(
        "tools/crossmap/crossmap_vcf.xml",
        "0.7.3+galaxy0",
        CROSSMAP_PACKAGES,
    ),
    "crossmap_wig": WrapperEvidence(
        "tools/crossmap/crossmap_wig.xml",
        "0.7.3+galaxy0",
        CROSSMAP_PACKAGES,
    ),
    "Add_a_column1": WrapperEvidence(
        "tools/column_maker/column_maker.xml",
        "2.1+galaxy0",
        ("python==3.12", "numpy==2.1.0"),
    ),
    "calculate_numeric_param": WrapperEvidence(
        "tools/calculate_numeric_param/calculate_numeric_param.xml",
        "0.1.0",
        (),
    ),
    "compose_text_param": WrapperEvidence(
        "tools/compose_text_param/compose_text_param.xml",
        "0.1.1",
        (),
    ),
    "compress_file": WrapperEvidence(
        "tools/compress_file/compress_file.xml",
        "0.1.0",
        ("gzip==1.11",),
    ),
    "collection_column_join": WrapperEvidence(
        "tools/collection_column_join/collection_column_join.xml",
        "0.0.3",
        ("coreutils==8.25",),
    ),
    "collection_element_identifiers": WrapperEvidence(
        "tools/collection_element_identifiers/collection_element_identifiers.xml",
        "0.0.3",
        (),
    ),
    "calculate_contrast_threshold": WrapperEvidence(
        "tools/calculate_contrast_threshold/calculate_contrast_threshold.xml",
        "1.0.0",
        ("numpy==1.15.4", "python==3.7.4"),
    ),
    "CoverageReport2": WrapperEvidence(
        "tools/coverage_report/CoverageReport.xml",
        "0.0.5+galaxy0",
        (
            "perl-number-format==1.76",
            "r-base==4.2.2",
            "bedtools==2.17.0",
            "samtools==0.1.18",
            "tectonic==0.12.0",
            "libcurl==7.87.0",
            "openssl==1.1.1w",
        ),
    ),
    "Extract genomic DNA 1": WrapperEvidence(
        "tools/extract_genomic_dna/extract_genomic_dna.xml",
        "3.0.3+galaxy3",
        ("bx-python==0.7.1", "six==1.13.0", "ucsc-fatotwobit==377"),
    ),
    "barcode_splitter": WrapperEvidence(
        "tools/barcode_splitter/barcode_splitter.xml",
        "0.18.4.0",
        ("barcode_splitter==0.18.4",),
    ),
    "bctools_convert_to_binary_barcode": WrapperEvidence(
        "tools/bctools/convert_bc_to_binary_RY.xml",
        "0.2.2+galaxy2",
        BCTOOLS_PACKAGES,
    ),
    "bctools_extract_crosslinked_nucleotides": WrapperEvidence(
        "tools/bctools/coords2clnt.xml",
        "0.2.2+galaxy2",
        BCTOOLS_PACKAGES,
    ),
    "bctools_extract_alignment_ends": WrapperEvidence(
        "tools/bctools/extract_aln_ends.xml",
        "0.2.2+galaxy2",
        BCTOOLS_PACKAGES,
    ),
    "bctools_extract_barcodes": WrapperEvidence(
        "tools/bctools/extract_bcs.xml",
        "0.2.2+galaxy2",
        BCTOOLS_PACKAGES,
    ),
    "bctools_merge_pcr_duplicates": WrapperEvidence(
        "tools/bctools/merge_pcr_duplicates.xml",
        "0.2.2+galaxy2",
        (*BCTOOLS_PACKAGES, "coreutils==8.31"),
    ),
    "bctools_remove_tail": WrapperEvidence(
        "tools/bctools/remove_tail.xml",
        "0.2.2+galaxy2",
        BCTOOLS_PACKAGES,
    ),
    "bctools_remove_spurious_events": WrapperEvidence(
        "tools/bctools/rm_spurious_events.xml",
        "0.2.2+galaxy2",
        (*BCTOOLS_PACKAGES, "coreutils==8.31"),
    ),
    "blastxml_to_gapped_gff3": WrapperEvidence(
        "tools/blastxml_to_gapped_gff3/blastxml_to_gapped_gff3.xml",
        "1.1",
        ("bcbiogff==0.6.4",),
    ),
    "cat_prepare": WrapperEvidence("tools/cat/cat_prepare.xml", "5.2.3+galaxy0", CAT_PACKAGES),
    "cat_contigs": WrapperEvidence("tools/cat/cat_contigs.xml", "5.2.3+galaxy0", CAT_PACKAGES),
    "cat_bins": WrapperEvidence("tools/cat/cat_bins.xml", "5.2.3+galaxy0", CAT_PACKAGES),
    "cat_add_names": WrapperEvidence("tools/cat/cat_add_names.xml", "5.2.3+galaxy0", CAT_PACKAGES),
    "cat_summarise": WrapperEvidence("tools/cat/cat_summarise.xml", "5.2.3+galaxy0", CAT_PACKAGES),
    "cawlign": WrapperEvidence("tools/cawlign/cawlign.xml", "0.1.15+galaxy0", ("cawlign==0.1.15",)),
}


class _ToolsIUCEvidenceMixin:
    GIT_URL = TOOLS_IUC_REPO_URL
    GALAXY_WRAPPER_GIT_URL = TOOLS_IUC_REPO_URL
    EXIT_SEMANTICS = "Galaxy wrapper validation or external command failure must produce a non-zero result."
    AUDIT_STATUS = "contract-checked-no-external-execution"

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        node_id = cls.__dict__.get("NODE_ID", "")
        if not node_id:
            return
        evidence = NODE_EVIDENCE[node_id]
        cls.GIT_COMMIT = evidence.commit
        cls.GALAXY_WRAPPER_GIT_COMMIT = evidence.commit
        cls.GALAXY_WRAPPER_PATH = evidence.wrapper_path
        cls.GALAXY_WRAPPER_VERSION = evidence.wrapper_version
        cls.PACKAGE_CONSTRAINTS = evidence.package_constraints
        cls.PACKAGE_CONSTRAINT = "; ".join(evidence.package_constraints)
        cls.SOURCE_URL = evidence.source_url
        cls.GALAXY_WRAPPER_SOURCE_URL = evidence.source_url
        cls.VERSION = evidence.wrapper_version


class ToolsIUCCommandContract(_ToolsIUCEvidenceMixin, CommandNode):
    """Evidence-backed command contract with no discoverable stable ID."""


class ToolsIUCBaseContract(_ToolsIUCEvidenceMixin, BaseNode):
    """Evidence-backed expression contract with no discoverable stable ID."""
