"""EMBOSS einverted: Find inverted repeats in nucleotide sequences.

Generated from the suite's own ACD definition for einverted in the pinned
emboss==6.6.0 image. ACD SHA-256: 7e83460550f39b7526fa54e5777ce4d845f7d619991b668814aaf961aaa9e7e9

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossEinvertedNode(EmbossBase):
    """Find inverted repeats in nucleotide sequences"""

    NODE_ID = 'emboss_einverted'
    DISPLAY_NAME = 'EMBOSS einverted'
    CATEGORY = "emboss"
    DESCRIPTION = 'Find inverted repeats in nucleotide sequences'
    SEARCH_ALIASES = ["emboss", 'einverted']
    RETURN_TYPES = ('FILE', 'FILE')
    RETURN_NAMES = ('outfile', 'outseq')
    OUTPUT_FILENAMES = ('outfile.out', 'outseq.out')
    REQUIRED_EXECUTABLES = ['einverted']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/einverted.html"
    PATH_INPUTS = ('sequence',)
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/einverted',
        "topics": [{'uri': 'http://edamontology.org/topic_0157', 'label': 'Sequence composition analysis'}, {'uri': 'http://edamontology.org/topic_0097', 'label': 'Nucleic acid structure analysis'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0379', 'label': 'Repeat sequence detection'}, {'uri': 'http://edamontology.org/operation_0278', 'label': 'RNA secondary structure prediction'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "gap": ('INT', {'min': 0, 'default': 12, 'description': 'Gap penalty'}),
                "threshold": ('INT', {'min': 0, 'default': 50, 'description': 'Minimum score threshold'}),
                "match": ('INT', {'min': 0, 'default': 3, 'description': 'Match score'}),
                "mismatch": ('INT', {'max': 0, 'default': -4, 'description': 'Mismatch score'}),
                "maxrepeat": ('INT', {'min': 0, 'default': 2000, 'description': 'Maximum extent of repeats'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['einverted']
        for name in cls.PATH_INPUTS:
            value = inputs.get(name)
            if value not in (None, ""):
                command.extend([f"-{name}", str(value)])
        output_dir = cls.output_dir(inputs)
        graph_flag = None
        # A stdout-only program has no output qualifier at all; its planned file
        # is filled by the executor's stdout capture instead.
        declared: list[str] = [] if False else list(['outfile', 'outseq'])
        for index, flag in enumerate(declared):
            if flag == graph_flag:
                command.extend([f"-{flag}", "png", "-goutfile", str(output_dir / flag)])
            else:
                command.extend([f"-{flag}", str(output_dir / cls.OUTPUT_FILENAMES[index])])
        # Request the plot even when it is not a required output, so EMBOSS does
        # not fall back to an interactive device and hang.
        if graph_flag and graph_flag not in declared:
            command.extend([f"-{graph_flag}", "png", "-goutfile", str(output_dir / graph_flag)])
        # Required scalar parameters must be rendered too. Emitting only the
        # optional ones silently dropped inputs like fuzznuc's ``-pattern`` and
        # made the tool fail with "Bad value for '-pattern'".
        declared_types = cls.INPUT_TYPES()
        for category in ("required", "optional"):
            for name, spec in declared_types.get(category, {}).items():
                if name in cls.PATH_INPUTS:
                    continue
                value = inputs.get(name)
                if value in (None, ""):
                    continue
                declared = spec[0] if isinstance(spec, (list, tuple)) else spec
                if declared == "FILE":
                    continue
                default = spec[1].get("default") if isinstance(spec, tuple) and len(spec) > 1 else None
                if declared == "BOOLEAN":
                    command.extend([f"-{name}", "Y" if value else "N"])
                    continue
                if value == default:
                    continue
                command.extend([f"-{name}", str(value)])
        # EMBOSS prompts for confirmation on some programs; -auto makes it
        # non-interactive, which is required in a batch runner.
        command.append("-auto")
        return command
