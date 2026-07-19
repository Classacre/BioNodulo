"""Compatibility imports for focused BEDTools nodes and unchanged BEDOPS IDs."""

# ruff: noqa: F401
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin._wrapped_tool_utils import (
    BEDOPS_CITATION_DOI,
    BEDOPS_CITATION_TEXT,
    BIONODULO_BUILTIN_ALIAS,
    DOI_URL,
    _add_shell_redirect,
    _as_list,
    _bedtools_common_output,
    _out,
)
from bionodulo.nodes.builtin.bedtools_family.annotate import BEDToolsAnnotateNode
from bionodulo.nodes.builtin.bedtools_family.bamtobed import BEDToolsBamToBedNode
from bionodulo.nodes.builtin.bedtools_family.bed12tobed6 import BEDToolsBed12ToBed6Node
from bionodulo.nodes.builtin.bedtools_family.bedpetobam import BEDToolsBedpeToBamNode
from bionodulo.nodes.builtin.bedtools_family.bedtobam import BEDToolsBedToBamNode
from bionodulo.nodes.builtin.bedtools_family.bedtoigv import BEDToolsBedToIgvNode
from bionodulo.nodes.builtin.bedtools_family.closestbed import BEDToolsClosestBedNode
from bionodulo.nodes.builtin.bedtools_family.cluster import BEDToolsClusterNode
from bionodulo.nodes.builtin.bedtools_family.complement import BEDToolsComplementNode
from bionodulo.nodes.builtin.bedtools_family.coverage import BEDToolsCoverageNode
from bionodulo.nodes.builtin.bedtools_family.expand import BEDToolsExpandNode
from bionodulo.nodes.builtin.bedtools_family.fisher import BEDToolsFisherNode
from bionodulo.nodes.builtin.bedtools_family.flank import BEDToolsFlankNode
from bionodulo.nodes.builtin.bedtools_family.genomecov import BEDToolsGenomeCoverageNode
from bionodulo.nodes.builtin.bedtools_family.getfasta import BEDToolsGetFastaNode
from bionodulo.nodes.builtin.bedtools_family.groupby import BEDToolsGroupByNode
from bionodulo.nodes.builtin.bedtools_family.intersectbed import BEDToolsIntersectBedNode
from bionodulo.nodes.builtin.bedtools_family.jaccard import BEDToolsJaccardNode
from bionodulo.nodes.builtin.bedtools_family.links import BEDToolsLinksNode
from bionodulo.nodes.builtin.bedtools_family.makewindows import BEDToolsMakeWindowsNode
from bionodulo.nodes.builtin.bedtools_family.map import BEDToolsMapNode
from bionodulo.nodes.builtin.bedtools_family.maskfasta import BEDToolsMaskFastaNode
from bionodulo.nodes.builtin.bedtools_family.merge import BEDToolsMergeNode
from bionodulo.nodes.builtin.bedtools_family.multicov import BEDToolsMultiCovNode
from bionodulo.nodes.builtin.bedtools_family.multiinter import BEDToolsMultiIntersectNode
from bionodulo.nodes.builtin.bedtools_family.nuc import BEDToolsNucNode
from bionodulo.nodes.builtin.bedtools_family.overlap import BEDToolsOverlapBedNode
from bionodulo.nodes.builtin.bedtools_family.random import BEDToolsRandomNode
from bionodulo.nodes.builtin.bedtools_family.reldist import BEDToolsRelativeDistanceNode
from bionodulo.nodes.builtin.bedtools_family.shuffle import BEDToolsShuffleNode
from bionodulo.nodes.builtin.bedtools_family.slop import BEDToolsSlopNode
from bionodulo.nodes.builtin.bedtools_family.sort import BEDToolsSortNode
from bionodulo.nodes.builtin.bedtools_family.spacing import BEDToolsSpacingNode
from bionodulo.nodes.builtin.bedtools_family.subtract import BEDToolsSubtractNode
from bionodulo.nodes.builtin.bedtools_family.tag import BEDToolsTagBedNode
from bionodulo.nodes.builtin.bedtools_family.unionbedg import BEDToolsUnionBedGraphNode
from bionodulo.nodes.builtin.bedtools_family.window import BEDToolsWindowNode
from bionodulo.nodes.command_node import CommandNode


class BEDOPSSortBedNode(CommandNode):
    """Sort BED records into BEDOPS canonical order."""

    NODE_ID = "bedops_sort_bed"
    DISPLAY_NAME = "BEDOPS Sort BED"
    REQUIRED_CONDA_PACKAGES = ["bedops"]
    CATEGORY = "genomics"
    DESCRIPTION = "Sort one or more BED files into BEDOPS canonical order, optionally emitting only unique or duplicate records."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedops", "sort-bed", "BEDOPS sort-bed", "sort BED", "unique BED", "duplicate BED"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("sorted_bed",)
    REQUIRED_EXECUTABLES = ["sort-bed"]
    DOCUMENTATION_URL = "https://bedops.readthedocs.io/en/latest/content/reference/file-management/sorting/sort-bed.html"
    CITATION_DOIS = [BEDOPS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDOPS_CITATION_DOI}"]
    CITATION_TEXT = BEDOPS_CITATION_TEXT
    VERSION = "2.4.42"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = [
            "sort-bed",
            "--max-mem",
            f"{int(inputs.get('memory_mb', 1024) or 1024)}M",
            "--tmpdir",
            str(inputs.get("tmpdir") or "."),
        ]
        if inputs.get("unique"):
            command.append("--unique")
        if inputs.get("duplicates"):
            command.append("--duplicates")
        command.extend(_as_list(inputs.get("inputs")))
        _add_shell_redirect(command, f"{_out(inputs)}/sorted.bed")
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "sorted.bed", output_dir)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not _as_list(inputs.get("inputs")):
            return "at least one BED input is required"
        if inputs.get("unique") and inputs.get("duplicates"):
            return "unique and duplicates modes are mutually exclusive"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"inputs": ("BED_LIST", {"description": "One or more BED files to sort"})},
            "optional": {
                "unique": ("BOOLEAN", {"default": False}),
                "duplicates": ("BOOLEAN", {"default": False}),
                "memory_mb": ("INT", {"default": 1024, "min": 1}),
                "tmpdir": ("DIRECTORY", {"advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDOPSSortBedGalaxyNode(BEDOPSSortBedNode):
    """Galaxy wrapper-ID compatible alias for BEDOPS sort-bed."""

    NODE_ID = "bedops-sort-bed"
    DISPLAY_NAME = "BEDOPS sort-bed"
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "bedops-sort-bed",
        "bedops",
        "sort-bed",
        "BEDOPS sort-bed",
        "sort BED",
        "unique BED",
        "duplicate BED",
    ]
