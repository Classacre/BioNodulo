"""EMBOSS seqretsplit: Read sequences and write them to individual files.

Generated from the suite's own ACD definition for seqretsplit in the pinned
emboss==6.6.0 image. ACD SHA-256: d536f134c0a4c55f7836c7c734c8126ea65fd7cca3dfc5cdc99630130e34354b

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossSeqretsplitNode(EmbossBase):
    """Read sequences and write them to individual files"""

    NODE_ID = 'emboss_seqretsplit'
    DISPLAY_NAME = 'EMBOSS seqretsplit'
    CATEGORY = "emboss"
    DESCRIPTION = 'Read sequences and write them to individual files'
    SEARCH_ALIASES = ["emboss", 'seqretsplit']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outseq',)
    OUTPUT_FILENAMES = ('outseq.out',)
    REQUIRED_EXECUTABLES = ['seqretsplit']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/seqretsplit.html"
    PATH_INPUTS = ('sequence',)
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/seqretsplit',
        "topics": [{'uri': 'http://edamontology.org/topic_0091', 'label': 'Data handling'}, {'uri': 'http://edamontology.org/topic_0090', 'label': 'Data search and retrieval'}],
        "operations": [{'uri': 'http://edamontology.org/operation_1813', 'label': 'Sequence retrieval'}, {'uri': 'http://edamontology.org/operation_2121', 'label': 'Sequence file processing'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "feature": ('BOOLEAN', {'description': 'Use feature information'}),
                "firstonly": ('BOOLEAN', {'description': 'Read one sequence and stop'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['seqretsplit']
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
