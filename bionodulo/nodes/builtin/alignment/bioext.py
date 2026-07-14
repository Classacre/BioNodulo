"""bioext — alignment node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BioExtBam2MsaNode(CommandNode):
    """Extract a FASTA multiple sequence alignment from an indexed BAM/SAM alignment."""
    NODE_ID = 'bioext_bam2msa'
    DISPLAY_NAME = 'Convert BAM'
    REQUIRED_CONDA_PACKAGES = ['python-bioext']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Convert indexed BAM or SAM alignments to a FASTA multiple sequence alignment with BioExt bam2msa.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'BioExt', 'bioext_bam2msa', 'bam2msa', 'Convert BAM', 'BAM to FASTA MSA', 'multiple sequence alignment', 'alignment extraction', 'HyPhy']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['bam2msa']
    DOCUMENTATION_URL = BIOEXT_DOCUMENTATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [BIOEXT_CITATION_URL]
    CITATION_TEXT = BIOEXT_CITATION_TEXT
    VERSION = '0.21.10+galaxy0'
    SHELL = True

    @classmethod
    def _region_values(cls, inputs: dict[str, Any]) -> tuple[int, int]:
        start = int(inputs.get('region_start', 0) or 0)
        end = int(inputs.get('region_end', 0) or 0)
        return (start, end)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_bam = f'{out}/input_bam'
        input_index = f'{input_bam}.bai'
        output = f'{out}/output.fasta'
        cmd = [f"ln -sf {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(input_bam)}", f"ln -sf {shlex.quote(str(inputs.get('bam_index', inputs.get('input_index', ''))))} {shlex.quote(input_index)}"]
        bam2msa = ['bam2msa']
        start, end = cls._region_values(inputs)
        if start and end:
            bam2msa.extend(['-r', f'{start}:{end}'])
        bam2msa.extend([input_bam, output])
        cmd.append(_shell_join(bam2msa))
        return ' && '.join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output.fasta']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('BAM', {'description': 'Indexed BAM or SAM alignment to convert to a FASTA alignment'})}, 'optional': {'bam_index': ('FILE', {'description': 'BAM index used by bam2msa'}), 'region_start': ('INT', {'default': 0, 'min': 0, 'description': 'Optional starting coordinate for region extraction'}), 'region_end': ('INT', {'default': 0, 'min': 0, 'description': 'Optional ending coordinate for region extraction'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input BAM/SAM file is required'
        start, end = cls._region_values(inputs)
        if bool(start) != bool(end):
            return 'region_start and region_end must be provided together'
        if start and end < start:
            return 'region_end must be greater than or equal to region_start'
        return super().VALIDATE_INPUTS(inputs)


class BioExtBealignNode(CommandNode):
    """Align FASTA reads to a reference with BioExt bealign."""
    NODE_ID = 'bioext_bealign'
    DISPLAY_NAME = 'Align sequences'
    REQUIRED_CONDA_PACKAGES = ['python-bioext', 'gawk', 'samtools']
    CATEGORY = 'alignment'
    DESCRIPTION = "Align FASTA sequences to a preset or history reference using BioExt bealign's codon-aware algorithm."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'BioExt', 'bioext_bealign', 'bealign', 'Align sequences', 'codon alignment', 'reference alignment', 'BAM alignment', 'TN-93', 'HyPhy']
    RETURN_TYPES = ('BAM', 'BAM', 'FASTA', 'FASTA')
    RETURN_NAMES = ('output', 'background', 'saved_reference', 'discarded_reads')
    REQUIRED_EXECUTABLES = ['bealign', 'samtools', 'gawk', 'sed']
    DOCUMENTATION_URL = BIOEXT_DOCUMENTATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [BIOEXT_CITATION_URL]
    CITATION_TEXT = BIOEXT_CITATION_TEXT
    VERSION = '0.21.10+galaxy0'
    SHELL = True
    PRESET_REFERENCES = ['HXB2_tat', 'HXB2_gag', 'HXB2_pol', 'HXB2_int', 'HXB2_vif', 'HXB2_pr', 'HXB2_vpr', 'NL4-3_prrt', 'HXB2_nef', 'HXB2_env', 'HXB2_rt', 'HXB2_prrt', 'HXB2_rev', 'HXB2_vpu', 'CoV2-3C', 'CoV2-S', 'CoV2-E', 'CoV2-M', 'CoV2-N', 'CoV2-endornase', 'CoV2-exonuclease', 'CoV2-helicase', 'CoV2-leader', 'CoV2-methyltransferase', 'CoV2-nsp2', 'CoV2-nsp3', 'CoV2-nsp4', 'CoV2-nsp6', 'CoV2-nsp7', 'CoV2-nsp8', 'CoV2-nsp9', 'CoV2-nsp10', 'CoV2-ORF1a', 'CoV2-ORF1b', 'CoV2-ORF3a', 'CoV2-ORF5', 'CoV2-ORF6', 'CoV2-ORF7a', 'CoV2-ORF7b', 'CoV2-ORF8', 'CoV2-ORF10', 'CoV2-RdRp']
    ALPHABETS = ['codon', 'dna', 'amino']
    SCORE_MATRICES = ['BLOSUM62', 'DNA65', 'DNA70', 'DNA88', 'DNA80', 'DNA95', 'PAM200', 'PAM250', 'HIV_BETWEEN_F']

    @classmethod
    def _reference_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('reference_type', 'preset') or 'preset')

    @classmethod
    def _reference(cls, inputs: dict[str, Any]) -> str:
        default = 'CoV2-nsp8' if cls._reference_type(inputs) == 'preset' else ''
        return str(inputs.get('reference', default) or default)

    @classmethod
    def _threads(cls, inputs: dict[str, Any]) -> int:
        return int(inputs.get('threads', 2) or 2)

    @classmethod
    def _sanitize_command(cls, source: str, target: str) -> str:
        return f'cat {shlex.quote(source)} {BIOEXT_SANITIZE_PIPE} {shlex.quote(target)}'

    @classmethod
    def _bealign_command(cls, inputs: dict[str, Any], source_fasta: str, output_bam: str, *, background: bool=False) -> str:
        out = _out(inputs)
        threads = cls._threads(inputs)
        cmd = ['bealign', '--reference', cls._reference(inputs), '--alphabet', str(inputs.get('alphabet', 'codon') or 'codon')]
        expected_identity = inputs.get('expected_identity')
        if expected_identity is not None and str(expected_identity) != '':
            cmd.extend(['--expected-identity', str(expected_identity)])
        if background:
            cmd.append('--keep-reference')
        elif inputs.get('discard'):
            cmd.extend(['--discard', f'{out}/discarded_reads.fasta'])
        cmd.extend(['--score-matrix', str(inputs.get('score_matrix', 'BLOSUM62') or 'BLOSUM62')])
        if inputs.get('reverse_complement'):
            cmd.append('--reverse-complement')
        if not background and inputs.get('keep_reference'):
            cmd.append('--keep-reference')
        cmd.extend(['--no-sort', source_fasta, output_bam])
        return f'NCPU=${{GALAXY_SLOTS:-{threads}}} {_shell_join(cmd)}'

    @classmethod
    def _has_background(cls, inputs: dict[str, Any]) -> bool:
        return bool(str(inputs.get('background_sequences', inputs.get('sequences', ''))).strip())

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        threads = cls._threads(inputs)
        reads = f'{out}/reads.fa'
        raw_bam = f'{out}/bealign_out.bam'
        output = f'{out}/output.bam'
        commands = ['set -o pipefail', cls._sanitize_command(str(inputs.get('input', '')), reads), cls._bealign_command(inputs, reads, raw_bam), f'samtools sort -@${{GALAXY_SLOTS:-{threads}}} -T ${{TMPDIR:-.}} -O bam -o {shlex.quote(output)} {shlex.quote(raw_bam)}']
        if cls._has_background(inputs):
            background_fasta = f'{out}/background.fa'
            background_bam = f'{out}/bealign_background.bam'
            background_output = f'{out}/background.bam'
            background_source = str(inputs.get('background_sequences', inputs.get('sequences', '')))
            commands.extend([cls._sanitize_command(background_source, background_fasta), cls._bealign_command(inputs, background_fasta, background_bam, background=True), f'samtools sort -@${{GALAXY_SLOTS:-{threads}}} -T ${{TMPDIR:-.}} -O bam -o {shlex.quote(background_output)} {shlex.quote(background_bam)}'])
        if cls._reference_type(inputs) == 'preset' and inputs.get('save_reference'):
            commands.append(_shell_join(['python', str(inputs.get('copy_reference_script', 'copy_reference.py')), '--reference', cls._reference(inputs), '--dataset', f'{out}/saved_reference.fasta']))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'output.bam']
        if cls._has_background(inputs):
            outputs.append(out / 'background.bam')
        if cls._reference_type(inputs) == 'preset' and inputs.get('save_reference'):
            outputs.append(out / 'saved_reference.fasta')
        if inputs.get('discard'):
            outputs.append(out / 'discarded_reads.fasta')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTA', {'description': 'FASTA reads to sanitize and align against the selected reference'})}, 'optional': {'reference_type': ('STRING', {'default': 'preset', 'options': ['preset', 'dataset']}), 'reference': ('FASTA', {'description': 'Preset reference key or history FASTA reference'}), 'save_reference': ('BOOLEAN', {'default': False, 'description': 'Save a selected BioExt preset reference'}), 'background_source': ('STRING', {'default': 'data_table', 'options': ['data_table', 'history']}), 'background_sequences': ('FASTA', {'description': 'Optional background FASTA sequences'}), 'expected_identity': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'description': 'Discard sequences below this identity'}), 'alphabet': ('STRING', {'default': 'codon', 'options': cls.ALPHABETS}), 'score_matrix': ('STRING', {'default': 'BLOSUM62', 'options': cls.SCORE_MATRICES}), 'discard': ('BOOLEAN', {'default': False, 'description': 'Write discarded reads to FASTA'}), 'reverse_complement': ('BOOLEAN', {'default': False}), 'keep_reference': ('BOOLEAN', {'default': False}), 'copy_reference_script': ('FILE', {'default': 'copy_reference.py', 'advanced': True}), 'threads': ('INT', {'default': 2, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input FASTA reads are required'
        reference_type = cls._reference_type(inputs)
        if reference_type not in {'preset', 'dataset'}:
            return 'reference_type must be one of: preset, dataset'
        reference = cls._reference(inputs)
        if reference_type == 'dataset' and (not reference):
            return 'reference FASTA is required when reference_type is dataset'
        if reference_type == 'preset' and reference not in cls.PRESET_REFERENCES:
            return 'reference must be one of the BioExt preset references'
        alphabet = str(inputs.get('alphabet', 'codon') or 'codon')
        if alphabet not in cls.ALPHABETS:
            return f"alphabet must be one of: {', '.join(cls.ALPHABETS)}"
        score_matrix = str(inputs.get('score_matrix', 'BLOSUM62') or 'BLOSUM62')
        if score_matrix not in cls.SCORE_MATRICES:
            return f"score_matrix must be one of: {', '.join(cls.SCORE_MATRICES)}"
        expected_identity = inputs.get('expected_identity')
        if expected_identity is not None and str(expected_identity) != '':
            identity = float(expected_identity)
            if identity < 0 or identity > 1:
                return 'expected_identity must be between 0 and 1'
        return super().VALIDATE_INPUTS(inputs)
