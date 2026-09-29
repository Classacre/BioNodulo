"""``unikmer rfilter``: Filter k-mers by taxonomic rank.

Generated from the tool's own --help output in the pinned unikmer 0.20.0 image.
Help page SHA-256: 11d913a99a385298a79019db7750fe927e78b76b214c2d5e0c4be6b909cd7130

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import UnikmerBase


class UnikmerRfilterNode(UnikmerBase):
    """Filter k-mers by taxonomic rank"""

    NODE_ID = 'unikmer_rfilter'
    DISPLAY_NAME = 'unikmer rfilter'
    SUBCOMMAND = 'rfilter'
    DESCRIPTION = 'Filter k-mers by taxonomic rank'
    SEARCH_ALIASES = ['unikmer', 'rfilter']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('unikmer_rfilter.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/unikmer/'
    REQUIRED_EXECUTABLES = ['unikmer']
    REQUIRED_CONDA_PACKAGES = ['unikmer']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input k-mer file (.unik) or FASTA/Q file'}),

            },
            "optional": {
                "black_list": ('STRING', {'description': 'black list of ranks to discard, e.g., \'"no rank", "clade"\'', 'default': ''}),
                "discard_noranks": ('BOOLEAN', {'description': 'discard ranks without order, type "unikmer filter --help" for details', 'default': False}),
                "discard_root": ('BOOLEAN', {'description': 'discard root taxid, defined by --root-taxid', 'default': False}),
                "equal_to": ('STRING', {'description': 'output taxIDs with rank equal to some ranks, multiple values can be separated with comma "," (e.g., -E "genus,species"), or give multiple times (e.g., -E genus -E species)', 'default': ''}),
                "higher_than": ('STRING', {'description': 'output ranks higher than a rank, exclusive with --lower-than', 'default': ''}),
                "list_order": ('BOOLEAN', {'description': 'list defined ranks in order', 'default': False}),
                "list_ranks": ('BOOLEAN', {'description': 'list ordered ranks in taxonomy database', 'default': False}),
                "lower_than": ('STRING', {'description': 'output ranks lower than a rank, exclusive with --higher-than', 'default': ''}),
                "rank_file": ('STRING', {'description': 'user-defined ordered taxonomic ranks, type "unikmer rfilter --help" for details', 'default': ''}),
                "root_taxid": ('STRING', {'description': 'root taxid', 'default': '1'}),
                "save_predictable_norank": ('BOOLEAN', {'description': 'do not discard some special ranks without order when using -L, where rank of the closest higher node is still lower than rank cutoff', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
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
        command.extend(['--out-prefix', "-"])
        command.append(str(inputs.get('input', "")))
        return command
