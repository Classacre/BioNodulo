"""kraken2 — metagenomics node(s). One tool per file (extracted from metagenomics.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any, Optional
from bionodulo.nodes.command_node import CommandNode, _shell_join
DOI_URL = 'https://doi.org/'
METAPHLAN_DOI = '10.1038/s41587-023-01688-w'
METAPHLAN_CITATION_TEXT = 'Extending and improving metagenomic taxonomic profiling with uncharacterized species using MetaPhlAn 4.'
HUMANN_CITATION_DOIS = ['10.7554/eLife.65088', '10.1371/journal.pcbi.1002358']
HUMANN_CITATION_TEXT = "bioBakery 3: a platform for analyzing meta'omic datasets; HUMAnN: the HMP Unified Metabolic Analysis Network."
KRAKEN2_CITATION_DOI = '10.1186/gb-2014-15-3-r46'
KRAKEN2_CITATION_TEXT = 'Kraken: ultrafast metagenomic sequence classification using exact alignments.'
BRACKEN_CITATION_DOI = '10.7717/peerj-cs.104'
BRACKEN_CITATION_TEXT = 'Bracken: estimating species abundance in metagenomics data.'
def _as_list(value: Any) -> list[str]:
    if value is None or value == '':
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v) != '']
    return [str(value)]
def _add_shell_redirect(cmd: list[str], output_path: str) -> None:
    cmd.extend(['>', output_path])
def _shell_join_allow_substitution(cmd: list[str]) -> str:
    parts: list[str] = []
    for token in cmd:
        parts.append(token if token.startswith('$(') else _shell_join([token]))
    return ' '.join(parts)


class Kraken2Node(CommandNode):
    """Taxonomic classification with Kraken2."""
    NODE_ID = 'kraken2'
    DISPLAY_NAME = 'Kraken2'
    REQUIRED_CONDA_PACKAGES = ['kraken2']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Assign taxonomic labels to sequencing reads with Kraken2.'
    SEARCH_ALIASES = ['BioNodulo builtin', 'Kraken2', 'taxonomic classification', 'classified reads', 'unclassified reads', 'Kraken report', 'MPA style report', 'minimizer data']
    RETURN_TYPES = ('KRAKEN_OUTPUT', 'KRAKEN_REPORT', 'FASTQ', 'FASTQ', 'DIRECTORY', 'DIRECTORY')
    RETURN_NAMES = ('output', 'report', 'classified_reads', 'unclassified_reads', 'classified_read_pairs', 'unclassified_read_pairs')
    REQUIRED_EXECUTABLES = ['kraken2']
    DOCUMENTATION_URL = 'https://ccb.jhu.edu/software/kraken2/'
    CITATION_DOIS = [KRAKEN2_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{KRAKEN2_CITATION_DOI}']
    CITATION_TEXT = KRAKEN2_CITATION_TEXT
    VERSION = '2.17.1'
    SHELL = True

    @classmethod
    def _out(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('output', '.'))

    @classmethod
    def _output_path(cls, out: str) -> str:
        return f'{out}/output.kraken'

    @classmethod
    def _report_path(cls, out: str) -> str:
        return f'{out}/report.kreport'

    @classmethod
    def _classified_path(cls, out: str, input_ext: str) -> str:
        return f'{out}/classified_reads.{input_ext}'

    @classmethod
    def _unclassified_path(cls, out: str, input_ext: str) -> str:
        return f'{out}/unclassified_reads.{input_ext}'

    @classmethod
    def _classified_pair_dir(cls, out: str) -> str:
        return f'{out}/classified_read_pairs'

    @classmethod
    def _unclassified_pair_dir(cls, out: str) -> str:
        return f'{out}/unclassified_read_pairs'

    @classmethod
    def _read_files(cls, inputs: dict[str, Any]) -> list[str]:
        reads = _as_list(inputs.get('reads'))
        if reads:
            return reads
        return [read for read in [str(inputs.get('r1', '')), str(inputs.get('r2', ''))] if read]

    @classmethod
    def _single_paired_selector(cls, inputs: dict[str, Any], reads: list[str]) -> str:
        if inputs.get('single_paired_selector'):
            return str(inputs['single_paired_selector'])
        if inputs.get('paired', False) or len(reads) > 1:
            return 'collection'
        return 'no'

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        input_ext = str(inputs.get('input_ext', '')).lower()
        if input_ext:
            return input_ext
        reads = cls._read_files(inputs)
        if not reads:
            return 'fastq'
        name = reads[0].lower()
        for ext in ('fastq.gz', 'fastq.bz2', 'fasta.gz', 'fasta.bz2', 'fq.gz', 'fq.bz2', 'fa.gz', 'fa.bz2'):
            if name.endswith(ext):
                return 'fastq.gz' if ext == 'fq.gz' else 'fastq.bz2' if ext == 'fq.bz2' else 'fasta.gz' if ext == 'fa.gz' else 'fasta.bz2' if ext == 'fa.bz2' else ext
        if name.endswith(('.fasta', '.fa', '.fna')):
            return 'fasta'
        return 'fastq'

    @classmethod
    def _split_command(cls, input_ext: str) -> str:
        if input_ext.endswith('.gz'):
            return 'gzip -c'
        if input_ext.endswith('.bz2'):
            return 'bzip2 -c'
        return 'cat'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = cls._out(inputs)
        reads = cls._read_files(inputs)
        selector = cls._single_paired_selector(inputs, reads)
        input_ext = cls._input_ext(inputs)
        cmd = ['kraken2', '--threads', str(inputs.get('threads', 8)), '--db', str(inputs.get('db', ''))]
        if inputs.get('quick'):
            cmd.append('--quick')
        if selector == 'collection':
            cmd.append('--paired')
            cmd.extend(reads[:2])
        elif reads:
            cmd.append(reads[0])
        if inputs.get('split_reads'):
            if selector == 'collection':
                cmd.extend(['--unclassified-out', 'un_out#', '--classified-out', 'cl_out#'])
            else:
                cmd.extend(['--unclassified-out', 'un_out', '--classified-out', 'cl_out'])
        cmd.extend(['--confidence', str(inputs.get('confidence', 0.0)), '--minimum-base-quality', str(inputs.get('min_base_quality', 0)), '--minimum-hit-groups', str(inputs.get('minimum_hit_groups', 2))])
        if inputs.get('use_names'):
            cmd.append('--use-names')
        if inputs.get('create_report', True):
            cmd.extend(['--report', cls._report_path(out)])
            if inputs.get('use_mpa_style'):
                cmd.append('--use-mpa-style')
            if inputs.get('report_zero_counts'):
                cmd.append('--report-zero-counts')
            if inputs.get('report_minimizer_data'):
                cmd.append('--report-minimizer-data')
        if inputs.get('memory_mapping'):
            cmd.append('--memory-mapping')
        command = _shell_join(cmd)
        command += ' > ' + shlex.quote(cls._output_path(out))
        if not inputs.get('split_reads'):
            return command
        split_command = cls._split_command(input_ext)
        if selector == 'collection':
            classified_dir = cls._classified_pair_dir(out)
            unclassified_dir = cls._unclassified_pair_dir(out)
            postprocess = [_shell_join(['mkdir', '-p', classified_dir, unclassified_dir]), f"{split_command} un_out_1 > {shlex.quote(f'{unclassified_dir}/forward.{input_ext}')}", f"{split_command} un_out_2 > {shlex.quote(f'{unclassified_dir}/reverse.{input_ext}')}", f"{split_command} cl_out_1 > {shlex.quote(f'{classified_dir}/forward.{input_ext}')}", f"{split_command} cl_out_2 > {shlex.quote(f'{classified_dir}/reverse.{input_ext}')}"]
        else:
            postprocess = [f'{split_command} un_out > {shlex.quote(cls._unclassified_path(out, input_ext))}', f'{split_command} cl_out > {shlex.quote(cls._classified_path(out, input_ext))}']
        return ' && '.join([command, *postprocess])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'output.kraken']
        if inputs.get('create_report', True):
            outputs.append(out / 'report.kreport')
        if inputs.get('split_reads'):
            selector = cls._single_paired_selector(inputs, cls._read_files(inputs))
            if selector == 'collection':
                outputs.extend([out / 'classified_read_pairs', out / 'unclassified_read_pairs'])
            else:
                input_ext = cls._input_ext(inputs)
                outputs.extend([out / f'classified_reads.{input_ext}', out / f'unclassified_reads.{input_ext}'])
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('db'):
            return 'db is required'
        reads = cls._read_files(inputs)
        if not reads:
            return 'reads is required'
        if cls._single_paired_selector(inputs, reads) == 'collection' and len(reads) < 2:
            return 'Paired Kraken2 input requires two read files'
        confidence = inputs.get('confidence', 0.0)
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            return 'confidence must be between 0 and 1'
        return True

    async def run(self, **kwargs: Any) -> Any:
        """Accept reads list and split into r1/r2 for Kraken2."""
        reads = kwargs.get('reads', [])
        if isinstance(reads, (list, tuple)) and len(reads) >= 2:
            kwargs['r1'] = reads[0]
            kwargs['r2'] = reads[1]
        return await super().run(**kwargs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'db': ('DIRECTORY', {'description': 'Kraken2 database directory'}), 'reads': ('FILE', {'description': 'Input sequences'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'single_paired_selector': ('STRING', {'default': 'no', 'options': ['no', 'collection'], 'description': 'Single reads or paired read collection'}), 'r1': ('FASTQ', {'default': '', 'description': 'Legacy forward reads input'}), 'r2': ('FASTQ', {'default': '', 'description': 'Legacy reverse reads input'}), 'input_ext': ('STRING', {'default': 'fastq', 'options': ['fasta', 'fasta.gz', 'fasta.bz2', 'fastq', 'fastq.gz', 'fastq.bz2'], 'description': 'Input extension used for split-read outputs'}), 'use_names': ('BOOLEAN', {'default': False, 'label': 'Print scientific names instead of just taxids'}), 'confidence': ('FLOAT', {'default': 0.0, 'min': 0.0, 'max': 1.0, 'step': 0.01, 'label': 'Confidence', 'advanced': True}), 'min_base_quality': ('INT', {'default': 0, 'min': 0, 'label': 'Minimum Base Quality', 'advanced': True}), 'minimum_hit_groups': ('INT', {'default': 2, 'label': 'Minimum hit groups', 'advanced': True}), 'quick': ('BOOLEAN', {'default': False, 'label': 'Enable quick operation', 'advanced': True}), 'split_reads': ('BOOLEAN', {'default': False, 'label': 'Split classified and unclassified outputs'}), 'create_report': ('BOOLEAN', {'default': True, 'label': 'Print a report with aggregate counts/clade'}), 'use_mpa_style': ('BOOLEAN', {'default': False, 'label': 'Format report output like Kraken 1 MPA report', 'advanced': True}), 'report_zero_counts': ('BOOLEAN', {'default': False, 'label': 'Report counts for all taxa', 'advanced': True}), 'report_minimizer_data': ('BOOLEAN', {'default': False, 'label': 'Report minimizer data', 'advanced': True}), 'memory_mapping': ('BOOLEAN', {'default': False, 'label': 'Memory Mapping', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class Kraken2BuildNode(CommandNode):
    """Build Kraken2 database."""
    NODE_ID = 'kraken2_build'
    DISPLAY_NAME = 'Kraken2 Build DB'
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Build a Kraken2 database from reference sequences'
    SEARCH_ALIASES = ['kraken2', 'build', 'database', 'custom db']
    RETURN_TYPES = ('DIRECTORY',)
    RETURN_NAMES = ('db',)
    REQUIRED_EXECUTABLES = ['kraken2-build']
    REQUIRED_CONDA_PACKAGES = ['kraken2']
    DOCUMENTATION_URL = 'https://ccb.jhu.edu/software/kraken2/'
    VERSION = '2.1.6'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        step = inputs.get('step', 'download-taxonomy')
        cmd = ['kraken2-build', '--db', str(inputs.get('db', '')), '--threads', str(inputs.get('threads', 8))]
        if step == 'download-taxonomy':
            cmd.append('--download-taxonomy')
        elif step == 'download-library':
            cmd.extend(['--download-library', str(inputs.get('library', 'bacteria'))])
        elif step == 'build':
            cmd.append('--build')
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'db': ('DIRECTORY', {'description': 'Output database directory'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64, 'display': 'slider'}), 'step': (['download-taxonomy', 'download-library', 'build'], {'default': 'download-taxonomy'})}, 'optional': {'library': ('STRING', {'default': 'bacteria', 'description': 'RefSeq library to download'})}, 'hidden': {}}
