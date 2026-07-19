"""Stable owner for ``minigraph_cactus``."""

from pathlib import Path

from .legacy import _MinigraphCactusContract


class MinigraphCactusNode(_MinigraphCactusContract):
    NODE_ID = "minigraph_cactus"

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        mapped: dict[str, Path] = {}
        for path in planned_paths:
            name = path.name
            if name.endswith(".vcf.gz.tbi"):
                port = "variants_vcf_index"
            elif name.endswith(".vcf.gz"):
                port = "variants_vcf"
            elif name.endswith(".gfa.gz"):
                port = "graph_gfa"
            elif name.endswith(".full.og"):
                port = "graph_odgi"
            elif name.endswith(".gbz"):
                port = "graph_gbz"
            else:
                raise ValueError(f"{cls.NODE_ID} planned an unknown artifact: {name}")
            mapped[port] = path
        return mapped
