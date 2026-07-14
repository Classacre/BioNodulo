"""mothur — taxonomy node(s). One tool per file (extracted from wrapped_taxonomy_humann.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class MothurTaxonomyToKronaNode(CommandNode):
    """Convert mothur consensus taxonomy tables to Krona text input."""
    NODE_ID = 'mothur_taxonomy_to_krona'
    DISPLAY_NAME = 'Taxonomy-to-Krona'
    REQUIRED_CONDA_PACKAGES = []
    CATEGORY = 'taxonomy'
    DESCRIPTION = 'Convert a mothur consensus taxonomy file to Krona text input format.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'mothur', 'mothur_taxonomy_to_krona', 'Taxonomy-to-Krona', 'mothur consensus taxonomy', 'Krona text input', 'strip confidence values', 'cons.taxonomy']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('outputfile',)
    REQUIRED_EXECUTABLES = ['cat', 'tail', 'cut', 'sed']
    DOCUMENTATION_URL = 'https://marbl.github.io/Krona/Documentation/'
    CITATION_DOIS = [MOTHUR_DOI, KRONA_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CITATION_DOIS]
    CITATION_TEXT = f"{MOTHUR_CITATION_TEXT} {KRONA_CITATION_TEXT.split(';', 1)[0]}."
    VERSION = '1.0'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/krona_taxonomy.tsv'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        pipeline = [f"cat {shlex.quote(str(inputs.get('inputfile', '')))}", 'tail -n +2', 'cut -f2,3', "sed 's/;/\\t/g'", 'sed \'s/"//g\'', "sed 's/[ \\t]*$//'"]
        if inputs.get('stripconfidences', False):
            pipeline.append("sed -r 's/[(][0-9]+[)]//g'")
        return f"{' | '.join(pipeline)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'krona_taxonomy.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('inputfile', '')).strip():
            return 'inputfile is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'inputfile': ('TSV', {'description': 'Mothur consensus taxonomy table with OTU, size, and taxonomy columns'})}, 'optional': {'stripconfidences': ('BOOLEAN', {'default': False, 'description': 'Remove taxonomy confidence values such as Bacteria(100)'})}, 'hidden': {'output': ('STRING', {})}}
