"""Pinned Tools-IUC evidence for HyPhy and metagenomics wrapper contracts."""

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
    exit_semantics: str
    upstream_source_url: str = ""
    upstream_ref: str = ""
    upstream_commit: str = ""
    commit: str = TOOLS_IUC_GIT_COMMIT

    @property
    def source_url(self) -> str:
        return f"{TOOLS_IUC_REPO_URL}/blob/{self.commit}/{self.wrapper_path}"


EXIT_CODE = "Galaxy detect_errors=exit_code; a non-zero command exit fails the job."
AGGRESSIVE = "Galaxy detect_errors=aggressive; non-zero exits and recognized fatal stderr fail the job."
GALAXY_DEFAULT = "No explicit detect_errors or stdio rule; Galaxy default error handling applies."

HYPHY_PACKAGES = ("hyphy==2.5.96",)
METAPHLAN_PACKAGES = ("metaphlan==4.2.4",)
MASH_PACKAGES = ("mash==2.3",)


def _hyphy(path: str) -> WrapperEvidence:
    return WrapperEvidence(
        f"tools/hyphy/{path}.xml",
        "2.5.96+galaxy0",
        HYPHY_PACKAGES,
        EXIT_CODE,
        "https://github.com/veg/hyphy",
        "2.5.96",
        "c2daaafe3f372e8e0f44e275db61f37c74a1516d",
    )


NODE_EVIDENCE = {
    "hyphy_absrel": _hyphy("hyphy_absrel"),
    "hyphy_annotate": _hyphy("hyphy_annotate"),
    "hyphy_b_still": _hyphy("hyphy_b_still"),
    "hyphy_bgm": _hyphy("hyphy_bgm"),
    "hyphy_fade": _hyphy("hyphy_fade"),
    "hyphy_fel": _hyphy("hyphy_fel"),
    "hyphy_fubar": _hyphy("hyphy_fubar"),
    "hyphy_gard": _hyphy("hyphy_gard"),
    "hyphy_infer_stasis_clusters": WrapperEvidence(
        "tools/hyphy/hyphy_infer_stasis_clusters.xml",
        "2.5.96+galaxy0",
        ("numpy==1.26.4", "scipy==1.13.1", "python==3.12"),
        EXIT_CODE,
        "https://github.com/veg/hyphy",
        "2.5.96",
        "c2daaafe3f372e8e0f44e275db61f37c74a1516d",
    ),
    "hyphy_meme": _hyphy("hyphy_meme"),
    "hyphy_prime": _hyphy("hyphy_prime"),
    "hyphy_relax": _hyphy("hyphy_relax"),
    "hyphy_slac": _hyphy("hyphy_slac"),
    "hyphy_sm19": _hyphy("hyphy_sm19"),
    "hyphy_strike_ambigs": _hyphy("hyphy_strike_ambigs"),
    "hyphy_busted": _hyphy("hyphy_busted"),
    "hyphy_cfel": _hyphy("hyphy_cfel"),
    "hyphy_conv": _hyphy("hyphy_conv"),
    "hyphy_cln": _hyphy("hyphy_cln"),
    "merge_metaphlan_tables": WrapperEvidence(
        "tools/metaphlan/merge_metaphlan_tables.xml",
        "4.2.4+galaxy0",
        METAPHLAN_PACKAGES,
        AGGRESSIVE,
    ),
    "extract_metaphlan_database": WrapperEvidence(
        "tools/metaphlan/extract_metaphlan_database.xml",
        "4.2.4+galaxy0",
        METAPHLAN_PACKAGES,
        AGGRESSIVE,
    ),
    "customize_metaphlan_database": WrapperEvidence(
        "tools/metaphlan/customize_metaphlan_database.xml",
        "4.2.4+galaxy0",
        (*METAPHLAN_PACKAGES, "seqtk==1.4"),
        AGGRESSIVE,
    ),
    "mash_dist": WrapperEvidence("tools/mash/mash_dist.xml", "2.3+galaxy0", MASH_PACKAGES, EXIT_CODE),
    "mash_sketch": WrapperEvidence("tools/mash/mash_sketch.xml", "2.3+galaxy3", MASH_PACKAGES, EXIT_CODE),
    "mash_paste": WrapperEvidence("tools/mash/mash_paste.xml", "2.3+galaxy0", MASH_PACKAGES, EXIT_CODE),
    "mash_screen": WrapperEvidence("tools/mash/mash_screen.xml", "2.3+galaxy4", MASH_PACKAGES, EXIT_CODE),
    "mashmap": WrapperEvidence("tools/mashmap/mashmap.xml", "3.1.3+galaxy0", ("mashmap==3.1.3",), GALAXY_DEFAULT),
    "fastani": WrapperEvidence(
        "tools/fastani/fastani.xml",
        "1.3",
        ("fastani==1.3",),
        EXIT_CODE,
        "https://github.com/ParBLiSS/FastANI",
        "v1.3",
        "6fabd06571fff2a21a08d00292baa6906fddbd7f",
    ),
}


class ToolsIUCCommandContract(CommandNode):
    """Attach exact wrapper evidence when a focused owner declares its stable ID."""

    GIT_URL = TOOLS_IUC_REPO_URL
    GALAXY_WRAPPER_GIT_URL = TOOLS_IUC_REPO_URL
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
        cls.EXIT_SEMANTICS = evidence.exit_semantics
        cls.UPSTREAM_SOURCE_URL = evidence.upstream_source_url
        cls.UPSTREAM_SOURCE_REF = evidence.upstream_ref
        cls.UPSTREAM_GIT_COMMIT = evidence.upstream_commit
        cls.SOURCE_URL = evidence.source_url
        cls.GALAXY_WRAPPER_SOURCE_URL = evidence.source_url
