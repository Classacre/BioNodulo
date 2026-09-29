"""EMBOSS prophet: Scan one or more sequences with a Gribskov or Henikoff profile.

Generated from the suite's own ACD definition for prophet in the pinned
emboss==6.6.0 image. ACD SHA-256: bd9b88e44d03bcc019951824c26b563b06e5d7c60dd4b25e360a9f35e00ec15c

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossProphetNode(EmbossBase):
    """Scan one or more sequences with a Gribskov or Henikoff profile"""

    NODE_ID = 'emboss_prophet'
    DISPLAY_NAME = 'EMBOSS prophet'
    CATEGORY = "emboss"
    DESCRIPTION = 'Scan one or more sequences with a Gribskov or Henikoff profile'
    SEARCH_ALIASES = ["emboss", 'prophet']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.out',)
    REQUIRED_EXECUTABLES = ['prophet']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/prophet.html"
    PATH_INPUTS = ('sequence', 'infile')
    REQUIRED_PATH_INPUTS = ('sequence', 'infile')
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/prophet',
        "topics": [{'uri': 'http://edamontology.org/topic_0188', 'label': 'Sequence profiles and HMMs'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0300', 'label': 'Sequence-profile alignment construction'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
                'infile': ("FILE", {"description": 'Profile or weight matrix file'}),
            },
            "optional": {
                "gapopen": ('FLOAT', {'default': 1.0, 'description': 'Gap opening coefficient'}),
                "gapextend": ('FLOAT', {'default': 1.0, 'description': 'Gap extension coefficient'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['prophet']
        for name in cls.PATH_INPUTS:
            value = inputs.get(name)
            if value not in (None, ""):
                command.extend([f"-{name}", str(value)])
        output_dir = cls.output_dir(inputs)
        graph_flag = None
        # A stdout-only program has no output qualifier at all; its planned file
        # is filled by the executor's stdout capture instead.
        declared: list[str] = [] if False else list(['outfile'])
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
