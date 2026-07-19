"""Pinned Tools-IUC authorities for annotation and sequence wrapper contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


AEGEAN_PACKAGES = ("aegean==0.16.0",)
ARRIBA_PACKAGES = ("arriba==2.5.1",)
ARTIC_PACKAGES = ("artic==1.7.3",)
SEQKIT_PACKAGES = ("seqkit==2.13.0",)

NODE_EVIDENCE = {
    "aegean_canongff3": WrapperEvidence("tools/aegean/canongff3.xml", "0.16.0+galaxy2", AEGEAN_PACKAGES),
    "aegean_gaeval": WrapperEvidence("tools/aegean/gaeval.xml", "0.16.0+galaxy2", AEGEAN_PACKAGES),
    "aegean_locuspocus": WrapperEvidence("tools/aegean/locuspocus.xml", "0.16.0+galaxy2", AEGEAN_PACKAGES),
    "aegean_parseval": WrapperEvidence("tools/aegean/parseval.xml", "0.16.0+galaxy2", AEGEAN_PACKAGES),
    "augustus": WrapperEvidence("tools/augustus/augustus.xml", "3.5.0+galaxy0", ("augustus==3.5.0",)),
    "augustus_training": WrapperEvidence(
        "tools/augustus/augustus_training.xml",
        "3.5.0+galaxy0",
        ("augustus==3.5.0", "maker==3.01.03"),
    ),
    "arriba": WrapperEvidence("tools/arriba/arriba.xml", "2.5.1+galaxy0", ARRIBA_PACKAGES),
    "arriba_draw_fusions": WrapperEvidence(
        "tools/arriba/arriba_draw_fusions.xml",
        "2.5.1+galaxy0",
        ARRIBA_PACKAGES,
    ),
    "arriba_get_filters": WrapperEvidence(
        "tools/arriba/arriba_get_filters.xml",
        "2.5.1+galaxy0",
        ARRIBA_PACKAGES,
    ),
    "artic_guppyplex": WrapperEvidence(
        "tools/artic/artic_guppyplex.xml",
        "1.7.3+galaxy1",
        ARTIC_PACKAGES,
    ),
    "artic_minion": WrapperEvidence("tools/artic/artic_minion.xml", "1.7.3+galaxy1", ARTIC_PACKAGES),
    "busco": WrapperEvidence(
        "tools/busco/busco.xml",
        "5.8.0+galaxy2",
        (
            "busco==5.8.0",
            "augustus==3.5.0",
            "tar==1.34",
            "fonts-conda-ecosystem==1",
            "sepp==4.5.5",
        ),
    ),
    "htseq_count": WrapperEvidence(
        "tools/htseq_count/htseq-count.xml",
        "2.1.2+galaxy0",
        ("htseq==2.1.2", "samtools==1.23", "gawk==5.3.1", "coreutils==9.5"),
    ),
    "roary": WrapperEvidence("tools/roary/roary.xml", "3.13.0+galaxy3", ("roary==3.13.0",)),
    "seqkit_stats": WrapperEvidence("tools/seqkit/seqkit_stats.xml", "2.13.0+galaxy0", SEQKIT_PACKAGES),
    "seqkit_grep": WrapperEvidence("tools/seqkit/seqkit_grep.xml", "2.13.0+galaxy0", SEQKIT_PACKAGES),
    "seqkit_head": WrapperEvidence("tools/seqkit/seqkit_head.xml", "2.13.0+galaxy0", SEQKIT_PACKAGES),
    "seqkit_fx2tab": WrapperEvidence("tools/seqkit/seqkit_fx2tab.xml", "2.13.0+galaxy0", SEQKIT_PACKAGES),
    "seqkit_sort": WrapperEvidence("tools/seqkit/seqkit_sort.xml", "2.13.0+galaxy0", SEQKIT_PACKAGES),
    "seqkit_locate": WrapperEvidence("tools/seqkit/seqkit_locate.xml", "2.13.0+galaxy0", SEQKIT_PACKAGES),
    "seqkit_translate": WrapperEvidence(
        "tools/seqkit/seqkit_translate.xml",
        "2.13.0+galaxy0",
        SEQKIT_PACKAGES,
    ),
    "seqkit_split2": WrapperEvidence("tools/seqkit/seqkit_split2.xml", "2.13.0+galaxy1", SEQKIT_PACKAGES),
    "amrfinderplus": WrapperEvidence(
        "tools/amrfinderplus/amrfinderplus.xml",
        "4.2.7+galaxy0",
        ("ncbi-amrfinderplus==4.2.7",),
    ),
}


class ToolsIUCCommandContract(CommandNode):
    """Attach exact wrapper evidence when a focused owner declares its stable ID."""

    GIT_URL = TOOLS_IUC_REPO_URL
    GALAXY_WRAPPER_GIT_URL = TOOLS_IUC_REPO_URL
    EXIT_SEMANTICS = "Galaxy wrapper validation or external command failure must produce a non-zero result."
    AUDIT_STATUS = "contract-checked-no-external-execution"
    OUTPUT_NAME_BY_BASENAME: dict[str, str] = {}

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

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        if cls.OUTPUT_NAME_BY_BASENAME:
            mapped: dict[str, Any] = {}
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
        return {
            "outputs": {
                name: [str(path) for path in value] if isinstance(value, list) else str(value)
                for name, value in mapped.items()
            }
        }
