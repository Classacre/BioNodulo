"""seqkit — sequence node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class SeqKitGrepNode(CommandNode):
    """Search FASTA/Q records by ID, name, or sequence with SeqKit grep."""
    NODE_ID = 'seqkit_grep'
    DISPLAY_NAME = 'SeqKit Grep'
    REQUIRED_CONDA_PACKAGES = ['seqkit']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Filter FASTA or FASTQ records by ID, full name, sequence motif, or a file of patterns using SeqKit grep.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqkit', 'grep', 'seqkit grep', 'FASTA grep', 'FASTQ grep', 'motif search', 'sequence filter']
    RETURN_TYPES = ('FASTQ', 'FASTA', 'STATS_FILE')
    RETURN_NAMES = ('fastq_output', 'fasta_output', 'count')
    REQUIRED_EXECUTABLES = ['seqkit']
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/usage/#grep'
    CITATION_DOIS = ['10.1371/journal.pone.0163962']
    CITATION_URLS = ['https://doi.org/10.1371/journal.pone.0163962']
    CITATION_TEXT = 'SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation.'
    VERSION = '2.13.0'
    SHELL = True

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        if inputs.get('count'):
            return 'count.txt'
        ext = str(inputs.get('output_ext', 'fasta.gz')).strip().lstrip('.') or 'fasta.gz'
        return f'grep.{ext}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['seqkit', 'grep', '--threads', str(inputs.get('threads', 4))]
        pattern_mode = str(inputs.get('pattern_mode', 'expression'))
        if pattern_mode == 'file':
            cmd.extend(['--pattern-file', str(inputs.get('pattern_file', ''))])
        else:
            cmd.extend(['--pattern', str(inputs.get('pattern', ''))])
            if inputs.get('use_regexp'):
                cmd.append('--use-regexp')
        for key, flag in (('allow_duplicated_patterns', '--allow-duplicated-patterns'), ('by_name', '--by-name'), ('by_seq', '--by-seq'), ('circular', '--circular'), ('count', '--count'), ('degenerate', '--degenerate'), ('delete_matched', '--delete-matched'), ('ignore_case', '--ignore-case'), ('invert_match', '--invert-match')):
            if inputs.get(key):
                cmd.append(flag)
        if inputs.get('by_seq') and (not inputs.get('degenerate')):
            cmd.extend(['--max-mismatch', str(inputs.get('max_mismatch', 0))])
        if inputs.get('only_positive_strand'):
            cmd.append('--only-positive-strand')
        if inputs.get('region'):
            cmd.extend(['--region', str(inputs.get('region'))])
        cmd.extend([str(inputs.get('input', '')), '>', f'{_out(inputs)}/{cls._output_name(inputs)}'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTQ_LIST', {'description': 'Input FASTA/FASTQ file'}), 'pattern_mode': ('STRING', {'default': 'expression', 'options': ['expression', 'file'], 'description': 'Pattern source'})}, 'optional': {'pattern': ('STRING', {'default': '', 'description': 'Pattern or motif sequence'}), 'pattern_file': ('FILE', {'description': 'Text file with one pattern per line'}), 'use_regexp': ('BOOLEAN', {'default': False, 'description': 'Interpret expression pattern as a regular expression'}), 'allow_duplicated_patterns': ('BOOLEAN', {'default': False, 'advanced': True}), 'by_name': ('BOOLEAN', {'default': False, 'description': 'Match against full sequence name/header'}), 'by_seq': ('BOOLEAN', {'default': False, 'description': 'Search sequence content'}), 'circular': ('BOOLEAN', {'default': False, 'description': 'Treat sequences as circular', 'advanced': True}), 'count': ('BOOLEAN', {'default': False, 'description': 'Print only the count of matching records'}), 'degenerate': ('BOOLEAN', {'default': False, 'description': 'Pattern contains degenerate bases'}), 'delete_matched': ('BOOLEAN', {'default': False, 'advanced': True}), 'ignore_case': ('BOOLEAN', {'default': False, 'description': 'Ignore case'}), 'invert_match': ('BOOLEAN', {'default': False, 'description': 'Select non-matching records'}), 'max_mismatch': ('INT', {'default': 0, 'min': 0, 'description': 'Allowed mismatches for sequence search'}), 'only_positive_strand': ('BOOLEAN', {'default': False, 'description': 'Search only the positive strand'}), 'region': ('STRING', {'default': '', 'description': 'Sequence region such as 1:30, :100, or -12:-1'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128}), 'output_ext': ('STRING', {'default': 'fasta.gz', 'options': ['fasta.gz', 'fasta', 'fastq.gz', 'fastq'], 'description': 'Sequence output extension'})}, 'hidden': {'output': ('STRING', {})}}


class SeqKitHeadNode(CommandNode):
    """Return the first N FASTA/Q records with SeqKit head."""
    NODE_ID = 'seqkit_head'
    DISPLAY_NAME = 'SeqKit Head'
    REQUIRED_CONDA_PACKAGES = ['seqkit']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Return the first N FASTA or FASTQ records with SeqKit head.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqkit', 'head', 'seqkit head', 'first records', 'FASTA head', 'FASTQ head']
    RETURN_TYPES = ('FASTQ',)
    RETURN_NAMES = ('head_output',)
    REQUIRED_EXECUTABLES = ['seqkit']
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/usage/#head'
    CITATION_DOIS = ['10.1371/journal.pone.0163962']
    CITATION_URLS = ['https://doi.org/10.1371/journal.pone.0163962']
    CITATION_TEXT = 'SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation.'
    VERSION = '2.13.0'
    SHELL = True

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', inputs.get('output_ext', 'fastq.gz'))).strip().lstrip('.') or 'fastq.gz'
        return f'input.{ext}'

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('output_ext', 'fastq.gz')).strip().lstrip('.') or 'fastq.gz'
        return f'head.{ext}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_name = cls._input_name(inputs)
        output_path = f'{_out(inputs)}/{cls._output_name(inputs)}'
        return ' '.join(['ln', '-sf', shlex.quote(str(inputs.get('input', ''))), shlex.quote(input_name), '&&', 'seqkit', 'head', shlex.quote(input_name), '--number', shlex.quote(str(inputs.get('number', 10))), '-o', shlex.quote(output_path), '--threads', shlex.quote(str(inputs.get('threads', 4)))])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTQ_LIST', {'description': 'Input FASTA or FASTQ file'}), 'number': ('INT', {'default': 10, 'min': 1, 'description': 'Number of FASTA/Q records to output'})}, 'optional': {'threads': ('INT', {'default': 4, 'min': 1, 'max': 128}), 'input_ext': ('STRING', {'default': 'fastq.gz', 'options': ['fasta.gz', 'fasta', 'fastq.gz', 'fastq'], 'advanced': True}), 'output_ext': ('STRING', {'default': 'fastq.gz', 'options': ['fasta.gz', 'fasta', 'fastq.gz', 'fastq']})}, 'hidden': {'output': ('STRING', {})}}


class SeqKitFx2tabNode(CommandNode):
    """Convert FASTA/Q records to tabular columns with SeqKit fx2tab."""
    NODE_ID = 'seqkit_fx2tab'
    DISPLAY_NAME = 'SeqKit fx2tab'
    REQUIRED_CONDA_PACKAGES = ['seqkit']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Convert FASTA or FASTQ records to tabular columns with SeqKit fx2tab.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqkit', 'fx2tab', 'FASTA to tabular', 'FASTQ to TSV', 'sequence table', 'GC content']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('tabular',)
    REQUIRED_EXECUTABLES = ['seqkit']
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/usage/#fx2tab'
    CITATION_DOIS = ['10.1371/journal.pone.0163962']
    CITATION_URLS = ['https://doi.org/10.1371/journal.pone.0163962']
    CITATION_TEXT = 'SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation.'
    VERSION = '2.13.0'
    SHELL = True

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fastqsanger.gz')).strip().lstrip('.') or 'fastqsanger.gz'
        return f'input.{ext}'

    @classmethod
    def _output_name(cls) -> str:
        return 'fx2tab.tsv'

    @classmethod
    def _joined_bases(cls, value: Any) -> str:
        return ''.join(_as_list(value)).replace(',', '')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_name = cls._input_name(inputs)
        cmd = ['seqkit', 'fx2tab', input_name]
        if inputs.get('alphabet'):
            cmd.append('--alphabet')
        if inputs.get('avg_qual'):
            cmd.append('--avg-qual')
        base_percentages = cls._joined_bases(inputs.get('base_percentages', inputs.get('B')))
        if base_percentages:
            cmd.extend(['-B', base_percentages])
        base_counts = cls._joined_bases(inputs.get('base_counts', inputs.get('C')))
        if base_counts:
            cmd.extend(['-C', base_counts])
        for key, flag in (('gc', '--gc'), ('gc_skew', '--gc-skew'), ('header_line', '--header-line'), ('length', '--length'), ('name', '--name'), ('no_qual', '--no-qual'), ('only_id', '--only-id')):
            if inputs.get(key):
                cmd.append(flag)
        if str(inputs.get('qual_ascii_base', '')) != '':
            cmd.extend(['--qual-ascii-base', str(inputs.get('qual_ascii_base'))])
        if inputs.get('seq_hash'):
            cmd.append('--seq-hash')
        cmd.extend(['>', f'{_out(inputs)}/{cls._output_name()}'])
        return f"ln -sf {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(input_name)} && " + ' '.join((shlex.quote(part) if part not in {'>'} else part for part in cmd))

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name()]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTQ_LIST', {'description': 'Input FASTA or FASTQ file'})}, 'optional': {'input_ext': ('STRING', {'default': 'fastqsanger.gz', 'options': ['fasta', 'fasta.gz', 'fastqsanger', 'fastqsanger.gz'], 'advanced': True}), 'alphabet': ('BOOLEAN', {'default': False, 'description': 'Output alphabet letters'}), 'avg_qual': ('BOOLEAN', {'default': False, 'description': 'Output average quality'}), 'base_percentages': ('STRING', {'default': '', 'description': 'Bases for percentage columns, e.g. A,T', 'advanced': True}), 'base_counts': ('STRING', {'default': '', 'description': 'Bases for count columns, e.g. A,N', 'advanced': True}), 'gc': ('BOOLEAN', {'default': False, 'description': 'Output GC content'}), 'gc_skew': ('BOOLEAN', {'default': False, 'description': 'Output GC skew'}), 'header_line': ('BOOLEAN', {'default': False, 'description': 'Output a header line'}), 'length': ('BOOLEAN', {'default': False, 'description': 'Output sequence length'}), 'name': ('BOOLEAN', {'default': False, 'description': 'Output names instead of sequences and qualities'}), 'no_qual': ('BOOLEAN', {'default': False, 'description': 'Suppress quality column'}), 'only_id': ('BOOLEAN', {'default': False, 'description': 'Output sequence ID instead of full header'}), 'qual_ascii_base': ('INT', {'default': 33, 'min': 0, 'advanced': True}), 'seq_hash': ('BOOLEAN', {'default': False, 'description': 'Output md5 hash of sequence'})}, 'hidden': {'output': ('STRING', {})}}


class SeqKitSortNode(CommandNode):
    """Sort FASTA/Q records with SeqKit sort."""
    NODE_ID = 'seqkit_sort'
    DISPLAY_NAME = 'SeqKit Sort'
    REQUIRED_CONDA_PACKAGES = ['seqkit']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Sort FASTA or FASTQ records by sequence ID, name, sequence, non-gap bases, or length with SeqKit.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqkit', 'sort', 'SeqKit sort', 'sort FASTA', 'sort FASTQ', 'sort by length', 'sort by sequence']
    RETURN_TYPES = ('FASTQ',)
    RETURN_NAMES = ('sorted_sequences',)
    REQUIRED_EXECUTABLES = ['seqkit']
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/usage/#sort'
    CITATION_DOIS = ['10.1371/journal.pone.0163962']
    CITATION_URLS = ['https://doi.org/10.1371/journal.pone.0163962']
    CITATION_TEXT = 'SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation.'
    VERSION = '2.13.0'
    SHELL = True

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', inputs.get('output_ext', 'fastq.gz'))).strip().lstrip('.') or 'fastq.gz'
        return f'input.{ext}'

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('output_ext', 'fastq.gz')).strip().lstrip('.') or 'fastq.gz'
        return f'sorted.{ext}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_name = cls._input_name(inputs)
        output_path = f'{_out(inputs)}/{cls._output_name(inputs)}'
        cmd = ['seqkit', 'sort', input_name]
        if inputs.get('reverse'):
            cmd.append('--reverse')
        sort_by = str(inputs.get('sort_by', ''))
        if sort_by:
            cmd.append(sort_by)
        cmd.extend(['-o', output_path, '--threads', str(inputs.get('threads', 4))])
        return f"ln -sf {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(input_name)} && " + ' '.join((shlex.quote(part) for part in cmd))

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTQ_LIST', {'description': 'Input FASTA or FASTQ file'})}, 'optional': {'sort_by': ('STRING', {'default': '', 'options': ['', '--by-bases', '--by-length', '--by-name', '--by-seq'], 'description': 'Sort by sequence ID, non-gap bases, length, full name, or sequence'}), 'reverse': ('BOOLEAN', {'default': False, 'description': 'Reverse the sorted result'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128}), 'input_ext': ('STRING', {'default': 'fastq.gz', 'options': ['fasta.gz', 'fasta', 'fastq.gz', 'fastq'], 'advanced': True}), 'output_ext': ('STRING', {'default': 'fastq.gz', 'options': ['fasta.gz', 'fasta', 'fastq.gz', 'fastq']})}, 'hidden': {'output': ('STRING', {})}}


class SeqKitLocateNode(CommandNode):
    """Locate FASTA subsequences or motifs with SeqKit locate."""
    NODE_ID = 'seqkit_locate'
    DISPLAY_NAME = 'SeqKit Locate'
    REQUIRED_CONDA_PACKAGES = ['seqkit']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Locate FASTA subsequences or motifs with optional mismatches and BED, GTF, or tabular output using SeqKit.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqkit', 'locate', 'SeqKit locate', 'motif search', 'subsequence search', 'mismatch', 'BED motifs', 'GTF motifs']
    RETURN_TYPES = ('TSV', 'BED', 'GFF_GTF')
    RETURN_NAMES = ('tabular', 'bed', 'gtf')
    REQUIRED_EXECUTABLES = ['seqkit']
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/usage/#locate'
    CITATION_DOIS = ['10.1371/journal.pone.0163962']
    CITATION_URLS = ['https://doi.org/10.1371/journal.pone.0163962']
    CITATION_TEXT = 'SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation.'
    VERSION = '2.13.0'
    SHELL = True

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fasta.gz')).strip().lstrip('.') or 'fasta.gz'
        return f'input.{ext}'

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        output_mode = str(inputs.get('output_mode', ''))
        return {'--bed': 'locate.bed', '--gtf': 'locate.gtf'}.get(output_mode, 'locate.tsv')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_name = cls._input_name(inputs)
        cmd = ['seqkit', 'locate', '--threads', str(inputs.get('threads', 4))]
        if str(inputs.get('pattern_mode', 'expression')) == 'file':
            cmd.extend(['--pattern-file', str(inputs.get('pattern_file', ''))])
        else:
            cmd.extend(['--pattern', str(inputs.get('pattern', ''))])
            if inputs.get('use_regexp'):
                cmd.append('--use-regexp')
        output_mode = str(inputs.get('output_mode', ''))
        if output_mode:
            cmd.append(output_mode)
        for key, flag in (('circular', '--circular'), ('degenerate', '--degenerate'), ('hide_matched', '--hide-matched'), ('ignore_case', '--ignore-case')):
            if inputs.get(key):
                cmd.append(flag)
        if not inputs.get('degenerate'):
            cmd.extend(['--max-mismatch', str(inputs.get('max_mismatch', 0))])
            if inputs.get('use_fmi'):
                cmd.append('--use-fmi')
        for key, flag in (('non_greedy', '--non-greedy'), ('only_positive_strand', '--only-positive-strand'), ('id_ncbi', '--id-ncbi')):
            if inputs.get(key):
                cmd.append(flag)
        cmd.extend(['--seq-type', str(inputs.get('seq_type', 'auto')), input_name, '>', f'{_out(inputs)}/{cls._output_name(inputs)}'])
        return f"ln -sf {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(input_name)} && " + ' '.join((shlex.quote(part) if part != '>' else part for part in cmd))

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTQ_LIST', {'description': 'Input FASTA file'}), 'pattern_mode': ('STRING', {'default': 'expression', 'options': ['expression', 'file'], 'description': 'Pattern source'})}, 'optional': {'pattern': ('STRING', {'default': '', 'description': 'Pattern or motif sequence'}), 'pattern_file': ('FILE', {'description': 'FASTA file with motif sequences'}), 'use_regexp': ('BOOLEAN', {'default': False, 'description': 'Interpret expression pattern as a regular expression'}), 'seq_type': ('STRING', {'default': 'auto', 'options': ['auto', 'dna', 'rna', 'protein'], 'description': 'Sequence type'}), 'output_mode': ('STRING', {'default': '', 'options': ['', '--gtf', '--bed'], 'description': 'Output format'}), 'circular': ('BOOLEAN', {'default': False, 'description': 'Treat sequences as circular', 'advanced': True}), 'degenerate': ('BOOLEAN', {'default': False, 'description': 'Pattern contains degenerate bases'}), 'hide_matched': ('BOOLEAN', {'default': False, 'description': 'Hide matched sequence column'}), 'ignore_case': ('BOOLEAN', {'default': False, 'description': 'Ignore case'}), 'max_mismatch': ('INT', {'default': 0, 'min': 0, 'description': 'Allowed mismatches'}), 'use_fmi': ('BOOLEAN', {'default': False, 'description': 'Use FM-index when degenerate matching is disabled', 'advanced': True}), 'non_greedy': ('BOOLEAN', {'default': False, 'description': 'Use non-greedy matching', 'advanced': True}), 'only_positive_strand': ('BOOLEAN', {'default': False, 'description': 'Search only the positive strand'}), 'id_ncbi': ('BOOLEAN', {'default': False, 'description': 'Parse NCBI-style FASTA identifiers', 'advanced': True}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128}), 'input_ext': ('STRING', {'default': 'fasta.gz', 'options': ['fasta.gz', 'fasta'], 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class SeqKitTranslateNode(CommandNode):
    """Translate nucleotide FASTA/Q records to protein sequences with SeqKit."""
    NODE_ID = 'seqkit_translate'
    DISPLAY_NAME = 'SeqKit Translate'
    REQUIRED_CONDA_PACKAGES = ['seqkit']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Translate DNA or RNA FASTA/FASTQ records to protein sequences with frame, codon table, and unknown-codon handling.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqkit', 'translate', 'SeqKit translate', 'DNA to protein', 'RNA to protein', 'codon table', 'six frame translation']
    RETURN_TYPES = ('FASTA', 'FASTQ')
    RETURN_NAMES = ('translated_fasta', 'translated_fastq')
    REQUIRED_EXECUTABLES = ['seqkit']
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/usage/#translate'
    CITATION_DOIS = ['10.1371/journal.pone.0163962']
    CITATION_URLS = ['https://doi.org/10.1371/journal.pone.0163962']
    CITATION_TEXT = 'SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation.'
    VERSION = '2.13.0'

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('output_ext', 'fasta.gz')).strip().lstrip('.') or 'fasta.gz'
        return f'translated.{ext}'

    @classmethod
    def _frames(cls, value: Any) -> str:
        frames = _as_list(value)
        if not frames:
            return '1'
        return ','.join((frame.replace(',', '') for frame in frames if frame.replace(',', '')))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['seqkit', 'translate', str(inputs.get('input', '')), '-o', f'{_out(inputs)}/{cls._output_name(inputs)}']
        unknown_action = str(inputs.get('unknown_action', inputs.get('selector', 'trimming')))
        if unknown_action == 'translate':
            if inputs.get('allow_unknown_codon'):
                cmd.append('--allow-unknown-codon')
        elif inputs.get('trim'):
            cmd.append('--trim')
        for key, flag in (('append_frame', '--append-frame'), ('clean', '--clean')):
            if inputs.get(key):
                cmd.append(flag)
        cmd.extend(['-f', cls._frames(inputs.get('frame', '1'))])
        if inputs.get('init_codon_as_M'):
            cmd.append('--init-codon-as-M')
        transl_table = str(inputs.get('transl_table', '1'))
        if transl_table:
            cmd.extend(['-T', transl_table])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTQ_LIST', {'description': 'Input FASTA or FASTQ nucleotide records'})}, 'optional': {'frame': ('STRING', {'default': '1', 'options': ['1', '2', '3', '-1', '-2', '-3', '6'], 'description': 'Frame or comma-separated frames to translate'}), 'append_frame': ('BOOLEAN', {'default': False, 'description': 'Append frame information to sequence IDs'}), 'transl_table': ('STRING', {'default': '1', 'options': ['1', '2', '3', '4', '5', '6', '9', '10', '11', '12', '13', '14', '16', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31'], 'description': 'NCBI genetic code table'}), 'clean': ('BOOLEAN', {'default': False, 'description': 'Change STOP codons from * to X'}), 'unknown_action': ('STRING', {'default': 'trimming', 'options': ['trimming', 'translate'], 'description': 'Trim terminal unknowns/stops or translate unknown codons to X'}), 'trim': ('BOOLEAN', {'default': False, 'description': 'Remove X and * characters from the right end'}), 'allow_unknown_codon': ('BOOLEAN', {'default': False, 'description': 'Translate unknown codons to X'}), 'init_codon_as_M': ('BOOLEAN', {'default': False, 'description': 'Translate initial codon as M'}), 'output_ext': ('STRING', {'default': 'fasta.gz', 'options': ['fasta.gz', 'fasta', 'fastq.gz', 'fastq']})}, 'hidden': {'output': ('STRING', {})}}


class SeqKitSplit2Node(CommandNode):
    """Split FASTA/Q records into files with SeqKit split2."""
    NODE_ID = 'seqkit_split2'
    DISPLAY_NAME = 'SeqKit Split2'
    REQUIRED_CONDA_PACKAGES = ['seqkit']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Split single-end or paired-end FASTA/FASTQ records into multiple files by part count, sequence count, or sequence length.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqkit', 'split2', 'SeqKit split2', 'split FASTQ', 'split FASTA', 'paired split', 'split by length', 'split by parts']
    RETURN_TYPES = ('DIRECTORY', 'DIRECTORY')
    RETURN_NAMES = ('split_files', 'paired_split_files')
    REQUIRED_EXECUTABLES = ['seqkit']
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/usage/#split2'
    CITATION_DOIS = ['10.1371/journal.pone.0163962']
    CITATION_URLS = ['https://doi.org/10.1371/journal.pone.0163962']
    CITATION_TEXT = 'SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation.'
    VERSION = '2.13.0'
    SHELL = True

    @classmethod
    def _input_name(cls, inputs: dict[str, Any], index: int | None=None) -> str:
        key = 'input_1_ext' if index in {None, 1} else 'input_2_ext'
        default = 'fastqsanger.gz' if index == 2 else 'fasta.gz'
        ext = str(inputs.get(key, default)).strip().lstrip('.') or default
        prefix = 'input' if index is None else f'input_{index}'
        return f'{prefix}.{ext}'

    @classmethod
    def _is_paired(cls, inputs: dict[str, Any]) -> bool:
        return str(inputs.get('input_type', inputs.get('type', 'single'))) == 'paired_collection'

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return 'paired_split_files' if cls._is_paired(inputs) else 'split_files'

    @classmethod
    def _add_split_selector(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        split_selector = str(inputs.get('split_selector', 'by_part'))
        if split_selector == 'by_size':
            cmd.extend(['-s', str(inputs.get('by_size', ''))])
            if cls._is_paired(inputs):
                cmd.extend(['--by-size-prefix', 'string', 'seqkit_split2_R{read}_'])
        elif split_selector == 'by_length':
            cmd.extend(['-l', str(inputs.get('by_length', ''))])
        else:
            cmd.extend(['-p', str(inputs.get('by_part', ''))])
            if cls._is_paired(inputs):
                cmd.extend(['--by-part-prefix', 'seqkit_split2_R{read}_'])

    @classmethod
    def _paired_rename_command(cls, out_dir: str) -> str:
        quoted_out = shlex.quote(out_dir)
        return f"""(find {quoted_out}/ -type f -name 'seqkit_split2_*.*' | while read -r file; do mv "$file" "$(echo "$file" | sed -E 's/(seqkit_split2)_(R1|R2)_([0-9]+)(\\..+)/\\1_\\3_\\2\\4/' | sed -E 's/_R1/_forward/; s/_R2/_reverse/')"; done)"""

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out_dir = f'{_out(inputs)}/{cls._output_name(inputs)}'
        parts = ['mkdir', '-p', out_dir]
        if cls._is_paired(inputs):
            input_1_name = cls._input_name(inputs, 1)
            input_2_name = cls._input_name(inputs, 2)
            cmd = ['seqkit', 'split2', '-1', input_1_name, '-2', input_2_name]
            cls._add_split_selector(cmd, inputs)
            cmd.extend(['-o', 'seqkit_split2', '-O', out_dir, '-j', str(inputs.get('threads', 4))])
            commands = [' '.join((shlex.quote(part) for part in parts)), f"ln -sf {shlex.quote(str(inputs.get('input_1', '')))} {shlex.quote(input_1_name)}", f"ln -sf {shlex.quote(str(inputs.get('input_2', '')))} {shlex.quote(input_2_name)}", ' '.join((shlex.quote(part) for part in cmd)), cls._paired_rename_command(out_dir)]
        else:
            input_name = cls._input_name(inputs)
            cmd = ['seqkit', 'split2', input_name]
            cls._add_split_selector(cmd, inputs)
            cmd.extend(['-o', 'seqkit_split2', '-O', out_dir, '-j', str(inputs.get('threads', 4))])
            commands = [' '.join((shlex.quote(part) for part in parts)), f"ln -sf {shlex.quote(str(inputs.get('input_1', inputs.get('input', ''))))} {shlex.quote(input_name)}", ' '.join((shlex.quote(part) for part in cmd))]
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / cls._output_name(inputs)
        out.mkdir(parents=True, exist_ok=True)
        return [out]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_type': ('STRING', {'default': 'single', 'options': ['single', 'paired_collection'], 'description': 'Single-end or paired-end reads'})}, 'optional': {'input_1': ('FASTQ_LIST', {'description': 'Single-end input or paired-end forward reads'}), 'input_2': ('FASTQ_LIST', {'description': 'Paired-end reverse reads'}), 'split_selector': ('STRING', {'default': 'by_part', 'options': ['by_part', 'by_size', 'by_length'], 'description': 'Split by number of parts, sequences per part, or sequence length'}), 'by_part': ('INT', {'default': 2, 'min': 1, 'description': 'Number of output parts'}), 'by_size': ('INT', {'default': 1000, 'min': 1, 'description': 'Sequences per output part'}), 'by_length': ('STRING', {'default': '50K', 'description': 'Chunk size with optional K/M/G suffix'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128}), 'input_1_ext': ('STRING', {'default': 'fasta.gz', 'options': ['fasta', 'fasta.gz', 'fastqsanger', 'fastqsanger.gz'], 'advanced': True}), 'input_2_ext': ('STRING', {'default': 'fastqsanger.gz', 'options': ['fasta', 'fasta.gz', 'fastqsanger', 'fastqsanger.gz'], 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
