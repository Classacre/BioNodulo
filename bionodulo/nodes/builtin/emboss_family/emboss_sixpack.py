"""EMBOSS sixpack: Display a DNA sequence with 6-frame translation and ORFs.

Generated from the suite's own ACD definition for sixpack in the pinned
emboss==6.6.0 image. ACD SHA-256: e6d4d2a5de43f10a2ad7317d6b8a1449072ea4e8cfdf685a9d99ae499f80050e

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossSixpackNode(EmbossBase):
    """Display a DNA sequence with 6-frame translation and ORFs"""

    NODE_ID = 'emboss_sixpack'
    DISPLAY_NAME = 'EMBOSS sixpack'
    CATEGORY = "emboss"
    DESCRIPTION = 'Display a DNA sequence with 6-frame translation and ORFs'
    SEARCH_ALIASES = ["emboss", 'sixpack']
    RETURN_TYPES = ('FILE', 'FILE')
    RETURN_NAMES = ('outfile', 'outseq')
    OUTPUT_FILENAMES = ('outfile.out', 'outseq.out')
    REQUIRED_EXECUTABLES = ['sixpack']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/sixpack.html"
    PATH_INPUTS = ('sequence',)
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/sixpack',
        "topics": [{'uri': 'http://edamontology.org/topic_0108', 'label': 'Translation'}, {'uri': 'http://edamontology.org/topic_0109', 'label': 'Gene finding'}, {'uri': 'http://edamontology.org/topic_0092', 'label': 'Data visualisation'}],
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
                "table": ('STRING', {'options': ['0', '1', '2', '3', '4', '5', '6', '9', '10', '11', '12', '13', '14', '15', '16', '21', '22', '23'], 'default': '0', 'description': 'Code to use'}),
                "firstorf": ('BOOLEAN', {'default': True, 'description': 'ORF at the beginning of the sequence'}),
                "lastorf": ('BOOLEAN', {'default': True, 'description': 'ORF at the end of the sequence'}),
                "mstart": ('BOOLEAN', {'default': False, 'description': 'ORF start with an M'}),
                "reverse": ('BOOLEAN', {'default': True, 'description': 'Display translation of reverse sense'}),
                "orfminsize": ('INT', {'min': 1, 'default': 1, 'description': 'Minimum size of ORFs (aa)'}),
                "uppercase": ('STRING', {'description': 'Regions to put in uppercase (eg: 4-57,78-94)'}),
                "highlight": ('STRING', {'description': 'Regions to colour in HTML (eg: 4-57 red 78-94 green)'}),
                "number": ('BOOLEAN', {'default': True, 'description': 'Number the sequences'}),
                "width": ('INT', {'min': 1, 'default': 60, 'description': 'Width of sequence to display'}),
                "length": ('INT', {'min': 0, 'default': 0, 'description': 'Line length of page (0 for indefinite)'}),
                "margin": ('INT', {'min': 0, 'default': 10, 'description': 'Margin around sequence for numbering.'}),
                "name": ('BOOLEAN', {'default': True, 'description': 'Display sequence ID'}),
                "description": ('BOOLEAN', {'default': True, 'description': 'Display description'}),
                "offset": ('INT', {'default': 1, 'description': 'Offset to start numbering the sequence from'}),
                "html": ('BOOLEAN', {'default': False, 'description': 'Use HTML formatting'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['sixpack']
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
