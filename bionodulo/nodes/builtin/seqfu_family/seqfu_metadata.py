"""``seqfu metadata``: Prepare mapping files from a directory containing FASTQ files.

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: 1d33f3f7cb3bd8d24677ffb39340a7848b4f04612b89eba72b13c39b5c2e1093

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import SeqfuBase


class SeqfuMetadataNode(SeqfuBase):
    """Prepare mapping files from a directory containing FASTQ files"""

    NODE_ID = 'seqfu_metadata'
    DISPLAY_NAME = 'seqfu metadata'
    SUBCOMMAND = 'metadata'
    DESCRIPTION = 'Prepare mapping files from a directory containing FASTQ files'
    SEARCH_ALIASES = ['seqfu', 'metadata']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqfu_metadata.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://telatin.github.io/seqfu2/'
    REQUIRED_EXECUTABLES = ['seqfu']
    REQUIRED_CONDA_PACKAGES = ['seqfu']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input_dir': ('DIRECTORY', {"description": "Input input dir"}),

            },
            "optional": {
                "for_tag": ('STRING', {'description': 'String found in filename of forward reads', 'default': '_R1'}),
                "rev_tag": ('STRING', {'description': 'String found in filename of forward reads', 'default': '_R2'}),
                "split": ('STRING', {'description': 'Separator used in filename to identify the sample ID', 'default': '_'}),
                "format": ('STRING', {'description': 'Output format: dadaist, irida, manifest,... list to list', 'default': 'manifest'}),
                "add_path": ('BOOLEAN', {'description': 'Add the reads absolute path as column', 'default': False}),
                "counts": ('BOOLEAN', {'description': 'Add the number of reads as a property column (experimental)', 'default': False}),
                "threads": ('INT', {'description': 'Number of simultaneously opened files (legacy: ignored)', 'default': ''}),
                "pe": ('BOOLEAN', {'description': 'Enforce paired-end reads (not supported)', 'default': False}),
                "ont": ('BOOLEAN', {'description': 'Long reads (Oxford Nanopore)', 'default': False}),
                "abs": ('BOOLEAN', {'description': 'Force absolute path', 'default': False}),
                "basename": ('BOOLEAN', {'description': 'Use basename instead of full path', 'default': False}),
                "force_tsv": ('BOOLEAN', {'description': "Force '\\t' separator, otherwise selected by the format", 'default': False}),
                "force_csv": ('BOOLEAN', {'description': "Force ',' separator, otherwise selected by the format", 'default': False}),
                "rand_meta": ('INT', {'description': 'Add a random metadata column with INT categories', 'default': ''}),
                "project": ('INT', {'description': 'Project ID (only for irida)', 'default': ''}),
                "meta_split": ('STRING', {'description': 'Separator in the SampleID to extract metadata, used in MetaPhage', 'default': '_'}),
                "meta_part": ('INT', {'description': 'Which part of the SampleID to extract metadata, used in MetaPhage', 'default': 1}),
                "meta_default": ('STRING', {'description': 'Default value for metadata, used in MetaPhage', 'default': 'Cond'}),
                "debug": ('BOOLEAN', {'description': 'Debug output', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['seqfu', cls.SUBCOMMAND]
        # Required flags must be rendered too. Iterating only "optional" silently
        # dropped every empirically-required flag (csvtk mutate --name and friends).
        declared_types = cls.INPUT_TYPES()
        for category in ("required", "optional"):
            for name, spec in declared_types.get(category, {}).items():
                if name in ('input_dir',):
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
        command.append(str(inputs.get('input_dir', "")))
        return command
