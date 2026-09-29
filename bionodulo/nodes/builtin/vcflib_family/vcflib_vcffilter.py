"""``vcffilter ``: vcflib filter the specified vcf file using the set of filters.

Generated from the tool's own --help output in the pinned vcffilter 1.0.15 image.
Help page SHA-256: 8296f64422f64e634cb20b8721a1b5b09d6fd55652842bf333efaa435fbe64fb

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcffilterNode(VcflibBase):
    """vcflib filter the specified vcf file using the set of filters"""

    NODE_ID = 'vcflib_vcffilter'
    DISPLAY_NAME = 'vcffilter'
    DESCRIPTION = 'vcflib filter the specified vcf file using the set of filters'
    SEARCH_ALIASES = ['vcffilter']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcffilter.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcffilter']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "info_filter": ('STRING', {'description': 'specifies a filter to apply to the info fields of records, removes alleles which do not pass the filter', 'default': ''}),
                "genotype_filter": ('STRING', {'description': 'specifies a filter to apply to the genotype fields of records', 'default': ''}),
                "keep_info": ('BOOLEAN', {'description': "used in conjunction with '-g', keeps variant info, but removes genotype", 'default': False}),
                "filter_sites": ('BOOLEAN', {'description': 'filter entire records, not just alleles', 'default': False}),
                "tag_pass": ('STRING', {'description': 'tag vcf records as positively filtered with this tag, print all records', 'default': ''}),
                "tag_fail": ('STRING', {'description': 'tag vcf records as negatively filtered with this tag, print all records', 'default': ''}),
                "append_filter": ('BOOLEAN', {'description': "append the existing filter tag, don't just replace it", 'default': False}),
                "allele_tag": ('STRING', {'description': 'apply -t on a per-allele basis.  adds or sets the corresponding INFO field tag', 'default': ''}),
                "invert": ('BOOLEAN', {'description': 'inverts the filter, e.g. grep -v', 'default': False}),
                "or": ('BOOLEAN', {'description': 'use logical OR instead of AND to combine filters', 'default': False}),
                "region": ('STRING', {'description': 'specify a region on which to target the filtering, requires a BGZF compressed file which has been indexed with tabix.  any number of regions may be specified.', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcffilter']
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
