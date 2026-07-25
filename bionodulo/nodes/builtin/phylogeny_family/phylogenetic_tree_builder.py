"""Deterministic Newick-selection manifest owner."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode

from .evidence import source_pinned
from .legacy import _phylogeny_node_output_dir, _split_text_list


def _canonical_newick(path: Path) -> str:
    from Bio import Phylo

    tree = Phylo.read(str(path), "newick")
    handle = StringIO()
    Phylo.write(tree, handle, "newick")
    return handle.getvalue().strip()


@source_pinned("phylogenetic_tree_builder")
class PhylogeneticTreeBuilderNode(BaseNode):
    """Select the most frequent canonical Newick string and write a manifest."""

    NODE_ID = "phylogenetic_tree_builder"
    DISPLAY_NAME = "Phylo Tree Builder"
    CATEGORY = "phylogeny"
    DESCRIPTION = (
        "Build phylogenetic trees using multiple methods with consensus from existing Newick outputs."
    )
    SEARCH_ALIASES = [
        "phylo tree builder",
        "consensus tree",
        "newick",
        "tree consensus",
        "phylogeny",
    ]
    RETURN_TYPES = ("NEWICK", "JSON")
    RETURN_NAMES = ("consensus_tree", "individual_trees")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["biopython"]
    DOCUMENTATION_URL = "https://biopython.org/wiki/Phylo"
    VERSION = "1.0.0"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "tree_files": (
                    "FILE",
                    {"description": "Newline- or comma-separated Newick tree files"},
                ),
            },
            "optional": {
                "methods": (
                    "STRING",
                    {"default": "", "description": "Names corresponding to tree_files"},
                ),
                "consensus_method": (
                    "STRING",
                    {"default": "majority", "options": ["majority", "first"]},
                ),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        tree_files = [Path(path) for path in _split_text_list(kwargs.get("tree_files"))]
        if not tree_files:
            raise ValueError("At least one tree file is required")

        methods = _split_text_list(kwargs.get("methods"))
        consensus_method = str(kwargs.get("consensus_method", "majority") or "majority")
        if consensus_method not in {"majority", "first"}:
            raise ValueError(f"Unsupported consensus method: {consensus_method}")

        entries: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        first_index: dict[str, int] = {}
        for index, path in enumerate(tree_files):
            if not path.exists():
                raise ValueError(f"Tree file not found: {path}")
            newick = _canonical_newick(path)
            counts[newick] = counts.get(newick, 0) + 1
            first_index.setdefault(newick, index)
            entries.append(
                {
                    "method": methods[index] if index < len(methods) else f"tree_{index + 1}",
                    "path": str(path),
                    "newick": newick,
                }
            )

        if consensus_method == "first":
            selected_newick = entries[0]["newick"]
        else:
            selected_newick = min(counts, key=lambda item: (-counts[item], first_index[item], item))
        selected_index = first_index[selected_newick]

        for entry in entries:
            entry["support_count"] = counts[entry["newick"]]
            entry["selected"] = entry["newick"] == selected_newick

        out_dir = _phylogeny_node_output_dir(self, context)
        consensus_path = out_dir / "consensus_tree.nwk"
        manifest_path = out_dir / "individual_trees.json"
        consensus_path.write_text(selected_newick + "\n", encoding="utf-8")
        manifest_path.write_text(
            json.dumps(
                {
                    "consensus_method": consensus_method,
                    "selected_tree_index": selected_index,
                    "tree_count": len(entries),
                    "trees": entries,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return str(consensus_path), str(manifest_path)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "consensus_tree.nwk", node_out / "individual_trees.json"]
