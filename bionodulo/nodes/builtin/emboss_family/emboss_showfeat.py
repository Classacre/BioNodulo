"""EMBOSS showfeat: Display features of a sequence in pretty format.

Generated from the suite's own ACD definition for showfeat in the pinned
emboss==6.6.0 image. ACD SHA-256: 44b67567e8f52a07eb39f8d272934a948115c372c313fbd3ca82c1dfa75a3b5e

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossShowfeatNode(EmbossBase):
    """Display features of a sequence in pretty format"""

    NODE_ID = 'emboss_showfeat'
    DISPLAY_NAME = 'EMBOSS showfeat'
    CATEGORY = "emboss"
    DESCRIPTION = 'Display features of a sequence in pretty format'
    SEARCH_ALIASES = ["emboss", 'showfeat']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.out',)
    REQUIRED_EXECUTABLES = ['showfeat']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/showfeat.html"
    PATH_INPUTS = ('sequence',)
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/showfeat',
        "topics": [{'uri': 'http://edamontology.org/topic_0160', 'label': 'Sequence sites and features'}, {'uri': 'http://edamontology.org/topic_0092', 'label': 'Data visualisation'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0564', 'label': 'Sequence rendering'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "sourcematch": ('STRING', {'default': '*', 'description': 'Source of feature to display'}),
                "typematch": ('STRING', {'default': '*', 'description': 'Type of feature to display'}),
                "tagmatch": ('STRING', {'default': '*', 'description': 'Tag of feature to display'}),
                "valuematch": ('STRING', {'default': '*', 'description': 'Value of feature tags to display'}),
                "sort": ('STRING', {'options': ['source'], 'default': 'start', 'description': "Sort features by Type, Start or Source, Nosort (don't sort - use input order) or join coding regions together and leave other features in the input or"}),
                "joinfeatures": ('BOOLEAN', {'default': False, 'description': 'Join coding regions together'}),
                "annotation": ('STRING', {'description': 'Regions to mark (eg: 4-57 promoter region 78-94 first exon)'}),
                "html": ('BOOLEAN', {'default': False, 'description': 'Use HTML formatting'}),
                "id": ('BOOLEAN', {'default': True, 'description': 'Show sequence ID'}),
                "description": ('BOOLEAN', {'default': True, 'description': 'Show description'}),
                "scale": ('BOOLEAN', {'default': True, 'description': 'Show scale line'}),
                "width": ('INT', {'min': 0, 'default': 60, 'description': 'Width of graphics lines'}),
                "collapse": ('BOOLEAN', {'default': False, 'description': 'Display features with the same type on one line'}),
                "forward": ('BOOLEAN', {'default': True, 'description': 'Display forward sense features'}),
                "reverse": ('BOOLEAN', {'default': True, 'description': 'Display reverse sense features'}),
                "unknown": ('BOOLEAN', {'default': True, 'description': 'Display unknown sense features'}),
                "strand": ('BOOLEAN', {'default': False, 'description': 'Display strand of features'}),
                "sourceshow": ('BOOLEAN', {'default': False, 'description': 'Display source of features'}),
                "position": ('BOOLEAN', {'default': False, 'description': 'Display position of features'}),
                "typeshow": ('BOOLEAN', {'default': True, 'description': 'Display type of features'}),
                "tagshow": ('BOOLEAN', {'default': False, 'description': 'Display tags of features'}),
                "valueshow": ('BOOLEAN', {'default': True, 'description': 'Display tag values of features'}),
                "stricttags": ('BOOLEAN', {'default': False, 'description': 'Only display the matching tags'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['showfeat']
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
