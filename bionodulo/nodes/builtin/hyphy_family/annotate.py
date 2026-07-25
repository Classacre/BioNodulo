"""Focused owner for ``hyphy_annotate``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract

class HyPhyAnnotateNode(ToolsIUCCommandContract):
    """Annotate branches in a Newick/NHX tree with HyPhy label-tree."""

    NODE_ID = "hyphy_annotate"
    DISPLAY_NAME = "HyPhy Annotate"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Annotate a Newick/NHX phylogenetic tree with HyPhy label-tree."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "label-tree",
        "Annotate",
        "Newick annotation",
        "branch labels",
        "phylogenetic tree annotation",
    ]
    RETURN_TYPES = ("PHYLOGENY_TREE", "TEXT")
    RETURN_NAMES = ("labeled_tree", "annotate_md_report")
    REQUIRED_EXECUTABLES = ["hyphy"]
    DOCUMENTATION_URL = "https://github.com/veg/hyphy/blob/master/res/TemplateBatchFiles/lib/label-tree.bf"
    CITATION_DOIS = [HYPHY_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{HYPHY_CITATION_DOI}"]
    CITATION_TEXT = HYPHY_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    SELECTION_METHODS = ["regexp", "list"]
    INTERNAL_NODE_STRATEGIES = [
        "All descendants",
        "None",
        "All descendants, no MRCA",
        "Some descendants",
        "Parsimony",
    ]
    LEAF_NODE_STRATEGIES = ["Label", "Skip"]

    @classmethod
    def _invert_value(cls, inputs: dict[str, Any]) -> str:
        value = inputs.get("invert", False)
        if isinstance(value, str):
            return "Yes" if value.lower() in {"true", "yes", "1", "on", "--invert yes"} else "No"
        return "Yes" if bool(value) else "No"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(["cp", str(inputs.get("input_tree", "")), "input.nhx"])]
        cmd = [
            "hyphy",
            "label-tree",
            "--tree",
            "input.nhx",
            "--output",
            f"{out}/labeled_tree.nhx",
        ]
        selection_method = str(inputs.get("selection_method", "regexp") or "regexp")
        if selection_method == "list":
            cmd.extend(["--list", str(inputs.get("list_file", ""))])
        else:
            cmd.extend(["--regexp", str(inputs.get("regexp", ""))])
        cmd.extend(
            [
                "--label",
                str(inputs.get("label", "Foreground") or "Foreground"),
                "--reroot",
                str(inputs.get("reroot", "None") or "None"),
                "--invert",
                cls._invert_value(inputs),
                "--internal-nodes",
                str(inputs.get("internal_nodes", "All descendants") or "All descendants"),
                "--leaf-nodes",
                str(inputs.get("leaf_nodes", "Label") or "Label"),
                ">",
                f"{out}/annotate_stdout.md",
                "2>/dev/null",
            ]
        )
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "labeled_tree.nhx", out / "annotate_stdout.md"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_tree", "")).strip():
            return "HyPhy Annotate input tree is required"
        selection_method = str(inputs.get("selection_method", "regexp") or "regexp")
        if selection_method not in cls.SELECTION_METHODS:
            return f"Unsupported HyPhy Annotate selection method: {selection_method}"
        if selection_method == "regexp":
            regexp = str(inputs.get("regexp", "")).strip()
            if not regexp:
                return "HyPhy Annotate regular expression is required"
            if regexp.endswith("\\"):
                return "HyPhy Annotate regular expression must not end with a backslash"
        if selection_method == "list" and not str(inputs.get("list_file", "")).strip():
            return "HyPhy Annotate sequence list file is required"
        if not str(inputs.get("label", "Foreground")).strip():
            return "HyPhy Annotate label is required"
        internal_nodes = str(inputs.get("internal_nodes", "All descendants") or "All descendants")
        if internal_nodes not in cls.INTERNAL_NODE_STRATEGIES:
            return f"Unsupported HyPhy Annotate internal-node strategy: {internal_nodes}"
        leaf_nodes = str(inputs.get("leaf_nodes", "Label") or "Label")
        if leaf_nodes not in cls.LEAF_NODE_STRATEGIES:
            return f"Unsupported HyPhy Annotate leaf-node strategy: {leaf_nodes}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_tree": ("PHYLOGENY_TREE", {"description": "Newick/NHX tree to annotate"}),
                "selection_method": (
                    "STRING",
                    {
                        "default": "regexp",
                        "options": cls.SELECTION_METHODS,
                        "description": "Select branches by regular expression or sequence-name list",
                    },
                ),
            },
            "optional": {
                "regexp": (
                    "STRING",
                    {"default": "", "description": "Regular expression used to select matching leaf names"},
                ),
                "list_file": (
                    "FILE",
                    {"default": "", "description": "Line list of sequence names used when selection method is list"},
                ),
                "label": ("STRING", {"default": "Foreground", "description": "Label to apply to selected branches"}),
                "reroot": (
                    "STRING",
                    {"default": "None", "description": "Tree node to reroot on, or None to skip rerooting"},
                ),
                "invert": ("BOOLEAN", {"default": False, "description": "Invert the regex or list branch selection"}),
                "internal_nodes": (
                    "STRING",
                    {
                        "default": "All descendants",
                        "options": cls.INTERNAL_NODE_STRATEGIES,
                        "description": "Strategy for labeling internal nodes",
                    },
                ),
                "leaf_nodes": (
                    "STRING",
                    {
                        "default": "Label",
                        "options": cls.LEAF_NODE_STRATEGIES,
                        "description": "Strategy for labeling selected leaves",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
