"""ampligone — sequence node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class AmpliGoneNode(CommandNode):
    """Find and remove primers from amplicon sequencing reads with AmpliGone."""
    NODE_ID = 'ampligone'
    DISPLAY_NAME = 'AmpliGone'
    REQUIRED_CONDA_PACKAGES = ['AmpliGone']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Remove primer-derived sequence from FASTQ or BAM amplicon reads using primer coordinates or primer FASTA against a reference.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'AmpliGone', 'AmpliGone primer removal', 'primer removal', 'amplicon reads', 'ARTIC primers', 'Nanopore', 'Illumina', 'fragmented amplicons']
    RETURN_TYPES = ('FASTQ', 'BED')
    RETURN_NAMES = ('cleaned_reads', 'primer_coordinates')
    REQUIRED_EXECUTABLES = ['ampligone']
    DOCUMENTATION_URL = 'https://rivm-bioinformatics.github.io/AmpliGone/'
    CITATION_DOIS = ['10.5281/zenodo.7684307']
    CITATION_URLS = [f'{DOI_URL}10.5281/zenodo.7684307']
    CITATION_TEXT = 'AmpliGone: find and remove primers from NGS amplicon reads.'
    VERSION = '2.0.1'
    SHELL = True

    @classmethod
    def _staged_ext(cls, datatype: Any, default: str) -> str:
        ext = str(datatype or default).replace('sanger', '').strip('.')
        return ext or default

    @classmethod
    def _cleaned_name(cls, inputs: dict[str, Any]) -> str:
        return 'cleaned_reads.fastq.gz' if str(inputs.get('input_ext', '')).endswith('.gz') else 'cleaned_reads.fastq'

    @classmethod
    def _staged_names(cls, inputs: dict[str, Any]) -> tuple[str, str, str, str]:
        out = _out(inputs)
        input_ext = cls._staged_ext(inputs.get('input_ext'), Path(str(inputs.get('input', ''))).suffix.lstrip('.') or 'fastq')
        reference_ext = cls._staged_ext(inputs.get('reference_ext'), 'fasta')
        primers_ext = cls._staged_ext(inputs.get('primers_ext'), Path(str(inputs.get('primers', ''))).suffix.lstrip('.') or 'bed')
        cleaned_name = cls._cleaned_name(inputs)
        return (f'{out}/reads.{input_ext}', f'{out}/reference.{reference_ext}', f'{out}/primers.{primers_ext}', f'{out}/{cleaned_name}')

    @classmethod
    def _should_export_primers(cls, inputs: dict[str, Any]) -> bool:
        return bool(inputs.get('export_primers')) and cls._staged_ext(inputs.get('primers_ext'), 'bed') == 'fasta'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        reads, reference, primers, cleaned = cls._staged_names(inputs)
        output_name = f'{out}/output.fastq.gz' if cleaned.endswith('.gz') else f'{out}/output.fastq'
        cmd = ['ln', '-sf', str(inputs.get('input', '')), reads, '&&', 'touch', cleaned, '&&', 'ln', '-sf', cleaned, output_name, '&&', 'ln', '-sf', str(inputs.get('reference', '')), reference, '&&', 'ln', '-sf', str(inputs.get('primers', '')), primers]
        if cls._should_export_primers(inputs):
            cmd.extend(['&&', 'touch', f'{out}/primer_coordinates.bed', '&&', 'ln', '-sf', f'{out}/primer_coordinates.bed', f'{out}/primers.bed'])
        cmd.extend(['&&', 'ampligone', '--input', reads, '--reference', reference, '--primers', primers, '--threads', f"${{GALAXY_SLOTS:-{inputs.get('threads', 2)}}}"])
        amplicon_type = str(inputs.get('amplicon_type', 'end-to-end') or '')
        if amplicon_type:
            cmd.extend(['--amplicon-type', amplicon_type])
        if amplicon_type == 'fragmented':
            cmd.extend(['--fragment-lookaround-size', str(inputs.get('fragment_lookaround_size', 10))])
        if inputs.get('error_rate') is not None and str(inputs.get('error_rate')) != '':
            cmd.extend(['--error-rate', str(inputs.get('error_rate'))])
        if cls._should_export_primers(inputs):
            cmd.extend(['--export-primers', f'{out}/primers.bed'])
        cmd.extend(['--output', output_name])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / cls._cleaned_name(inputs)]
        if cls._should_export_primers(inputs):
            outputs.append(out / 'primer_coordinates.bed')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTQ', {'description': 'Reads in FASTQ, gzipped FASTQ, or BAM format'}), 'reference': ('FASTA', {'description': 'Reference genome FASTA'}), 'primers': ('FILE', {'description': 'Primer sequences in FASTA or BED format'})}, 'optional': {'input_ext': ('STRING', {'default': 'fastq', 'options': ['fastq', 'fastq.gz', 'bam'], 'advanced': True}), 'reference_ext': ('STRING', {'default': 'fasta', 'advanced': True}), 'primers_ext': ('STRING', {'default': 'bed', 'options': ['bed', 'fasta'], 'advanced': True}), 'export_primers': ('BOOLEAN', {'default': False, 'description': 'Export detected primer coordinates when primers are provided as FASTA'}), 'amplicon_type': ('STRING', {'default': 'end-to-end', 'options': ['end-to-end', 'end-to-mid', 'fragmented'], 'description': 'Expected relationship between read length and amplicon length'}), 'fragment_lookaround_size': ('INT', {'default': 10, 'min': 0, 'description': 'Bases to search around primer sites for fragmented amplicons'}), 'error_rate': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 1, 'description': 'Maximum allowed primer-search error rate'}), 'threads': ('INT', {'default': 2, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}
