"""Pinned source and packaging evidence for wrapped variant/assembly tools.

The family is intentionally structural: commands are asserted against these
authorities, but no external bioinformatics executable is run by the test suite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolEvidence:
    """One exact upstream or immutable artifact authority for a tool contract."""

    version: str
    package: str | None
    source_url: str
    tag: str | None = None
    commit: str | None = None
    source_sha256: str | None = None
    container: str | None = None
    container_digest: str | None = None
    documentation_url: str | None = None
    source_paths: tuple[str, ...] = ()
    documentation_locator: str | None = None
    exit_semantics: str | None = None


def _github(
    version: str,
    package: str,
    repository: str,
    tag: str,
    commit: str,
    *,
    documentation_url: str | None = None,
) -> ToolEvidence:
    return ToolEvidence(
        version=version,
        package=package,
        source_url=f"https://github.com/{repository}/tree/{commit}",
        tag=tag,
        commit=commit,
        documentation_url=documentation_url,
    )


TOOL_EVIDENCE: dict[str, ToolEvidence] = {
    "lofreq": _github(
        "2.1.5",
        "lofreq",
        "CSB5/lofreq",
        "v2.1.5",
        "8fe42b04dcd9775fb618d8004649421c0632b35c",
        documentation_url="https://csb5.github.io/lofreq/commands/",
    ),
    "freyja": _github(
        "2.0.1",
        "freyja",
        "andersen-lab/Freyja",
        "v2.0.1",
        "275994c0cdfe654baee101160e86046ab7f27bd1",
    ),
    "preseq": _github(
        "3.2.0",
        "preseq",
        "smithlabcode/preseq",
        "v3.2.0",
        "3dc2a7b1a2d3fdadedaeffebdceb29ea88dbd8bb",
        documentation_url="https://preseq.readthedocs.io/",
    ),
    "abyss": _github(
        "2.3.10",
        "abyss",
        "bcgsc/abyss",
        "2.3.10",
        "5dc06d676b4c2bd51a5f7e38f79eed273bb6b9fa",
    ),
    "bayescan": ToolEvidence(
        version="2.1",
        package="bayescan",
        source_url="https://cmpg.unibe.ch/software/BayeScan/files/BayeScan2.1.zip",
        source_sha256="c6bbc52a5a6a30e895951faf2bd6291ca47fdccdc708e693fce02389548d5547",
        documentation_url="https://cmpg.unibe.ch/software/BayeScan/files/BayeScan2.1_manual.pdf",
        source_paths=("source/start.cpp", "source/read_write.cpp"),
        documentation_locator="BayeScan2.1_manual.pdf pages 3-4 and 8",
        exit_semantics=(
            "Input, file-open, and invalid-prior failures return 1. An invocation without "
            "options prints usage and exits 0, so BioNodulo also validates the required input "
            "and requires every planned result artifact to exist."
        ),
    ),
    "bellavista": ToolEvidence(
        version="0.0.2",
        package=None,
        source_url="https://github.com/pkosurilab/BellaVista",
        container="quay.io/bgruening/bellavista:0.0.2-3",
        container_digest="sha256:014ffed486f9b9f4905b3c2022e76e73daba45ef9864f2ae5a6c5fcefa762413",
    ),
    "bellerophon": _github(
        "1.0",
        "bellerophon",
        "davebx/bellerophon",
        "1.0",
        "e1925ddee76890bb2bbe6b7b983986a7c06fc0fa",
    ),
    "chromeister": _github(
        "1.5.a",
        "chromeister",
        "estebanpw/chromeister",
        "1.5.a",
        "0daec07544a211370bf0a9cb8c938ef6a4eb8ac8",
    ),
    "pybigtools": _github(
        "0.2.5",
        "pybigtools",
        "jackh726/bigtools",
        "pybigtools@v0.2.5",
        "4f79f761b87d51f787bb6270f7efff2177460a00",
        documentation_url="https://bigtools.readthedocs.io/",
    ),
    "ampligone": _github(
        "2.0.1",
        "ampligone",
        "RIVM-bioinformatics/AmpliGone",
        "v2.0.1",
        "40261533da2672e3d84e92b505f5601c5b2befdf",
    ),
    "binette": _github(
        "1.2.1",
        "binette",
        "genotoul-bioinfo/Binette",
        "v1.2.1",
        "4f8791e9b411708b0717dbd8e1296a68ac72ae24",
        documentation_url="https://binette.readthedocs.io/",
    ),
    "biapy": ToolEvidence(
        version="3.6.8",
        package=None,
        source_url="https://github.com/BiaPyX/BiaPy/tree/6eed2e1c9fd25774a3635656dc8fa92949e00c08",
        tag="v3.6.8",
        commit="6eed2e1c9fd25774a3635656dc8fa92949e00c08",
        container="biapyx/biapy:3.6.8-11.8",
        container_digest="sha256:6ed6d1c093e4cadfd6ca8c4358c5795f5772d4089ceffd201d766db304ec6bef",
    ),
    "binning_refiner": _github(
        "1.4.3",
        "binning_refiner",
        "songweizhi/Binning_refiner",
        "source-version-1.4.3",
        "2c7a40d642c49367d1e53fe2b668842b21a50e1e",
    ),
    "bioext": _github(
        "0.21.10+galaxy0",
        "python-bioext",
        "veg/BioExt",
        "v0.21.10",
        "09f827669e68f26621a8b438840ffa8f78516b36",
    ),
    "beagle": ToolEvidence(
        version="5.4_29Oct24.c8e",
        package="beagle",
        source_url="https://faculty.washington.edu/browning/beagle/beagle.29Oct24.c8e.jar",
        source_sha256="938f0b1ab12385e0686790cef52d7b9491c96c0c1837af5c0d62c9a6576a8956",
        documentation_url="https://faculty.washington.edu/browning/beagle/beagle_5.4_18Mar22.pdf",
    ),
    "breseq": _github(
        "0.35.5",
        "breseq",
        "barricklab/breseq",
        "v0.35.5",
        "9f368df527615544cff7267fa0ad68f5bad29551",
    ),
    "biscot": _github(
        "2.3.3",
        "biscot",
        "institut-de-genomique/biscot",
        "v2.3.3",
        "937156536d9799e4dc9ab75179e37081518933f3",
    ),
    "bigscape": _github(
        "1.1.9",
        "bigscape",
        "medema-group/BiG-SCAPE",
        "v1.1.9",
        "bb2264c8101f8f7204f2799e41aeef2a2505da72",
    ),
    "compleasm": _github(
        "0.2.6",
        "compleasm",
        "huangnengCSU/compleasm",
        "v0.2.6",
        "740079325e25bf1790f69c42f6fa635343efa0ed",
    ),
    "eastr": _github(
        "2.1.1",
        "eastr-cpp",
        "ishinder/eastr-cpp",
        "v2.1.1",
        "e1a7181b5e9877304e73eb00d19804f199f4142a",
    ),
    "export2graphlan": _github(
        "0.20",
        "export2graphlan",
        "SegataLab/export2graphlan",
        "0.20",
        "a1414fad43dd4ccf5dc9c6a7a6e254d2d85eb787",
    ),
    "graphlan": _github(
        "1.1.3",
        "graphlan",
        "biobakery/graphlan",
        "1.1.3",
        "b68faf302e011e14c430523c6c888f984d81c947",
    ),
    "exonerate": ToolEvidence(
        version="2.4.0",
        package="exonerate",
        source_url="https://ftp.ebi.ac.uk/pub/software/vertebrategenomics/exonerate/exonerate-2.4.0.tar.gz",
        source_sha256="f849261dc7c97ef1f15f222e955b0d3daf994ec13c9db7766f1ac7e77baa4042",
    ),
    "evidencemodeler": _github(
        "2.1.0",
        "evidencemodeler",
        "EVidenceModeler/EVidenceModeler",
        "EVidenceModeler-v2.1.0",
        "8eb4fec90f1c01c8e8f97ebb0e745bd9832634fa",
    ),
    "comebin": _github(
        "1.0.4",
        "comebin",
        "ziyewang/COMEBin",
        "1.0.4",
        "236b986483f5c5aab9535048bc046edb7748be27",
    ),
    "drep": _github(
        "3.6.2",
        "drep",
        "MrOlm/drep",
        "source-version-3.6.2",
        "72520544327b8074c572e306b6ea3a50c5084535",
    ),
    "amber": _github(
        "2.0.7",
        "cami-amber",
        "CAMI-challenge/AMBER",
        "v2.0.7",
        "3d7499349a3d6294fed9640ffc4bf4c73c1c3c8d",
    ),
    "biobox_add_taxid": _github(
        "1.2+galaxy0",
        "biobox_add_taxid",
        "SantaMcCloud/biobox_add_taxid",
        "release-1.2",
        "459ffe175a3d43633b84af0d00105e61c22b193a",
    ),
    "fargene": _github(
        "0.1",
        "fargene",
        "thanhleviet/fargene",
        "v0.1",
        "ab972bffbb2e1a68ab6ab89231c395cac2465576",
    ),
    "metabat2": ToolEvidence(
        version="2.18.23",
        package="metabat2",
        source_url="https://bitbucket.org/berkeleylab/metabat/commits/c869c524d0f131d60a03be64bd26b89738160652",
        tag="2.18_23_gc869c52",
        commit="c869c524d0f131d60a03be64bd26b89738160652",
        source_sha256="ab4a4df1a4af3ce315317318a53b242e4f91d03e9ffe356279a69dd5df4d7e3c",
    ),
    "fastspar": _github(
        "1.0.0",
        "fastspar",
        "scwatts/fastspar",
        "v1.0.0",
        "86ff4bf1a451578694affe61b5c41e015fe77f3c",
    ),
    "ivar": _github(
        "1.4.4",
        "ivar",
        "andersen-lab/ivar",
        "v1.4.4",
        "e666e4c1663ba37a34b9d209b7bd5aea58299121",
    ),
    "gtdbtk": _github(
        "2.7.2",
        "gtdbtk",
        "Ecogenomics/GTDBTk",
        "2.7.2",
        "f17decef1f9d9cf5b4d31fd21f5c9d32d813abdc",
    ),
}


NODE_TO_TOOL = {
    "lofreq_call": "lofreq",
    "lofreq_alnqual": "lofreq",
    "lofreq_indelqual": "lofreq",
    "lofreq_filter": "lofreq",
    "lofreq_viterbi": "lofreq",
    "freyja_variants": "freyja",
    "freyja_demix": "freyja",
    "freyja_boot": "freyja",
    "freyja_aggregate_plot": "freyja",
    "preseq_c_curve": "preseq",
    "preseq_lc_extrap": "preseq",
    "abyss_pe": "abyss",
    "abyss-pe": "abyss",
    "bayescan": "bayescan",
    "BayeScan": "bayescan",
    "bellavista_prepare": "bellavista",
    "bellerophon": "bellerophon",
    "chromeister": "chromeister",
    "bigwig_outlier_bed": "pybigtools",
    "ampligone": "ampligone",
    "binette": "binette",
    "biapy": "biapy",
    "bin_refiner": "binning_refiner",
    "bioext_bam2msa": "bioext",
    "bioext_bealign": "bioext",
    "beagle": "beagle",
    "breseq": "breseq",
    "biscot": "biscot",
    "bigscape": "bigscape",
    "compleasm": "compleasm",
    "eastr": "eastr",
    "export2graphlan": "export2graphlan",
    "graphlan_annotate": "graphlan",
    "graphlan": "graphlan",
    "exonerate": "exonerate",
    "evidencemodeler": "evidencemodeler",
    "comebin": "comebin",
    "comebin_bam": "comebin",
    "drep_compare": "drep",
    "drep_dereplicate": "drep",
    "cami_amber": "amber",
    "cami_amber_add": "amber",
    "cami_amber_convert": "amber",
    "biobox_add_taxid": "biobox_add_taxid",
    "fargene": "fargene",
    "metabat2": "metabat2",
    "metabat2_jgi_summarize_bam_contig_depths": "metabat2",
    "fastspar": "fastspar",
    "fastspar_reduce": "fastspar",
    "fastspar_pvalues": "fastspar",
    "ivar_consensus": "ivar",
    "ivar_filtervariants": "ivar",
    "ivar_trim": "ivar",
    "ivar_removereads": "ivar",
    "ivar_variants": "ivar",
    "gtdbtk_classify_wf": "gtdbtk",
}


def pin_contract(node_class: type[Any]) -> type[Any]:
    """Attach immutable evidence without duplicating it across operation classes."""

    node_id = node_class.__dict__.get("NODE_ID") or node_class.__dict__.get("LEGACY_NODE_ID")
    if not node_id:
        raise RuntimeError(f"{node_class.__name__} does not declare a node identity")
    evidence = TOOL_EVIDENCE[NODE_TO_TOOL[node_id]]
    if node_class.VERSION != evidence.version:
        raise RuntimeError(
            f"{node_id} declares {node_class.VERSION}, expected {evidence.version}"
        )

    node_class.SOURCE_URL = evidence.source_url
    node_class.UPSTREAM_SOURCE = evidence.source_url
    node_class.UPSTREAM_TAG = evidence.tag
    node_class.GIT_COMMIT = evidence.commit
    node_class.SOURCE_SHA256 = evidence.source_sha256
    if evidence.source_paths:
        node_class.SOURCE_PATHS = evidence.source_paths
    if evidence.documentation_locator:
        node_class.DOCUMENTATION_LOCATOR = evidence.documentation_locator
    node_class.CONTAINER_DIGEST = evidence.container_digest
    if evidence.documentation_url:
        node_class.DOCUMENTATION_URL = evidence.documentation_url
    if evidence.package:
        package_version = evidence.version.split("+galaxy", maxsplit=1)[0]
        node_class.BIOCONDA_VERSION = package_version
        node_class.BIOCONDA_CONSTRAINT = f"{evidence.package}={package_version}"
    else:
        node_class.BIOCONDA_VERSION = None
        node_class.BIOCONDA_CONSTRAINT = None
    node_class.SOURCE_AUTHORITIES = {
        "upstream": evidence.source_url,
        "documentation": node_class.DOCUMENTATION_URL,
        "artifact_sha256": evidence.source_sha256,
        "source_paths": evidence.source_paths,
        "documentation_locator": evidence.documentation_locator,
        "container": evidence.container,
        "container_digest": evidence.container_digest,
    }
    node_class.EXIT_SEMANTICS = evidence.exit_semantics or (
        "The execution context must treat any non-zero process exit as failure; planned outputs are "
        "not execution evidence and must exist before a successful result is returned."
    )
    node_class.AUDIT_STATUS = "contract-checked-no-binary-execution"
    return node_class


__all__ = ["NODE_TO_TOOL", "TOOL_EVIDENCE", "ToolEvidence", "pin_contract"]
