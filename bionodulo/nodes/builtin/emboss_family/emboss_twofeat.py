"""EMBOSS twofeat: Find neighbouring pairs of features in sequence(s).

Generated from the suite's own ACD definition for twofeat in the pinned
emboss==6.6.0 image. ACD SHA-256: 2c94ef5d504356b7eeff3287d181c4dfd43c991c3086f1d86de33b512b271705

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossTwofeatNode(EmbossBase):
    """Find neighbouring pairs of features in sequence(s)"""

    NODE_ID = 'emboss_twofeat'
    DISPLAY_NAME = 'EMBOSS twofeat'
    CATEGORY = "emboss"
    DESCRIPTION = 'Find neighbouring pairs of features in sequence(s)'
    SEARCH_ALIASES = ["emboss", 'twofeat']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.txt',)
    REQUIRED_EXECUTABLES = ['twofeat']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/twofeat.html"
    PATH_INPUTS = ('sequence',)
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/twofeat',
        "topics": [{'uri': 'http://edamontology.org/topic_0160', 'label': 'Sequence sites and features'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0255', 'label': 'Feature table query'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "asource": ('STRING', {'default': '*', 'description': 'Source of first feature'}),
                "atype": ('STRING', {'default': '*', 'description': 'Type of first feature'}),
                "asense": ('STRING', {'options': ['0'], 'default': '0', 'description': 'Sense of first feature'}),
                "aminscore": ('FLOAT', {'default': 0.0, 'description': 'Minimum score of first feature'}),
                "amaxscore": ('FLOAT', {'default': 0.0, 'description': 'Maximum score of first feature'}),
                "atag": ('STRING', {'default': '*', 'description': 'Tag of first feature'}),
                "avalue": ('STRING', {'default': '*', 'description': "Value of first feature's tags"}),
                "bsource": ('STRING', {'default': '*', 'description': 'Source of second feature'}),
                "btype": ('STRING', {'default': '*', 'description': 'Type of second feature'}),
                "bsense": ('STRING', {'options': ['0'], 'default': '0', 'description': 'Sense of second feature'}),
                "bminscore": ('FLOAT', {'default': 0.0, 'description': 'Minimum score of second feature'}),
                "bmaxscore": ('FLOAT', {'default': 0.0, 'description': 'Maximum score of second feature'}),
                "btag": ('STRING', {'default': '*', 'description': 'Tag of second feature'}),
                "bvalue": ('STRING', {'default': '*', 'description': "Value of second feature's tags"}),
                "overlap": ('STRING', {'options': ['A'], 'default': 'A', 'description': 'Specify overlap'}),
                "minrange": ('INT', {'default': 0, 'description': 'The minimum distance between the features'}),
                "maxrange": ('INT', {'default': 0, 'description': 'The maximum distance between the features'}),
                "rangetype": ('STRING', {'options': ['N'], 'default': 'N', 'description': 'Specify position'}),
                "sense": ('STRING', {'options': ['A'], 'default': 'A', 'description': 'Specify sense'}),
                "order": ('STRING', {'options': ['A'], 'default': 'A', 'description': 'Specify order'}),
                "twoout": ('STRING', {'default': 'N', 'description': 'Do you want the two features written out individually'}),
                "typeout": ('STRING', {'default': 'misc_feature', 'description': 'Name of the output new feature'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['twofeat']
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
