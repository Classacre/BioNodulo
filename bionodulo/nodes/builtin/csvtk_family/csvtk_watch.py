"""``csvtk watch``: monitor the specified fields.

Generated from the tool's own --help output in the pinned csvtk v0.31.0 image.
Help page SHA-256: 3c3901fd0df34e6907245801363d987ffcde2bdd3cd0096140351cabcc904df6

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase


class CsvtkWatchNode(CsvtkBase):
    """monitor the specified fields"""

    NODE_ID = 'csvtk_watch'
    DISPLAY_NAME = 'csvtk watch'
    SUBCOMMAND = 'watch'
    DESCRIPTION = 'monitor the specified fields'
    SEARCH_ALIASES = ['csvtk', 'watch']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('csvtk_watch.out',)
    DOCUMENTATION_URL = 'https://github.com/shenwei356/csvtk'
    REQUIRED_EXECUTABLES = ['csvtk']
    REQUIRED_CONDA_PACKAGES = ['csvtk']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'table': ("FILE", {"description": 'Input table file'}),

            },
            "optional": {
                "delimiter": (
                    "STRING",
                    {
                        "default": "tab",
                        "options": ["tab", "comma"],
                        "description": "Input delimiter",
                    },
                ),
                "bins": ('INT', {'description': 'number of histogram bins', 'default': -1}),
                "delay": ('INT', {'description': 'sleep this many seconds after plotting', 'default': 1}),
                "dump": ('BOOLEAN', {'description': 'print histogram data to stderr instead of plotting', 'default': False}),
                "field": ('STRING', {'description': 'field to watch', 'default': ''}),
                "image": ('STRING', {'description': 'save histogram to this PDF/image file', 'default': ''}),
                "log": ('BOOLEAN', {'description': 'log10(x+1) transform numeric values', 'default': False}),
                "pass": ('BOOLEAN', {'description': 'passthrough mode (forward input to output)', 'default': False}),
                "print_freq": ('INT', {'description': 'print/report after this many records (-1 for print after EOF)', 'default': -1}),
                "reset": ('BOOLEAN', {'description': 'reset histogram after every report', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ['csvtk', cls.SUBCOMMAND]
        mode = str(inputs.get("delimiter", "tab") or "tab")
        if mode == "tab":
            command.append("--tabs")
        # Required flags must be rendered too. Iterating only "optional" silently
        # dropped every empirically-required flag (csvtk mutate --name and friends).
        declared_types = cls.INPUT_TYPES()
        for category in ("required", "optional"):
            for name, spec in declared_types.get(category, {}).items():
                if name in ('delimiter', 'table'):
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
        command.append(str(inputs.get('table', "")))
        return command
