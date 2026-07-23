"""Pinned Tools-IUC evidence for taxonomy, BIOM, HUMAnN, and trace contracts."""

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


BIOM_PACKAGES = ("biom-format==2.1.17",)
KRAKENTOOLS_PACKAGES = ("krakentools==1.2.1",)
HUMANN_PACKAGES = ("humann==3.9",)
TRACY_PACKAGES = ("tracy==0.7.8",)

NODE_EVIDENCE = {
    "est_abundance": WrapperEvidence(
        "tools/bracken/est-abundance.xml",
        "3.1+galaxy0",
        ("bracken==3.1",),
    ),
    "magicblast": WrapperEvidence(
        "tools/blast/magicblast.xml",
        "1.7.0+galaxy2",
        ("magicblast==1.7.0", "samtools==1.18"),
    ),
    "bmtagger": WrapperEvidence(
        "tools/bmtagger/bmtagger.xml",
        "3.101+galaxy0",
        ("bmtagger==3.101",),
    ),
    "biom_summarize_table": WrapperEvidence(
        "tools/biom_format/biom_summarize_table.xml",
        "2.1.17+galaxy0",
        BIOM_PACKAGES,
    ),
    "biom_normalize_table": WrapperEvidence(
        "tools/biom_format/biom_normalize_table.xml",
        "2.1.17+galaxy0",
        BIOM_PACKAGES,
    ),
    "biom_subset_table": WrapperEvidence(
        "tools/biom_format/biom_subset_table.xml",
        "2.1.17+galaxy0",
        BIOM_PACKAGES,
    ),
    "biom_from_uc": WrapperEvidence(
        "tools/biom_format/biom_from_uc.xml",
        "2.1.17+galaxy0",
        BIOM_PACKAGES,
    ),
    "biom_add_metadata": WrapperEvidence(
        "tools/biom_format/biom_add_metadata.xml",
        "2.1.17+galaxy0",
        BIOM_PACKAGES,
    ),
    "biom_convert": WrapperEvidence(
        "tools/biom_format/biom_convert.xml",
        "2.1.17+galaxy0",
        BIOM_PACKAGES,
    ),
    "krakentools_combine_kreports": WrapperEvidence(
        "tools/krakentools/combine_kreports.xml",
        "1.2.1+galaxy2",
        KRAKENTOOLS_PACKAGES,
    ),
    "krakentools_alpha_diversity": WrapperEvidence(
        "tools/krakentools/alpha_diversity.xml",
        "1.2.1+galaxy0",
        KRAKENTOOLS_PACKAGES,
    ),
    "krakentools_beta_diversity": WrapperEvidence(
        "tools/krakentools/beta_diversity.xml",
        "1.2.1+galaxy0",
        KRAKENTOOLS_PACKAGES,
    ),
    "krakentools_kreport2krona": WrapperEvidence(
        "tools/krakentools/kreport2krona.xml",
        "1.2.1+galaxy0",
        KRAKENTOOLS_PACKAGES,
    ),
    "taxonomy_krona_chart": WrapperEvidence(
        "tools/taxonomy_krona_chart/taxonomy_krona_chart.xml",
        "2.7.1+galaxy0",
        ("krona==2.7.1",),
    ),
    "mothur_taxonomy_to_krona": WrapperEvidence(
        "tools/mothur/taxonomy-to-krona.xml",
        "1.0",
        (),
    ),
    "krakentools_kreport2mpa": WrapperEvidence(
        "tools/krakentools/kreport2mpa.xml",
        "1.2.1+galaxy0",
        KRAKENTOOLS_PACKAGES,
    ),
    "krakentools_extract_kraken_reads": WrapperEvidence(
        "tools/krakentools/extract_kraken_reads.xml",
        "1.2.1+galaxy0",
        (*KRAKENTOOLS_PACKAGES, "gzip==1.14"),
    ),
    "recentrifuge": WrapperEvidence(
        "tools/recentrifuge/recentrifuge.xml",
        "1.16.1+galaxy0",
        ("recentrifuge==1.16.1",),
    ),
    "taxpasta": WrapperEvidence(
        "tools/taxpasta/taxpasta.xml",
        "0.7.0+galaxy0",
        ("taxpasta==0.7.0",),
    ),
    "taxonkit_name2taxid": WrapperEvidence(
        "tools/taxonkit/taxonkit_name2taxid.xml",
        "0.20.0+galaxy0",
        ("taxonkit==0.20.0",),
    ),
    "taxonkit_profile2cami": WrapperEvidence(
        "tools/taxonkit/taxonkit_profile2cami.xml",
        "0.20.0+galaxy0",
        ("taxonkit==0.20.0",),
    ),
    "tracy_basecall": WrapperEvidence(
        "tools/tracy/tracy_basecall.xml",
        "0.7.8+galaxy0",
        TRACY_PACKAGES,
    ),
    "tracy_align": WrapperEvidence(
        "tools/tracy/tracy_align.xml",
        "0.7.8+galaxy0",
        TRACY_PACKAGES,
    ),
    "tracy_assemble": WrapperEvidence(
        "tools/tracy/tracy_assemble.xml",
        "0.7.8+galaxy0",
        TRACY_PACKAGES,
    ),
    "tracy_decompose": WrapperEvidence(
        "tools/tracy/tracy_decompose.xml",
        "0.7.8+galaxy0",
        TRACY_PACKAGES,
    ),
    "humann_join_tables": WrapperEvidence(
        "tools/humann/humann_join_tables.xml",
        "3.9+galaxy0",
        HUMANN_PACKAGES,
    ),
    "humann_renorm_table": WrapperEvidence(
        "tools/humann/humann_renorm_table.xml",
        "3.9+galaxy0",
        HUMANN_PACKAGES,
    ),
    "humann_split_table": WrapperEvidence(
        "tools/humann/humann_split_table.xml",
        "3.9+galaxy0",
        HUMANN_PACKAGES,
    ),
    "humann_split_stratified_table": WrapperEvidence(
        "tools/humann/humann_split_stratified_table.xml",
        "3.9+galaxy0",
        HUMANN_PACKAGES,
    ),
    "humann_reduce_table": WrapperEvidence(
        "tools/humann/humann_reduce_table.xml",
        "3.9+galaxy0",
        HUMANN_PACKAGES,
    ),
    "humann_regroup_table": WrapperEvidence(
        "tools/humann/humann_regroup_table.xml",
        "3.9+galaxy0",
        HUMANN_PACKAGES,
    ),
    "humann_rename_table": WrapperEvidence(
        "tools/humann/humann_rename_table.xml",
        "3.9+galaxy0",
        HUMANN_PACKAGES,
    ),
    "humann_unpack_pathways": WrapperEvidence(
        "tools/humann/humann_unpack_pathways.xml",
        "3.9+galaxy0",
        HUMANN_PACKAGES,
    ),
    "humann_barplot": WrapperEvidence(
        "tools/humann/humann_barplot.xml",
        "3.9+galaxy0",
        HUMANN_PACKAGES,
    ),
    "hybpiper": WrapperEvidence(
        "tools/hybpiper/hybpiper.xml",
        "2.1.6+galaxy0",
        ("hybpiper==2.1.6",),
    ),
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
