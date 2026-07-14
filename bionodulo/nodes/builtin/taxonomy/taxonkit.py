"""taxonkit — taxonomy node(s). One tool per file (extracted from wrapped_taxonomy_humann.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class TaxonKitName2TaxidNode(CommandNode):
    """Convert taxon names to NCBI taxonomy identifiers with TaxonKit."""
    NODE_ID = 'taxonkit_name2taxid'
    DISPLAY_NAME = 'Name2taxid'
    REQUIRED_CONDA_PACKAGES = ['taxonkit', 'tar']
    CATEGORY = 'taxonomy'
    DESCRIPTION = 'Convert NCBI taxon names in a tabular column to taxids with TaxonKit.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'TaxonKit', 'Name2taxid', 'TaxonKit name2taxid', 'NCBI taxid lookup', 'taxon names to taxids']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['taxonkit', 'tar']
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/taxonkit/'
    CITATION_DOIS = ['10.1016/j.jgg.2021.03.006']
    CITATION_URLS = [f'{DOI_URL}10.1016/j.jgg.2021.03.006']
    CITATION_TEXT = 'TaxonKit: a practical and efficient NCBI taxonomy toolkit.'
    VERSION = '0.20.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        setup = [shlex.join(['mkdir', '-p', out, '.taxonkit'])]
        data_source = str(inputs.get('data_source', 'cached') or 'cached')
        if data_source == 'history':
            taxdump = str(inputs.get('taxdump', ''))
            setup.extend([shlex.join(['ln', '-s', taxdump, 'taxdump.tar.gz']), shlex.join(['tar', '-xf', 'taxdump.tar.gz', '-C', '.'])])
        else:
            taxonomy_dir = str(inputs.get('taxonomy_dir', ''))
            for filename in ['names.dmp', 'merged.dmp', 'nodes.dmp', 'delnodes.dmp']:
                setup.append(shlex.join(['ln', '-s', f'{taxonomy_dir}/{filename}', filename]))
        cmd = ['taxonkit', 'name2taxid', '--data-dir', '.', '--name-field', str(inputs.get('name_field', ''))]
        if inputs.get('sci_name'):
            cmd.append('--sci-name')
        if inputs.get('show_rank'):
            cmd.append('--show-rank')
        cmd.append(str(inputs.get('input', '')))
        return ' && '.join([*setup, f"{shlex.join(cmd)} > {shlex.quote(f'{out}/names2taxid.tsv')}"])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'names2taxid.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        raw_name_field = inputs.get('name_field')
        if raw_name_field is None or str(raw_name_field) == '':
            return 'name_field is required'
        try:
            name_field = int(raw_name_field)
        except (TypeError, ValueError):
            return 'name_field must be an integer'
        if name_field < 1:
            return 'name_field must be >= 1'
        data_source = str(inputs.get('data_source', 'cached') or 'cached')
        if data_source not in {'cached', 'history'}:
            return 'data_source must be one of: cached, history'
        if data_source == 'history' and (not str(inputs.get('taxdump', '')).strip()):
            return 'taxdump is required when data_source is history'
        if data_source == 'cached' and (not str(inputs.get('taxonomy_dir', '')).strip()):
            return 'taxonomy_dir is required when data_source is cached'
        return super().VALIDATE_INPUTS(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('TSV', {'description': 'Tabular or one-name-per-line input containing NCBI taxon names'}), 'name_field': ('INT', {'min': 1, 'default': 1, 'description': 'One-based column containing taxon names'}), 'data_source': ('STRING', {'default': 'cached', 'options': ['cached', 'history'], 'description': 'Use cached taxonomy files or a taxdump archive'})}, 'optional': {'taxonomy_dir': ('DIRECTORY', {'default': '', 'description': 'Cached NCBI taxonomy directory containing names.dmp, nodes.dmp, merged.dmp, and delnodes.dmp'}), 'taxdump': ('FILE', {'default': '', 'description': 'NCBI taxdump.tar.gz archive when data_source is history'}), 'sci_name': ('BOOLEAN', {'default': False, 'description': 'Only search scientific names'}), 'show_rank': ('BOOLEAN', {'default': False, 'description': 'Include the resolved taxon rank in the output'})}, 'hidden': {'output': ('STRING', {})}}


class TaxonKitProfile2CamiNode(CommandNode):
    """Convert taxonomic abundance profiles to CAMI format with TaxonKit."""
    NODE_ID = 'taxonkit_profile2cami'
    DISPLAY_NAME = 'Profile2CAMI'
    REQUIRED_CONDA_PACKAGES = ['taxonkit']
    CATEGORY = 'taxonomy'
    DESCRIPTION = 'Convert metagenomic taxonomic profile tables to CAMI format with TaxonKit.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'TaxonKit', 'Profile2CAMI', 'TaxonKit profile2cami', 'CAMI profile format', 'taxonomic profile conversion']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('cami_output',)
    REQUIRED_EXECUTABLES = ['taxonkit']
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/taxonkit/'
    CITATION_DOIS = ['10.1016/j.jgg.2021.03.006']
    CITATION_URLS = [f'{DOI_URL}10.1016/j.jgg.2021.03.006']
    CITATION_TEXT = 'TaxonKit: a practical and efficient NCBI taxonomy toolkit.'
    VERSION = '0.20.0'
    SHELL = True
    RANKS = ['superkingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species', 'strain']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ['taxonkit', 'profile2cami', '--data-dir', str(inputs.get('taxonomy', '')), '--abundance-field', str(inputs.get('abundance_field', 2)), '--taxid-field', str(inputs.get('taxid_field', 1))]
        for input_name, flag in (('percentage', '-p'), ('recompute_abd', '-R'), ('keep_zero', '-0'), ('no_sum_up', '-S')):
            if inputs.get(input_name):
                cmd.append(flag)
        _add_if_value(cmd, '-s', inputs.get('sample_id'))
        _add_if_value(cmd, '-t', inputs.get('taxonomy_id'))
        ranks = _as_list(inputs.get('ranks'))
        if ranks:
            cmd.extend(['--show-rank', ','.join(ranks)])
        cmd.append(str(inputs.get('input_file', '')))
        return f"{shlex.join(cmd)} > {shlex.quote(f'{out}/cami_profile.tsv')}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'cami_profile.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'input_file is required'
        if not str(inputs.get('taxonomy', '')).strip():
            return 'taxonomy is required'
        for name in ['abundance_field', 'taxid_field']:
            raw = inputs.get(name)
            if raw is None or str(raw) == '':
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < 1:
                return f'{name} must be >= 1'
        unsupported_ranks = [rank for rank in _as_list(inputs.get('ranks')) if rank not in cls.RANKS]
        if unsupported_ranks:
            return f"ranks contains unsupported values: {', '.join(unsupported_ranks)}"
        return super().VALIDATE_INPUTS(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('TSV', {'description': 'Tab-delimited profile table with TaxId and abundance columns'}), 'taxonomy': ('DIRECTORY', {'description': 'NCBI taxonomy directory used by TaxonKit'})}, 'optional': {'abundance_field': ('INT', {'default': 2, 'min': 1, 'description': 'One-based abundance field index'}), 'taxid_field': ('INT', {'default': 1, 'min': 1, 'description': 'One-based TaxId field index'}), 'percentage': ('BOOLEAN', {'default': False, 'description': 'Input abundances are percentages'}), 'recompute_abd': ('BOOLEAN', {'default': False, 'description': 'Recompute abundance when deleted TaxIds are encountered'}), 'keep_zero': ('BOOLEAN', {'default': False, 'description': 'Keep taxa with zero abundance'}), 'no_sum_up': ('BOOLEAN', {'default': False, 'description': 'Do not sum abundance from children to parents'}), 'sample_id': ('STRING', {'default': '', 'description': 'Optional sample ID to include in the CAMI output'}), 'taxonomy_id': ('STRING', {'default': '', 'description': 'Optional taxonomy ID to include in the CAMI output'}), 'ranks': ('STRING', {'default': [], 'multiple': True, 'options': cls.RANKS, 'description': 'Ranks to show in the CAMI output'})}, 'hidden': {'output': ('STRING', {})}}
