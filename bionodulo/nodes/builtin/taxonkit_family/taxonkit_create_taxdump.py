"""``taxonkit create-taxdump``: Create NCBI-style taxdump files for custom taxonomy, e.g., GTDB and ICTV.

Generated from the tool's own --help output in the pinned taxonkit v0.20.0 image.
Help page SHA-256: 2ac733d9b09a8fa068afc6a3790f419cfe3090d79ef6f963bf30b6e7c4cc3ccb

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import TaxonkitBase


class TaxonkitCreateTaxdumpNode(TaxonkitBase):
    """Create NCBI-style taxdump files for custom taxonomy, e.g., GTDB and ICTV"""

    NODE_ID = 'taxonkit_create_taxdump'
    DISPLAY_NAME = 'taxonkit create-taxdump'
    SUBCOMMAND = 'create-taxdump'
    DESCRIPTION = 'Create NCBI-style taxdump files for custom taxonomy, e.g., GTDB and ICTV'
    SEARCH_ALIASES = ['taxonkit', 'create-taxdump']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('taxonkit_create_taxdump.out',)
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
                "field_accession": ('INT', {'description': 'field index of assembly accession (genome ID), for outputting taxid.map', 'default': ''}),
                "field_accession_as_subspecies": ('BOOLEAN', {'description': 'treate the accession as subspecies rank', 'default': False}),
                "field_accession_re": ('STRING', {'description': 'regular expression to extract assembly accession', 'default': '^(.+)$'}),
                "force": ('BOOLEAN', {'description': 'overwrite existing output directory', 'default': False}),
                "gtdb": ('BOOLEAN', {'description': 'input files are GTDB taxonomy file', 'default': False}),
                "gtdb_re_subs": ('STRING', {'description': 'regular expression to extract assembly accession as the subspecies (default "^\\\\w\\\\w_GC[AF]_(.+)\\\\.\\\\d+$")', 'default': ''}),
                "line_chunk_size": ('INT', {'description': 'number of lines to process for each thread, and 4 threads is fast enough. (default 5000)', 'default': ''}),
                "null": ('STRING', {'description': 'null value of taxa', 'default': '[,NULL,NA]'}),
                "old_taxdump_dir": ('STRING', {'description': 'taxdump directory of the previous version, for generating merged.dmp and delnodes.dmp', 'default': ''}),
                "out_dir": ('STRING', {'description': 'output directory', 'default': ''}),
                "rank_names": ('STRING', {'description': 'names of all ranks, leave it empty to use the (lowercase) first row of input as rank names', 'default': ''}),
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
