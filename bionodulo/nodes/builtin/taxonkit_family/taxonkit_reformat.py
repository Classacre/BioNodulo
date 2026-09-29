"""``taxonkit reformat``: Reformat lineage in canonical ranks.

Generated from the tool's own --help output in the pinned taxonkit v0.20.0 image.
Help page SHA-256: bd990d7acb17e43baf2f4cc71a01f112ef0b000802ae37c11559202dfaf0e14e

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import TaxonkitBase


class TaxonkitReformatNode(TaxonkitBase):
    """Reformat lineage in canonical ranks"""

    NODE_ID = 'taxonkit_reformat'
    DISPLAY_NAME = 'taxonkit reformat'
    SUBCOMMAND = 'reformat'
    DESCRIPTION = 'Reformat lineage in canonical ranks'
    SEARCH_ALIASES = ['taxonkit', 'reformat']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('taxonkit_reformat.out',)
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
                "add_prefix": ('BOOLEAN', {'description': 'add prefixes for all ranks, single prefix for a rank is defined by flag --prefix-X', 'default': False}),
                "fill_miss_rank": ('BOOLEAN', {'description': 'fill missing rank with lineage information of the next higher rank', 'default': False}),
                "format": ('STRING', {'description': 'output format, placeholders of rank are needed (default "{k};{p};{c};{o};{f};{g};{s}")', 'default': ''}),
                "lineage_field": ('INT', {'description': 'field index of lineage. data should be tab-separated', 'default': 2}),
                "miss_rank_repl": ('STRING', {'description': 'replacement string for missing rank', 'default': ''}),
                "miss_rank_repl_prefix": ('STRING', {'description': 'prefix for estimated taxon names', 'default': 'unclassified '}),
                "miss_rank_repl_suffix": ('STRING', {'description': 'suffix for estimated taxon names. "rank" for rank name, "" for no suffix (default "rank")', 'default': ''}),
                "miss_taxid_repl": ('STRING', {'description': 'replacement string for missing taxid', 'default': ''}),
                "output_ambiguous_result": ('BOOLEAN', {'description': 'output one of the ambigous result', 'default': False}),
                "prefix_C": ('STRING', {'description': 'prefix for cellular root, used along with flag -P/--add-prefix (default "d__")', 'default': ''}),
                "prefix_K": ('STRING', {'description': 'prefix for kingdom, used along with flag -P/--add-prefix (default "K__")', 'default': ''}),
                "prefix_S": ('STRING', {'description': 'prefix for subspecies, used along with flag -P/--add-prefix (default "S__")', 'default': ''}),
                "prefix_T": ('STRING', {'description': 'prefix for strain, used along with flag -P/--add-prefix (default "T__")', 'default': ''}),
                "prefix_a": ('STRING', {'description': 'prefix for acellular root, used along with flag -P/--add-prefix (default "d__")', 'default': ''}),
                "prefix_c": ('STRING', {'description': 'prefix for class, used along with flag -P/--add-prefix', 'default': 'c__'}),
                "prefix_d": ('STRING', {'description': 'prefix for domain, used along with flag -P/--add-prefix (default "d__")', 'default': ''}),
                "prefix_f": ('STRING', {'description': 'prefix for family, used along with flag -P/--add-prefix (default "f__")', 'default': ''}),
                "prefix_g": ('STRING', {'description': 'prefix for genus, used along with flag -P/--add-prefix', 'default': 'g__'}),
                "prefix_k": ('STRING', {'description': 'prefix for superkingdom, used along with flag -P/--add-prefix (default "k__")', 'default': ''}),
                "prefix_o": ('STRING', {'description': 'prefix for order, used along with flag -P/--add-prefix', 'default': 'o__'}),
                "prefix_p": ('STRING', {'description': 'prefix for phylum, used along with flag -P/--add-prefix (default "p__")', 'default': ''}),
                "prefix_r": ('STRING', {'description': 'prefix for realm, used along with flag -P/--add-prefix', 'default': 'r__'}),
                "prefix_s": ('STRING', {'description': 'prefix for species, used along with flag -P/--add-prefix (default "s__")', 'default': ''}),
                "prefix_t": ('STRING', {'description': 'prefix for subspecies/strain, used along with flag -P/--add-prefix (default "t__")', 'default': ''}),
                "pseudo_strain": ('BOOLEAN', {'description': 'use the node with lowest rank as strain name, only if which rank is lower than "species" and not "subpecies" nor "strain". It affects {t}, {S}, {T}. This flag needs flag -F', 'default': False}),
                "show_lineage_taxids": ('BOOLEAN', {'description': 'show corresponding taxids of reformated lineage', 'default': False}),
                "taxid_field": ('INT', {'description': 'field index of taxid. input data should be tab-separated. it overrides -i/--lineage-field', 'default': ''}),
                "trim": ('BOOLEAN', {'description': 'do not fill or add prefix for missing rank lower than current rank', 'default': False}),
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
