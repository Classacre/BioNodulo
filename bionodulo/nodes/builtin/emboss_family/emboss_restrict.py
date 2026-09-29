"""EMBOSS restrict: Report restriction enzyme cleavage sites in a nucleotide sequence.

Generated from the suite's own ACD definition for restrict in the pinned
emboss==6.6.0 image. ACD SHA-256: f0f168f60e01e661a408a7d90a70e7326d8937829c17855fb9cb0ec088145610

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossRestrictNode(EmbossBase):
    """Report restriction enzyme cleavage sites in a nucleotide sequence"""

    NODE_ID = 'emboss_restrict'
    DISPLAY_NAME = 'EMBOSS restrict'
    CATEGORY = "emboss"
    DESCRIPTION = 'Report restriction enzyme cleavage sites in a nucleotide sequence'
    SEARCH_ALIASES = ["emboss", 'restrict']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.txt',)
    REQUIRED_EXECUTABLES = ['restrict']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/restrict.html"
    PATH_INPUTS = ('sequence', 'datafile', 'mfile')
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/restrict',
        "topics": [{'uri': 'http://edamontology.org/topic_0100', 'label': 'Nucleic acid restriction'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0431', 'label': 'Restriction site recognition'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "sitelen": ('INT', {'min': 2, 'max': 20, 'default': 4, 'description': 'Minimum recognition site length'}),
                "enzymes": ('STRING', {'default': 'all', 'description': 'Comma separated enzyme list'}),
                "min": ('INT', {'min': 1, 'max': 1000, 'default': 1, 'description': 'Minimum cuts per RE'}),
                "max": ('INT', {'default': 2000000000, 'description': 'Maximum cuts per RE'}),
                "solofragment": ('BOOLEAN', {'default': False, 'description': 'List individual enzymes with their fragments'}),
                "single": ('BOOLEAN', {'default': False, 'description': 'Force single site only cuts'}),
                "blunt": ('BOOLEAN', {'default': True, 'description': 'Allow blunt end cutters'}),
                "sticky": ('BOOLEAN', {'default': True, 'description': 'Allow sticky end cutters'}),
                "ambiguity": ('BOOLEAN', {'default': True, 'description': 'Allow ambiguous matches'}),
                "plasmid": ('BOOLEAN', {'default': False, 'description': 'Allow circular DNA'}),
                "methylation": ('BOOLEAN', {'default': False, 'description': 'Use methylation data'}),
                "commercial": ('BOOLEAN', {'default': True, 'description': 'Only enzymes with suppliers'}),
                "limit": ('BOOLEAN', {'default': True, 'description': 'Limits reports to one isoschizomer'}),
                "alphabetic": ('BOOLEAN', {'default': False, 'description': 'Sort output alphabetically'}),
                "fragments": ('BOOLEAN', {'default': False, 'description': 'Show fragment lengths'}),
                'datafile': ("FILE", {"description": 'Restriction enzyme data file (optional)'}),
                'mfile': ("FILE", {"description": 'Restriction enzyme methylation data file'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['restrict']
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
