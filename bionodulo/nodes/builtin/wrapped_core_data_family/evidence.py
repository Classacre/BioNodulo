"""Pinned wrapper and package evidence for focused core-data nodes."""

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

    @property
    def source_url(self) -> str:
        return f"{TOOLS_IUC_BASE}/{self.wrapper_path}"


ANNDATA_PACKAGES = (
    "anndata=0.11.4",
    "scanpy=1.11.5",
    "loompy=3.0.8",
    "pandas=2.3.3",
)
ANNOTATION_DB_PACKAGES = tuple(
    f"bioconductor-org.{organism}.db=3.18.0"
    for organism in ("hs.eg", "mm.eg", "dm.eg", "dr.eg", "rn.eg", "at.tair", "gg.eg", "bt.eg")
)
BAREDSC_PACKAGES = ("baredsc=1.1.3", "gzip=1.13")


NODE_EVIDENCE: dict[str, WrapperEvidence] = {
    "anndata_export": WrapperEvidence("0.11.4+galaxy3", "tools/anndata/export.xml", ANNDATA_PACKAGES),
    "anndata_import": WrapperEvidence("0.11.4+galaxy3", "tools/anndata/import.xml", ANNDATA_PACKAGES),
    "anndata_inspect": WrapperEvidence("0.11.4+galaxy3", "tools/anndata/inspect.xml", ANNDATA_PACKAGES),
    "anndata_manipulate": WrapperEvidence("0.11.4+galaxy3", "tools/anndata/manipulate.xml", ANNDATA_PACKAGES),
    "modify_loom": WrapperEvidence("0.11.4+galaxy3", "tools/anndata/modify_loom.xml", ANNDATA_PACKAGES),
    "anndata2ri": WrapperEvidence(
        "1.3.2+galaxy1",
        "tools/anndata2ri/anndata2ri.xml",
        ("anndata2ri=1.3.2", "anndata=0.10.9", "bioconductor-singlecellexperiment=1.24.0"),
    ),
    "celltypist": WrapperEvidence("1.7.1+galaxy1", "tools/celltypist/celltypist.xml", ("celltypist=1.7.1",)),
    "cemitool": WrapperEvidence(
        "1.34.0+galaxy0",
        "tools/cemitool/cemitool.xml",
        ("bioconductor-cemitool=1.34.0", "r-ggplot2=4.0.2", "r-getopt=1.20.4"),
    ),
    "charts": WrapperEvidence(
        "1.0.1",
        "tools/charts/charts.xml",
        ("r-getopt=1.20.0", "r-matrix=1.2-12"),
    ),
    "annotatemyids": WrapperEvidence(
        "3.18.0+galaxy0",
        "tools/annotatemyids/annotateMyIDs.xml",
        ANNOTATION_DB_PACKAGES,
    ),
    "argnorm": WrapperEvidence("1.0.0+galaxy0", "tools/argnorm/argnorm.xml", ("argnorm=1.0.0",)),
    "autobigs-cli": WrapperEvidence(
        "0.6.2+galaxy0",
        "tools/autobigs/autobigs-cli.xml",
        ("autobigs-cli=0.6.2",),
    ),
    "mlst": WrapperEvidence("2.22.0", "tools/mlst/mlst.xml", ("mlst=2.22.0",)),
    "mlst_list": WrapperEvidence("2.22.0", "tools/mlst/mlst_list.xml", ("mlst=2.22.0",)),
    "seqsero2": WrapperEvidence("1.3.2+galaxy0", "tools/seqsero2/seqsero2.xml", ("seqsero2=1.3.2",)),
    "b2btools_single_sequence": WrapperEvidence(
        "3.0.5+galaxy0",
        "tools/b2btools/b2btools_single_sequence.xml",
        ("b2btools=3.0.5",),
    ),
    "bp_genbank2gff3": WrapperEvidence(
        "1.1",
        "tools/bioperl/bp_genbank2gff3.xml",
        ("perl-bioperl=1.7.2",),
    ),
    "basil": WrapperEvidence("1.2.0+galaxy2", "tools/basil/basil.xml", ("anise_basil=1.2.0",)),
    "bbgtobigwig": WrapperEvidence(
        "0.1",
        "tools/bbgbigwig/bam_bed_gff_to_bigwig.xml",
        ("ucsc-bedgraphtobigwig=455", "bedtools=2.31.1", "coreutils=9.5", "python=3.12.3"),
    ),
    "baredsc_1d": WrapperEvidence("1.1.3+galaxy0", "tools/baredsc/baredsc_1d.xml", BAREDSC_PACKAGES),
    "baredsc_2d": WrapperEvidence("1.1.3+galaxy0", "tools/baredsc/baredsc_2d.xml", BAREDSC_PACKAGES),
    "baredsc_combine_1d": WrapperEvidence(
        "1.1.3+galaxy0",
        "tools/baredsc/baredsc_combine_1d.xml",
        BAREDSC_PACKAGES,
    ),
    "baredsc_combine_2d": WrapperEvidence(
        "1.1.3+galaxy0",
        "tools/baredsc/baredsc_combine_2d.xml",
        BAREDSC_PACKAGES,
    ),
    "bax2bam": WrapperEvidence("0.0.11+galaxy0", "tools/bax2bam/bax2bam.xml", ("bax2bam=0.0.11",)),
    "berokka": WrapperEvidence("0.2.3", "tools/berokka/berokka.xml", ("berokka=0.2.3",)),
    "bam_to_scidx": WrapperEvidence(
        "1.0.1",
        "tools/bam_to_scidx/bam_to_scidx.xml",
        ("openjdk=8.0.112",),
    ),
    "fasta_regex_finder": WrapperEvidence(
        "0.1.0",
        "tools/bioinformatics_cafe/fastaregexfinder.xml",
        ("python=3.8",),
    ),
    "cd_hit": WrapperEvidence("4.8.1+galaxy0", "tools/cdhit/cd_hit.xml", ("cd-hit=4.8.1",)),
    "clustering_from_distmat": WrapperEvidence(
        "1.1.2+galaxy0",
        "tools/clustering_from_distmat/clustering_from_distmat.xml",
        ("python=3.12", "scipy=1.14.0", "pandas=2.3.3"),
    ),
    "add_input_name_as_column": WrapperEvidence(
        "0.3.0",
        "tools/add_input_name_as_column/add_input_name_as_column.xml",
        ("python=3.13.7",),
    ),
    "addName": WrapperEvidence(
        "0.3.0",
        "tools/add_input_name_as_column/add_input_name_as_column.xml",
        ("python=3.13.7",),
    ),
    "column_remove_by_header": WrapperEvidence(
        "1.0",
        "tools/column_remove_by_header/column_remove_by_header.xml",
        ("python=3.10.4",),
    ),
    "column_order_header_sort": WrapperEvidence(
        "0.0.1",
        "tools/column_order_header_sort/column_order_header_sort.xml",
        ("python=3.6.1", "gawk=4.1.3"),
    ),
    "datamash_ops": WrapperEvidence(
        "1.9+galaxy0",
        "tools/datamash/datamash-ops.xml",
        ("datamash=1.9",),
    ),
    "datamash_transpose": WrapperEvidence(
        "1.9+galaxy1",
        "tools/datamash/datamash-transpose.xml",
        ("datamash=1.9", "coreutils=9.5"),
    ),
    "datamash_reverse": WrapperEvidence(
        "1.9+galaxy0",
        "tools/datamash/datamash-reverse.xml",
        ("datamash=1.9",),
    ),
    "falco": WrapperEvidence("1.3.2+galaxy0", "tools/falco/falco.xml", ("falco=1.3.2",)),
}


