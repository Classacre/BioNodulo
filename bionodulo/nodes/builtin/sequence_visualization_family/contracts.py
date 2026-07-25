"""Pinned Tools-IUC evidence for sequence and Circos wrapper contracts."""

from __future__ import annotations

from dataclasses import dataclass

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


CIRCOS_PACKAGES = (
    "circos==0.69.8",
    "bcbiogff==0.6.6",
    "biopython==1.79",
    "pybigwig==0.3.18",
    "circos-tools==0.23",
    "grep==3.10",
    "tar==1.34",
)

NODE_EVIDENCE = {
    "barrnap": WrapperEvidence("tools/barrnap/barrnap.xml", "1.2.2", ("barrnap==0.9",)),
    "fasta-stats": WrapperEvidence(
        "tools/fasta_stats/fasta-stats.xml",
        "2.0",
        ("numpy==1.21.4", "biopython==1.79"),
    ),
    "chopper": WrapperEvidence("tools/chopper/chopper.xml", "0.13.0+galaxy0", ("chopper==0.13.0",)),
    "chopin2": WrapperEvidence(
        "tools/chopin2/chopin2.xml",
        "1.0.9.post1+galaxy0",
        ("chopin2==1.0.9.post1",),
    ),
    "cite_seq_count": WrapperEvidence(
        "tools/cite_seq_count/cite_seq_count.xml",
        "1.4.4+galaxy0",
        (
            "cite-seq-count==1.4.4",
            "python==3.7.12",
            "umi_tools==1.0.0",
            "python-levenshtein==0.20.7",
            "levenshtein==0.20.7",
            "pandas==0.25.3",
            "bzip2==1.0.8",
            "expat==2.5.0",
            "multiprocess==0.70.14",
            "numpy==1.21.6",
            "pysam==0.16",
            "scipy==1.7.3",
        ),
    ),
    "cialign": WrapperEvidence("tools/cialign/cialign.xml", "1.1.4+galaxy1", ("cialign==1.1.4",)),
    "chromap": WrapperEvidence("tools/chromap/chromap.xml", "0.3.2+galaxy0", ("chromap==0.3.2",)),
    "circexplorer2": WrapperEvidence(
        "tools/circexplorer2/circexplorer2.xml",
        "2.3.8+galaxy0",
        ("circexplorer2==2.3.8",),
    ),
    "circos": WrapperEvidence("tools/circos/circos.xml", "0.69.8+galaxy12", CIRCOS_PACKAGES),
    "circos_resample": WrapperEvidence("tools/circos/resample.xml", "0.69.8+galaxy12", CIRCOS_PACKAGES),
    "circos_gc_skew": WrapperEvidence("tools/circos/gc_skew.xml", "0.69.8+galaxy12", CIRCOS_PACKAGES),
    "circos_wiggle_to_scatter": WrapperEvidence(
        "tools/circos/scatter-from-wiggle.xml",
        "0.69.8+galaxy12",
        CIRCOS_PACKAGES,
    ),
    "circos_interval_to_text": WrapperEvidence(
        "tools/circos/text-from-interval.xml",
        "0.69.8+galaxy12",
        CIRCOS_PACKAGES,
    ),
    "circos_interval_to_tile": WrapperEvidence(
        "tools/circos/tiles-from-interval.xml",
        "0.69.8+galaxy12",
        CIRCOS_PACKAGES,
    ),
    "circos_aln_to_links": WrapperEvidence(
        "tools/circos/alignments-to-links.xml",
        "0.69.8+galaxy12",
        CIRCOS_PACKAGES,
    ),
    "circos_binlinks": WrapperEvidence("tools/circos/binlinks.xml", "0.69.8+galaxy12", CIRCOS_PACKAGES),
    "circos_bundlelinks": WrapperEvidence(
        "tools/circos/bundlelinks.xml",
        "0.69.8+galaxy12",
        CIRCOS_PACKAGES,
    ),
    "circos_wiggle_to_stacked": WrapperEvidence(
        "tools/circos/stack-histogram.xml",
        "0.69.8+galaxy12",
        CIRCOS_PACKAGES,
    ),
    "circos_tableviewer": WrapperEvidence(
        "tools/circos/tableviewer.xml",
        "0.69.8+galaxy12",
        CIRCOS_PACKAGES,
    ),
    "filtlong": WrapperEvidence("tools/filtlong/filtlong.xml", "0.3.1+galaxy0", ("filtlong==0.3.1",)),
}


class ToolsIUCCommandContract(CommandNode):
    """Attach exact wrapper evidence when a focused owner declares its stable ID."""

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
