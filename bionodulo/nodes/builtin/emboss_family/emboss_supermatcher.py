"""EMBOSS supermatcher: Calculate approximate local pair-wise alignments of larger sequences.

Generated from the suite's own ACD definition for supermatcher in the pinned
emboss==6.6.0 image. ACD SHA-256: 5436e023eafe40b460c0ad53e6643f6673525e5cb01dd48d41966c4246715d9c

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossSupermatcherNode(EmbossBase):
    """Calculate approximate local pair-wise alignments of larger sequences"""

    NODE_ID = 'emboss_supermatcher'
    DISPLAY_NAME = 'EMBOSS supermatcher'
    CATEGORY = "emboss"
    DESCRIPTION = 'Calculate approximate local pair-wise alignments of larger sequences'
    SEARCH_ALIASES = ["emboss", 'supermatcher']
    RETURN_TYPES = ('FILE', 'FILE')
    RETURN_NAMES = ('outfile', 'errfile')
    OUTPUT_FILENAMES = ('outfile.out', 'errfile.out')
    REQUIRED_EXECUTABLES = ['supermatcher']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/supermatcher.html"
    PATH_INPUTS = ('asequence', 'bsequence', 'datafile')
    REQUIRED_PATH_INPUTS = ('asequence', 'bsequence')
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/supermatcher',
        "topics": [{'uri': 'http://edamontology.org/topic_0182', 'label': 'Sequence alignment'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0493', 'label': 'Pairwise sequence alignment construction (local)'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'asequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
                'bsequence': ((("FASTA", "FILE")), {"description": 'Input file'}),
            },
            "optional": {
                "minscore": ('FLOAT', {'default': 0.0, 'description': 'Minimum alignment score'}),
                "gapopen": ('FLOAT', {'description': 'Gap opening penalty'}),
                "gapextend": ('FLOAT', {'description': 'Gap extension penalty'}),
                "width": ('INT', {'min': 1, 'default': 16, 'description': 'Alignment width'}),
                "wordlen": ('INT', {'min': 3, 'default': 6, 'description': 'Word length for initial matching'}),
                'datafile': ("FILE", {"description": 'Matrix file'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['supermatcher']
        for name in cls.PATH_INPUTS:
            value = inputs.get(name)
            if value not in (None, ""):
                command.extend([f"-{name}", str(value)])
        output_dir = cls.output_dir(inputs)
        graph_flag = None
        # A stdout-only program has no output qualifier at all; its planned file
        # is filled by the executor's stdout capture instead.
        declared: list[str] = [] if False else list(['outfile', 'errfile'])
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
