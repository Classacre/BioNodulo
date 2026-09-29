"""EMBOSS pepcoil: Predict coiled coil regions in protein sequences.

Generated from the suite's own ACD definition for pepcoil in the pinned
emboss==6.6.0 image. ACD SHA-256: bf96c828b314408fbe45e47549d5d638fcc5ed81d10f7598cec9f7bbce0010df

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossPepcoilNode(EmbossBase):
    """Predict coiled coil regions in protein sequences"""

    NODE_ID = 'emboss_pepcoil'
    DISPLAY_NAME = 'EMBOSS pepcoil'
    CATEGORY = "emboss"
    DESCRIPTION = 'Predict coiled coil regions in protein sequences'
    SEARCH_ALIASES = ["emboss", 'pepcoil']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.txt',)
    REQUIRED_EXECUTABLES = ['pepcoil']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/pepcoil.html"
    PATH_INPUTS = ('sequence',)
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/pepcoil',
        "topics": [{'uri': 'http://edamontology.org/topic_0178', 'label': 'Protein secondary structure prediction'}, {'uri': 'http://edamontology.org/topic_0736', 'label': 'Protein domains and folds'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0268', 'label': 'Protein super-secondary structure prediction'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "window": ('INT', {'min': 7, 'max': 28, 'default': 28, 'description': 'Window size'}),
                "coil": ('BOOLEAN', {'default': True, 'description': 'Report coiled coil regions'}),
                "frame": ('BOOLEAN', {'description': 'Show coil frameshifts'}),
                "other": ('BOOLEAN', {'default': False, 'description': 'Report non coiled coil regions'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['pepcoil']
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