def pin_contract(node_class: type[Any]) -> type[Any]:
    """Attach exact wrapper provenance and fail import on version drift."""

    node_id = getattr(node_class, "NODE_ID", "") or node_class.LEGACY_NODE_ID
    evidence = NODE_EVIDENCE[node_id]
    if node_class.VERSION != evidence.version:
        raise RuntimeError(
            f"{node_id} declares {node_class.VERSION}, expected {evidence.version}"
        )
    node_class.WRAPPER_GIT_COMMIT = TOOLS_IUC_COMMIT
    node_class.WRAPPER_SOURCE = evidence.wrapper_path
    node_class.SOURCE_URL = evidence.source_url
    node_class.UPSTREAM_SOURCE = evidence.wrapper_path
    node_class.PACKAGE_CONSTRAINTS = evidence.package_constraints
    node_class.SOURCE_AUTHORITIES = {
        "galaxy_wrapper": evidence.source_url,
        "upstream_documentation": node_class.DOCUMENTATION_URL,
    }
    node_class.EXIT_SEMANTICS = (
        "The pinned Galaxy wrapper treats the documented non-zero process exit as failure. "
        "Planned outputs are structural declarations and must not be treated as execution evidence."
    )
    node_class.AUDIT_STATUS = "contract-checked-no-external-execution"
    return node_class


__all__ = [
    "NODE_EVIDENCE",
    "TOOLS_IUC_COMMIT",
    "WrapperEvidence",
    "pin_contract",
]
