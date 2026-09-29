"""EMBOSS cirdna: Draw circular map of DNA constructs.

Generated from the suite's own ACD definition for cirdna in the pinned
emboss==6.6.0 image. ACD SHA-256: 889ae6a13cc8eed7ba94b1cee722392227f5cf568613d70710422e4833ffafcd

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossCirdnaNode(EmbossBase):
    """Draw circular map of DNA constructs"""

    NODE_ID = 'emboss_cirdna'
    DISPLAY_NAME = 'EMBOSS cirdna'
    CATEGORY = "emboss"
    DESCRIPTION = 'Draw circular map of DNA constructs'
    SEARCH_ALIASES = ["emboss", 'cirdna']
    RETURN_TYPES = ('FILE', 'FILE')
    RETURN_NAMES = ('posticks', 'posblocks')
    OUTPUT_FILENAMES = ('posticks.out', 'posblocks.out')
    REQUIRED_EXECUTABLES = ['cirdna']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/cirdna.html"
    PATH_INPUTS = ('infile',)
    REQUIRED_PATH_INPUTS = ('infile',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/cirdna',
        "topics": [{'uri': 'http://edamontology.org/topic_0092', 'label': 'Data visualisation'}, {'uri': 'http://edamontology.org/topic_0640', 'label': 'Nucleic acid sequence analysis'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0578', 'label': 'DNA circular map rendering'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'infile': ("FILE", {"description": 'Commands to the cirdna drawing program file'}),
            },
            "optional": {
                "maxgroups": ('INT', {'min': 1, 'default': 20, 'description': 'Maximum number of groups'}),
                "maxlabels": ('INT', {'min': 1, 'default': 10000, 'description': 'Maximum number of labels'}),
                "ruler": ('BOOLEAN', {'default': True, 'description': 'Draw a ruler'}),
                "blocktype": ('STRING', {'options': ['Open', 'Filled', 'Outline'], 'default': 'Filled', 'description': 'Type of blocks'}),
                "originangle": ('FLOAT', {'default': 90.0, 'description': "Position in degrees of the molecule's origin on the circle"}),
                "intersymbol": ('BOOLEAN', {'default': True, 'description': 'Horizontal junctions between blocks'}),
                "intercolour": ('INT', {'min': 0, 'max': 15, 'default': 1, 'description': 'Colour of junctions between blocks (enter a colour number)'}),
                "interticks": ('BOOLEAN', {'default': False, 'description': 'Horizontal junctions between ticks'}),
                "gapsize": ('INT', {'min': 0, 'default': 500, 'description': 'Interval between ticks in the ruler'}),
                "ticklines": ('BOOLEAN', {'default': False, 'description': "Vertical lines at the ruler's ticks"}),
                "textheight": ('FLOAT', {'default': 1.0, 'description': 'Text scale factor'}),
                "textlength": ('FLOAT', {'default': 1.0, 'description': 'Length of text multiplier'}),
                "tickheight": ('FLOAT', {'default': 1.0, 'description': 'Height of ticks multiplier'}),
                "blockheight": ('FLOAT', {'default': 1.0, 'description': 'Height of blocks multiplier'}),
                "rangeheight": ('FLOAT', {'default': 1.0, 'description': 'Height of range ends multiplier'}),
                "gapgroup": ('FLOAT', {'default': 1.0, 'description': 'Space between groups multiplier'}),
                "postext": ('FLOAT', {'default': 1.0, 'description': 'Space between text and ticks, blocks, and ranges multiplier'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['cirdna']
        for name in cls.PATH_INPUTS:
            value = inputs.get(name)
            if value not in (None, ""):
                command.extend([f"-{name}", str(value)])
        output_dir = cls.output_dir(inputs)
        graph_flag = 'graphout'
        # A stdout-only program has no output qualifier at all; its planned file
        # is filled by the executor's stdout capture instead.
        declared: list[str] = [] if False else list(['posticks', 'posblocks'])
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
