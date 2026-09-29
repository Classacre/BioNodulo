"""``vcfintersect ``: vcflib 1.0.15 set analysis.

Generated from the tool's own --help output in the pinned vcfintersect 1.0.15 image.
Help page SHA-256: a902d5ec3767fe903fca0c19b32d7e828ee1c9b79ad3548f68539bbc7cffb58e

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfintersectNode(VcflibBase):
    """vcflib 1.0.15 set analysis"""

    NODE_ID = 'vcflib_vcfintersect'
    DISPLAY_NAME = 'vcfintersect'
    DESCRIPTION = 'vcflib 1.0.15 set analysis'
    SEARCH_ALIASES = ['vcfintersect']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfintersect.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfintersect']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "bed": ('STRING', {'description': 'use intervals provided by this BED file', 'default': ''}),
                "region": ('STRING', {'description': 'use 1-based tabix-style region (e.g. chrZ:10-20), multiples allowed', 'default': ''}),
                "start_only": ('BOOLEAN', {'description': "don't use the reference length information in the record to determine overlap status, just use the start posiion", 'default': False}),
                "invert": ('BOOLEAN', {'description': 'invert the selection, printing only records which would not have been printed out', 'default': False}),
                "intersect_vcf": ('STRING', {'description': 'use this VCF for set intersection generation', 'default': ''}),
                "union_vcf": ('STRING', {'description': 'use this VCF for set union generation', 'default': ''}),
                "window_size": ('STRING', {'description': 'compare records up to this many bp away', 'default': 'default 30'}),
                "reference": ('STRING', {'description': 'FASTA reference file, required with -i and -u', 'default': ''}),
                "loci": ('BOOLEAN', {'description': 'output whole loci when one alternate allele matches', 'default': False}),
                "ref_match": ('BOOLEAN', {'description': 'intersect on the basis of record REF string', 'default': False}),
                "tag": ('STRING', {'description': "attach TAG to each record's info field if it would intersect", 'default': ''}),
                "tag_value": ('STRING', {'description': "use this value to indicate that the allele is passing '.' will be used otherwise.  default: 'PASS'", 'default': ''}),
                "merge_from": ('STRING', {'description': 'FROM-TAG', 'default': ''}),
                "merge_to": ('STRING', {'description': 'TO-TAG   merge from FROM-TAG used in the -i file, setting TO-TAG in the current file.', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfintersect']
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
        command.append(str(inputs.get('input', "")))
        return command
