"""eukrep — metagenomics node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class EukRepNode(CommandNode):
    """Classify eukaryotic and prokaryotic metagenomic sequences."""
    NODE_ID = 'eukrep'
    DISPLAY_NAME = 'EukRep'
    REQUIRED_CONDA_PACKAGES = ['eukrep']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Classify eukaryotic and prokaryotic sequences from metagenomic datasets with EukRep.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'EukRep', 'eukrep', 'metagenomic eukaryotes', 'eukaryotic scaffolds', 'prokaryotic sequences', 'metagenome classification', 'SVM k-mer classifier']
    RETURN_TYPES = ('FASTA', 'FASTA', 'STATS_FILE', 'STATS_FILE')
    RETURN_NAMES = ('eukaryote_sequences', 'prokaryote_sequences', 'eukaryote_names', 'prokaryote_names')
    REQUIRED_EXECUTABLES = ['EukRep']
    DOCUMENTATION_URL = 'https://github.com/patrickwest/EukRep'
    CITATION_DOIS = [EUKREP_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{EUKREP_CITATION_DOI}']
    CITATION_TEXT = EUKREP_CITATION_TEXT
    VERSION = '0.6.7'
    SHELL = True

    @classmethod
    def _staged_input_name(cls, input_path: Any) -> str:
        suffixes = Path(str(input_path or '')).suffixes
        if len(suffixes) >= 2 and suffixes[-2:] == ['.fa', '.gz']:
            return 'input.fa.gz'
        if len(suffixes) >= 2 and suffixes[-2:] == ['.fasta', '.gz']:
            return 'input.fasta.gz'
        suffix = suffixes[-1] if suffixes else '.fa'
        return f'input{suffix}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged = cls._staged_input_name(inputs.get('input'))
        cmd = ['EukRep', '-i', staged, '-o', f'{_out(inputs)}/output.fa', '--min', str(inputs.get('min', 3000)), '--kmer_len', str(inputs.get('kmer_len', 5))]
        if inputs.get('prokarya'):
            cmd.extend(['--prokarya', f'{_out(inputs)}/output_prokarya.fa'])
        if inputs.get('seq_names'):
            cmd.append('--seq_names')
        cmd.extend(['-m', str(inputs.get('stringency', 'balanced') or 'balanced'), '--tie', str(inputs.get('tie', 'euk') or 'euk')])
        return f"ln -s {shlex.quote(str(inputs.get('input', '')))} {staged} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'output.fa']
        if inputs.get('prokarya'):
            outputs.append(out / 'output_prokarya.fa')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('input'):
            return 'input FASTA is required'
        try:
            min_length = int(inputs.get('min', 3000))
        except (TypeError, ValueError):
            return 'min must be an integer'
        if min_length < 0:
            return 'min must be >= 0'
        try:
            kmer_len = int(inputs.get('kmer_len', 5))
        except (TypeError, ValueError):
            return 'kmer_len must be an integer'
        if not 3 <= kmer_len <= 6:
            return 'kmer_len must be between 3 and 6'
        stringency = str(inputs.get('stringency', 'balanced') or 'balanced')
        if stringency not in {'strict', 'balanced', 'lenient'}:
            return 'stringency must be one of: strict, balanced, lenient'
        tie = str(inputs.get('tie', 'euk') or 'euk')
        if tie not in {'euk', 'prok', 'rand', 'skip'}:
            return 'tie must be one of: euk, prok, rand, skip'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTA', {'description': 'Metagenomic sequences in FASTA or FASTA.GZ format'})}, 'optional': {'min': ('INT', {'default': 3000, 'min': 0, 'description': 'Minimum sequence length for prediction'}), 'kmer_len': ('INT', {'default': 5, 'min': 3, 'max': 6, 'description': 'K-mer length'}), 'prokarya': ('BOOLEAN', {'default': False, 'description': 'Also output predicted prokaryotic sequences'}), 'seq_names': ('BOOLEAN', {'default': False, 'description': 'Output sequence headers instead of full FASTA records'}), 'stringency': ('STRING', {'default': 'balanced', 'options': ['strict', 'balanced', 'lenient'], 'description': 'Eukaryotic scaffold classification stringency'}), 'tie': ('STRING', {'default': 'euk', 'options': ['euk', 'prok', 'rand', 'skip'], 'description': 'How to handle equal eukaryotic/prokaryotic chunk predictions'})}, 'hidden': {'output': ('STRING', {})}}
