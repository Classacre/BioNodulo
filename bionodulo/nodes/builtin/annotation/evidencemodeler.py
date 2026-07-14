"""evidencemodeler — annotation node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class EvidenceModelerNode(CommandNode):
    """Combine gene prediction evidence into consensus gene structures with EVidenceModeler."""
    NODE_ID = 'evidencemodeler'
    DISPLAY_NAME = 'EVidenceModeler'
    REQUIRED_CONDA_PACKAGES = ['evidencemodeler']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Combine ab initio gene predictions, protein alignments, and transcript alignments into consensus gene structures.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'EVidenceModeler', 'EvidenceModeler gene structure consensus', 'EVM', 'gene predictions', 'protein alignments', 'transcript alignments']
    RETURN_TYPES = ('GFF3', 'FASTA')
    RETURN_NAMES = ('evm_gff', 'evm_pep')
    REQUIRED_EXECUTABLES = ['EVidenceModeler']
    DOCUMENTATION_URL = 'https://github.com/EVidenceModeler/EVidenceModeler.github.io'
    CITATION_DOIS = ['10.1186/gb-2008-9-1-r7', '10.1080/21501203.2011.606851']
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CITATION_DOIS]
    CITATION_TEXT = 'Automated eukaryotic gene structure annotation using EVidenceModeler and the Program to Assemble Spliced Alignments; Eukaryotic genome annotation using EVidenceModeler and the Program to Assemble Spliced Alignments.'
    VERSION = '2.1.0'
    SHELL = True
    STOP_CODONS = ['TAA', 'TGA', 'TAG']
    BINARY_OPTIONS = ['0', '1']

    @classmethod
    def _stop_codons(cls, inputs: dict[str, Any]) -> str:
        values = _as_list(inputs.get('stop_codon'))
        return ','.join(values) if values else 'TAA,TGA,TAG'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(['ln', '-s', str(inputs.get('input_genome', '')), 'input_genome.fasta']), _shell_join(['ln', '-s', str(inputs.get('input_predictions', '')), 'input_predictions.gff']), _shell_join(['ln', '-s', str(inputs.get('input_weights', '')), 'input_weights.txt']), _shell_join(['ln', '-s', str(inputs.get('input_proteins', '')), 'input_proteins.gff'])]
        if inputs.get('input_transcript'):
            commands.append(_shell_join(['ln', '-s', str(inputs.get('input_transcript')), 'input_transcript.gff']))
        cmd = ['EVidenceModeler', '--sample_id', 'galaxy', '--genome', './input_genome.fasta', '--gene_predictions', './input_predictions.gff', '--weights', './input_weights.txt', '--protein_alignments', './input_proteins.gff', '--segmentSize', str(inputs.get('segmentsize', 100000)), '--overlapSize', str(inputs.get('overlapsize', 10000))]
        if inputs.get('input_transcript'):
            cmd.extend(['--transcript_alignments', './input_transcript.gff'])
        _add_if_value(cmd, '--repeats', inputs.get('input_repeat'))
        _add_if_value(cmd, '--terminalExons', inputs.get('input_terminalexon'))
        cmd.extend(['--stop_codons', cls._stop_codons(inputs), '--min_intron_length', str(inputs.get('min_intron_length', 20)), '--search_long_introns', str(inputs.get('search_long_introns', 0)), '--re_search_intergenic', str(inputs.get('re_search_intergenic', 0)), '--terminal_intergenic_re_search', str(inputs.get('terminal_intergenic_re_search', 0))])
        commands.append(_shell_join(cmd))
        commands.append(_shell_join(['cp', 'galaxy.EVM.gff3', f'{out}/galaxy.EVM.gff3']))
        commands.append(_shell_join(['cp', 'galaxy.EVM.pep', f'{out}/galaxy.EVM.pep']))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'galaxy.EVM.gff3', out / 'galaxy.EVM.pep']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_genome': ('FASTA', {'description': 'Genome FASTA input'}), 'input_predictions': ('GFF3', {'description': 'Gene predictions GFF3'}), 'input_weights': ('TXT', {'description': 'EvidenceModeler weights file'}), 'input_proteins': ('GFF3', {'description': 'Protein alignment GFF3'})}, 'optional': {'input_transcript': ('GFF3', {'default': '', 'description': 'Transcript alignment GFF3'}), 'segmentsize': ('INT', {'default': 100000, 'min': 1, 'description': 'Length of one sequence segment'}), 'overlapsize': ('INT', {'default': 10000, 'min': 0, 'description': 'Sequence overlap between segments'}), 'input_repeat': ('GFF3', {'default': '', 'description': 'Masked genome repeats'}), 'input_terminalexon': ('GFF3', {'default': '', 'description': 'Terminal exon evidence file'}), 'stop_codon': ('STRING_LIST', {'default': ['TAA', 'TGA', 'TAG'], 'options': cls.STOP_CODONS, 'description': 'Stop codons to use'}), 'min_intron_length': ('INT', {'default': 20, 'min': 0}), 'search_long_introns': ('STRING', {'default': '0', 'options': cls.BINARY_OPTIONS}), 're_search_intergenic': ('STRING', {'default': '0', 'options': cls.BINARY_OPTIONS}), 'terminal_intergenic_re_search': ('STRING', {'default': '0', 'options': cls.BINARY_OPTIONS})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ['input_genome', 'input_predictions', 'input_weights', 'input_proteins']:
            if not str(inputs.get(name, '')).strip():
                return f'{name} is required'
        for name, minimum in {'segmentsize': 1, 'overlapsize': 0, 'min_intron_length': 0}.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == '':
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < minimum:
                return f'{name} must be >= {minimum}'
        for name in ['search_long_introns', 're_search_intergenic', 'terminal_intergenic_re_search']:
            value = str(inputs.get(name, 0))
            if value not in cls.BINARY_OPTIONS:
                return f'{name} must be one of: 0, 1'
        stop_codons = _as_list(inputs.get('stop_codon'))
        if stop_codons and any((codon not in cls.STOP_CODONS for codon in stop_codons)):
            return 'stop_codon values must be one or more of: TAA, TGA, TAG'
        return super().VALIDATE_INPUTS(inputs)
