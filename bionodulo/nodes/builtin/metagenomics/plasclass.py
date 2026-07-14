"""plasclass — metagenomics node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class PlasClassNode(CommandNode):
    """Classify assembled contigs as plasmid or chromosome sequences."""
    NODE_ID = 'plasclass'
    DISPLAY_NAME = 'PlasClass'
    REQUIRED_CONDA_PACKAGES = ['plasclass']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Classify plasmid and chromosome sequences in metagenomic or isolate assemblies with PlasClass.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'PlasClass', 'plasclass', 'plasmid sequence classification', 'plasmid classifier', 'chromosome classification', 'metagenomic contigs', 'isolate assemblies']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('classification_scores',)
    REQUIRED_EXECUTABLES = ['classify_fasta.py']
    DOCUMENTATION_URL = 'https://github.com/Shamir-Lab/PlasClass'
    CITATION_DOIS = [PLASCLASS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{PLASCLASS_CITATION_DOI}']
    CITATION_TEXT = PLASCLASS_CITATION_TEXT
    VERSION = '0.1.1'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return ['classify_fasta.py', '--fasta', str(inputs.get('fasta', '')), '--outfile', f'{_out(inputs)}/classification_scores.tsv', '--num_processes', f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'classification_scores.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('fasta'):
            return 'input FASTA is required'
        threads = inputs.get('threads', 1)
        try:
            if int(threads) < 1:
                return 'threads must be >= 1'
        except (TypeError, ValueError):
            return 'threads must be an integer'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'fasta': ('FASTA', {'description': 'FASTA sequences to classify as plasmid or chromosome contigs'})}, 'optional': {'threads': ('INT', {'default': 1, 'min': 1, 'max': 64})}, 'hidden': {'output': ('STRING', {})}}
