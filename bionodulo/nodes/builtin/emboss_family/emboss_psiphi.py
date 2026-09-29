"""EMBOSS psiphi: Calculates phi and psi torsion angles from protein coordinates.

Generated from the suite's own ACD definition for psiphi in the pinned
emboss==6.6.0 image. ACD SHA-256: 8207686fdd0131a0a032ad9f539996ed40db03921c29732f5550ce3660f73c58

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossPsiphiNode(EmbossBase):
    """Calculates phi and psi torsion angles from protein coordinates"""

    NODE_ID = 'emboss_psiphi'
    DISPLAY_NAME = 'EMBOSS psiphi'
    CATEGORY = "emboss"
    DESCRIPTION = 'Calculates phi and psi torsion angles from protein coordinates'
    SEARCH_ALIASES = ["emboss", 'psiphi']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.txt',)
    REQUIRED_EXECUTABLES = ['psiphi']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/psiphi.html"
    PATH_INPUTS = ('infile',)
    REQUIRED_PATH_INPUTS = ('infile',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/psiphi',
        "topics": [{'uri': 'http://edamontology.org/topic_2814', 'label': 'Protein structure analysis'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0249', 'label': 'Torsion angle calculation'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'infile': ("FILE", {"description": 'Clean protein structure coordinates file'}),
            },
            "optional": {
                "chainnumber": ('INT', {'min': 1, 'default': 1, 'description': 'Number of the chain for which torsion angles should be calculated'}),
                "startresiduenumber": ('INT', {'min': 1, 'default': 1, 'description': 'First residue in chain for which torsion angles should be calculated'}),
                "finishresiduenumber": ('INT', {'default': 1, 'description': 'Last residue in chain for which torsion angles should be calculated (1 = last residue)'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['psiphi']
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
