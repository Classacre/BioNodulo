"""Pinned authorities for the remaining focused annotation nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar


@dataclass(frozen=True)
class AnnotationEvidence:
    version: str
    source_url: str
    source_ref: str
    git_commit: str
    package_constraints: tuple[str, ...]
    executable: str
    documentation_url: str
    wrapper_version: str = ""


NODE_EVIDENCE = {
    "bakta": AnnotationEvidence(
        "1.9.4",
        "https://github.com/oschwengers/bakta/tree/v1.9.4",
        "v1.9.4",
        "a7ac1c8641cf8a11888b0295c30f0b2e0b8f34fa",
        ("bakta==1.9.4",),
        "bakta",
        "https://github.com/oschwengers/bakta/blob/v1.9.4/README.md",
        "1.9.4+galaxy1",
    ),
    "eggnog_mapper": AnnotationEvidence(
        "2.1.14",
        "https://github.com/eggnogdb/eggnog-mapper/tree/v2.1.14",
        "v2.1.14",
        "6ec647a3f7dd2ceb9d7b0b4ce0a357acd2524f3e",
        ("eggnog-mapper==2.1.14",),
        "emapper.py",
        "https://github.com/eggnogdb/eggnog-mapper/wiki",
    ),
    "vep_annotate": AnnotationEvidence(
        "113.4",
        "https://github.com/Ensembl/ensembl-vep/tree/release/113.4",
        "release/113.4",
        "a6786e4357f442a81624f58d9e79f343909d717f",
        ("ensembl-vep==113.4",),
        "vep",
        "https://www.ensembl.org/info/docs/tools/vep/script/vep_options.html",
    ),
    "annovar": AnnotationEvidence(
        "2020-06-08",
        "https://annovar.openbioinformatics.org/en/latest/user-guide/download/",
        "ANNOVAR 2020-06-08 licensed distribution",
        "",
        (),
        "table_annovar.pl",
        "https://annovar.openbioinformatics.org/en/latest/user-guide/startup/",
    ),
    "funcotate_table": AnnotationEvidence(
        "4.6.2.0",
        "https://github.com/broadinstitute/gatk/tree/4.6.2.0",
        "4.6.2.0 Funcotator",
        "76edc75c26504da94bbaee66584e107e76ee15de",
        ("gatk4==4.6.2.0",),
        "gatk",
        "https://gatk.broadinstitute.org/hc/en-us/articles/360037224432-Funcotator",
    ),
    "funcotator": AnnotationEvidence(
        "4.6.2.0",
        "https://github.com/broadinstitute/gatk/tree/4.6.2.0",
        "4.6.2.0 Funcotator",
        "76edc75c26504da94bbaee66584e107e76ee15de",
        ("gatk4==4.6.2.0",),
        "gatk",
        "https://gatk.broadinstitute.org/hc/en-us/articles/360037224432-Funcotator",
    ),
    "bcftools_annotate": AnnotationEvidence(
        "1.24",
        "https://github.com/samtools/bcftools/tree/fb9f0f783e0f67d734f6fa7fe4df9d230522f196",
        "1.24 annotate",
        "fb9f0f783e0f67d734f6fa7fe4df9d230522f196",
        ("bcftools==1.24", "htslib==1.23.1"),
        "bcftools",
        "https://samtools.github.io/bcftools/bcftools.html#annotate",
        "1.22+galaxy0",
    ),
    "annotate_vcf": AnnotationEvidence(
        "0.3.9",
        "https://github.com/brentp/vcfanno/tree/v0.3.9",
        "v0.3.9 with BCFtools 1.24 output/index handling",
        "d409a9b73dc6ef5b3be45cb84604889eac0d52c5",
        ("vcfanno==0.3.9", "bcftools==1.24", "htslib==1.23.1"),
        "vcfanno",
        "https://github.com/brentp/vcfanno/blob/v0.3.9/README.md",
    ),
    "interproscan": AnnotationEvidence(
        "5.59-91.0",
        "https://github.com/ebi-pf-team/interproscan/tree/5.59-91.0",
        "5.59-91.0 reproducible Bioconda contract",
        "e6a3ca6f4262ac1a542123ef1a278c189da2e26f",
        ("interproscan==5.59_91.0",),
        "interproscan.sh",
        "https://interproscan-docs.readthedocs.io/en/v5/HowToRun.html",
        "5.59-91.0+galaxy3",
    ),
}


NodeT = TypeVar("NodeT", bound=type)


def attach_evidence(node_class: NodeT) -> NodeT:
    """Attach one exact source record without changing the inherited contract."""
    evidence = NODE_EVIDENCE[node_class.NODE_ID]
    node_class.VERSION = evidence.version
    node_class.SOURCE_URL = evidence.source_url
    node_class.SOURCE_REF = evidence.source_ref
    node_class.GIT_COMMIT = evidence.git_commit
    node_class.PACKAGE_CONSTRAINTS = evidence.package_constraints
    node_class.PACKAGE_CONSTRAINT = "; ".join(evidence.package_constraints)
    node_class.DOCUMENTATION_URL = evidence.documentation_url
    node_class.EXIT_SEMANTICS = "Validation failures and non-zero external commands fail the node."
    node_class.AUDIT_STATUS = "contract-checked-no-external-execution"
    if evidence.wrapper_version:
        node_class.GALAXY_WRAPPER_VERSION = evidence.wrapper_version
    return node_class
