"""arriba — databases node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ArribaGetFiltersNode(CommandNode):
    """Copy bundled Arriba reference filter files into workflow outputs."""
    NODE_ID = 'arriba_get_filters'
    DISPLAY_NAME = 'Arriba Get Filters'
    REQUIRED_CONDA_PACKAGES = ['arriba']
    CATEGORY = 'databases'
    DESCRIPTION = 'Copy bundled Arriba blacklist, known-fusion, protein-domain, and cytoband reference files.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Arriba Get Filters', 'arriba_get_filters', 'blacklist', 'known fusions', 'protein domains', 'cytobands', 'download_references.sh']
    RETURN_TYPES = ('FILE', 'FILE', 'GFF', 'TSV')
    RETURN_NAMES = ('blacklist', 'known_fusions', 'protein_domains', 'cytobands')
    REQUIRED_EXECUTABLES = ['arriba', 'find', 'grep', 'cp']
    DOCUMENTATION_URL = 'https://github.com/suhrig/arriba/wiki/04-Input-files'
    CITATION_DOIS = [ARRIBA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{ARRIBA_CITATION_DOI}']
    CITATION_TEXT = ARRIBA_CITATION_TEXT
    VERSION = '2.5.1+galaxy0'
    SHELL = True
    REFERENCES = ['GRCh38', 'GRCh37', 'hg38', 'hg19', 'GRCm39', 'GRCm38', 'mm39', 'mm10']
    OUTPUT_FILES = {'blacklist': 'blacklist.tsv.gz', 'known_fusions': 'known_fusions.tsv.gz', 'protein_domains': 'protein_domains.gff3', 'cytobands': 'cytobands.tsv'}

    @classmethod
    def _reference_name(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('arriba_reference_name', 'GRCh38') or 'GRCh38').split('+')[0].replace('viral', '')

    @classmethod
    def _path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f'{_out(inputs)}/{filename}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        ref_name = cls._reference_name(inputs)
        commands = ['BASE_DIR=$(dirname $(dirname $(which arriba)))', 'REF_SCRIPT=$(find $BASE_DIR -name download_references.sh)', 'REF_DIR=$(dirname $REF_SCRIPT)', f'REF_NAME={shlex.quote(ref_name)}', 'echo $REF_NAME']
        for pattern, filename in [('blacklist_*', cls.OUTPUT_FILES['blacklist']), ('known_fusions_*', cls.OUTPUT_FILES['known_fusions']), ('protein_domains_*', cls.OUTPUT_FILES['protein_domains']), ('cytobands_*', cls.OUTPUT_FILES['cytobands'])]:
            commands.append(f"cp $(find $REF_DIR -name '{pattern}' | grep -i $REF_NAME) {shlex.quote(cls._path(inputs, filename))}")
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILES['blacklist'], out / cls.OUTPUT_FILES['known_fusions'], out / cls.OUTPUT_FILES['protein_domains'], out / cls.OUTPUT_FILES['cytobands']]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        ref_name = cls._reference_name(inputs)
        if ref_name not in cls.REFERENCES:
            return f"arriba_reference_name must be one of: {', '.join(cls.REFERENCES)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'arriba_reference_name': ('STRING', {'default': 'GRCh38', 'options': cls.REFERENCES, 'description': 'Bundled Arriba reference file set to copy'})}, 'hidden': {'output': ('STRING', {})}}
