"""EMBOSS showpep: Display protein sequences with features in pretty format.

Generated from the suite's own ACD definition for showpep in the pinned
emboss==6.6.0 image. ACD SHA-256: 04b9b1efd32e07a20dc91ae44b2f5bcccbedc3fe0fa1003af1a9e945143aa4a6

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossShowpepNode(EmbossBase):
    """Display protein sequences with features in pretty format"""

    NODE_ID = 'emboss_showpep'
    DISPLAY_NAME = 'EMBOSS showpep'
    CATEGORY = "emboss"
    DESCRIPTION = 'Display protein sequences with features in pretty format'
    SEARCH_ALIASES = ["emboss", 'showpep']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.out',)
    REQUIRED_EXECUTABLES = ['showpep']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/showpep.html"
    PATH_INPUTS = ('sequence',)
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/showpep',
        "topics": [{'uri': 'http://edamontology.org/topic_0092', 'label': 'Data visualisation'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0564', 'label': 'Sequence rendering'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "format": ('STRING', {'options': ['0'], 'default': '2', 'description': 'Display format'}),
                "things": ('STRING', {'options': ['S'], 'default': 'B,N,T,S,A,F', 'description': 'Enter a list of things to display'}),
                "uppercase": ('STRING', {'description': 'Regions to put in uppercase (eg: 4-57,78-94)'}),
                "highlight": ('STRING', {'description': 'Regions to colour in HTML (eg: 4-57 red 78-94 green)'}),
                "annotation": ('STRING', {'description': 'Regions to mark (eg: 4-57 promoter region 78-94 first exon)'}),
                "sourcematch": ('STRING', {'default': '*', 'description': 'Source of feature to display'}),
                "typematch": ('STRING', {'default': '*', 'description': 'Type of feature to display'}),
                "minscore": ('FLOAT', {'default': 0.0, 'description': 'Minimum score of feature to display'}),
                "maxscore": ('FLOAT', {'default': 0.0, 'description': 'Maximum score of feature to display'}),
                "tagmatch": ('STRING', {'default': '*', 'description': 'Tag of feature to display'}),
                "valuematch": ('STRING', {'default': '*', 'description': 'Value of feature tags to display'}),
                "stricttags": ('BOOLEAN', {'default': False, 'description': 'Only display the matching tags'}),
                "threeletter": ('BOOLEAN', {'default': False, 'description': 'Display protein sequences in three-letter code'}),
                "number": ('BOOLEAN', {'default': False, 'description': 'Number the sequences'}),
                "width": ('INT', {'min': 1, 'default': 60, 'description': 'Width of sequence to display'}),
                "length": ('INT', {'min': 0, 'default': 0, 'description': 'Line length of page (0 for indefinite)'}),
                "margin": ('INT', {'min': 0, 'default': 10, 'description': 'Margin around sequence for numbering'}),
                "name": ('BOOLEAN', {'default': True, 'description': 'Show sequence ID'}),
                "description": ('BOOLEAN', {'default': True, 'description': 'Show description'}),
                "offset": ('INT', {'default': 1, 'description': 'Offset to start numbering the sequence from'}),
                "html": ('BOOLEAN', {'default': False, 'description': 'Use HTML formatting'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['showpep']
        for name in cls.PATH_INPUTS:
            value = inputs.get(name)
            if value not in (None, ""):
                command.extend([f"-{name}", str(value)])
        output_dir = cls.output_dir(inputs)
        graph_flag = None
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
