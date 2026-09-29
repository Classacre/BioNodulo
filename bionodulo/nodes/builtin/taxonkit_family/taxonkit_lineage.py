"""``taxonkit lineage``: Query taxonomic lineage of given TaxIds.

Generated from the tool's own --help output in the pinned taxonkit v0.20.0 image.
Help page SHA-256: f7fce4b810fe994f6845dd06f746f435be22becb43172990e7321231f1971438

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import TaxonkitBase


class TaxonkitLineageNode(TaxonkitBase):
    """Query taxonomic lineage of given TaxIds"""

    NODE_ID = 'taxonkit_lineage'
    DISPLAY_NAME = 'taxonkit lineage'
    SUBCOMMAND = 'lineage'
    DESCRIPTION = 'Query taxonomic lineage of given TaxIds'
    SEARCH_ALIASES = ['taxonkit', 'lineage']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('taxonkit_lineage.out',)
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/taxonkit/'
    REQUIRED_EXECUTABLES = ['taxonkit']
    REQUIRED_CONDA_PACKAGES = ['taxonkit']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input file: TaxId list, taxdump files, or profile, depending on the subcommand'}),

            },
            "optional": {
                "no_lineage": ('BOOLEAN', {'description': 'do not show lineage, when user just want names or/and ranks', 'default': False}),
                "show_lineage_ranks": ('BOOLEAN', {'description': 'appending ranks of all levels', 'default': False}),
                "show_lineage_taxids": ('BOOLEAN', {'description': 'appending lineage consisting of taxids', 'default': False}),
                "show_name": ('BOOLEAN', {'description': 'appending scientific name', 'default': False}),
                "show_rank": ('BOOLEAN', {'description': 'appending rank of taxids', 'default': False}),
                "show_status_code": ('BOOLEAN', {'description': 'show status code before lineage', 'default': False}),
                "taxid_field": ('INT', {'description': 'field index of taxid. input data should be tab-separated', 'default': 1}),
                "data_dir": ('STRING', {'description': 'directory containing nodes.dmp and names.dmp'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ['taxonkit', cls.SUBCOMMAND]
        # Required flags must be rendered too. Iterating only "optional" silently
        # dropped every empirically-required flag (csvtk mutate --name and friends).
        declared_types = cls.INPUT_TYPES()
        for category in ("required", "optional"):
            for name, spec in declared_types.get(category, {}).items():
                if name in ('input',):
                    continue
                value = inputs.get(name)
                if value in (None, ""):
                    continue
                declared = spec[0] if isinstance(spec, (list, tuple)) else spec
                default = spec[1].get("default") if isinstance(spec, tuple) and len(spec) > 1 else None
                token = getattr(cls, "FLAG_TOKENS", {}).get(name) or f"--{name.replace('_', '-')}"
                if declared == "BOOLEAN":
                    if bool(value):
                        command.append(token)
                    continue
                if value == default:
                    continue
                command.extend([token, str(value)])
        command.extend(['--out-file', str(output_dir / cls.OUTPUT_FILENAMES[0])])
        command.append(str(inputs.get('input', "")))
        return command
