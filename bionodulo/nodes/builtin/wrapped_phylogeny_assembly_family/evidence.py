"""Pinned Tools-IUC evidence for phylogeny and assembly wrapper contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TOOLS_IUC_COMMIT = "8eb66da1f6f16fde92688ee6c500d2bcdc924a47"
TOOLS_IUC_BASE = f"https://github.com/galaxyproject/tools-iuc/blob/{TOOLS_IUC_COMMIT}"


@dataclass(frozen=True)
class WrapperEvidence:
    """Exact Galaxy wrapper revision and resolved package requirements."""

    version: str
    wrapper_path: str
    package_constraints: tuple[str, ...]
    wrapper_id: str | None = None

    @property
    def source_url(self) -> str:
        return f"{TOOLS_IUC_BASE}/{self.wrapper_path}"


AMAS_PACKAGES = ("amas=1.0",)
ART_PACKAGES = ("art=2016.06.05",)
BBTOOLS_PACKAGES = ("bbmap=39.08", "samtools=1.20")
ALPHAGENOME_PACKAGES = ("alphagenome=0.6.1", "cyvcf2=0.31.4", "pandas=2.3.3")


NODE_EVIDENCE: dict[str, WrapperEvidence] = {
    "assembly_stats": WrapperEvidence(
        "17.02+galaxy0",
        "tools/assembly-stats/assembly-stats.xml",
        ("rjchallis-assembly-stats=17.02",),
    ),
    "amas_summary": WrapperEvidence("1.0+galaxy0", "tools/amas/amas_summary.xml", AMAS_PACKAGES),
    "amas_concat": WrapperEvidence("1.0+galaxy0", "tools/amas/amas_concat.xml", AMAS_PACKAGES),
    "amas_split": WrapperEvidence("1.0+galaxy0", "tools/amas/amas_split.xml", AMAS_PACKAGES),
    "amas_remove": WrapperEvidence("1.0+galaxy0", "tools/amas/amas_remove.xml", AMAS_PACKAGES),
    "amas_replicate": WrapperEvidence("1.0+galaxy0", "tools/amas/amas_replicate.xml", AMAS_PACKAGES),
    "clustalw": WrapperEvidence("2.1+galaxy1", "tools/clustalw/rgClustalw.xml", ("clustalw=2.1",)),
    "quicktree": WrapperEvidence(
        "2.5+galaxy1",
        "tools/quicktree/quicktree.xml",
        ("quicktree=2.5", "hmmer=3.4"),
    ),
    "rapidnj": WrapperEvidence("2.3.2", "tools/rapidnj/rapidnj.xml", ("rapidnj=v2.3.2",)),
    "phyml": WrapperEvidence(
        "3.3.20220408+galaxy0",
        "tools/phyml/phyml.xml",
        ("phyml=3.3.20220408",),
    ),
    "flash": WrapperEvidence("1.2.11.4", "tools/flash/flash.xml", ("flash=1.2.11",)),
    "iuc_pear": WrapperEvidence("0.9.6.4", "tools/pear/pear.xml", ("pear=0.9.6",)),
    "fraggenescan": WrapperEvidence(
        "1.30.0",
        "tools/fraggenescan/fraggenescan.xml",
        ("fraggenescan=1.30",),
    ),
    "prodigal": WrapperEvidence(
        "2.6.3+galaxy0",
        "tools/prodigal/prodigal.xml",
        ("prodigal=2.6.3",),
    ),
    "eukrep": WrapperEvidence("0.6.7+galaxy0", "tools/eukrep/eukrep.xml", ("eukrep=0.6.7",)),
    "gamma": WrapperEvidence("2.2+galaxy0", "tools/gamma/gamma.xml", ("GAMMA=2.2",)),
    "gamma_s": WrapperEvidence("2.2+galaxy0", "tools/gamma/gamma-s.xml", ("GAMMA=2.2",)),
    "red": WrapperEvidence("2018.09.10+galaxy1", "tools/red/red.xml", ("red=2018.09.10",)),
    "abritamr": WrapperEvidence(
        "1.3.0+galaxy0",
        "tools/abritamr/abritamr.xml",
        ("abritamr=1.3.0",),
    ),
    "nonpareil": WrapperEvidence(
        "3.5.5+galaxy1",
        "tools/nonpareil/nonpareil.xml",
        ("nonpareil=3.5.5",),
    ),
    "bbtools_bbduk": WrapperEvidence("39.08+galaxy4", "tools/bbtools/bbduk.xml", BBTOOLS_PACKAGES),
    "bbtools_bbmerge": WrapperEvidence("39.08+galaxy4", "tools/bbtools/bbmerge.xml", BBTOOLS_PACKAGES),
    "bbtools_bbnorm": WrapperEvidence("39.08+galaxy4", "tools/bbtools/bbnorm.xml", BBTOOLS_PACKAGES),
    "bbtools_tadpole": WrapperEvidence("39.08+galaxy4", "tools/bbtools/tadpole.xml", BBTOOLS_PACKAGES),
    "bbtools_callvariants": WrapperEvidence(
        "39.08+galaxy4",
        "tools/bbtools/callvariants.xml",
        BBTOOLS_PACKAGES,
    ),
    "bbtools_bbmap": WrapperEvidence("39.08+galaxy4", "tools/bbtools/bbmap.xml", BBTOOLS_PACKAGES),
    "plasclass": WrapperEvidence(
        "0.1.1+galaxy0",
        "tools/plasclass/plasclass.xml",
        ("plasclass=0.1.1",),
    ),
    "plasflow": WrapperEvidence(
        "1.1.0+galaxy0",
        "tools/plasflow/plasflow.xml",
        ("plasflow=1.1.0",),
        wrapper_id="PlasFlow",
    ),
    "minia": WrapperEvidence("3.2.6", "tools/minia/minia.xml", ("minia=3.2.6",)),
    "genomescope": WrapperEvidence(
        "2.1.0+galaxy0",
        "tools/genomescope/genomescope.xml",
        ("genomescope2=2.1.0",),
    ),
    "art_illumina": WrapperEvidence(
        "2016.06.05+galaxy2016.06.05",
        "tools/art/art_illumina.xml",
        ART_PACKAGES,
    ),
    "art_454": WrapperEvidence(
        "2016.06.05+galaxy2016.06.05",
        "tools/art/art_454.xml",
        ART_PACKAGES,
    ),
    "art_solid": WrapperEvidence(
        "2016.06.05+galaxy2016.06.05",
        "tools/art/art_solid.xml",
        ART_PACKAGES,
    ),
    "amplican": WrapperEvidence(
        "1.14.0+galaxy1",
        "tools/amplican/amplican.xml",
        ("bioconductor-amplican=1.14.0",),
    ),
    "allegro": WrapperEvidence("3+galaxy0", "tools/allegro/allegro.xml", ("allegro=3",)),
    "alphagenome_interval_predictor": WrapperEvidence(
        "0.6.1+galaxy1",
        "tools/alphagenome/alphagenome_interval_predictor.xml",
        ALPHAGENOME_PACKAGES,
    ),
    "alphagenome_ism_scanner": WrapperEvidence(
        "0.6.1+galaxy1",
        "tools/alphagenome/alphagenome_ism_scanner.xml",
        ALPHAGENOME_PACKAGES,
    ),
    "alphagenome_sequence_predictor": WrapperEvidence(
        "0.6.1+galaxy1",
        "tools/alphagenome/alphagenome_sequence_predictor.xml",
        ALPHAGENOME_PACKAGES,
    ),
    "alphagenome_variant_effect": WrapperEvidence(
        "0.6.1+galaxy1",
        "tools/alphagenome/alphagenome_variant_effect.xml",
        ALPHAGENOME_PACKAGES,
    ),
    "alphagenome_variant_scorer": WrapperEvidence(
        "0.6.1+galaxy1",
        "tools/alphagenome/alphagenome_variant_scorer.xml",
        ALPHAGENOME_PACKAGES,
    ),
}

ERROR_DETECTION_BY_ID = {node_id: "exit_code" for node_id in NODE_EVIDENCE}
for node_id in {
    "flash",
    "iuc_pear",
    "fraggenescan",
    "bbtools_bbduk",
    "bbtools_bbmerge",
    "bbtools_bbnorm",
    "bbtools_tadpole",
    "bbtools_callvariants",
    "bbtools_bbmap",
}:
    ERROR_DETECTION_BY_ID[node_id] = "aggressive"
for node_id in {"phyml", "art_illumina", "art_454", "art_solid", "allegro"}:
    ERROR_DETECTION_BY_ID[node_id] = "galaxy-default"

ALPHAGENOME_CREDENTIAL = "alphagenome:api_key -> ALPHAGENOME_API_KEY"
ALPHAGENOME_IDS = {
    "alphagenome_interval_predictor",
    "alphagenome_ism_scanner",
    "alphagenome_sequence_predictor",
    "alphagenome_variant_effect",
    "alphagenome_variant_scorer",
}


def pin_contract(node_class: type[Any]) -> type[Any]:
    """Attach immutable wrapper evidence and fail import on version drift."""

    evidence = NODE_EVIDENCE[node_class.NODE_ID]
    if node_class.VERSION != evidence.version:
        raise RuntimeError(
            f"{node_class.NODE_ID} declares {node_class.VERSION}, expected {evidence.version}"
        )
    node_class.WRAPPER_GIT_COMMIT = TOOLS_IUC_COMMIT
    node_class.WRAPPER_SOURCE = evidence.wrapper_path
    node_class.WRAPPER_TOOL_ID = evidence.wrapper_id or node_class.NODE_ID
    node_class.SOURCE_URL = evidence.source_url
    node_class.UPSTREAM_SOURCE = evidence.wrapper_path
    node_class.PACKAGE_CONSTRAINTS = evidence.package_constraints
    node_class.WRAPPER_ERROR_DETECTION = ERROR_DETECTION_BY_ID[node_class.NODE_ID]
    node_class.CREDENTIAL_REQUIREMENTS = (
        (ALPHAGENOME_CREDENTIAL,) if node_class.NODE_ID in ALPHAGENOME_IDS else ()
    )
    node_class.SOURCE_AUTHORITIES = {
        "galaxy_wrapper": evidence.source_url,
        "upstream_documentation": node_class.DOCUMENTATION_URL,
    }
    if node_class.NODE_ID in ALPHAGENOME_IDS:
        node_class.SOURCE_AUTHORITIES["galaxy_credentials"] = (
            f"{TOOLS_IUC_BASE}/tools/alphagenome/macros.xml"
        )
    detection = node_class.WRAPPER_ERROR_DETECTION
    if detection == "exit_code":
        failure = "The wrapper explicitly uses detect_errors=exit_code; a non-zero process exit fails the job."
    elif detection == "aggressive":
        failure = "The wrapper explicitly uses Galaxy aggressive error detection for process and stderr failures."
    else:
        failure = "The wrapper does not override Galaxy's profile-specific default command error detection."
    node_class.EXIT_SEMANTICS = (
        f"{failure} Conditional planned outputs are structural declarations, not execution evidence."
    )
    node_class.AUDIT_STATUS = "contract-checked-no-external-execution"
    return node_class


__all__ = [
    "ALPHAGENOME_CREDENTIAL",
    "ERROR_DETECTION_BY_ID",
    "NODE_EVIDENCE",
    "TOOLS_IUC_COMMIT",
    "WrapperEvidence",
    "pin_contract",
]
