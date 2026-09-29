"""``unikmer grep``: Search k-mers from binary files.

Generated from the tool's own --help output in the pinned unikmer 0.20.0 image.
Help page SHA-256: 49d155fedbb433d2dd42a3dea16bf2c9cea9aa5e19c318d896289b545869784c

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import UnikmerBase


class UnikmerGrepNode(UnikmerBase):
    """Search k-mers from binary files"""

    NODE_ID = 'unikmer_grep'
    DISPLAY_NAME = 'unikmer grep'
    SUBCOMMAND = 'grep'
    DESCRIPTION = 'Search k-mers from binary files'
    SEARCH_ALIASES = ['unikmer', 'grep']
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("output_dir",)
    OUTPUT_FILENAMES = ()
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/unikmer/'
    REQUIRED_EXECUTABLES = ['unikmer']
    REQUIRED_CONDA_PACKAGES = ['unikmer']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input k-mer file (.unik) or FASTA/Q file'}),
                "query": ('STRING', {'description': 'query k-mers/taxids (multiple values delimted by comma supported)', 'default': ''}),
            },
            "optional": {
                "degenerate": ('BOOLEAN', {'description': 'query k-mers contains degenerate base', 'default': False}),
                "force": ('BOOLEAN', {'description': 'overwrite output directory', 'default': False}),
                "invert_match": ('BOOLEAN', {'description': 'invert the sense of matching, to select non-matching records', 'default': False}),
                "multiple_outfiles": ('BOOLEAN', {'description': 'write results into separated files for multiple input files', 'default': False}),
                "out_suffix": ('STRING', {'description': 'output suffix', 'default': '.grep'}),
                "query_file": ('STRING', {'description': 'query file (one k-mer/taxid per line)', 'default': ''}),
                "query_is_taxid": ('BOOLEAN', {'description': 'queries are taxids', 'default': False}),
                "query_unik_file": ('STRING', {'description': 'query file in .unik format', 'default': ''}),
                "repeated": ('BOOLEAN', {'description': 'only print duplicate k-mers', 'default': False}),
                "sort": ('BOOLEAN', {'description': 'sort k-mers, this significantly reduce file size for k<=25. This flag overides global flag -c/--compact', 'default': False}),
                "unique": ('BOOLEAN', {'description': 'remove duplicate k-mers', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ['unikmer', cls.SUBCOMMAND]
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
        command.extend(['--out-dir', str(output_dir)])
        command.extend(["--out-prefix", str(output_dir / "output")])
        command.append(str(inputs.get('input', "")))
        return command
