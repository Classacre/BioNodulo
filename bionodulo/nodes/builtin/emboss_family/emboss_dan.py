"""EMBOSS dan: Calculate nucleic acid melting temperature.

Generated from the suite's own ACD definition for dan in the pinned
emboss==6.6.0 image. ACD SHA-256: 89aa650647092c15b0b28cf1e959a718bd7e4a0467d87a2f483f7a82502d26d5

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossDanNode(EmbossBase):
    """Calculate nucleic acid melting temperature"""

    NODE_ID = 'emboss_dan'
    DISPLAY_NAME = 'EMBOSS dan'
    CATEGORY = "emboss"
    DESCRIPTION = 'Calculate nucleic acid melting temperature'
    SEARCH_ALIASES = ["emboss", 'dan']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.txt',)
    REQUIRED_EXECUTABLES = ['dan']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/dan.html"
    PATH_INPUTS = ('sequence',)
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/dan',
        "topics": [{'uri': 'http://edamontology.org/topic_0094', 'label': 'Nucleic acid thermodynamics'}, {'uri': 'http://edamontology.org/topic_0157', 'label': 'Sequence composition analysis'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0455', 'label': 'Nucleic acid thermodynamic property calculation'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "windowsize": ('INT', {'min': 1, 'max': 100, 'default': 20, 'description': 'Enter window size'}),
                "shiftincrement": ('INT', {'min': 1, 'default': 1, 'description': 'Enter shift increment'}),
                "dnaconc": ('FLOAT', {'default': 50.0, 'description': 'Enter DNA concentration (nM)'}),
                "saltconc": ('FLOAT', {'default': 50.0, 'description': 'Enter salt concentration (mM)'}),
                "product": ('STRING', {'description': 'Prompt for product values'}),
                "formamide": ('FLOAT', {'default': 0.0, 'description': 'Enter percentage of formamide'}),
                "mismatch": ('FLOAT', {'default': 0.0, 'description': 'Enter percent mismatch'}),
                "prodlen": ('INT', {'description': 'Enter the product length'}),
                "thermo": ('STRING', {'description': 'Thermodynamic calculations'}),
                "temperature": ('FLOAT', {'default': 25.0, 'description': 'Enter temperature'}),
                "rna": ('BOOLEAN', {'description': 'Use RNA data values'}),
                "plot": ('STRING', {'description': 'Produce a plot'}),
                "mintemp": ('FLOAT', {'default': 55.0, 'description': 'Enter minimum temperature'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['dan']
        for name in cls.PATH_INPUTS:
            value = inputs.get(name)
            if value not in (None, ""):
                command.extend([f"-{name}", str(value)])
        output_dir = cls.output_dir(inputs)
        graph_flag = 'graph'
        # A stdout-only program has no output qualifier at all; its planned file
        # is filled by the executor's stdout capture instead.
        declared: list[str] = [] if False else list(['outfile'])
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
