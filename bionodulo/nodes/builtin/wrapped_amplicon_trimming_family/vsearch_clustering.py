"""Focused VSEARCH clustering node."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract
from .vsearch_adapter import VSearchNodeBase


class VSearchClusterNode(VSearchNodeBase):
    """Cluster FASTA sequences with the pinned Galaxy VSEARCH wrapper."""

    NODE_ID = "vsearch_cluster"
    DISPLAY_NAME = "VSEARCH Cluster"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Cluster amplicon sequences with VSEARCH cluster_fast or cluster_smallmem."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "vsearch", "cluster_fast", "cluster_smallmem", "otu clustering", "centroids"]
    RETURN_TYPES = (
        "FASTA",
        "FASTA",
        "FASTA",
        "STATS_FILE",
        "FASTA",
        "FASTA",
        "TSV",
        "FASTA",
        "TSV",
        "TSV",
    )
    RETURN_NAMES = (
        "msaout",
        "consout",
        "centroids",
        "alnout",
        "notmatched",
        "matched",
        "blast6out",
        "fastapairs",
        "uc_outfile",
        "clusters_uc",
    )
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3.0"

    OUTPUT_FILES = {
        "msaout": "clusters_msa.fasta",
        "consout": "cluster_consensus.fasta",
        "centroids": "centroids.fasta",
        "alnout": "cluster_alignments.txt",
        "notmatched": "notmatched.fasta",
        "matched": "matched.fasta",
        "blast6out": "clusters.tsv",
        "fastapairs": "cluster_pairs.fasta",
        "uc_outfile": "clusters.uc",
    }
    OUTPUT_FLAGS = {
        "msaout": "--msaout",
        "consout": "--consout",
        "centroids": "--centroids",
        "alnout": "--alnout",
        "notmatched": "--notmatched",
        "matched": "--matched",
        "blast6out": "--blast6out",
        "fastapairs": "--fastapairs",
    }

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        selected = [value.removeprefix("--") for value in _as_list(inputs.get("outputs"))]
        return selected or ["blast6out"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = cls._general_command(inputs)
        mode = str(inputs.get("cluster_mode", inputs.get("clustering_mode_select", "cluster_fast")))
        cmd.extend([f"--{mode}", str(inputs.get("sequences", inputs.get("infile", "")))])
        _add_if_value(cmd, "--maxrejects", inputs.get("maxrejects", 32))
        _add_if_value(cmd, "--maxaccepts", inputs.get("maxaccepts", 1))
        if inputs.get("cons_truncate"):
            cmd.append("--cons_truncate")
        cmd.extend(["--id", str(inputs.get("identity", inputs.get("id", 0.97)))])
        cmd.extend(["--iddef", str(inputs.get("iddef", "2"))])
        out = _out(inputs)
        for name in cls._selected_outputs(inputs):
            cmd.extend([cls.OUTPUT_FLAGS[name], f"{out}/{cls.OUTPUT_FILES[name]}"])
        cmd.extend(["--qmask", str(inputs.get("qmask", "dust") or "dust")])
        if inputs.get("sizein"):
            cmd.append("--sizein")
        if inputs.get("sizeout"):
            cmd.append("--sizeout")
        cmd.extend(["--strand", str(inputs.get("strand", "plus") or "plus")])
        if inputs.get("usersort"):
            cmd.append("--usersort")
        if inputs.get("uc"):
            cmd.extend(["--uc", f"{out}/{cls.OUTPUT_FILES['uc_outfile']}"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        names = cls._selected_outputs(inputs)
        if inputs.get("uc"):
            names.append("uc_outfile")
        return [out / cls.OUTPUT_FILES[name] for name in dict.fromkeys(names)]

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        reverse = {filename: name for name, filename in cls.OUTPUT_FILES.items()}
        mapped = {reverse[path.name]: path for path in planned_paths}
        if "uc_outfile" in mapped:
            mapped["clusters_uc"] = mapped["uc_outfile"]
        return mapped

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("sequences", inputs.get("infile", ""))).strip():
            return "sequences is required"
        mode = str(inputs.get("cluster_mode", inputs.get("clustering_mode_select", "cluster_fast")))
        if mode not in {"cluster_fast", "cluster_smallmem"}:
            return "cluster_mode must be one of: cluster_fast, cluster_smallmem"
        selected = cls._selected_outputs(inputs)
        unsupported = [name for name in selected if name not in cls.OUTPUT_FLAGS]
        if unsupported:
            return f"outputs contains unsupported values: {', '.join(unsupported)}"
        try:
            identity = float(inputs.get("identity", inputs.get("id", 0.97)))
        except (TypeError, ValueError):
            return "identity must be a number"
        if not 0 <= identity <= 1:
            return "identity must be between 0 and 1"
        if str(inputs.get("qmask", "dust")) not in {"none", "dust", "soft"}:
            return "qmask must be one of: none, dust, soft"
        if str(inputs.get("strand", "plus")) not in {"plus", "both"}:
            return "strand must be one of: plus, both"
        if str(inputs.get("iddef", "2")) not in {"0", "1", "2", "3", "4"}:
            return "iddef must be one of: 0, 1, 2, 3, 4"
        for name, default in (("maxaccepts", 1), ("maxrejects", 32)):
            raw = inputs.get(name, default)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 0:
                return f"{name} must be >= 0"
        return cls._validate_common(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"sequences": ("FASTA", {"description": "Sequences to cluster"})},
            "optional": {
                "cluster_mode": (
                    "STRING",
                    {"default": "cluster_fast", "options": ["cluster_fast", "cluster_smallmem"]},
                ),
                "outputs": (
                    "STRING_LIST",
                    {
                        "default": ["blast6out"],
                        "multiple": True,
                        "options": list(cls.OUTPUT_FLAGS),
                        "description": "Galaxy clustering outputs to emit",
                    },
                ),
                "identity": ("FLOAT", {"default": 0.97, "min": 0, "max": 1}),
                "iddef": ("STRING", {"default": "2", "options": ["0", "1", "2", "3", "4"]}),
                "usersort": ("BOOLEAN", {"default": False}),
                "cons_truncate": ("BOOLEAN", {"default": False}),
                "qmask": ("STRING", {"default": "dust", "options": ["none", "dust", "soft"]}),
                "sizein": ("BOOLEAN", {"default": False}),
                "sizeout": ("BOOLEAN", {"default": False}),
                "strand": ("STRING", {"default": "plus", "options": ["plus", "both"]}),
                "maxaccepts": ("INT", {"default": 1, "min": 0}),
                "maxrejects": ("INT", {"default": 32, "min": 0}),
                "uc": ("BOOLEAN", {"default": False}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(VSearchClusterNode)
