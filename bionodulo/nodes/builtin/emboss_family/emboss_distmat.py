"""EMBOSS distmat: Create a distance matrix from a multiple sequence alignment.

Generated from the suite's own ACD definition for distmat in the pinned
emboss==6.6.0 image. ACD SHA-256: bc7b8220f5a03940c3380a9d4afc50470297e936aced4850821bba4601b4e701

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossDistmatNode(EmbossBase):
    """Create a distance matrix from a multiple sequence alignment"""

    NODE_ID = 'emboss_distmat'
    DISPLAY_NAME = 'EMBOSS distmat'
    CATEGORY = "emboss"
    DESCRIPTION = 'Create a distance matrix from a multiple sequence alignment'
    SEARCH_ALIASES = ["emboss", 'distmat']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.out',)
    REQUIRED_EXECUTABLES = ['distmat']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/distmat.html"
    PATH_INPUTS = ('sequence',)
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/distmat',
        "topics": [{'uri': 'http://edamontology.org/topic_0159', 'label': 'Sequence comparison'}, {'uri': 'http://edamontology.org/topic_0084', 'label': 'Phylogenetics'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0289', 'label': 'Sequence distance matrix generation'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "nucmethod": ('STRING', {'options': ['0', '1', '2', '3', '4', '5'], 'default': '0', 'description': 'Method to use'}),
                "protmethod": ('STRING', {'options': ['0', '1', '2'], 'default': '0', 'description': 'Method to use'}),
                "ambiguous": ('BOOLEAN', {'default': False, 'description': 'Use the ambiguous codes in the calculation.'}),
                "gapweight": ('FLOAT', {'default': 0.0, 'description': 'Weight given to gaps'}),
                "position": ('INT', {'default': 123, 'description': 'Base position to analyse'}),
                "calculatea": ('BOOLEAN', {'default': False, 'description': "Calculate the nucleotide Jin-Nei parameter 'a'"}),
                "parametera": ('FLOAT', {'default': 1.0, 'description': "Nucleotide Jin-Nei parameter 'a'"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['distmat']
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
