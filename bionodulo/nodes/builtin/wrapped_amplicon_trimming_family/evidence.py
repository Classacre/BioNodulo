"""Pinned Tools-IUC evidence for amplicon, trimming, and utility wrappers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TOOLS_IUC_COMMIT = "8eb66da1f6f16fde92688ee6c500d2bcdc924a47"
TOOLS_IUC_BASE = f"https://github.com/galaxyproject/tools-iuc/blob/{TOOLS_IUC_COMMIT}"


@dataclass(frozen=True)
class WrapperEvidence:
    """Exact wrapper revision and resolved package requirements."""

    version: str
    wrapper_path: str
    package_constraints: tuple[str, ...]
    wrapper_id: str | None = None
    error_detection: str = "exit_code"

    @property
    def source_url(self) -> str:
        return f"{TOOLS_IUC_BASE}/{self.wrapper_path}"


@dataclass(frozen=True)
class AssetEvidence:
    """Pinned helper copied from the wrapper repository."""

    wrapper_path: str
    sha256: str

    @property
    def source_url(self) -> str:
        return f"{TOOLS_IUC_BASE}/{self.wrapper_path}"


AMPVIS2_PACKAGES = (
    "r-ampvis2=2.8.11",
    "r-readr=2.1.5",
    "bioconductor-phyloseq=1.50.0",
)
ALDEX2_PACKAGES = (
    "bioconductor-aldex2=1.26.0",
    "r-data.table=1.14.2",
    "r-optparse=1.7.1",
    "r-qgraph=1.9.2",
)
ANCOMBC_PACKAGES = (
    "bioconductor-ancombc=1.4.0",
    "r-data.table=1.14.2",
    "r-optparse=1.7.1",
)
ANGSD_PACKAGES = ("angsd=0.940", "samtools=1.23", "python=3.11")
VSEARCH_PACKAGES = ("vsearch=2.8.3",)


NODE_EVIDENCE: dict[str, WrapperEvidence] = {
    "ampvis2_alpha_diversity": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/alpha_diversity.xml", AMPVIS2_PACKAGES),
    "ampvis2_boxplot": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/boxplot.xml", AMPVIS2_PACKAGES),
    "ampvis2_core": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/core.xml", AMPVIS2_PACKAGES),
    "ampvis2_export_fasta": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/export_fasta.xml", AMPVIS2_PACKAGES),
    "ampvis2_export_otu": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/export_otu.xml", AMPVIS2_PACKAGES),
    "ampvis2_frequency": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/frequency.xml", AMPVIS2_PACKAGES),
    "ampvis2_heatmap": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/heatmap.xml", AMPVIS2_PACKAGES),
    "ampvis2_load": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/load.xml", AMPVIS2_PACKAGES),
    "ampvis2_merge_ampvis2": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/merge_ampvis2.xml", AMPVIS2_PACKAGES),
    "ampvis2_mergereplicates": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/mergereplicates.xml", AMPVIS2_PACKAGES),
    "ampvis2_octave": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/octave.xml", AMPVIS2_PACKAGES),
    "ampvis2_ordinate": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/ordinate.xml", AMPVIS2_PACKAGES),
    "ampvis2_otu_network": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/otu_network.xml", AMPVIS2_PACKAGES),
    "ampvis2_rankabundance": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/rankabundance.xml", AMPVIS2_PACKAGES),
    "ampvis2_rarecurve": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/rarecurve.xml", AMPVIS2_PACKAGES),
    "ampvis2_setmetadata": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/setmetadata.xml", AMPVIS2_PACKAGES),
    "ampvis2_subset_samples": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/subset_samples.xml", AMPVIS2_PACKAGES),
    "ampvis2_subset_taxa": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/subset_taxa.xml", AMPVIS2_PACKAGES),
    "ampvis2_timeseries": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/timeseries.xml", AMPVIS2_PACKAGES),
    "ampvis2_venn": WrapperEvidence("2.8.11+galaxy2", "tools/ampvis2/venn.xml", AMPVIS2_PACKAGES),
    "aldex2": WrapperEvidence("1.26.0+galaxy0", "tools/aldex2/aldex2.xml", ALDEX2_PACKAGES),
    "ancombc": WrapperEvidence("1.4.0+galaxy0", "tools/ancombc/ancombc.xml", ANCOMBC_PACKAGES),
    "angsd": WrapperEvidence("0.940+galaxy0", "tools/angsd/angsd.xml", ANGSD_PACKAGES),
    "angsd_contamination": WrapperEvidence("0.940+galaxy0", "tools/angsd/angsd_contamination.xml", ANGSD_PACKAGES),
    "miniasm": WrapperEvidence("0.3_r179+galaxy1", "tools/miniasm/miniasm.xml", ("miniasm=0.3_r179",)),
    "megahit_contig2fastg": WrapperEvidence("1.1.3+galaxy1", "tools/megahit_contig2fastg/megahit_contig2fastg.xml", ("megahit=1.1.3",)),
    "prinseq": WrapperEvidence("0.20.4+galaxy2", "tools/prinseq/prinseq.xml", ("prinseq=0.20.4",), error_detection="exit_code+stdio"),
    "adapter_removal": WrapperEvidence("2.3.4+galaxy0", "tools/adapter_removal/adapter_removal.xml", ("adapterremoval=2.3.4",)),
    "trimn": WrapperEvidence("1.0", "tools/TrimNs/TrimNs.xml", ("trimns_vgp=1.0",), wrapper_id="trimns"),
    "trimns": WrapperEvidence("0.1.0", "tools/TrimNs/TrimNs.xml", ("trimns_vgp=1.0",)),
    "vsearch_search": WrapperEvidence("2.8.3.1", "tools/vsearch/search.xml", VSEARCH_PACKAGES, error_detection="stdio"),
    "vsearch_cluster": WrapperEvidence("2.8.3.0", "tools/vsearch/clustering.xml", VSEARCH_PACKAGES, wrapper_id="vsearch_clustering", error_detection="stdio"),
    "vsearch_dereplication": WrapperEvidence("2.8.3.0", "tools/vsearch/dereplication.xml", VSEARCH_PACKAGES, error_detection="stdio"),
    "vsearch_masking": WrapperEvidence("2.8.3.0", "tools/vsearch/masking.xml", VSEARCH_PACKAGES, error_detection="stdio"),
    "vsearch_shuffling": WrapperEvidence("2.8.3.0", "tools/vsearch/shuffling.xml", VSEARCH_PACKAGES, error_detection="stdio"),
    "vsearch_sorting": WrapperEvidence("2.8.3.0", "tools/vsearch/sorting.xml", VSEARCH_PACKAGES, error_detection="stdio"),
    "vsearch_alignment": WrapperEvidence("2.8.3.0", "tools/vsearch/alignment.xml", VSEARCH_PACKAGES, error_detection="stdio"),
    "vsearch_chimera_detection": WrapperEvidence("2.8.3.0", "tools/vsearch/chimera.xml", VSEARCH_PACKAGES, error_detection="stdio"),
}


ASSET_EVIDENCE = {
    "aldex2.R": AssetEvidence("tools/aldex2/aldex2.R", "0d894c18a6b22005610ad2c93bd1c6201695dacabd05f5845b2f7b1ac29b8e12"),
    "ancombc.R": AssetEvidence("tools/ancombc/ancombc.R", "7e6ae4427a3f31fda476222854623ed8d5049cf1519612d77944c809d6f90454"),
    "print_x_contamination.py": AssetEvidence("tools/angsd/print_x_contamination.py", "82b8493b34496acfd9067d228fd8d4d0e48114fc1f1977ee393caa29da04d131"),
}


def pin_contract(node_class: type[Any]) -> type[Any]:
    """Attach immutable wrapper evidence and fail import on drift."""

    evidence = NODE_EVIDENCE[node_class.NODE_ID]
    if node_class.VERSION != evidence.version:
        raise RuntimeError(f"{node_class.NODE_ID} declares {node_class.VERSION}, expected {evidence.version}")
    node_class.WRAPPER_GIT_COMMIT = TOOLS_IUC_COMMIT
    node_class.WRAPPER_SOURCE = evidence.wrapper_path
    node_class.WRAPPER_TOOL_ID = evidence.wrapper_id or node_class.NODE_ID
    node_class.SOURCE_URL = evidence.source_url
    node_class.UPSTREAM_SOURCE = evidence.wrapper_path
    node_class.PACKAGE_CONSTRAINTS = evidence.package_constraints
    node_class.WRAPPER_ERROR_DETECTION = evidence.error_detection
    node_class.SOURCE_AUTHORITIES = {
        "galaxy_wrapper": evidence.source_url,
        "upstream_documentation": node_class.DOCUMENTATION_URL,
    }
    if evidence.error_detection == "stdio":
        node_class.FAILURE_PATTERNS = ("Error:", "Exception:")
        failure = "The wrapper rejects non-zero exits and output containing Error: or Exception:."
    elif evidence.error_detection == "exit_code+stdio":
        node_class.STDERR_FATAL_PATTERNS = ("ERROR",)
        node_class.STDERR_WARNING_PATTERNS = ("WARNING",)
        failure = "The wrapper rejects non-zero exits and fatal ERROR messages on stderr."
    else:
        failure = "The wrapper explicitly uses detect_errors=exit_code."
    node_class.EXIT_SEMANTICS = f"{failure} Planned outputs are not execution evidence."
    node_class.AUDIT_STATUS = "contract-checked-no-external-execution"
    return node_class


__all__ = [
    "ASSET_EVIDENCE",
    "NODE_EVIDENCE",
    "TOOLS_IUC_COMMIT",
    "WrapperEvidence",
    "pin_contract",
]
