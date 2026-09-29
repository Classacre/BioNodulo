"""EMBOSS rebaseextract: Process the REBASE database for use by restriction enzyme applications.

Generated from the suite's own ACD definition for rebaseextract in the pinned
emboss==6.6.0 image. ACD SHA-256: 58717f67d11f4a1304d2bf29c16db04dc3f7df6e28701cd989e34ebba8dbb293

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossRebaseextractNode(EmbossBase):
    """Process the REBASE database for use by restriction enzyme applications"""

    NODE_ID = 'emboss_rebaseextract'
    DISPLAY_NAME = 'EMBOSS rebaseextract'
    CATEGORY = "emboss"
    DESCRIPTION = 'Process the REBASE database for use by restriction enzyme applications'
    SEARCH_ALIASES = ["emboss", 'rebaseextract']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('stdout',)
    OUTPUT_FILENAMES = ('stdout.txt',)
    STDOUT_OUTPUT_INDEX = 0
    REQUIRED_EXECUTABLES = ['rebaseextract']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/rebaseextract.html"
    PATH_INPUTS = ('infile', 'protofile')
    REQUIRED_PATH_INPUTS = ('infile', 'protofile')
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/rebaseextract',
        "topics": [{'uri': 'http://edamontology.org/topic_0100', 'label': 'Nucleic acid restriction'}, {'uri': 'http://edamontology.org/topic_0091', 'label': 'Data handling'}],
        "operations": [{'uri': 'http://edamontology.org/operation_1812', 'label': 'Data loading'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'infile': ("FILE", {"description": 'REBASE database withrefm file'}),
                'protofile': ("FILE", {"description": 'REBASE database proto file'}),
            },
            "optional": {
                "equivalences": ('BOOLEAN', {'default': True, 'description': 'Create prototype equivalence file'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['rebaseextract']
        for name in cls.PATH_INPUTS:
            value = inputs.get(name)
            if value not in (None, ""):
                command.extend([f"-{name}", str(value)])
        output_dir = cls.output_dir(inputs)
        graph_flag = None
        # A stdout-only program has no output qualifier at all; its planned file
        # is filled by the executor's stdout capture instead.
        declared: list[str] = [] if True else list(['stdout'])
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
