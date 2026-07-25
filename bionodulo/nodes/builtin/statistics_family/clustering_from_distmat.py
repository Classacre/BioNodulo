"""Focused clustering node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_core_data_family.evidence import pin_contract

class ClusteringFromDistmatNode(CommandNode):
    """Hierarchically cluster samples from a symmetric distance matrix."""

    NODE_ID = "clustering_from_distmat"
    DISPLAY_NAME = "Distance matrix-based hierarchical clustering"
    REQUIRED_CONDA_PACKAGES = ["python", "scipy", "pandas"]
    CATEGORY = "clustering"
    DESCRIPTION = "Cluster samples from a symmetric distance matrix with SciPy hierarchical clustering."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "clustering_from_distmat",
        "Distance matrix-based hierarchical clustering",
        "distance matrix",
        "hierarchical clustering",
        "SciPy linkage",
        "UPGMA",
        "WPGMA",
        "dendrogram",
        "newick",
        "cut_tree",
        "cluster assignments",
    ]
    RETURN_TYPES = ("PHYLOGENY_TREE", "TSV")
    RETURN_NAMES = ("clustering_dendrogram", "clustering_assignment")
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://docs.scipy.org/doc/scipy/reference/cluster.hierarchy.html"
    CITATION_DOIS = [SCIPY_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{SCIPY_CITATION_DOI}"]
    CITATION_TEXT = SCIPY_CITATION_TEXT
    VERSION = "1.1.2+galaxy0"
    SHELL = True

    METHODS = ["single", "complete", "average", "weighted", "centroid", "median", "ward"]
    MISSING_NAMES_OPTIONS = ["", "--nr", "--nc"]
    CLUSTER_ASSIGNMENT_OPTIONS = ["dendrogram-only", "n-cluster", "height"]

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {"", "false", "0", "no", "off"}
        return bool(value)

    @classmethod
    def _cluster_assignment(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("cluster_assignment", "dendrogram-only") or "dendrogram-only")

    @classmethod
    def _dendrogram_requested(cls, inputs: dict[str, Any]) -> bool:
        return cls._cluster_assignment(inputs) == "dendrogram-only" or cls._bool_flag(inputs.get("generate_dendrogram", False))

    @classmethod
    def _assignment_requested(cls, inputs: dict[str, Any]) -> bool:
        return cls._cluster_assignment(inputs) in {"n-cluster", "height"}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        assignment = cls._cluster_assignment(inputs)
        cmd = [
            "python",
            str(inputs.get("script_path", "clustering_from_distmat.py") or "clustering_from_distmat.py"),
            str(inputs.get("distmat", "")),
            "result",
            "--method",
            str(inputs.get("method", "average") or "average"),
        ]
        missing_names = str(inputs.get("missing_names", "") or "")
        if missing_names:
            cmd.append(missing_names)
        cmd.append("--newick")
        if assignment == "n-cluster":
            cmd.extend(["--n-clusters", str(inputs.get("n_cluster", 5))])
        elif assignment == "height":
            cmd.extend(["--height", str(inputs.get("height", 5.0))])
        min_cluster_size = int(inputs.get("min_cluster_size", 2))
        if assignment != "dendrogram-only" and min_cluster_size != 2:
            cmd.extend(["--min-cluster-size", str(min_cluster_size)])
        commands = [_shell_join(["mkdir", "-p", out]), f"cd {shlex.quote(out)}", _shell_join(cmd)]
        if cls._dendrogram_requested(inputs):
            commands.append(_shell_join(["mv", "result.tree", "clustering_dendrogram.newick"]))
        if cls._assignment_requested(inputs):
            commands.append(_shell_join(["mv", "result.cluster_assignments.tsv", "clustering_assignment.tsv"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = []
        if cls._dendrogram_requested(inputs):
            outputs.append(out / "clustering_dendrogram.newick")
        if cls._assignment_requested(inputs):
            outputs.append(out / "clustering_assignment.tsv")
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < minimum:
            return f"{key} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("distmat", "")).strip():
            return "distmat is required"
        method = str(inputs.get("method", "average") or "average")
        if method not in cls.METHODS:
            return f"method must be one of: {', '.join(cls.METHODS)}"
        missing_names = str(inputs.get("missing_names", "") or "")
        if missing_names not in cls.MISSING_NAMES_OPTIONS:
            return f"missing_names must be one of: {', '.join(cls.MISSING_NAMES_OPTIONS)}"
        assignment = cls._cluster_assignment(inputs)
        if assignment not in cls.CLUSTER_ASSIGNMENT_OPTIONS:
            return f"cluster_assignment must be one of: {', '.join(cls.CLUSTER_ASSIGNMENT_OPTIONS)}"
        if assignment == "n-cluster":
            result = cls._validate_int_min(inputs, "n_cluster", 5, 1)
            if result is not True:
                return result
        elif assignment == "height":
            try:
                float(inputs.get("height", 5.0))
            except (TypeError, ValueError):
                return "height must be numeric"
        if assignment != "dendrogram-only":
            result = cls._validate_int_min(inputs, "min_cluster_size", 2, 1)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "distmat": ("TSV", {"description": "Symmetric tabular distance matrix with sample names"}),
            },
            "optional": {
                "method": (
                    "STRING",
                    {"default": "average", "options": cls.METHODS, "description": "SciPy linkage clustering method"},
                ),
                "missing_names": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.MISSING_NAMES_OPTIONS,
                        "description": "Input omits row names, column names, or neither",
                    },
                ),
                "cluster_assignment": (
                    "STRING",
                    {
                        "default": "dendrogram-only",
                        "options": cls.CLUSTER_ASSIGNMENT_OPTIONS,
                        "description": "Generate only a dendrogram or also cut the tree into clusters",
                    },
                ),
                "n_cluster": ("INT", {"default": 5, "min": 1}),
                "height": ("FLOAT", {"default": 5.0}),
                "min_cluster_size": ("INT", {"default": 2, "min": 1}),
                "generate_dendrogram": (
                    "BOOLEAN",
                    {"default": False, "description": "Also keep the Newick dendrogram when generating assignments"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "clustering_from_distmat.py",
                        "advanced": True,
                        "description": "Path to the Galaxy clustering_from_distmat.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(ClusteringFromDistmatNode)

__all__ = ['ClusteringFromDistmatNode']
