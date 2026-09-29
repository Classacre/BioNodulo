"""EMBOSS emma: Multiple sequence alignment (ClustalW wrapper).

Generated from the suite's own ACD definition for emma in the pinned
emboss==6.6.0 image. ACD SHA-256: 73239ab1d1ffa951e6ae92ce7aab2efbecb129666a80d944a995d7ed2e270f98

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossEmmaNode(EmbossBase):
    """Multiple sequence alignment (ClustalW wrapper)"""

    NODE_ID = 'emboss_emma'
    DISPLAY_NAME = 'EMBOSS emma'
    CATEGORY = "emboss"
    DESCRIPTION = 'Multiple sequence alignment (ClustalW wrapper)'
    SEARCH_ALIASES = ["emboss", 'emma']
    RETURN_TYPES = ('FILE', 'FILE')
    RETURN_NAMES = ('outseq', 'dendoutfile')
    OUTPUT_FILENAMES = ('outseq.out', 'dendoutfile.out')
    REQUIRED_EXECUTABLES = ['emma']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/emma.html"
    PATH_INPUTS = ('sequence', 'dendfile', 'pairwisedatafile', 'mamatrixfile')
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/emma',
        "topics": [{'uri': 'http://edamontology.org/topic_0182', 'label': 'Sequence alignment'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0499', 'label': 'Multiple sequence alignment construction (phylogenetic tree-based)'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "onlydend": ('STRING', {'default': 'N', 'description': 'Only produce dendrogram file'}),
                "dendreuse": ('STRING', {'default': 'N', 'description': 'Do alignment using an old dendrogram'}),
                "slowalign": ('STRING', {'default': 'Y', 'description': 'Do you want to carry out slow pairwise alignment'}),
                "pwmatrix": ('STRING', {'options': ['b'], 'default': 'b', 'description': 'Select matrix'}),
                "pwdnamatrix": ('STRING', {'options': ['i'], 'default': 'i', 'description': 'Select matrix'}),
                "matrix": ('STRING', {'options': ['b'], 'default': 'b', 'description': 'Select matrix'}),
                "dnamatrix": ('STRING', {'options': ['i'], 'default': 'i', 'description': 'Select matrix'}),
                "pwgapopen": ('FLOAT', {'default': 10.0, 'description': 'Slow pairwise alignment: gap opening penalty'}),
                "pwgapextend": ('FLOAT', {'default': 0.1, 'description': 'Slow pairwise alignment: gap extension penalty'}),
                "ktup": ('INT', {'min': 0, 'max': 4, 'description': 'Fast pairwise alignment: similarity scores: K-Tuple size'}),
                "gapw": ('INT', {'min': 0, 'description': 'Fast pairwise alignment: similarity scores: gap penalty'}),
                "topdiags": ('INT', {'min': 0, 'description': 'Fast pairwise alignment: similarity scores: number of diagonals to be considered'}),
                "window": ('INT', {'min': 0, 'description': 'Fast pairwise alignment: similarity scores: diagonal window size'}),
                "nopercent": ('BOOLEAN', {'default': False, 'description': 'Fast pairwise alignment: similarity scores: suppresses percentage score'}),
                "gapopen": ('FLOAT', {'default': 10.0, 'description': 'Multiple alignment: Gap opening penalty'}),
                "gapextend": ('FLOAT', {'default': 5.0, 'description': 'Multiple alignment: Gap extension penalty'}),
                "endgaps": ('BOOLEAN', {'default': True, 'description': 'Use end gap separation penalty'}),
                "gapdist": ('INT', {'min': 0, 'default': 8, 'description': 'Gap separation distance'}),
                "norgap": ('BOOLEAN', {'default': False, 'description': 'No residue specific gaps'}),
                "hgapres": ('STRING', {'default': 'GPSNDQEKR', 'description': 'List of hydrophilic residues'}),
                "nohgap": ('BOOLEAN', {'default': False, 'description': 'No hydrophilic gaps'}),
                "maxdiv": ('INT', {'min': 0, 'max': 100, 'default': 30, 'description': 'Cut-off to delay the alignment of the most divergent sequences'}),
                'dendfile': ("FILE", {"description": 'Dendrogram (tree file) from clustalw file (optional)'}),
                'pairwisedatafile': ("FILE", {"description": 'Comparison matrix file (optional)'}),
                'mamatrixfile': ("FILE", {"description": 'Comparison matrix file (optional)'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['emma']
        for name in cls.PATH_INPUTS:
            value = inputs.get(name)
            if value not in (None, ""):
                command.extend([f"-{name}", str(value)])
        output_dir = cls.output_dir(inputs)
        graph_flag = None
        # A stdout-only program has no output qualifier at all; its planned file
        # is filled by the executor's stdout capture instead.
        declared: list[str] = [] if False else list(['outseq', 'dendoutfile'])
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
