"""EMBOSS showorf: Display a nucleotide sequence and translation in pretty format.

Generated from the suite's own ACD definition for showorf in the pinned
emboss==6.6.0 image. ACD SHA-256: dca6a0ce09123980f2ac9fe890c78f9daf654a5da3e5dad41911ff1ccdd0e65c

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossShoworfNode(EmbossBase):
    """Display a nucleotide sequence and translation in pretty format"""

    NODE_ID = 'emboss_showorf'
    DISPLAY_NAME = 'EMBOSS showorf'
    CATEGORY = "emboss"
    DESCRIPTION = 'Display a nucleotide sequence and translation in pretty format'
    SEARCH_ALIASES = ["emboss", 'showorf']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.out',)
    REQUIRED_EXECUTABLES = ['showorf']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/showorf.html"
    PATH_INPUTS = ('sequence',)
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/showorf',
        "topics": [{'uri': 'http://edamontology.org/topic_0108', 'label': 'Translation'}, {'uri': 'http://edamontology.org/topic_0109', 'label': 'Gene finding'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0371', 'label': 'DNA translation'}, {'uri': 'http://edamontology.org/operation_0564', 'label': 'Sequence rendering'}, {'uri': 'http://edamontology.org/operation_0436', 'label': 'Coding region prediction'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "frames": ('STRING', {'options': ['0'], 'default': '1,2,3,4,5,6', 'description': 'Select one or more values'}),
                "table": ('STRING', {'options': ['0', '1', '2', '3', '4', '5', '6', '9', '10', '11', '12', '13', '14', '15', '16', '21', '22', '23'], 'default': '0', 'description': 'Genetic code to use'}),
                "ruler": ('BOOLEAN', {'default': True, 'description': 'Add a ruler'}),
                "plabel": ('BOOLEAN', {'default': True, 'description': 'Number translations'}),
                "nlabel": ('BOOLEAN', {'default': True, 'description': 'Number DNA sequence'}),
                "width": ('INT', {'min': 10, 'default': 50, 'description': 'Width of screen'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['showorf']
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
