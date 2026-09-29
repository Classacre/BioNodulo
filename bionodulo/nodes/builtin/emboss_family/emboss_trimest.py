"""EMBOSS trimest: Remove poly-A tails from nucleotide sequences.

Generated from the suite's own ACD definition for trimest in the pinned
emboss==6.6.0 image. ACD SHA-256: cd2a21e1aeb88c102781369d252bb39cf72475373a0076316cf0b17292355775

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossTrimestNode(EmbossBase):
    """Remove poly-A tails from nucleotide sequences"""

    NODE_ID = 'emboss_trimest'
    DISPLAY_NAME = 'EMBOSS trimest'
    CATEGORY = "emboss"
    DESCRIPTION = 'Remove poly-A tails from nucleotide sequences'
    SEARCH_ALIASES = ["emboss", 'trimest']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outseq',)
    OUTPUT_FILENAMES = ('outseq.out',)
    REQUIRED_EXECUTABLES = ['trimest']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/trimest.html"
    PATH_INPUTS = ('sequence',)
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/trimest',
        "topics": [{'uri': 'http://edamontology.org/topic_0747', 'label': 'Nucleic acid sites and features'}, {'uri': 'http://edamontology.org/topic_0090', 'label': 'Data search and retrieval'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0428', 'label': 'PolyA signal detection'}, {'uri': 'http://edamontology.org/operation_0369', 'label': 'Sequence cutting'}, {'uri': 'http://edamontology.org/operation_0363', 'label': 'Nucleic acid sequence reverse and complement'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "minlength": ('INT', {'min': 1, 'default': 4, 'description': 'Minimum length of a poly-A tail'}),
                "mismatches": ('INT', {'min': 0, 'default': 1, 'description': 'Number of contiguous mismatches allowed in a tail'}),
                "reverse": ('BOOLEAN', {'default': True, 'description': 'Write the reverse complement when poly-T is removed'}),
                "tolower": ('STRING', {'default': 'N', 'description': 'Change poly-A tail to lower-case'}),
                "fiveprime": ('BOOLEAN', {'default': True, 'description': "Remove poly-T tails at the 5' end of the sequence."}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['trimest']
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
