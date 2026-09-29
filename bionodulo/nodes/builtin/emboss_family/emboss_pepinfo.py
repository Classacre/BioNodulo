"""EMBOSS pepinfo: Plot amino acid properties of a protein sequence in parallel..

Generated from the suite's own ACD definition for pepinfo in the pinned
emboss==6.6.0 image. ACD SHA-256: 1c0f2f4723d836587e023802380b399b53a97f13594f69ec1c4b39147a5ed06b

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossPepinfoNode(EmbossBase):
    """Plot amino acid properties of a protein sequence in parallel."""

    NODE_ID = 'emboss_pepinfo'
    DISPLAY_NAME = 'EMBOSS pepinfo'
    CATEGORY = "emboss"
    DESCRIPTION = 'Plot amino acid properties of a protein sequence in parallel.'
    SEARCH_ALIASES = ["emboss", 'pepinfo']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.out',)
    REQUIRED_EXECUTABLES = ['pepinfo']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/pepinfo.html"
    PATH_INPUTS = ('sequence', 'aaproperties', 'aahydropathy')
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/pepinfo',
        "topics": [{'uri': 'http://edamontology.org/topic_0123', 'label': 'Protein properties'}, {'uri': 'http://edamontology.org/topic_0157', 'label': 'Sequence composition analysis'}, {'uri': 'http://edamontology.org/topic_0092', 'label': 'Data visualisation'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0250', 'label': 'Protein property calculation'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "hwindow": ('INT', {'min': 1, 'default': 9, 'description': 'Window size for hydropathy averaging'}),
                "generalplot": ('BOOLEAN', {'default': True, 'description': 'Plot histogram of general properties'}),
                "hydropathyplot": ('BOOLEAN', {'default': True, 'description': 'Plot graphs of hydropathy'}),
                'aaproperties': ("FILE", {"description": 'Amino acid chemical classes data file'}),
                'aahydropathy': ("FILE", {"description": 'Amino acid hydropathy values data file'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['pepinfo']
        for name in cls.PATH_INPUTS:
            value = inputs.get(name)
            if value not in (None, ""):
                command.extend([f"-{name}", str(value)])
        output_dir = cls.output_dir(inputs)
        graph_flag = 'graph'
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
