"""EMBOSS edialign: Local multiple alignment of sequences.

Generated from the suite's own ACD definition for edialign in the pinned
emboss==6.6.0 image. ACD SHA-256: fd3e04ebd7bf7ae9febf3200902d316312d20730b88991f196c01d588cd7f849

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossEdialignNode(EmbossBase):
    """Local multiple alignment of sequences"""

    NODE_ID = 'emboss_edialign'
    DISPLAY_NAME = 'EMBOSS edialign'
    CATEGORY = "emboss"
    DESCRIPTION = 'Local multiple alignment of sequences'
    SEARCH_ALIASES = ["emboss", 'edialign']
    RETURN_TYPES = ('FILE', 'FILE')
    RETURN_NAMES = ('outfile', 'outseq')
    OUTPUT_FILENAMES = ('outfile.out', 'outseq.out')
    REQUIRED_EXECUTABLES = ['edialign']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/edialign.html"
    PATH_INPUTS = ('sequences',)
    REQUIRED_PATH_INPUTS = ('sequences',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/edialign',
        "topics": [{'uri': 'http://edamontology.org/topic_0182', 'label': 'Sequence alignment'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0495', 'label': 'Multiple sequence alignment construction (local)'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequences': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "nucmode": ('STRING', {'options': ['n', 'nt', 'ma'], 'default': 'n', 'description': 'Nucleic acid sequence alignment mode'}),
                "revcomp": ('BOOLEAN', {'default': False, 'description': 'Also consider the reverse complement'}),
                "overlapw": ('STRING', {'default': 'default (when Nseq =< 35)', 'description': 'Use overlap weights'}),
                "linkage": ('STRING', {'options': ['UPGMA', 'max', 'min'], 'default': 'UPGMA', 'description': 'Clustering method to construct sequence tree'}),
                "maxfragl": ('INT', {'min': 0, 'default': 40, 'description': 'Maximum fragment length'}),
                "fragmat": ('BOOLEAN', {'default': False, 'description': 'Consider only N-fragment pairs that start with two matches'}),
                "fragsim": ('INT', {'min': 0, 'default': 4, 'description': 'Consider only P-fragment pairs if first amino acid or codon pair has similarity score of at least n'}),
                "itscore": ('BOOLEAN', {'default': False, 'description': 'Use iterative score'}),
                "threshold": ('FLOAT', {'default': 0.0, 'description': 'Threshold for considering diagonal for alignment'}),
                "mask": ('BOOLEAN', {'default': False, 'description': "Replace unaligned characters by stars '*' rather then putting them in lowercase"}),
                "dostars": ('BOOLEAN', {'default': False, 'description': 'Activate writing of stars instead of numbers'}),
                "starnum": ('INT', {'min': 0, 'default': 4, 'description': "Put up to n stars '*' instead of digits 0-9 to indicate level of conservation"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['edialign']
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
