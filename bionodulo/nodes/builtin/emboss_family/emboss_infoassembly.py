"""EMBOSS infoassembly: Display information about assemblies.

Generated from the suite's own ACD definition for infoassembly in the pinned
emboss==6.6.0 image. ACD SHA-256: 3b561fc711231cfd416ecbd369c14cc1b4cfaa2cebcd40024330272879a3f201

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossInfoassemblyNode(EmbossBase):
    """Display information about assemblies"""

    NODE_ID = 'emboss_infoassembly'
    DISPLAY_NAME = 'EMBOSS infoassembly'
    CATEGORY = "emboss"
    DESCRIPTION = 'Display information about assemblies'
    SEARCH_ALIASES = ["emboss", 'infoassembly']
    RETURN_TYPES = ('FILE', 'FILE', 'FILE')
    RETURN_NAMES = ('outassembly', 'gcbiasmetricsoutfile', 'qualvaluesdistoutfile')
    OUTPUT_FILENAMES = ('outassembly.out', 'gcbiasmetricsoutfile.out', 'qualvaluesdistoutfile.out')
    REQUIRED_EXECUTABLES = ['infoassembly']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/infoassembly.html"
    PATH_INPUTS = ('refsequence',)
    REQUIRED_PATH_INPUTS = ('refsequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/infoassembly',
        "topics": [{'uri': 'http://edamontology.org/topic_0090', 'label': 'Data search and retrieval'}],
        "operations": [{'uri': 'http://edamontology.org/operation_2422', 'label': 'Data retrieval'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "assembly": ('STRING', {'description': 'assembly'}),
                'refsequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "windowsize": ('INT', {'default': 100, 'description': 'Window size'}),
                "bisulfite": ('BOOLEAN', {'default': False, 'description': 'Bisulfite treated'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['infoassembly']
        for name in cls.PATH_INPUTS:
            value = inputs.get(name)
            if value not in (None, ""):
                command.extend([f"-{name}", str(value)])
        output_dir = cls.output_dir(inputs)
        graph_flag = None
        # A stdout-only program has no output qualifier at all; its planned file
        # is filled by the executor's stdout capture instead.
        declared: list[str] = [] if False else list(['outassembly', 'gcbiasmetricsoutfile', 'qualvaluesdistoutfile'])
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
