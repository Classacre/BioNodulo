"""extract — metagenomics node(s). One tool per file (extracted from wrapped_hyphy_metagenomics.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ExtractMetaPhlAnDatabaseNode(CommandNode):
    """Extract marker sequences and metadata from a cached MetaPhlAn database."""
    NODE_ID = 'extract_metaphlan_database'
    DISPLAY_NAME = 'Extract MetaPhlAn DB'
    REQUIRED_CONDA_PACKAGES = ['metaphlan']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Reconstruct marker sequences and marker metadata from a cached MetaPhlAn BowTie2 database.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'MetaPhlAn', 'bowtie2-inspect', 'marker sequences', 'marker metadata', 'customizemetadata.py']
    RETURN_TYPES = ('FASTA', 'JSON')
    RETURN_NAMES = ('marker_sequences', 'marker_metadata')
    REQUIRED_EXECUTABLES = ['bowtie2-inspect', 'python']
    DOCUMENTATION_URL = 'https://github.com/biobakery/MetaPhlAn'
    CITATION_DOIS = [METAPHLAN_DOI]
    CITATION_URLS = [f'{DOI_URL}{METAPHLAN_DOI}']
    CITATION_TEXT = METAPHLAN_CITATION_TEXT
    VERSION = '4.2.4'
    SHELL = True

    @classmethod
    def _database_prefix(cls, inputs: dict[str, Any]) -> str:
        database_path = str(inputs.get('database_path', '')).rstrip('/')
        database_key = str(inputs.get('database_key', ''))
        return f'{database_path}/{database_key}' if database_path else database_key

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        database_prefix = cls._database_prefix(inputs)
        inspect_cmd = ['bowtie2-inspect', database_prefix]
        _add_shell_redirect(inspect_cmd, f'{out}/marker_sequences.fasta')
        metadata_cmd = ['python', str(inputs.get('customizemetadata_script', 'customizemetadata.py')), 'transform_pkl_to_json', '--pkl', f'{database_prefix}.pkl', '--json', f'{out}/marker_metadata.json']
        return f'{_shell_join(inspect_cmd)} && {shlex.join(metadata_cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'marker_sequences.fasta', out / 'marker_metadata.json']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'database_path': ('DIRECTORY', {'description': 'Directory containing the cached MetaPhlAn BowTie2 database files'}), 'database_key': ('STRING', {'default': 'mpa_vJun23_CHOCOPhlAnSGB_202403', 'description': 'MetaPhlAn database key/prefix, used with the matching .pkl metadata file'})}, 'optional': {'customizemetadata_script': ('FILE', {'default': 'customizemetadata.py', 'description': 'Path to MetaPhlAn customizemetadata.py used to convert database metadata pickle to JSON'})}, 'hidden': {'output': ('STRING', {})}}
