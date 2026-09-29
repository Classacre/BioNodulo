"""EMBOSS getorf: Find and extract open reading frames (ORFs).

Generated from the suite's own ACD definition for getorf in the pinned
emboss==6.6.0 image. ACD SHA-256: 94cec2f32ec9b72f7725dbb50f99a20b57ab49dcf96214110fbaa2ddca7f2c09

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossGetorfNode(EmbossBase):
    """Find and extract open reading frames (ORFs)"""

    NODE_ID = 'emboss_getorf'
    DISPLAY_NAME = 'EMBOSS getorf'
    CATEGORY = "emboss"
    DESCRIPTION = 'Find and extract open reading frames (ORFs)'
    SEARCH_ALIASES = ["emboss", 'getorf']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outseq',)
    OUTPUT_FILENAMES = ('outseq.out',)
    REQUIRED_EXECUTABLES = ['getorf']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/getorf.html"
    PATH_INPUTS = ('sequence',)
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/getorf',
        "topics": [{'uri': 'http://edamontology.org/topic_0109', 'label': 'Gene finding'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0436', 'label': 'Coding region prediction'}, {'uri': 'http://edamontology.org/operation_0371', 'label': 'DNA translation'}],
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
                "minsize": ('INT', {'default': 30, 'description': 'Minimum nucleotide size of ORF to report'}),
                "maxsize": ('INT', {'default': 1000000, 'description': 'Maximum nucleotide size of ORF to report'}),
                "find": ('STRING', {'options': ['0', '1', '2', '3', '4', '5', '6'], 'default': '0', 'description': 'Type of output'}),
                "methionine": ('BOOLEAN', {'default': True, 'description': 'Change initial START codons to Methionine'}),
                "circular": ('BOOLEAN', {'default': False, 'description': 'Is the sequence circular'}),
                "reverse": ('BOOLEAN', {'default': True, 'description': 'Find ORFs in the reverse sequence'}),
                "flanking": ('INT', {'default': 100, 'description': 'Number of flanking nucleotides to report'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['getorf']
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
