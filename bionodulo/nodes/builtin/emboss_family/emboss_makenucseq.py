"""EMBOSS makenucseq: Create random nucleotide sequences.

Generated from the suite's own ACD definition for makenucseq in the pinned
emboss==6.6.0 image. ACD SHA-256: 1918ff64339683322ef8f390f0ad08150c7630ef6e66e19bd355979163866889

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossMakenucseqNode(EmbossBase):
    """Create random nucleotide sequences"""

    NODE_ID = 'emboss_makenucseq'
    DISPLAY_NAME = 'EMBOSS makenucseq'
    CATEGORY = "emboss"
    DESCRIPTION = 'Create random nucleotide sequences'
    SEARCH_ALIASES = ["emboss", 'makenucseq']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outseq',)
    OUTPUT_FILENAMES = ('outseq.out',)
    REQUIRED_EXECUTABLES = ['makenucseq']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/makenucseq.html"
    PATH_INPUTS = ('codonfile',)
    REQUIRED_PATH_INPUTS = ('codonfile',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/makenucseq',
        "topics": [{'uri': 'http://edamontology.org/topic_0091', 'label': 'Data handling'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0364', 'label': 'Random sequence generation'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'codonfile': ("FILE", {"description": 'Codon usage file (optional)'}),
            },
            "optional": {
                "amount": ('INT', {'min': 1, 'default': 100, 'description': 'Number of sequences created'}),
                "length": ('INT', {'min': 1, 'default': 100, 'description': 'Length of each sequence'}),
                "useinsert": ('STRING', {'default': 'N', 'description': 'Do you want to make an insert'}),
                "insert": ('STRING', {'description': 'Inserted string'}),
                "start": ('INT', {'min': 1, 'default': 1, 'description': 'Start point of inserted sequence'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['makenucseq']
        for name in cls.PATH_INPUTS:
            value = inputs.get(name)
            if value not in (None, ""):
                command.extend([f"-{name}", str(value)])
        output_dir = cls.output_dir(inputs)
        graph_flag = None
        # A stdout-only program has no output qualifier at all; its planned file
        # is filled by the executor's stdout capture instead.
        declared: list[str] = [] if False else list(['outseq'])
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
