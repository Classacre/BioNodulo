"""Assembly statistics wrapper contract."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class AssemblyStatsNode(CommandNode):
    """Render assembly metric visualisations using assembly-stats."""

    NODE_ID = "assembly_stats"
    DISPLAY_NAME = "Assembly Stats"
    REQUIRED_CONDA_PACKAGES = ["rjchallis-assembly-stats"]
    CATEGORY = "assembly"
    DESCRIPTION = "Generate assembly metric visualisations or JSON statistics from a genome FASTA file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "assembly-stats",
        "Assembly stats",
        "asm2stats.minmaxgc.pl",
        "genome assembly metrics",
        "assembly visualisation",
        "snail plot",
        "N50",
        "GC content",
    ]
    RETURN_TYPES = ("HTML_REPORT", "JSON")
    RETURN_NAMES = ("output_html", "output_json")
    REQUIRED_EXECUTABLES = ["asm2stats.minmaxgc.pl"]
    DOCUMENTATION_URL = "https://github.com/rjchallis/assembly-stats"
    CITATION_DOIS = [ASSEMBLY_STATS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ASSEMBLY_STATS_CITATION_DOI}"]
    CITATION_TEXT = ASSEMBLY_STATS_CITATION_TEXT
    VERSION = "17.02+galaxy0"
    SHELL = True

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        output_format = str(inputs.get("output_format", "html") or "html").lower()
        return "json" if output_format == "json" else "html"

    @classmethod
    def _tool_directory(cls, inputs: dict[str, Any]) -> str:
        tool_directory = inputs.get("tool_directory")
        if tool_directory:
            return shlex.quote(str(tool_directory))
        return '"${BIONODULO_ASSEMBLY_STATS_TOOL_DIR:-.}"'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_fasta = shlex.quote(str(inputs.get("input_fasta", "")))
        if cls._output_format(inputs) == "json":
            return f"asm2stats.minmaxgc.pl {input_fasta} > {shlex.quote(f'{out}/output.json')}"

        output_files = f"{out}/output_files"
        json_dir = f"{output_files}/json"
        tool_directory = cls._tool_directory(inputs)
        parts = [
            'SRC="$(dirname $(which asm2stats.pl))/../opt/assembly-stats"',
            f"mkdir -p {shlex.quote(json_dir)}",
            f'cp -r "$SRC/css/" {shlex.quote(output_files)}',
            f'cp -r "$SRC/js/" {shlex.quote(output_files)}',
            f"cp {tool_directory}/d3-tip.js {shlex.quote(f'{output_files}/js/d3-tip.js')}",
            f"cp {tool_directory}/assembly-stats.html {shlex.quote(f'{out}/output.html')}",
            f"cp {tool_directory}/assembly-stats.html {shlex.quote(output_files)}",
            f"asm2stats.minmaxgc.pl {input_fasta} > {shlex.quote(f'{json_dir}/output.assembly-stats.json')}",
        ]
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = ".json" if cls._output_format(inputs) == "json" else ".html"
        return [out / f"output{suffix}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Genome assembly FASTA"}),
            },
            "optional": {
                "output_format": (
                    "STRING",
                    {"default": "html", "options": ["html", "json"], "description": "Galaxy output format"},
                ),
            },
            "hidden": {"output": ("STRING", {}), "tool_directory": ("STRING", {})},
        }

pin_contract(AssemblyStatsNode)

__all__ = ["AssemblyStatsNode"]
