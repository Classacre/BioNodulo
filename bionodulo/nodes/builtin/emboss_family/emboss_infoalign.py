"""EMBOSS infoalign: Display basic information about a multiple sequence alignment.

Generated from the suite's own ACD definition for infoalign in the pinned
emboss==6.6.0 image. ACD SHA-256: c46e13926dcc8a8a6b002f2e44f68b337a441c8329cf7162afcf80bb1a68599d

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossInfoalignNode(EmbossBase):
    """Display basic information about a multiple sequence alignment"""

    NODE_ID = 'emboss_infoalign'
    DISPLAY_NAME = 'EMBOSS infoalign'
    CATEGORY = "emboss"
    DESCRIPTION = 'Display basic information about a multiple sequence alignment'
    SEARCH_ALIASES = ["emboss", 'infoalign']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.out',)
    REQUIRED_EXECUTABLES = ['infoalign']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/infoalign.html"
    PATH_INPUTS = ('sequence', 'matrix')
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/infoalign',
        "topics": [{'uri': 'http://edamontology.org/topic_0182', 'label': 'Sequence alignment'}, {'uri': 'http://edamontology.org/topic_0090', 'label': 'Data search and retrieval'}],
        "operations": [{'uri': 'http://edamontology.org/operation_2422', 'label': 'Data retrieval'}, {'uri': 'http://edamontology.org/operation_0564', 'label': 'Sequence rendering'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "refseq": ('STRING', {'default': '0', 'description': 'The number or the name of the reference sequence'}),
                "plurality": ('FLOAT', {'default': 50.0, 'description': 'Plurality check % for consensus'}),
                "identity": ('FLOAT', {'default': 0.0, 'description': 'Required % of identities at a position fro consensus'}),
                "html": ('BOOLEAN', {'default': False, 'description': 'Format output as an HTML table'}),
                "only": ('BOOLEAN', {'default': False, 'description': 'Display the specified columns'}),
                "heading": ('BOOLEAN', {'description': 'Display column headings'}),
                "usa": ('BOOLEAN', {'description': 'Display the USA of the sequence'}),
                "name": ('BOOLEAN', {'description': "Display 'name' column"}),
                "seqlength": ('BOOLEAN', {'description': "Display 'seqlength' column"}),
                "alignlength": ('BOOLEAN', {'description': "Display 'alignlength' column"}),
                "gaps": ('BOOLEAN', {'description': 'Display number of gaps'}),
                "gapcount": ('BOOLEAN', {'description': 'Display number of gap positions'}),
                "idcount": ('BOOLEAN', {'description': 'Display number of identical positions'}),
                "simcount": ('BOOLEAN', {'description': 'Display number of similar positions'}),
                "diffcount": ('BOOLEAN', {'description': 'Display number of different positions'}),
                "change": ('BOOLEAN', {'description': 'Display % number of changed positions'}),
                "weight": ('BOOLEAN', {'description': "Display 'weight' column"}),
                "description": ('BOOLEAN', {'description': "Display 'description' column"}),
                'matrix': ("FILE", {"description": 'Similarity scoring Matrix file'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['infoalign']
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
