"""``taxonkit list``: List taxonomic subtrees of given TaxIds.

Generated from the tool's own --help output in the pinned taxonkit v0.20.0 image.
Help page SHA-256: f9911ed47716cc42fc98fd996e24410df657392a15891e6ae7725ef8886c7e5e

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import TaxonkitBase


class TaxonkitListNode(TaxonkitBase):
    """List taxonomic subtrees of given TaxIds"""

    NODE_ID = 'taxonkit_list'
    DISPLAY_NAME = 'taxonkit list'
    SUBCOMMAND = 'list'
    DESCRIPTION = 'List taxonomic subtrees of given TaxIds'
    SEARCH_ALIASES = ['taxonkit', 'list']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('taxonkit_list.out',)
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
                "ids": ('STRING', {'description': 'TaxId(s), multiple values should be separated by comma', 'default': ''}),
                "indent": ('STRING', {'description': 'indent', 'default': '  '}),
                "json": ('BOOLEAN', {'description': 'output in JSON format. you can save the result in file with suffix ".json" and open with modern text editor', 'default': False}),
                "show_name": ('BOOLEAN', {'description': 'output scientific name', 'default': False}),
                "show_rank": ('BOOLEAN', {'description': 'output rank', 'default': False}),
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
