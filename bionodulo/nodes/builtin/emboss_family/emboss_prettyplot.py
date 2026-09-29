"""EMBOSS prettyplot: Draw a sequence alignment with pretty formatting.

Generated from the suite's own ACD definition for prettyplot in the pinned
emboss==6.6.0 image. ACD SHA-256: a65f568147d66906ab0bc4216ebae7944d2eee8b7db216151a9c045489a6157f

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossPrettyplotNode(EmbossBase):
    """Draw a sequence alignment with pretty formatting"""

    NODE_ID = 'emboss_prettyplot'
    DISPLAY_NAME = 'EMBOSS prettyplot'
    CATEGORY = "emboss"
    DESCRIPTION = 'Draw a sequence alignment with pretty formatting'
    SEARCH_ALIASES = ["emboss", 'prettyplot']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('graph',)
    OUTPUT_FILENAMES = ('graph.1.png',)
    REQUIRED_EXECUTABLES = ['prettyplot']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/prettyplot.html"
    PATH_INPUTS = ('sequences', 'matrixfile')
    REQUIRED_PATH_INPUTS = ('sequences',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/prettyplot',
        "topics": [{'uri': 'http://edamontology.org/topic_0182', 'label': 'Sequence alignment'}, {'uri': 'http://edamontology.org/topic_0092', 'label': 'Data visualisation'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0562', 'label': 'Sequence alignment reformatting'}, {'uri': 'http://edamontology.org/operation_0564', 'label': 'Sequence rendering'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequences': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "residuesperline": ('INT', {'default': 50, 'description': 'Number of residues to be displayed on each line'}),
                "blocksperline": ('INT', {'min': 1, 'default': 1, 'description': 'Blocks of residues on each line'}),
                "ccolours": ('BOOLEAN', {'default': True, 'description': 'Colour residues by their consensus value.'}),
                "cidentity": ('STRING', {'default': 'RED', 'description': 'Colour to display identical residues (RED)'}),
                "csimilarity": ('STRING', {'default': 'GREEN', 'description': 'Colour to display similar residues (GREEN)'}),
                "cother": ('STRING', {'default': 'BLACK', 'description': 'Colour to display other residues (BLACK)'}),
                "docolour": ('BOOLEAN', {'default': False, 'description': 'Colour residues by table oily, amide etc.'}),
                "shade": ('STRING', {'description': 'Shading'}),
                "pair": ('STRING', {'default': '1.5,1.0,0.5', 'description': 'Values to represent identical similar related'}),
                "identity": ('INT', {'min': 0, 'default': 0, 'description': 'Only match those which are identical in all sequences.'}),
                "doboxes": ('BOOLEAN', {'default': True, 'description': 'Display prettyboxes'}),
                "boxcol": ('BOOLEAN', {'default': False, 'description': 'Colour the background in the boxes'}),
                "boxuse": ('STRING', {'default': 'GREY', 'description': 'Colour to be used for background. (GREY)'}),
                "name": ('BOOLEAN', {'default': True, 'description': 'Display the sequence names'}),
                "maxnamelen": ('INT', {'default': 10, 'description': 'Margin size for the sequence name.'}),
                "number": ('BOOLEAN', {'default': True, 'description': 'Display the residue number'}),
                "listoptions": ('BOOLEAN', {'default': True, 'description': 'Display the date and options used'}),
                "ratio": ('FLOAT', {'default': 0.5, 'description': 'Plurality ratio for a consensus match'}),
                "consensus": ('BOOLEAN', {'default': False, 'description': 'Display the consensus'}),
                "collision": ('BOOLEAN', {'default': True, 'description': 'Allow collisions in calculating consensus'}),
                "alternative": ('STRING', {'options': ['0', '1', '2', '3'], 'default': '0', 'description': 'Use alternative collisions routine'}),
                "showscore": ('INT', {'default': -1, 'description': 'Print residue scores'}),
                "portrait": ('BOOLEAN', {'default': False, 'description': 'Set page to Portrait'}),
                'matrixfile': ("FILE", {"description": 'Matrix file'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['prettyplot']
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
