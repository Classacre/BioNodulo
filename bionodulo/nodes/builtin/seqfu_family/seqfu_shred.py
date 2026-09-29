"""``seqfu shred``: Systematically produce a "shotgun" of input sequences. Can read from standard in.

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: 9a77eeae7bada0b3ea7a93858a18ea7921379558e78cabed0a129581776d83c1

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqfuBase


class SeqfuShredNode(SeqfuBase):
    """Systematically produce a "shotgun" of input sequences. Can read from standard input."""

    NODE_ID = 'seqfu_shred'
    DISPLAY_NAME = 'seqfu shred'
    SUBCOMMAND = 'shred'
    DESCRIPTION = 'Systematically produce a "shotgun" of input sequences. Can read from standard input.'
    SEARCH_ALIASES = ['seqfu', 'shred']
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("output_dir",)
    OUTPUT_FILENAMES = ()
    DOCUMENTATION_URL = 'https://telatin.github.io/seqfu2/'
    REQUIRED_EXECUTABLES = ['seqfu']
    REQUIRED_CONDA_PACKAGES = ['seqfu']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input sequence file'}),

            },
            "optional": {
                "length": ('INT', {'description': 'Segment length', 'default': 100}),
                "step": ('INT', {'description': 'Distance from one segment start to the following', 'default': 10}),
                "quality": ('INT', {'description': 'Quality (constant) for the segment, if -1 is provided will be printed in FASTA [default: 40]', 'default': ''}),
                "add_rc": ('BOOLEAN', {'description': 'Print every other read in reverse complement', 'default': False}),
                "basename": ('BOOLEAN', {'description': 'Prepend the file basename to the read name', 'default': False}),
                "split_basename": ('STRING', {'description': 'Split the file basename at this character', 'default': '.'}),
                "prefix_separator": ('STRING', {'description': 'Join the basename with the rest of the read name with this', 'default': '_'}),
                "frag_len": ('INT', {'description': 'Total fragment length', 'default': 500}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ['seqfu', cls.SUBCOMMAND]
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
        command.extend(['--out-prefix', str(output_dir / "output")])
        command.append(str(inputs.get('input', "")))
        return command
