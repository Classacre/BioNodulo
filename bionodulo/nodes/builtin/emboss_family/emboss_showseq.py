"""EMBOSS showseq: Display sequences with features in pretty format.

Generated from the suite's own ACD definition for showseq in the pinned
emboss==6.6.0 image. ACD SHA-256: c18b6b7747a16b6972296aff05f4f245a370d312e105ecc601fa27d5ef2f24b4

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossShowseqNode(EmbossBase):
    """Display sequences with features in pretty format"""

    NODE_ID = 'emboss_showseq'
    DISPLAY_NAME = 'EMBOSS showseq'
    CATEGORY = "emboss"
    DESCRIPTION = 'Display sequences with features in pretty format'
    SEARCH_ALIASES = ["emboss", 'showseq']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.out',)
    REQUIRED_EXECUTABLES = ['showseq']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/showseq.html"
    PATH_INPUTS = ('sequence', 'mfile')
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/showseq',
        "topics": [{'uri': 'http://edamontology.org/topic_0108', 'label': 'Translation'}, {'uri': 'http://edamontology.org/topic_0100', 'label': 'Nucleic acid restriction'}, {'uri': 'http://edamontology.org/topic_0092', 'label': 'Data visualisation'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0371', 'label': 'DNA translation'}, {'uri': 'http://edamontology.org/operation_0575', 'label': 'Restriction map rendering'}, {'uri': 'http://edamontology.org/operation_0564', 'label': 'Sequence rendering'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "format": ('STRING', {'options': ['0'], 'default': '2', 'description': 'Display format'}),
                "things": ('STRING', {'options': ['S'], 'default': 'B,N,T,S,A,F', 'description': 'Enter a list of things to display'}),
                "translate": ('STRING', {'description': 'Regions to translate (eg: 4-57,78-94)'}),
                "revtranslate": ('STRING', {'description': 'Regions to translate in reverse direction (eg: 78-94,4-57)'}),
                "uppercase": ('STRING', {'description': 'Regions to put in uppercase (eg: 4-57,78-94)'}),
                "highlight": ('STRING', {'description': 'Regions to colour in HTML (eg: 4-57 red 78-94 green)'}),
                "annotation": ('STRING', {'description': 'Regions to mark (eg: 4-57 promoter region 78-94 first exon)'}),
                "enzymes": ('STRING', {'default': 'all', 'description': 'Comma separated restriction enzyme list'}),
                "table": ('STRING', {'options': ['0', '1', '2', '3', '4', '5', '6', '9', '10', '11', '12', '13', '14', '15', '16', '21', '22', '23'], 'default': '0', 'description': 'Genetic code to use'}),
                "sourcematch": ('STRING', {'default': '*', 'description': 'Source of feature to display'}),
                "typematch": ('STRING', {'default': '*', 'description': 'Type of feature to display'}),
                "sensematch": ('INT', {'min': -1, 'max': 1, 'default': 0, 'description': 'Sense of feature to display'}),
                "minscore": ('FLOAT', {'default': 0.0, 'description': 'Minimum score of feature to display'}),
                "maxscore": ('FLOAT', {'default': 0.0, 'description': 'Maximum score of feature to display'}),
                "tagmatch": ('STRING', {'default': '*', 'description': 'Tag of feature to display'}),
                "valuematch": ('STRING', {'default': '*', 'description': 'Value of feature tags to display'}),
                "stricttags": ('BOOLEAN', {'default': False, 'description': 'Only display the matching tags'}),
                "flatreformat": ('BOOLEAN', {'default': False, 'description': 'Display RE sites in flat format'}),
                "mincuts": ('INT', {'min': 1, 'max': 1000, 'default': 1, 'description': 'Minimum cuts per RE'}),
                "maxcuts": ('INT', {'default': 2000000000, 'description': 'Maximum cuts per RE'}),
                "sitelen": ('INT', {'min': 2, 'max': 20, 'default': 4, 'description': 'Minimum recognition site length'}),
                "single": ('BOOLEAN', {'default': False, 'description': 'Force single RE site only cuts'}),
                "blunt": ('BOOLEAN', {'default': True, 'description': 'Allow blunt end RE cutters'}),
                "sticky": ('BOOLEAN', {'default': True, 'description': 'Allow sticky end RE cutters'}),
                "ambiguity": ('BOOLEAN', {'default': True, 'description': 'Allow ambiguous RE matches'}),
                "plasmid": ('BOOLEAN', {'default': False, 'description': 'Allow circular DNA'}),
                "methylation": ('BOOLEAN', {'default': False, 'description': 'Use methylation data'}),
                "commercial": ('BOOLEAN', {'default': True, 'description': 'Only use restriction enzymes with suppliers'}),
                "limit": ('BOOLEAN', {'default': True, 'description': 'Limits RE hits to one isoschizomer'}),
                "orfminsize": ('INT', {'min': 0, 'default': 0, 'description': 'Minimum size of ORFs'}),
                "threeletter": ('BOOLEAN', {'default': False, 'description': 'Display protein sequences in three-letter code'}),
                "number": ('BOOLEAN', {'default': False, 'description': 'Number the sequences'}),
                "width": ('INT', {'min': 1, 'default': 60, 'description': 'Width of sequence to display'}),
                "length": ('INT', {'min': 0, 'default': 0, 'description': 'Line length of page (0 for indefinite)'}),
                "margin": ('INT', {'min': 0, 'default': 10, 'description': 'Margin around sequence for numbering'}),
                "name": ('BOOLEAN', {'default': True, 'description': 'Show sequence ID'}),
                "description": ('BOOLEAN', {'default': True, 'description': 'Show description'}),
                "offset": ('INT', {'default': 1, 'description': 'Offset to start numbering the sequence from'}),
                "html": ('BOOLEAN', {'default': False, 'description': 'Use HTML formatting'}),
                'mfile': ("FILE", {"description": 'Restriction enzyme methylation data file'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['showseq']
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
