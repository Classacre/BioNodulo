"""EMBOSS pepwindowall: Draw Kyte-Doolittle hydropathy plot for a protein alignment.

Generated from the suite's own ACD definition for pepwindowall in the pinned
emboss==6.6.0 image. ACD SHA-256: 2b5446ec7e3d4cb70a36e113e637e8da53b450f7be9cfaefb57e3092ae337111

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossPepwindowallNode(EmbossBase):
    """Draw Kyte-Doolittle hydropathy plot for a protein alignment"""

    NODE_ID = 'emboss_pepwindowall'
    DISPLAY_NAME = 'EMBOSS pepwindowall'
    CATEGORY = "emboss"
    DESCRIPTION = 'Draw Kyte-Doolittle hydropathy plot for a protein alignment'
    SEARCH_ALIASES = ["emboss", 'pepwindowall']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('graph',)
    OUTPUT_FILENAMES = ('graph.1.png',)
    REQUIRED_EXECUTABLES = ['pepwindowall']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/pepwindowall.html"
    PATH_INPUTS = ('sequences', 'datafile')
    REQUIRED_PATH_INPUTS = ('sequences',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/pepwindowall',
        "topics": [{'uri': 'http://edamontology.org/topic_0137', 'label': 'Protein hydropathy'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0401', 'label': 'Protein hydropathy calculation (from sequence)'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequences': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "window": ('INT', {'min': 1, 'default': 19, 'description': 'Window size'}),
                "normalize": ('BOOLEAN', {'default': False, 'description': 'Normalize data values'}),
                'datafile': ("FILE", {"description": 'AAINDEX entry data file'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['pepwindowall']
        for name in cls.PATH_INPUTS:
            value = inputs.get(name)
            if value not in (None, ""):
                command.extend([f"-{name}", str(value)])
        output_dir = cls.output_dir(inputs)
        graph_flag = 'graph'
        # A stdout-only program has no output qualifier at all; its planned file
        # is filled by the executor's stdout capture instead.
        declared: list[str] = [] if False else list(['graph'])
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
