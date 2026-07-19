"""Pinned release and source authorities for focused variant utility nodes."""

from __future__ import annotations

from dataclasses import dataclass

from bionodulo.nodes.command_node import CommandNode


@dataclass(frozen=True)
class VariantEvidence:
    version: str
    source_url: str
    source_ref: str
    package_constraints: tuple[str, ...]
    git_commit: str = ""


NODE_EVIDENCE = {
    "sniffles2": VariantEvidence(
        "2.5.3",
        "https://github.com/fritzsedlazeck/Sniffles/tree/v2.5.3",
        "v2.5.3",
        ("sniffles==2.5.3",),
    ),
    "sniffles2_call": VariantEvidence(
        "2.5.3",
        "https://github.com/fritzsedlazeck/Sniffles/tree/v2.5.3",
        "v2.5.3",
        ("sniffles==2.5.3",),
    ),
    "pbsv": VariantEvidence(
        "2.10.0",
        "https://github.com/PacificBiosciences/pbsv/tree/v2.10.0",
        "v2.10.0",
        ("pbsv==2.10.0",),
    ),
    "sv_stats": VariantEvidence(
        "1.0",
        "https://pysam.readthedocs.io/en/latest/api.html#pysam.VariantFile",
        "BioNodulo Python contract using pysam VariantFile",
        ("pysam>=0.22", "matplotlib>=3.8"),
    ),
    "vcf_comparison": VariantEvidence(
        "3.12.1",
        "https://realtimegenomics.github.io/rtg-tools/rtg_command_reference.html#vcfeval",
        "RTG Tools 3.12.1 vcfeval",
        ("rtg-tools==3.12.1", "matplotlib>=3.8"),
    ),
    "strelka2": VariantEvidence(
        "2.9.10",
        "https://github.com/Illumina/strelka/tree/v2.9.10",
        "v2.9.10",
        ("strelka==2.9.10",),
    ),
    "gridss": VariantEvidence(
        "2.13.2",
        "https://github.com/PapenfussLab/gridss/tree/v2.13.2",
        "v2.13.2",
        ("gridss==2.13.2",),
    ),
    "melt_mobile_elements": VariantEvidence(
        "2",
        "https://melt.igs.umaryland.edu/",
        "MELT 2 supplied-jar contract",
        ("openjdk>=17",),
    ),
    "survivor_merge": VariantEvidence(
        "1.0.7",
        "https://github.com/fritzsedlazeck/SURVIVOR/tree/v1.0.7",
        "v1.0.7",
        ("survivor==1.0.7",),
    ),
    "cutesv": VariantEvidence(
        "2.1.1",
        "https://github.com/tjiangHIT/cuteSV/tree/v2.1.1",
        "v2.1.1",
        ("cute-sv==2.1.1",),
    ),
    "svim": VariantEvidence(
        "2.0.0",
        "https://github.com/eldariont/svim/tree/v2.0.0",
        "v2.0.0",
        ("svim==2.0.0",),
    ),
    "smoove": VariantEvidence(
        "0.2.8",
        "https://github.com/brentp/smoove/tree/v0.2.8",
        "v0.2.8",
        ("smoove==0.2.8", "lumpy-sv>=0.3.1", "svtyper>=0.7.1"),
    ),
    "cnvkit_batch": VariantEvidence(
        "0.9.12",
        "https://github.com/etal/cnvkit/tree/dd834b0b5b482f174d1dcb7c35b358087309c6b3",
        "dd834b0b5b482f174d1dcb7c35b358087309c6b3",
        ("cnvkit==0.9.12",),
        git_commit="dd834b0b5b482f174d1dcb7c35b358087309c6b3",
    ),
    "cnvkit_call": VariantEvidence(
        "0.9.12",
        "https://github.com/etal/cnvkit/tree/dd834b0b5b482f174d1dcb7c35b358087309c6b3",
        "dd834b0b5b482f174d1dcb7c35b358087309c6b3",
        ("cnvkit==0.9.12",),
        git_commit="dd834b0b5b482f174d1dcb7c35b358087309c6b3",
    ),
    "cnvkit_plot": VariantEvidence(
        "0.9.12",
        "https://github.com/etal/cnvkit/tree/dd834b0b5b482f174d1dcb7c35b358087309c6b3",
        "dd834b0b5b482f174d1dcb7c35b358087309c6b3",
        ("cnvkit==0.9.12",),
        git_commit="dd834b0b5b482f174d1dcb7c35b358087309c6b3",
    ),
    "cnvnator": VariantEvidence(
        "0.4.1",
        "https://github.com/abyzovlab/CNVnator/tree/v0.4.1",
        "v0.4.1",
        ("cnvnator==0.4.1",),
    ),
    "control_freec": VariantEvidence(
        "11.6",
        "https://github.com/BoevaLab/FREEC/tree/v11.6",
        "v11.6",
        ("control-freec==11.6",),
    ),
    "bcftools_index": VariantEvidence(
        "1.24",
        "https://github.com/samtools/bcftools/tree/fb9f0f783e0f67d734f6fa7fe4df9d230522f196",
        "1.24",
        ("bcftools==1.24",),
        git_commit="fb9f0f783e0f67d734f6fa7fe4df9d230522f196",
    ),
    "platypus": VariantEvidence(
        "0.8.1",
        "https://github.com/andyrimmer/Platypus/tree/v0.8.1",
        "v0.8.1",
        ("platypus-variant==0.8.1",),
    ),
    "deepvariant": VariantEvidence(
        "1.6.0",
        "https://github.com/google/deepvariant/tree/v1.6.0",
        "v1.6.0",
        ("deepvariant==1.6.0",),
    ),
    "clair3": VariantEvidence(
        "2.0.1",
        "https://github.com/HKU-BAL/Clair3/tree/v2.0.1",
        "v2.0.1",
        ("clair3==2.0.1",),
    ),
    "vcftools_filter": VariantEvidence(
        "0.1.17",
        "https://github.com/vcftools/vcftools/tree/v0.1.17",
        "v0.1.17",
        ("vcftools==0.1.17",),
    ),
}


class VariantEvidenceContract(CommandNode):
    """Attach exact release evidence when a focused owner declares its ID."""

    EXIT_SEMANTICS = "Input validation or a non-zero external command result fails the node."
    AUDIT_STATUS = "contract-checked-no-external-execution"

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        node_id = cls.__dict__.get("NODE_ID", "")
        if not node_id:
            return
        evidence = NODE_EVIDENCE[node_id]
        cls.VERSION = evidence.version
        cls.SOURCE_URL = evidence.source_url
        cls.SOURCE_REF = evidence.source_ref
        cls.PACKAGE_CONSTRAINTS = evidence.package_constraints
        cls.PACKAGE_CONSTRAINT = "; ".join(evidence.package_constraints)
        if evidence.git_commit:
            cls.GIT_COMMIT = evidence.git_commit
