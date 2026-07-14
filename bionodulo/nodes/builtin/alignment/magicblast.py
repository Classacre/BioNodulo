"""magicblast — alignment node(s). One tool per file (extracted from wrapped_taxonomy_humann.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class MagicBlastNode(CommandNode):
    """Map large RNA or DNA reads against a genome or transcriptome with Magic-BLAST."""
    NODE_ID = 'magicblast'
    DISPLAY_NAME = 'Magic-BLAST'
    REQUIRED_CONDA_PACKAGES = ['magicblast', 'samtools']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Map large RNA or DNA sequencing reads against a whole genome or transcriptome.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Magic-BLAST', 'magicblast', 'RNA-seq aligner', 'long and short reads', 'whole genome mapping', 'transcriptome mapping', 'spliced alignments', 'BLAST mapper']
    RETURN_TYPES = ('BAM', 'FILE')
    RETURN_NAMES = ('output', 'output_unaligned')
    REQUIRED_EXECUTABLES = ['magicblast', 'samtools', 'gunzip']
    DOCUMENTATION_URL = 'https://ncbi.github.io/magicblast/'
    CITATION_DOIS = [MAGICBLAST_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{MAGICBLAST_CITATION_DOI}']
    CITATION_TEXT = MAGICBLAST_CITATION_TEXT
    VERSION = '1.7.0+galaxy2'
    SHELL = True
    DB_OPTIONS = ['histdb', 'db', 'file']
    OUTFMTS = ['bam', 'tabular']
    SORT_OPTIONS = ['coordinate', 'name', 'unsorted']
    UNALIGNED_FORMATS = ['bam', 'tabular', 'fasta']
    REFTYPES = ['genome', 'transcriptome']

    @classmethod
    def _outfmt(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('outfmt', 'bam') or 'bam')

    @classmethod
    def _output_sort(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('output_sort', 'coordinate') or 'coordinate')

    @classmethod
    def _unaligned_output_sort(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('unaligned_output_sort', inputs.get('output_sort', 'coordinate')) or 'coordinate')

    @classmethod
    def _unaligned_fmt(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('unaligned_fmt', 'bam') or 'bam')

    @classmethod
    def _is_gzip(cls, path: Any, explicit_type: Any='') -> bool:
        value = str(explicit_type or path or '').lower()
        return value.endswith('.gz') or value in {'fasta.gz', 'fastqsanger.gz'}

    @classmethod
    def _is_fastq(cls, path: Any, explicit_type: Any='') -> bool:
        value = str(explicit_type or path or '').lower()
        return 'fastq' in value or 'fastqsanger' in value or value.endswith(('.fq', '.fq.gz'))

    @classmethod
    def _file_arg(cls, path: str, *, compressed: bool) -> str:
        quoted = shlex.quote(path)
        return f'<(gunzip -c {quoted})' if compressed else quoted

    @classmethod
    def _bool_text(cls, value: Any, default: bool) -> str:
        if value is None or value == '':
            value = default
        if isinstance(value, str):
            return 'false' if value.lower() in {'false', '0', 'no'} else 'true'
        return 'true' if bool(value) else 'false'

    @classmethod
    def _main_output_path(cls, inputs: dict[str, Any]) -> str:
        suffix = 'bam' if cls._outfmt(inputs) == 'bam' else 'tabular'
        return f'{_out(inputs)}/output.{suffix}'

    @classmethod
    def _unaligned_output_path(cls, inputs: dict[str, Any]) -> str:
        suffix = {'bam': 'bam', 'tabular': 'tabular', 'fasta': 'fasta'}[cls._unaligned_fmt(inputs)]
        return f'{_out(inputs)}/output_unaligned.{suffix}'

    @classmethod
    def _add_restrict_search(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        for key in ('gilist', 'negative_gilist', 'seqidlist', 'negative_seqidlist', 'taxidlist', 'negative_taxidlist'):
            _add_if_value(cmd, f'-{key}', inputs.get(key))
        _add_if_value(cmd, '--taxids', inputs.get('taxids'))
        _add_if_value(cmd, '--negative_taxids', inputs.get('negative_taxids'))

    @classmethod
    def _samtools_bam_conversion(cls, input_sam: str, output_bam: str, sort_mode: str) -> str:
        if sort_mode == 'coordinate':
            return f'samtools sort -@${{GALAXY_SLOTS:-4}} -O bam {shlex.quote(input_sam)} > {shlex.quote(output_bam)}'
        if sort_mode == 'name':
            return f'samtools sort -n -@${{GALAXY_SLOTS:-4}} -O bam {shlex.quote(input_sam)} > {shlex.quote(output_bam)}'
        return f'samtools view -@${{GALAXY_SLOTS:-4}} -bS {shlex.quote(input_sam)} > {shlex.quote(output_bam)}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        query = str(inputs.get('query', ''))
        query_type = inputs.get('query_type', inputs.get('query_ext', ''))
        threads = int(inputs.get('threads', 8) or 8)
        cmd = ['magicblast', '-num_threads', f'${{GALAXY_SLOTS:-{threads}}}', '-query', cls._file_arg(query, compressed=cls._is_gzip(query, query_type))]
        query_mate = str(inputs.get('query_mate', '') or '')
        if query_mate:
            mate_type = inputs.get('query_mate_type', query_type)
            cmd.extend(['-paired', '-query_mate', cls._file_arg(query_mate, compressed=cls._is_gzip(query_mate, mate_type))])
        if cls._is_fastq(query, query_type):
            cmd.extend(['-infmt', 'fastq'])
        db_selector = str(inputs.get('db_opts_selector', 'histdb') or 'histdb')
        if db_selector == 'histdb':
            histdb = str(inputs.get('histdb', inputs.get('db', '')))
            cmd.extend(['-db', f"{histdb.rstrip('/')}/blastdb" if histdb and (not histdb.endswith('blastdb')) else histdb])
        elif db_selector == 'db':
            cmd.extend(['-db', str(inputs.get('database', ''))])
        else:
            subject = str(inputs.get('subject', ''))
            subject_type = inputs.get('subject_type', inputs.get('subject_ext', ''))
            cmd.extend(['-subject', cls._file_arg(subject, compressed=cls._is_gzip(subject, subject_type))])
        for key, default in (('word_size', 18), ('gapopen', 0), ('gapextend', 0), ('penalty', -4), ('max_intron_length', 500000)):
            cmd.extend([f'-{key}', str(inputs.get(key, default))])
        if inputs.get('lcase_masking'):
            cmd.append('-lcase_masking')
        cmd.extend(['-validate_seqs', cls._bool_text(inputs.get('validate_seqs'), True)])
        cmd.extend(['-limit_lookup', cls._bool_text(inputs.get('limit_lookup'), True)])
        cmd.extend(['-max_db_word_count', str(inputs.get('max_db_word_count', 30))])
        cmd.extend(['-lookup_stride', str(inputs.get('lookup_stride', 0))])
        cls._add_restrict_search(cmd, inputs)
        cmd.extend(['-score', str(inputs.get('score', 0))])
        max_edit_dist = int(inputs.get('max_edit_dist', 0) or 0)
        if max_edit_dist > 0:
            cmd.extend(['-max_edit_dist', str(max_edit_dist)])
        cmd.extend(['-splice', cls._bool_text(inputs.get('splice'), True)])
        cmd.extend(['-reftype', str(inputs.get('reftype', 'genome') or 'genome')])
        report_unaligned = str(inputs.get('report_unaligned', 'yes') or 'yes')
        report_separately = str(inputs.get('report_unaligned_separately', 'no') or 'no')
        if report_unaligned == 'yes' and report_separately == 'yes':
            cmd.extend(['-out_unaligned', 'out_unaligned'])
            unaligned_arg = 'sam' if cls._unaligned_fmt(inputs) == 'bam' else cls._unaligned_fmt(inputs)
            cmd.extend(['-unaligned_fmt', unaligned_arg])
        elif report_unaligned == 'no':
            cmd.append('-no_unaligned')
        if inputs.get('no_discordant'):
            cmd.append('-no_discordant')
        post_commands: list[str] = []
        if cls._outfmt(inputs) == 'bam':
            if inputs.get('md_tag'):
                cmd.append('-md_tag')
            if query_mate and inputs.get('no_query_id_trim'):
                cmd.append('-no_query_id_trim')
            cmd.extend(['-out', 'output.sam'])
            post_commands.append(cls._samtools_bam_conversion('output.sam', cls._main_output_path(inputs), cls._output_sort(inputs)))
        else:
            cmd.extend(['-out', cls._main_output_path(inputs), '-outfmt', cls._outfmt(inputs)])
        if report_unaligned == 'yes' and report_separately == 'yes':
            if cls._unaligned_fmt(inputs) == 'bam':
                post_commands.append(cls._samtools_bam_conversion('out_unaligned', cls._unaligned_output_path(inputs), cls._unaligned_output_sort(inputs)))
            else:
                post_commands.append(f'mv out_unaligned {shlex.quote(cls._unaligned_output_path(inputs))}')
        rendered = _shell_join(cmd)
        slots_var = f'${{GALAXY_SLOTS:-{threads}}}'
        rendered = rendered.replace(shlex.quote(slots_var), slots_var)
        if post_commands:
            rendered = ' && '.join([rendered, *post_commands])
        return rendered

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = 'bam' if cls._outfmt(inputs) == 'bam' else 'tabular'
        outputs = [out / f'output.{suffix}']
        if str(inputs.get('report_unaligned', 'yes') or 'yes') == 'yes' and str(inputs.get('report_unaligned_separately', 'no') or 'no') == 'yes':
            unaligned_suffix = {'bam': 'bam', 'tabular': 'tabular', 'fasta': 'fasta'}[cls._unaligned_fmt(inputs)]
            outputs.append(out / f'output_unaligned.{unaligned_suffix}')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('query', '')).strip():
            return 'query is required'
        db_selector = str(inputs.get('db_opts_selector', 'histdb') or 'histdb')
        if db_selector not in cls.DB_OPTIONS:
            return f"db_opts_selector must be one of: {', '.join(cls.DB_OPTIONS)}"
        if db_selector == 'histdb' and (not str(inputs.get('histdb', inputs.get('db', ''))).strip()):
            return 'histdb is required when db_opts_selector is histdb'
        if db_selector == 'db' and (not str(inputs.get('database', '')).strip()):
            return 'database is required when db_opts_selector is db'
        if db_selector == 'file' and (not str(inputs.get('subject', '')).strip()):
            return 'subject is required when db_opts_selector is file'
        outfmt = cls._outfmt(inputs)
        if outfmt not in cls.OUTFMTS:
            return f"outfmt must be one of: {', '.join(cls.OUTFMTS)}"
        output_sort = cls._output_sort(inputs)
        if output_sort not in cls.SORT_OPTIONS:
            return f"output_sort must be one of: {', '.join(cls.SORT_OPTIONS)}"
        unaligned_sort = cls._unaligned_output_sort(inputs)
        if unaligned_sort not in cls.SORT_OPTIONS:
            return f"unaligned_output_sort must be one of: {', '.join(cls.SORT_OPTIONS)}"
        if cls._unaligned_fmt(inputs) not in cls.UNALIGNED_FORMATS:
            return f"unaligned_fmt must be one of: {', '.join(cls.UNALIGNED_FORMATS)}"
        if str(inputs.get('reftype', 'genome') or 'genome') not in cls.REFTYPES:
            return f"reftype must be one of: {', '.join(cls.REFTYPES)}"
        if int(inputs.get('word_size', 18) or 18) < 12:
            return 'word_size must be >= 12'
        for key in ('gapopen', 'gapextend', 'max_intron_length', 'max_db_word_count', 'lookup_stride', 'score', 'max_edit_dist'):
            if int(inputs.get(key, 0) or 0) < 0:
                return f'{key} must be >= 0'
        if int(inputs.get('penalty', -4) or -4) > 0:
            return 'penalty must be <= 0'
        return super().VALIDATE_INPUTS(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'query': ('FASTQ', {'description': 'FASTA or fastqsanger query reads, optionally gzip-compressed'})}, 'optional': {'query_mate': ('FASTQ', {'default': '', 'description': 'Optional mate reads for paired-end mapping'}), 'query_type': ('STRING', {'default': '', 'options': ['', 'fasta', 'fasta.gz', 'fastqsanger', 'fastqsanger.gz'], 'advanced': True}), 'query_mate_type': ('STRING', {'default': '', 'options': ['', 'fasta', 'fasta.gz', 'fastqsanger', 'fastqsanger.gz'], 'advanced': True}), 'db_opts_selector': ('STRING', {'default': 'histdb', 'options': cls.DB_OPTIONS}), 'histdb': ('DIRECTORY', {'default': '', 'description': 'History BLAST database directory'}), 'database': ('FILE', {'default': '', 'description': 'Locally installed nucleotide BLAST database path'}), 'subject': ('FASTA', {'default': '', 'description': 'Subject FASTA file to search instead of a database'}), 'subject_type': ('STRING', {'default': '', 'options': ['', 'fasta', 'fasta.gz'], 'advanced': True}), 'word_size': ('INT', {'default': 18, 'min': 12}), 'gapopen': ('INT', {'default': 0, 'min': 0}), 'gapextend': ('INT', {'default': 0, 'min': 0}), 'penalty': ('INT', {'default': -4, 'max': 0}), 'max_intron_length': ('INT', {'default': 500000, 'min': 0}), 'lcase_masking': ('BOOLEAN', {'default': False}), 'validate_seqs': ('BOOLEAN', {'default': True}), 'limit_lookup': ('BOOLEAN', {'default': True}), 'max_db_word_count': ('INT', {'default': 30, 'min': 0}), 'lookup_stride': ('INT', {'default': 0, 'min': 0}), 'gilist': ('TSV', {'default': ''}), 'negative_gilist': ('TSV', {'default': ''}), 'seqidlist': ('TSV', {'default': ''}), 'negative_seqidlist': ('TSV', {'default': ''}), 'taxids': ('STRING', {'default': ''}), 'taxidlist': ('TSV', {'default': ''}), 'negative_taxids': ('STRING', {'default': ''}), 'negative_taxidlist': ('TSV', {'default': ''}), 'score': ('INT', {'default': 0, 'min': 0}), 'max_edit_dist': ('INT', {'default': 0, 'min': 0}), 'splice': ('BOOLEAN', {'default': True}), 'reftype': ('STRING', {'default': 'genome', 'options': cls.REFTYPES}), 'report_unaligned': ('STRING', {'default': 'yes', 'options': ['yes', 'no']}), 'report_unaligned_separately': ('STRING', {'default': 'no', 'options': ['no', 'yes']}), 'unaligned_fmt': ('STRING', {'default': 'bam', 'options': cls.UNALIGNED_FORMATS}), 'unaligned_output_sort': ('STRING', {'default': 'coordinate', 'options': cls.SORT_OPTIONS}), 'outfmt': ('STRING', {'default': 'bam', 'options': cls.OUTFMTS}), 'output_sort': ('STRING', {'default': 'coordinate', 'options': cls.SORT_OPTIONS}), 'md_tag': ('BOOLEAN', {'default': False}), 'no_query_id_trim': ('BOOLEAN', {'default': False}), 'no_discordant': ('BOOLEAN', {'default': False}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}
