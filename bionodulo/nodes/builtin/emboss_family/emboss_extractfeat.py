"""EMBOSS extractfeat: Extract features from sequence(s).

Generated from the suite's own ACD definition for extractfeat in the pinned
emboss==6.6.0 image. ACD SHA-256: 7f7fa9a84242d70c319318656092712b3fb4e34e3a89672ea7508c45c1d61583

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossExtractfeatNode(EmbossBase):
    """Extract features from sequence(s)"""

    NODE_ID = 'emboss_extractfeat'
    DISPLAY_NAME = 'EMBOSS extractfeat'
    CATEGORY = "emboss"
    DESCRIPTION = 'Extract features from sequence(s)'
    SEARCH_ALIASES = ["emboss", 'extractfeat']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outseq',)
    OUTPUT_FILENAMES = ('outseq.out',)
    REQUIRED_EXECUTABLES = ['extractfeat']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/extractfeat.html"
    PATH_INPUTS = ('sequence',)
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/extractfeat',
        "topics": [{'uri': 'http://edamontology.org/topic_0160', 'label': 'Sequence sites and features'}, {'uri': 'http://edamontology.org/topic_0091', 'label': 'Data handling'}],
        "operations": [{'uri': 'http://edamontology.org/operation_2422', 'label': 'Data retrieval'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "before": ('INT', {'default': 0, 'description': 'Amount of sequence before feature to extract'}),
                "after": ('INT', {'default': 0, 'description': 'Amount of sequence after feature to extract'}),
                "source": ('STRING', {'default': '*', 'description': 'Source of feature to display'}),
                "type": ('STRING', {'default': '*', 'description': 'Type of feature to extract'}),
                "sense": ('INT', {'default': 0, 'description': 'Sense of feature to extract'}),
                "minscore": ('FLOAT', {'default': 0.0, 'description': 'Minimum score of feature to extract'}),
                "maxscore": ('FLOAT', {'default': 0.0, 'description': 'Maximum score of feature to extract'}),
                "tag": ('STRING', {'default': '*', 'description': 'Tag of feature to extract'}),
                "value": ('STRING', {'default': '*', 'description': 'Value of feature tags to extract'}),
                "join": ('BOOLEAN', {'default': False, 'description': 'Output introns etc. as one sequence'}),
                "featinname": ('BOOLEAN', {'default': False, 'description': 'Append type of feature to output sequence name'}),
                "describe": ('STRING', {'description': 'Feature tag names to add to the description'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['extractfeat']
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
