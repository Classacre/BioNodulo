"""Pinned source and package authorities for pangenomics operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


TOOLS_IUC_COMMIT = "8eb66da1f6f16fde92688ee6c500d2bcdc924a47"
VG_COMMIT = "1859bc3225bc32c64ebdff2530c68857b11beae7"
VG_FASTAHACK_COMMIT = "75f12d25df9416b9d49b84c70dcc58406afce11a"
VG_TABIXPP_COMMIT = "ae5cdf846af85bd1d0e310c05e5c67b037f51a25"
VG_VCFLIB_COMMIT = "0b01ccf90905bb664e4242967c01adcb24299111"
VCFLIB_COMMIT = "fa6831e9c83059f1c2dc71218bb5b390c5fe917a"
PANACUS_COMMIT = "f70f563c62029589bb79fd2c85821fcfa2ef33f9"
PANAROO_COMMIT = "a79bb11f1d61f58cd367e1be52f2e0120b8934cb"
MINIGRAPH_COMMIT = "7e3e65c5e55a10e2968f32cef5c04eee9330521b"
CACTUS_COMMIT = "3147387e9ca6ad9710b3cdebf029c5c2574e8367"


@dataclass(frozen=True)
class PangenomicsEvidence:
    version: str
    git_url: str
    commit: str
    source_paths: tuple[str, ...]
    documentation_url: str
    package_constraints: tuple[str, ...]
    source_ref: str
    secondary_source_urls: tuple[str, ...] = ()
    wrapper_version: str = ""
    wrapper_commit: str = ""
    wrapper_path: str = ""

    @property
    def source_urls(self) -> tuple[str, ...]:
        return tuple(f"{self.git_url}/blob/{self.commit}/{path}" for path in self.source_paths)


VG_EVIDENCE = {
    "vg_construct": ("src/subcommand/construct_main.cpp",),
    "vg_index": (
        "src/subcommand/autoindex_main.cpp",
        "src/subcommand/convert_main.cpp",
        "src/index_registry.cpp",
    ),
    "vg_map": (
        "src/subcommand/giraffe_main.cpp",
        "src/subcommand/map_main.cpp",
        "scripts/giraffe-wrangler.sh",
    ),
    "vg_call": ("src/subcommand/pack_main.cpp", "src/subcommand/call_main.cpp"),
    "pangenome_sv": ("src/subcommand/convert_main.cpp", "src/subcommand/deconstruct_main.cpp"),
}


NODE_EVIDENCE: dict[str, PangenomicsEvidence] = {
    node_id: PangenomicsEvidence(
        version="1.63.1",
        git_url="https://github.com/vgteam/vg",
        commit=VG_COMMIT,
        source_paths=paths,
        documentation_url=f"https://github.com/vgteam/vg/tree/{VG_COMMIT}",
        package_constraints=("vg==1.63.1",),
        source_ref="v1.63.1",
    )
    for node_id, paths in VG_EVIDENCE.items()
}

NODE_EVIDENCE.update(
    {
        "vg_construct": PangenomicsEvidence(
            version="1.63.1",
            git_url="https://github.com/vgteam/vg",
            commit=VG_COMMIT,
            source_paths=("src/subcommand/construct_main.cpp", "src/constructor.cpp"),
            documentation_url=f"https://github.com/vgteam/vg/tree/{VG_COMMIT}",
            package_constraints=("vg==1.63.1",),
            source_ref="v1.63.1",
            secondary_source_urls=(
                f"https://github.com/vgteam/fastahack/blob/{VG_FASTAHACK_COMMIT}/Fasta.cpp",
                f"https://github.com/vcflib/vcflib/blob/{VG_VCFLIB_COMMIT}/src/Variant.h",
                f"https://github.com/ekg/tabixpp/blob/{VG_TABIXPP_COMMIT}/tabix.cpp",
            ),
        ),
        "pangenome_sv": PangenomicsEvidence(
            version="1.63.1",
            git_url="https://github.com/vgteam/vg",
            commit=VG_COMMIT,
            source_paths=VG_EVIDENCE["pangenome_sv"],
            documentation_url=f"https://github.com/vgteam/vg/tree/{VG_COMMIT}",
            package_constraints=("vg==1.63.1", "bcftools==1.24", "htslib==1.23.1"),
            source_ref="v1.63.1",
            secondary_source_urls=(
                "https://github.com/samtools/bcftools/blob/fb9f0f783e0f67d734f6fa7fe4df9d230522f196/filter.c",
                "https://github.com/samtools/htslib/blob/d1a2a873552a4fb8c30b3a77620c5f8bef7a7143/bgzip.c",
                "https://github.com/samtools/htslib/blob/d1a2a873552a4fb8c30b3a77620c5f8bef7a7143/tabix.c",
            ),
        ),
        "vcf_decompose": PangenomicsEvidence(
            version="1.0.9",
            git_url="https://github.com/vcflib/vcflib",
            commit=VCFLIB_COMMIT,
            source_paths=("src/vcfwave.cpp", "src/vcfallelicprimitives.cpp"),
            documentation_url=(
                f"https://github.com/vcflib/vcflib/blob/{VCFLIB_COMMIT}/doc/vcfwave.md"
            ),
            package_constraints=("vcflib==1.0.9", "htslib==1.23.1"),
            source_ref="v1.0.9",
            secondary_source_urls=(
                "https://github.com/samtools/htslib/blob/d1a2a873552a4fb8c30b3a77620c5f8bef7a7143/bgzip.c",
                "https://github.com/samtools/htslib/blob/d1a2a873552a4fb8c30b3a77620c5f8bef7a7143/tabix.c",
            ),
        ),
        "pangenome_stats": PangenomicsEvidence(
            version="0.3.3",
            git_url="https://github.com/marschall-lab/panacus",
            commit=PANACUS_COMMIT,
            source_paths=("src/commands/histgrowth.rs", "src/lib.rs"),
            documentation_url=(
                f"https://github.com/marschall-lab/panacus/blob/{PANACUS_COMMIT}/README.md"
            ),
            package_constraints=("panacus==0.3.3",),
            source_ref="v0.3.3",
        ),
        "pangenome_gene": PangenomicsEvidence(
            version="1.5.0",
            git_url="https://github.com/gtonkinhill/panaroo",
            commit=PANAROO_COMMIT,
            source_paths=("panaroo/__main__.py", "docs/gettingstarted/output.md"),
            documentation_url=(
                f"https://github.com/gtonkinhill/panaroo/blob/{PANAROO_COMMIT}/docs/gettingstarted/quickstart.md"
            ),
            package_constraints=("panaroo==1.5.0",),
            source_ref="v1.5.0",
        ),
        "minigraph": PangenomicsEvidence(
            version="0.21",
            git_url="https://github.com/lh3/minigraph",
            commit=MINIGRAPH_COMMIT,
            source_paths=("README.md", "main.c"),
            documentation_url=f"https://github.com/lh3/minigraph/blob/{MINIGRAPH_COMMIT}/README.md",
            package_constraints=("minigraph==0.21",),
            source_ref="v0.21",
        ),
        "minigraph_cactus": PangenomicsEvidence(
            version="2.9.9",
            git_url="https://github.com/ComparativeGenomicsToolkit/cactus",
            commit=CACTUS_COMMIT,
            source_paths=(
                "src/cactus/refmap/cactus_pangenome.py",
                "src/cactus/refmap/cactus_graphmap_join.py",
                "src/cactus/progressive/seqFile.py",
            ),
            documentation_url=(
                f"https://github.com/ComparativeGenomicsToolkit/cactus/blob/{CACTUS_COMMIT}/doc/pangenome.md"
            ),
            package_constraints=("cactus==2.9.9",),
            source_ref="v2.9.9",
        ),
        "cactus_cactus": PangenomicsEvidence(
            version="2.7.1+galaxy0",
            git_url="https://github.com/ComparativeGenomicsToolkit/cactus",
            commit=CACTUS_COMMIT,
            source_paths=("doc/progressive.md", "doc/pangenome.md"),
            documentation_url=(
                f"https://github.com/galaxyproject/tools-iuc/blob/{TOOLS_IUC_COMMIT}/tools/cactus/cactus_cactus.xml"
            ),
            package_constraints=("cactus==2.9.9",),
            source_ref="v2.9.9 runtime with Tools-IUC wrapper 2.7.1+galaxy0",
            wrapper_version="2.7.1+galaxy0",
            wrapper_commit=TOOLS_IUC_COMMIT,
            wrapper_path="tools/cactus/cactus_cactus.xml",
        ),
        "cactus_export": PangenomicsEvidence(
            version="2.7.1+galaxy0",
            git_url="https://github.com/ComparativeGenomicsToolkit/cactus",
            commit=CACTUS_COMMIT,
            source_paths=("doc/progressive.md",),
            documentation_url=(
                f"https://github.com/galaxyproject/tools-iuc/blob/{TOOLS_IUC_COMMIT}/tools/cactus/cactus_export.xml"
            ),
            package_constraints=("cactus==2.9.9", "tar>=1.34"),
            source_ref="v2.9.9 runtime with Tools-IUC wrapper 2.7.1+galaxy0",
            wrapper_version="2.7.1+galaxy0",
            wrapper_commit=TOOLS_IUC_COMMIT,
            wrapper_path="tools/cactus/cactus_export.xml",
        ),
    }
)


class PangenomicsCommandContract(CommandNode):
    """Attach pinned evidence and return sparse outputs by their declared names."""

    CATEGORY = "pangenomics"
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = "Input validation or any non-zero pipeline command fails the node."
    OUTPUT_NAME_BY_BASENAME: dict[str, str] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        node_id = cls.__dict__.get("NODE_ID", "")
        if not node_id:
            return
        evidence = NODE_EVIDENCE[node_id]
        cls.VERSION = evidence.version
        cls.GIT_URL = evidence.git_url
        cls.GIT_COMMIT = evidence.commit
        cls.SOURCE_REF = evidence.source_ref
        cls.SOURCE_URLS = evidence.source_urls
        cls.SOURCE_URL = evidence.source_urls[0]
        cls.SECONDARY_SOURCE_URLS = evidence.secondary_source_urls
        cls.DOCUMENTATION_URL = evidence.documentation_url
        cls.PACKAGE_CONSTRAINTS = evidence.package_constraints
        cls.PACKAGE_CONSTRAINT = "; ".join(evidence.package_constraints)
        if evidence.wrapper_path:
            cls.GALAXY_WRAPPER_VERSION = evidence.wrapper_version
            cls.GALAXY_WRAPPER_GIT_COMMIT = evidence.wrapper_commit
            cls.GALAXY_WRAPPER_PATH = evidence.wrapper_path
            cls.GALAXY_WRAPPER_SOURCE_URL = evidence.documentation_url

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        if cls.OUTPUT_NAME_BY_BASENAME:
            mapped: dict[str, Path] = {}
            for path in planned_paths:
                try:
                    output_name = cls.OUTPUT_NAME_BY_BASENAME[path.name]
                except KeyError as exc:
                    raise ValueError(f"{cls.NODE_ID} planned an unknown artifact: {path.name}") from exc
                if output_name in mapped:
                    raise ValueError(f"{cls.NODE_ID} planned duplicate output port: {output_name}")
                mapped[output_name] = path
            return mapped
        if len(planned_paths) > len(cls.RETURN_NAMES):
            raise ValueError(f"{cls.NODE_ID} planned more artifacts than declared output ports")
        return dict(zip(cls.RETURN_NAMES, planned_paths, strict=False))

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        planned = await super().run(**kwargs)
        mapped = self.__class__.MAP_PLANNED_OUTPUTS([Path(path) for path in planned])
        return {"outputs": {name: str(path) for name, path in mapped.items()}}
