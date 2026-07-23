"""Focused owner for ``mashmap``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract

class MashMapNode(ToolsIUCCommandContract):
    """Compute approximate local alignment boundaries with MashMap."""

    NODE_ID = "mashmap"
    DISPLAY_NAME = "MashMap"
    REQUIRED_CONDA_PACKAGES = ["mashmap"]
    CATEGORY = "genomics"
    DESCRIPTION = "Compute fast approximate local alignment boundaries between query and reference DNA sequences."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mashmap",
        "MashMap3",
        "local alignment boundaries",
        "PAF",
        "genome mapping",
        "long read mapping",
        "minmers",
        "minhash",
    ]
    RETURN_TYPES = ("PAF",)
    RETURN_NAMES = ("mashout",)
    REQUIRED_EXECUTABLES = ["mashmap"]
    DOCUMENTATION_URL = "https://github.com/marbl/MashMap"
    CITATION_DOIS = [
        "10.1093/bioinformatics/btad512",
        "10.1093/bioinformatics/bty597",
        "10.1007/978-3-319-56970-3_5",
    ]
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = (
        "Minmers are a generalization of minimizers that enable unbiased local Jaccard estimation; "
        "a fast approximate algorithm for computing local alignment boundaries; "
        "A fast adaptive algorithm for computing whole-genome homology maps; "
        "A Fast Approximate Algorithm for Mapping Long Reads to Large Reference Databases."
    )
    VERSION = "3.1.3"
    SHELL = True
    FILTER_MODES = ("map", "one-to-one", "none")

    async def run(self, **kwargs: Any) -> Any:
        output_dir = kwargs.get("output_dir")
        context = kwargs.get("context")
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        node_out = Path(output_dir) / self.__class__.NODE_ID if output_dir else Path(".")
        node_out.mkdir(parents=True, exist_ok=True)
        query_files = _as_list(kwargs.get("query"))
        ref_files = _as_list(kwargs.get("reflist"))
        if len(query_files) > 1:
            (node_out / "query").write_text("\n".join(query_files) + "\n", encoding="utf-8")
        if len(ref_files) > 1:
            (node_out / "reflist").write_text("\n".join(ref_files) + "\n", encoding="utf-8")
        return await super().run(**kwargs)

    @classmethod
    def _list_prelude(cls, path: str, files: list[str]) -> str:
        quoted = " ".join(shlex.quote(item) for item in files)
        return f"printf '%s\\n' {quoted} > {shlex.quote(path)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        query_files = _as_list(inputs.get("query"))
        ref_files = _as_list(inputs.get("reflist"))
        query_list = f"{out}/query"
        ref_list = f"{out}/reflist"
        commands: list[str] = []
        if len(ref_files) > 1:
            commands.append(cls._list_prelude(ref_list, ref_files))
        if len(query_files) > 1:
            commands.append(cls._list_prelude(query_list, query_files))

        cmd = [
            "mashmap",
            "--threads",
            "${GALAXY_SLOTS:-1}",
            "--perc_identity",
            str(inputs.get("perc_identity", 85.0)),
            "--segLength",
            str(inputs.get("seqLength", 5000)),
            "--filter_mode",
            str(inputs.get("filter_mode", "map")),
        ]
        if inputs.get("dense", True):
            cmd.append("--dense")
        if inputs.get("reportPercentage"):
            cmd.append("--reportPercentage")
        if inputs.get("noMerge"):
            cmd.append("--noMerge")
        if inputs.get("noHgFilter"):
            cmd.append("--noHgFilter")
        _add_if_value(cmd, "--kmerThreshold", inputs.get("kmerThreshold"))
        _add_if_value(cmd, "--kmerComplexity", inputs.get("kmerComplexity"))
        sketch_size = int(inputs.get("sketchSize", 0) or 0)
        if sketch_size > 0:
            cmd.extend(["-J", str(sketch_size)])
        if len(ref_files) == 1:
            cmd.extend(["-r", ref_files[0]])
        else:
            cmd.extend(["--rl", ref_list])
        if len(query_files) == 1:
            cmd.extend(["-q", query_files[0]])
        else:
            cmd.extend(["--ql", query_list])
        _add_shell_redirect(cmd, f"{out}/mashmap.out")
        commands.append(_shell_join(cmd).replace("'${GALAXY_SLOTS:-1}'", "${GALAXY_SLOTS:-1}"))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "mashmap.out"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("query")):
            return "At least one query sequence is required"
        if not _as_list(inputs.get("reflist")):
            return "At least one reference sequence is required"
        perc_identity = float(inputs.get("perc_identity", 85.0))
        if perc_identity < 0 or perc_identity > 100:
            return "perc_identity must be between 0 and 100"
        seq_length = int(inputs.get("seqLength", 5000))
        if seq_length < 1:
            return "seqLength must be at least 1"
        sketch_size = int(inputs.get("sketchSize", 0) or 0)
        if sketch_size < 0:
            return "sketchSize must be at least 0"
        kmer_threshold = inputs.get("kmerThreshold")
        if kmer_threshold not in (None, "") and float(kmer_threshold) < 0:
            return "kmerThreshold must be at least 0"
        kmer_complexity = inputs.get("kmerComplexity")
        if kmer_complexity not in (None, ""):
            complexity = float(kmer_complexity)
            if complexity < 0 or complexity > 1:
                return "kmerComplexity must be between 0 and 1"
        filter_mode = str(inputs.get("filter_mode", "map"))
        if filter_mode not in cls.FILTER_MODES:
            return f"filter_mode must be one of: {', '.join(cls.FILTER_MODES)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": (
                    "FASTA_LIST",
                    {"multiple": True, "description": "One or more query FASTA or FASTQ sequences"},
                ),
                "reflist": (
                    "FASTA_LIST",
                    {"multiple": True, "description": "One or more reference FASTA or FASTQ sequences"},
                ),
            },
            "optional": {
                "perc_identity": (
                    "FLOAT",
                    {"default": 85.0, "min": 0, "max": 100, "description": "Minimum identity threshold to report"},
                ),
                "seqLength": (
                    "INT",
                    {"default": 5000, "min": 1, "description": "Minimum segment length in base pairs"},
                ),
                "sketchSize": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Sketch size; 0 lets MashMap choose automatically"},
                ),
                "dense": (
                    "BOOLEAN",
                    {"default": True, "description": "Increase seed density for more accurate ANI estimates"},
                ),
                "kmerThreshold": (
                    "FLOAT",
                    {"default": "", "min": 0.0, "description": "Ignore the top fraction of most frequent k-mer windows"},
                ),
                "kmerComplexity": (
                    "FLOAT",
                    {"default": "", "min": 0.0, "max": 1.0, "description": "Threshold for k-mer complexity filtering"},
                ),
                "filter_mode": (
                    "STRING",
                    {
                        "default": "map",
                        "options": list(cls.FILTER_MODES),
                        "description": "Alignment filtering strategy",
                    },
                ),
                "reportPercentage": (
                    "BOOLEAN",
                    {"default": False, "description": "Report predicted ANI values in [0, 100]"},
                ),
                "noMerge": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not merge consecutive segment-level mappings"},
                ),
                "noHgFilter": (
                    "BOOLEAN",
                    {"default": False, "description": "Use MashMap2-style first-pass filtering"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
