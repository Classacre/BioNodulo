"""eastr — rna_seq node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class EASTRNode(CommandNode):
    """Detect and remove spurious RNA-seq splice junction alignments with EASTR."""
    NODE_ID = 'eastr'
    DISPLAY_NAME = 'EASTR'
    REQUIRED_CONDA_PACKAGES = ['eastr-cpp', 'bowtie2']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Emend spliced transcript read alignments by identifying and removing spurious splice junctions.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'EASTR', 'EASTR splice junction filtering', 'spurious splice junctions', 'spliced transcript reads', 'filtered BAM', 'Bowtie2 junction screening']
    RETURN_TYPES = ('BED', 'BAM', 'BED', 'BED', 'TXT')
    RETURN_NAMES = ('removed_junctions', 'filtered_bam', 'kept_junctions', 'original_junctions', 'log')
    REQUIRED_EXECUTABLES = ['eastr', 'bowtie2-build']
    DOCUMENTATION_URL = 'https://github.com/iepertea/EASTR'
    CITATION_DOIS = ['10.1038/s41467-023-43017-4']
    CITATION_URLS = [f'{DOI_URL}10.1038/s41467-023-43017-4']
    CITATION_TEXT = 'EASTR: identifying and eliminating systematic spurious spliced alignments in RNA-seq data.'
    VERSION = '2.1.1'
    SHELL = True
    INPUT_SELECT_OPTIONS = ['bam', 'gtf', 'bed']
    ADVANCED_INT_OPTIONS = {'bt2_k': ('--bt2_k', 10), 'overhang': ('-o', 50), 'anchor': ('-a', 7), 'min_duplicate_exon_length': ('--min_duplicate_exon_length', 27), 'min_junc_score': ('--min_junc_score', 1), 'match_score': ('-A', 3), 'mismatch_penalty': ('-B', 4), 'kmer': ('-k', 3), 'window': ('-w', 2), 'min_chain_score': ('-m', 25)}

    @classmethod
    def _input_select(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_select', inputs.get('input_type', '')) or '')

    @classmethod
    def _optional_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        raw = inputs.get('optional_outputs')
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(',') if part.strip()]
        return _as_list(raw)

    @classmethod
    def _option_value(cls, inputs: dict[str, Any], name: str, default: int) -> str:
        return str(inputs.get(name, inputs.get(f'adv_{name}', default)))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        input_select = cls._input_select(inputs)
        reference = f'{out}/reference.fa'
        cmd = ['ln', '-s', str(inputs.get('reference', '')), reference]
        if input_select == 'bam':
            cmd.extend(['&&', 'ln', '-s', str(inputs.get('input', '')), f'{out}/input.bam'])
            if inputs.get('bam_index'):
                cmd.extend(['&&', 'ln', '-s', str(inputs.get('bam_index')), f'{out}/input.bam.bai'])
        cmd.extend(['&&', 'eastr', '-r', reference, '-p', f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"])
        if input_select == 'bam':
            cmd.extend(['--bam', f'{out}/input.bam', '--out_filtered_bam', f'{out}/filtered.bam'])
        elif input_select == 'gtf':
            cmd.extend(['--gtf', str(inputs.get('input', ''))])
        else:
            cmd.extend(['--bed', str(inputs.get('input', ''))])
        cmd.extend(['--out_removed_junctions', f'{out}/removed_junctions.bed'])
        optional_outputs = cls._optional_outputs(inputs)
        if 'kept' in optional_outputs:
            cmd.extend(['--out_kept_junctions', f'{out}/kept_junctions.bed'])
        if 'original' in optional_outputs:
            cmd.extend(['--out_original_junctions', f'{out}/original_junctions.bed'])
        for name, (flag, default) in cls.ADVANCED_INT_OPTIONS.items():
            cmd.extend([flag, cls._option_value(inputs, name, default)])
        if inputs.get('trusted_bed'):
            cmd.extend(['--trusted_bed', str(inputs.get('trusted_bed'))])
        if inputs.get('log'):
            cmd.extend(['--verbose', '2>', f'{out}/eastr.log'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'removed_junctions.bed']
        if cls._input_select(inputs) == 'bam':
            outputs.append(out / 'filtered.bam')
        optional_outputs = cls._optional_outputs(inputs)
        if 'kept' in optional_outputs:
            outputs.append(out / 'kept_junctions.bed')
        if 'original' in optional_outputs:
            outputs.append(out / 'original_junctions.bed')
        if inputs.get('log'):
            outputs.append(out / 'eastr.log')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_select': ('STRING', {'default': 'bam', 'options': cls.INPUT_SELECT_OPTIONS, 'description': 'Input mode: coordinate-sorted BAM, transcript GTF, or intron BED'}), 'input': ('FILE', {'description': 'BAM, GTF, or BED input matching input_select'}), 'reference': ('FASTA', {'description': 'Reference genome FASTA used for junction sequence screening'})}, 'optional': {'bam_index': ('FILE', {'default': '', 'description': 'BAM index, staged next to BAM for BAM input mode'}), 'optional_outputs': ('STRING_LIST', {'default': [], 'options': ['kept', 'original'], 'description': 'Additional kept/original junction BED outputs'}), 'bt2_k': ('INT', {'default': 10, 'min': 1, 'description': 'Minimum distinct Bowtie2 alignments for spurious classification'}), 'overhang': ('INT', {'default': 50, 'min': 1, 'description': 'Flanking sequence length on each side of a junction'}), 'anchor': ('INT', {'default': 7, 'min': 1, 'description': 'Minimum anchor length in each exon'}), 'min_duplicate_exon_length': ('INT', {'default': 27, 'min': 1}), 'min_junc_score': ('INT', {'default': 1, 'min': 0}), 'match_score': ('INT', {'default': 3, 'min': 1}), 'mismatch_penalty': ('INT', {'default': 4, 'min': 1}), 'kmer': ('INT', {'default': 3, 'min': 1}), 'window': ('INT', {'default': 2, 'min': 1}), 'min_chain_score': ('INT', {'default': 25, 'min': 1}), 'trusted_bed': ('BED', {'default': '', 'description': 'Trusted junctions that will never be removed'}), 'log': ('BOOLEAN', {'default': False, 'description': 'Capture EASTR verbose progress output'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_select = cls._input_select(inputs)
        if not input_select:
            return 'input_select is required'
        if input_select not in cls.INPUT_SELECT_OPTIONS:
            return 'input_select must be one of: bam, gtf, bed'
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        if not str(inputs.get('reference', '')).strip():
            return 'reference FASTA is required'
        for name, (_, default) in cls.ADVANCED_INT_OPTIONS.items():
            value = int(inputs.get(name, inputs.get(f'adv_{name}', default)))
            minimum = 0 if name == 'min_junc_score' else 1
            if value < minimum:
                return f'{name} must be >= {minimum}'
        for output in cls._optional_outputs(inputs):
            if output not in {'kept', 'original'}:
                return f'unknown EASTR optional output: {output}'
        return super().VALIDATE_INPUTS(inputs)
