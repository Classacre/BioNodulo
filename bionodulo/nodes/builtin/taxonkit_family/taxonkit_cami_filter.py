"""``taxonkit cami-filter``: Remove taxa of given TaxIds and their descendants in CAMI metagenomic profile.

Generated from the tool's own --help output in the pinned taxonkit v0.20.0 image.
Help page SHA-256: 97b2fb07e71d0e817194064a4e7fd58a5d78fea38176b0862ec08502deda656f

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import TaxonkitBase


class TaxonkitCamiFilterNode(TaxonkitBase):
    """Remove taxa of given TaxIds and their descendants in CAMI metagenomic profile"""

    NODE_ID = 'taxonkit_cami_filter'
    DISPLAY_NAME = 'taxonkit cami-filter'
    SUBCOMMAND = 'cami-filter'
    DESCRIPTION = 'Remove taxa of given TaxIds and their descendants in CAMI metagenomic profile'
    SEARCH_ALIASES = ['taxonkit', 'cami-filter']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('taxonkit_cami_filter.out',)
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
                "field_percentage": ('INT', {'description': 'field index of PERCENTAGE', 'default': 5}),
                "field_rank": ('INT', {'description': 'field index of taxid', 'default': 2}),
                "field_taxid": ('INT', {'description': 'field index of taxid', 'default': 1}),
                "field_taxpath": ('INT', {'description': 'field index of TAXPATH', 'default': 3}),
                "field_taxpathsn": ('INT', {'description': 'field index of TAXPATHSN', 'default': 4}),
                "leaf_ranks": ('STRING', {'description': 'only consider leaves at these ranks', 'default': '[species,strain,no rank]'}),
                "show_rank": ('STRING', {'description': 'only show TaxIds and names of these ranks (default [superkingdom,phylum,class,order,family,genus,species,strain])', 'default': ''}),
                "taxid_sep": ('STRING', {'description': 'separator of taxid in TAXPATH and TAXPATHSN', 'default': '|'}),
                "taxids": ('STRING', {'description': 'the parent taxid(s) to filter out', 'default': ''}),
                "taxids_file": ('STRING', {'description': 'file(s) for the parent taxid(s) to filter out, one taxid per line', 'default': ''}),
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
