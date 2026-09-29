"""EMBOSS remap: Display restriction enzyme binding sites in a nucleotide sequence.

Generated from the suite's own ACD definition for remap in the pinned
emboss==6.6.0 image. ACD SHA-256: a7d55ebd9a4eddfb18f63b34e6623cc1dd02508a8f5fe449321dc7372ba44a4e

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossRemapNode(EmbossBase):
    """Display restriction enzyme binding sites in a nucleotide sequence"""

    NODE_ID = 'emboss_remap'
    DISPLAY_NAME = 'EMBOSS remap'
    CATEGORY = "emboss"
    DESCRIPTION = 'Display restriction enzyme binding sites in a nucleotide sequence'
    SEARCH_ALIASES = ["emboss", 'remap']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.out',)
    REQUIRED_EXECUTABLES = ['remap']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/remap.html"
    PATH_INPUTS = ('sequence', 'mfile')
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/remap',
        "topics": [{'uri': 'http://edamontology.org/topic_0100', 'label': 'Nucleic acid restriction'}, {'uri': 'http://edamontology.org/topic_0108', 'label': 'Translation'}, {'uri': 'http://edamontology.org/topic_0092', 'label': 'Data visualisation'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0431', 'label': 'Restriction site recognition'}, {'uri': 'http://edamontology.org/operation_0575', 'label': 'Restriction map rendering'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "enzymes": ('STRING', {'default': 'all', 'description': 'Comma separated enzyme list'}),
                "sitelen": ('INT', {'min': 2, 'max': 20, 'default': 4, 'description': 'Minimum recognition site length'}),
                "mincuts": ('INT', {'min': 1, 'max': 1000, 'default': 1, 'description': 'Minimum cuts per RE'}),
                "maxcuts": ('INT', {'default': 2000000000, 'description': 'Maximum cuts per RE'}),
                "single": ('BOOLEAN', {'default': False, 'description': 'Force single site only cuts'}),
                "blunt": ('BOOLEAN', {'default': True, 'description': 'Allow blunt end cutters'}),
                "sticky": ('BOOLEAN', {'default': True, 'description': 'Allow sticky end cutters'}),
                "ambiguity": ('BOOLEAN', {'default': True, 'description': 'Allow ambiguous matches'}),
                "plasmid": ('BOOLEAN', {'default': False, 'description': 'Allow circular DNA'}),
                "methylation": ('BOOLEAN', {'default': False, 'description': 'Use methylation data'}),
                "commercial": ('BOOLEAN', {'default': True, 'description': 'Only enzymes with suppliers'}),
                "table": ('STRING', {'options': ['0', '1', '2', '3', '4', '5', '6', '9', '10', '11', '12', '13', '14', '15', '16', '21', '22', '23'], 'default': '0', 'description': 'Genetic code to use'}),
                "frame": ('STRING', {'options': ['1'], 'default': '6', 'description': 'Frame(s) to translate'}),
                "cutlist": ('BOOLEAN', {'default': True, 'description': 'List the enzymes that cut'}),
                "flatreformat": ('BOOLEAN', {'default': False, 'description': 'Display RE sites in flat format'}),
                "limit": ('BOOLEAN', {'default': True, 'description': 'Limits reports to one isoschizomer'}),
                "translation": ('BOOLEAN', {'default': True, 'description': 'Display translation'}),
                "reverse": ('BOOLEAN', {'default': True, 'description': 'Display cut sites and translation of reverse sense'}),
                "orfminsize": ('INT', {'min': 0, 'default': 0, 'description': 'Minimum size of ORFs'}),
                "uppercase": ('STRING', {'description': 'Regions to put in uppercase (eg: 4-57,78-94)'}),
                "highlight": ('STRING', {'description': 'Regions to colour in HTML (eg: 4-57 red 78-94 green)'}),
                "threeletter": ('BOOLEAN', {'default': False, 'description': 'Display protein sequences in three-letter code'}),
                "number": ('BOOLEAN', {'default': False, 'description': 'Number the sequences'}),
                "width": ('INT', {'min': 1, 'default': 60, 'description': 'Width of sequence to display'}),
                "length": ('INT', {'min': 0, 'default': 0, 'description': 'Line length of page (0 for indefinite)'}),
                "margin": ('INT', {'min': 0, 'default': 10, 'description': 'Margin around sequence for numbering'}),
                "name": ('BOOLEAN', {'default': True, 'description': 'Display sequence ID'}),
                "description": ('BOOLEAN', {'default': True, 'description': 'Display description'}),
                "offset": ('INT', {'default': 1, 'description': 'Offset to start numbering the sequence from'}),
                "html": ('BOOLEAN', {'default': False, 'description': 'Use HTML formatting'}),
                'mfile': ("FILE", {"description": 'Restriction enzyme methylation data file'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['remap']
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
