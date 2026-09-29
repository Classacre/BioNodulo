"""``taxonkit reformat2``: Reformat lineage in chosen ranks, allowing more ranks than 'reformat'.

Generated from the tool's own --help output in the pinned taxonkit v0.20.0 image.
Help page SHA-256: 0c2355f9c7b053f01cd73c443984b05c25ea70d5c0439897bc12ae72f087484e

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import TaxonkitBase


class TaxonkitReformat2Node(TaxonkitBase):
    """Reformat lineage in chosen ranks, allowing more ranks than 'reformat'"""

    NODE_ID = 'taxonkit_reformat2'
    DISPLAY_NAME = 'taxonkit reformat2'
    SUBCOMMAND = 'reformat2'
    DESCRIPTION = "Reformat lineage in chosen ranks, allowing more ranks than 'reformat'"
    SEARCH_ALIASES = ['taxonkit', 'reformat2']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('taxonkit_reformat2.out',)
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
                "format": ('STRING', {'description': 'output format, placeholders of rank are needed (default "{domain|acellular root|superkingdom};{phylum};{class};{order};{family};{genus};{species}")', 'default': ''}),
                "miss_rank_repl": ('STRING', {'description': 'replacement string for missing rank', 'default': ''}),
                "miss_taxid_repl": ('STRING', {'description': 'replacement string for missing taxid', 'default': ''}),
                "no_ranks": ('STRING', {'description': 'rank names of no-rank. A lineage might have many "no rank" ranks, we only keep the last one below known ranks (default [no rank,clade])', 'default': ''}),
                "show_lineage_taxids": ('BOOLEAN', {'description': 'show corresponding taxids of reformated lineage', 'default': False}),
                "taxid_field": ('INT', {'description': 'field index of taxid. input data should be tab-separated. it overrides -i/--lineage-field (default 1)', 'default': ''}),
                "trim": ('BOOLEAN', {'description': 'do not replace missing ranks lower than the rank of the current node', 'default': False}),
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
