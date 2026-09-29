"""``taxonkit filter``: Filter TaxIds by taxonomic rank range.

Generated from the tool's own --help output in the pinned taxonkit v0.20.0 image.
Help page SHA-256: 057d6a19590024e7ab994e5cf0d95aab214efbc2d48b722f3dd04d917e0aa3cd

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import TaxonkitBase


class TaxonkitFilterNode(TaxonkitBase):
    """Filter TaxIds by taxonomic rank range"""

    NODE_ID = 'taxonkit_filter'
    DISPLAY_NAME = 'taxonkit filter'
    SUBCOMMAND = 'filter'
    DESCRIPTION = 'Filter TaxIds by taxonomic rank range'
    SEARCH_ALIASES = ['taxonkit', 'filter']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('taxonkit_filter.out',)
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
                "black_list": ('STRING', {'description': 'black list of ranks to discard, e.g., \'-B "no rank" -B "clade"', 'default': ''}),
                "discard_noranks": ('BOOLEAN', {'description': 'discard all ranks without order, type "taxonkit filter --help" for details', 'default': False}),
                "discard_root": ('BOOLEAN', {'description': 'discard root taxid, defined by --root-taxid', 'default': False}),
                "equal_to": ('STRING', {'description': 'output TaxIds with rank equal to some ranks, multiple values can be separated with comma "," (e.g., -E "genus,species"), or give multiple times (e.g., -E genus -E species)', 'default': ''}),
                "higher_than": ('STRING', {'description': 'output TaxIds with rank higher than a rank, exclusive with --lower-than', 'default': ''}),
                "list_order": ('BOOLEAN', {'description': 'list user defined ranks in order, from "$HOME/.taxonkit/ranks.txt"', 'default': False}),
                "list_ranks": ('BOOLEAN', {'description': 'list ordered ranks in taxonomy database, sorted in user defined order', 'default': False}),
                "lower_than": ('STRING', {'description': 'output TaxIds with rank lower than a rank, exclusive with --higher-than', 'default': ''}),
                "rank_file": ('STRING', {'description': 'user-defined ordered taxonomic ranks, type "taxonkit filter --help" for details', 'default': ''}),
                "root_taxid": ('STRING', {'description': 'root taxid', 'default': '1'}),
                "save_predictable_norank": ('BOOLEAN', {'description': 'do not discard some special ranks without order when using -L, where rank of the closest higher node is still lower than rank cutoff', 'default': False}),
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
