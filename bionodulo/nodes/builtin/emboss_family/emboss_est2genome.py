"""EMBOSS est2genome: Align EST sequences to genomic DNA sequence.

Generated from the suite's own ACD definition for est2genome in the pinned
emboss==6.6.0 image. ACD SHA-256: d94043b325954698fcdb1e08ae572119843f0f4ce505947ec2af54f1ba073e35

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossEst2genomeNode(EmbossBase):
    """Align EST sequences to genomic DNA sequence"""

    NODE_ID = 'emboss_est2genome'
    DISPLAY_NAME = 'EMBOSS est2genome'
    CATEGORY = "emboss"
    DESCRIPTION = 'Align EST sequences to genomic DNA sequence'
    SEARCH_ALIASES = ["emboss", 'est2genome']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.out',)
    REQUIRED_EXECUTABLES = ['est2genome']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/est2genome.html"
    PATH_INPUTS = ('estsequence', 'genomesequence')
    REQUIRED_PATH_INPUTS = ('estsequence', 'genomesequence')
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/est2genome',
        "topics": [{'uri': 'http://edamontology.org/topic_0182', 'label': 'Sequence alignment'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0292', 'label': 'Sequence alignment construction'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'estsequence': ((("FASTA", "FILE")), {"description": 'Spliced EST nucleotide sequence(s)'}),
                'genomesequence': ((("FASTA", "FILE")), {"description": 'Unspliced genomic nucleotide sequence'}),
            },
            "optional": {
                "match": ('INT', {'default': 1, 'description': 'Score for matching two bases'}),
                "mismatch": ('INT', {'default': 1, 'description': 'Cost for mismatching two bases'}),
                "gappenalty": ('INT', {'default': 2, 'description': 'Gap penalty'}),
                "intronpenalty": ('INT', {'default': 40, 'description': 'Intron penalty'}),
                "splicepenalty": ('INT', {'default': 20, 'description': 'Splice site penalty'}),
                "minscore": ('INT', {'default': 30, 'description': 'Minimum accepted score'}),
                "reverse": ('BOOLEAN', {'description': 'Reverse orientation'}),
                "usesplice": ('BOOLEAN', {'default': True, 'description': 'Use donor and acceptor splice sites'}),
                "mode": ('STRING', {'options': ['both', 'forward', 'reverse'], 'default': 'both', 'description': 'Comparison mode'}),
                "best": ('BOOLEAN', {'default': True, 'description': 'Print out only best alignment'}),
                "space": ('FLOAT', {'default': 10.0, 'description': 'Space threshold (in megabytes)'}),
                "shuffle": ('INT', {'description': 'Shuffle'}),
                "seed": ('INT', {'default': 20825, 'description': 'Random number seed'}),
                "align": ('BOOLEAN', {'description': 'Show the alignment'}),
                "width": ('INT', {'default': 50, 'description': 'Alignment width'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['est2genome']
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
