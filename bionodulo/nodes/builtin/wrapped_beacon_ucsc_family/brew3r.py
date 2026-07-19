"""BREW3R annotation repair node."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_beacon_ucsc_family.adapter import (
    ASSET_SHA256,
    BREW3R_CONTAINER,
    BREW3R_CONTAINER_DIGEST,
    BREW3R_DOCKERFILE_GIT_COMMIT,
    BREW3R_PLATFORM,
    asset_path,
    pin_contract,
)

class Brew3rRNode(CommandNode):
    """Extend GTF annotations at 3' ends with BREW3R.r."""

    NODE_ID = "brew3r_r"
    DISPLAY_NAME = "BREW3R.r"
    REQUIRED_CONDA_PACKAGES = ["bioconductor-brew3r.r", "bioconductor-rtracklayer", "r-getopt"]
    CATEGORY = "annotation"
    DESCRIPTION = "Extend GTF annotations at 3' ends with another GTF while preventing new gene overlaps."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BREW3R.r",
        "brew3r_r",
        "extend GTF",
        "GTF extension",
        "3-prime exon extension",
        "StringTie annotation extension",
    ]
    RETURN_TYPES = ("GTF", "TSV")
    RETURN_NAMES = ("output", "output_table")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = BREW3R_R_CITATION_URL
    CITATION_URLS = [BREW3R_R_CITATION_URL]
    CITATION_TEXT = BREW3R_R_CITATION_TEXT
    VERSION = "1.0.2+galaxy1"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.gtf"

    @classmethod
    def _table_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_table.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "Rscript",
            str(inputs.get("script_path") or asset_path("brew3r.r_script.R")),
            "--gtf_to_extend",
            str(inputs.get("gtf_to_extend", "")),
            "--gtf_to_overlap",
            str(inputs.get("gtf_to_overlap", "")),
        ]
        if inputs.get("sup_output", False):
            cmd.extend(["--sup_output", cls._table_path(inputs)])
        if inputs.get("no_add", False):
            cmd.append("--no_add")
        _add_if_value(cmd, "--exclude_pattern", inputs.get("exclude_pattern"))
        if inputs.get("filter_unstranded", False):
            cmd.append("--filter_unstranded")
        cmd.extend(["-o", cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "output.gtf"]
        if inputs.get("sup_output", False):
            outputs.append(out / "output_table.tsv")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("gtf_to_extend", "")).strip():
            return "gtf_to_extend is required"
        if not str(inputs.get("gtf_to_overlap", "")).strip():
            return "gtf_to_overlap is required"
        for key in ("sup_output", "no_add", "filter_unstranded"):
            value = inputs.get(key)
            if value is not None and not isinstance(value, bool):
                return f"{key} must be a boolean"
        if any(quote in str(inputs.get("exclude_pattern", "")) for quote in ("'", '"')):
            return "exclude_pattern must not contain quotes"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gtf_to_extend": ("GTF", {"description": "Input GTF annotation to extend at 3' ends"}),
                "gtf_to_overlap": ("GTF", {"description": "Template GTF annotation used to extend the input"}),
            },
            "optional": {
                "sup_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Write a supplementary overlap-resolution table"},
                ),
                "no_add": ("BOOLEAN", {"default": False, "description": "Do not add new exons"}),
                "exclude_pattern": (
                    "STRING",
                    {"default": "", "description": "Regular-expression pattern for gene names that should not be extended"},
                ),
                "filter_unstranded": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Filter unstranded template intervals that overlap genes on both strands",
                    },
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Optional override; blank uses the pinned bundled BREW3R.r script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(
    [Brew3rRNode],
    runtime_version="1.0.2",
    package_constraint="Galaxy wrapper requires the pinned lldelisle/brew3r:v2 container",
)
Brew3rRNode.CONTAINER_IMAGE = BREW3R_CONTAINER
Brew3rRNode.CONTAINER_DIGEST = BREW3R_CONTAINER_DIGEST
Brew3rRNode.CONTAINER_PLATFORM = BREW3R_PLATFORM
Brew3rRNode.CONTAINER_DOCKERFILE_GIT_COMMIT = BREW3R_DOCKERFILE_GIT_COMMIT
Brew3rRNode.WRAPPER_ASSET_SHA256 = ASSET_SHA256["brew3r.r_script.R"]
Brew3rRNode.RUNTIME_EXECUTION_GAP = (
    "CommandNode currently executes the host Pixi environment; the authoritative wrapper used the pinned amd64 container."
)
