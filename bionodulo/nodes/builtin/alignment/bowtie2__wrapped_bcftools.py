"""bowtie2 — alignment node(s). One tool per file (extracted from wrapped_bcftools.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class Bowtie2Node(CommandNode):
    """Map reads with Galaxy's Bowtie2 wrapper and emit BAM/SAM alignments."""
    NODE_ID = 'bowtie2'
    DISPLAY_NAME = 'Bowtie2'
    REQUIRED_CONDA_PACKAGES = ['bowtie2', 'samtools']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Map reads against a reference genome with Bowtie2 and emit BAM or SAM alignments.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Bowtie2', 'bowtie2', 'bowtie2-build', 'read mapping', 'paired-end alignment', 'BAM output', 'SAM output']
    RETURN_TYPES = ('BAM', 'TXT', 'FASTQ', 'FASTQ', 'FASTQ', 'FASTQ')
    RETURN_NAMES = ('alignments', 'mapping_stats', 'unaligned_reads', 'aligned_reads', 'unaligned_read_pairs', 'aligned_read_pairs')
    REQUIRED_EXECUTABLES = ['bowtie2', 'bowtie2-build', 'samtools']
    DOCUMENTATION_URL = 'https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml'
    CITATION_DOIS = [BOWTIE2_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{BOWTIE2_CITATION_DOI}']
    CITATION_TEXT = BOWTIE2_CITATION_TEXT
    VERSION = '2.5.5+galaxy0'
    SHELL = True
    REFERENCE_SOURCE_OPTIONS = ['indexed', 'history']
    LIBRARY_TYPE_OPTIONS = ['single', 'paired_collection']
    ANALYSIS_TYPE_OPTIONS = ['simple', 'full']
    PRESET_OPTIONS = ['no_presets', '--very-fast', '--fast', '--sensitive', '--very-sensitive', '--very-fast-local', '--fast-local', '--sensitive-local', '--very-sensitive-local']
    SAM_OUTPUT_FORMAT_OPTIONS = ['bam', 'sam', 'qname_input_sorted_bam']
    READS_FORMAT_OPTIONS = ['fastq', 'fasta']
    READS_COMPRESSION_OPTIONS = ['', 'gz', 'bz2']
    PAIRED_ORIENTATION_OPTIONS = ['--fr', '--rf', '--ff']
    QV_ENCODING_OPTIONS = ['--phred33', '--phred64']
    REPORTING_OPTIONS = ['no', 'k', 'a']
    INT_MIN_KEYS = {'I': 0, 'X': 0, 'skip': 0, 'qupto': 1, 'trim5': 0, 'trim3': 0, 'N': 0, 'seed_L': 0, 'dpad': 0, 'gbar': 0, 'ma': 0, 'np': 0, 'rdg_read_open': 0, 'rdg_read_extend': 0, 'rfg_ref_open': 0, 'rfg_ref_extend': 0, 'k': 1, 'D': 0, 'R': 0, 'seed': 0}

    @classmethod
    def _out_alignments(cls, inputs: dict[str, Any]) -> str:
        suffix = 'sam' if cls._sam_output_format(inputs) == 'sam' else 'bam'
        return f'{_out(inputs)}/alignments.{suffix}'

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('reference_source_selector', inputs.get('reference_source', 'indexed')) or 'indexed')

    @classmethod
    def _ref_file(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('ref_file', inputs.get('reference', '')) or '')

    @classmethod
    def _reference_prelude_and_index(cls, inputs: dict[str, Any]) -> tuple[list[str], str]:
        ref_file = cls._ref_file(inputs)
        if cls._reference_source(inputs) == 'history':
            return (['bowtie2-build', '--threads', '${GALAXY_SLOTS:-4}', ref_file, 'genome', '&&'], 'genome')
        return ([], ref_file)

    @classmethod
    def _library_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('library_type', inputs.get('type', 'single')) or 'single')

    @classmethod
    def _paired_collection_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        reads_value = inputs.get('input_1', inputs.get('reads', inputs.get('reads_collection', '')))
        if isinstance(reads_value, dict):
            return (str(reads_value.get('forward', '')), str(reads_value.get('reverse', '')))
        reads = _as_list(reads_value)
        return (reads[0] if reads else '', reads[1] if len(reads) > 1 else '')

    @classmethod
    def _single_read(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_1', inputs.get('read1', '')) or '')

    @classmethod
    def _reads_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('reads_format', 'fastq') or 'fastq')

    @classmethod
    def _reads_compression(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get('reads_compression', '') or '')
        if explicit:
            return explicit
        reads = [cls._single_read(inputs)] if cls._library_type(inputs) == 'single' else list(cls._paired_collection_reads(inputs))
        lowered = ' '.join(reads).lower()
        if '.gz' in lowered:
            return 'gz'
        if '.bz2' in lowered:
            return 'bz2'
        return ''

    @classmethod
    def _analysis_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('analysis_type_selector', 'simple') or 'simple')

    @classmethod
    def _sam_output_format(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get('sam_options_selector', 'no') or 'no') != 'yes':
            return 'bam'
        if inputs.get('reorder') is True or inputs.get('reorder') == '--reorder':
            return 'qname_input_sorted_bam'
        if inputs.get('sam_opt') is True or str(inputs.get('sam_opt', '')).lower() == 'true':
            return 'sam'
        return str(inputs.get('sam_output_format', 'bam') or 'bam')

    @classmethod
    def _flag_path(cls, inputs: dict[str, Any], stem: str, *, paired: bool) -> str:
        if paired:
            return f'{_out(inputs)}/{stem}'
        suffix = 'fasta' if cls._reads_format(inputs) == 'fasta' else 'fastq'
        return f'{_out(inputs)}/{stem}.{suffix}'

    @classmethod
    def _read_pair_output_paths(cls, inputs: dict[str, Any], stem: str) -> list[Path]:
        suffix = 'fasta' if cls._reads_format(inputs) == 'fasta' else 'fastq'
        return [Path(f'{stem}.1.{suffix}'), Path(f'{stem}.2.{suffix}')]

    @classmethod
    def _add_read_inputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._reads_format(inputs) == 'fasta':
            cmd.append('-f')
        if cls._library_type(inputs) == 'single':
            cmd.extend(['-U', cls._single_read(inputs)])
            compression = cls._reads_compression(inputs)
            if inputs.get('unaligned_file'):
                cmd.extend([{'gz': '--un-gz', 'bz2': '--un-bz2'}.get(compression, '--un'), cls._flag_path(inputs, 'unaligned_reads', paired=False)])
            if inputs.get('aligned_file'):
                cmd.extend([{'gz': '--al-gz', 'bz2': '--al-bz2'}.get(compression, '--al'), cls._flag_path(inputs, 'aligned_reads', paired=False)])
            return
        read1, read2 = cls._paired_collection_reads(inputs)
        cmd.extend(['-1', read1, '-2', read2])
        compression = cls._reads_compression(inputs)
        if inputs.get('unaligned_file'):
            cmd.extend([{'gz': '--un-conc-gz', 'bz2': '--un-conc-bz2'}.get(compression, '--un-conc'), cls._flag_path(inputs, 'unaligned_reads', paired=True)])
        if inputs.get('aligned_file'):
            cmd.extend([{'gz': '--al-conc-gz', 'bz2': '--al-conc-bz2'}.get(compression, '--al-conc'), cls._flag_path(inputs, 'aligned_reads', paired=True)])
        if str(inputs.get('paired_options_selector', 'no') or 'no') == 'yes':
            for flag, key, default in (('-I', 'I', 0), ('-X', 'X', 500)):
                cmd.extend([flag, str(inputs.get(key, default))])
            cmd.append(str(inputs.get('fr_rf_ff', '--fr') or '--fr'))
            for key, flag in (('no_mixed', '--no-mixed'), ('no_discordant', '--no-discordant'), ('dovetail', '--dovetail'), ('no_contain', '--no-contain'), ('no_overlap', '--no-overlap')):
                if inputs.get(key):
                    cmd.append(flag)

    @classmethod
    def _add_read_group(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if str(inputs.get('rg_selector', 'do_not_set') or 'do_not_set') == 'do_not_set':
            return
        rg_id = str(inputs.get('rg_id', inputs.get('ID', '')) or '')
        if not rg_id:
            seed = cls._single_read(inputs) if cls._library_type(inputs) == 'single' else cls._paired_collection_reads(inputs)[0]
            rg_id = _safe_name(seed) if seed else 'read_group'
        cmd.extend(['--rg-id', rg_id])
        for tag, key in (('SM', 'rg_sm'), ('PL', 'rg_pl'), ('LB', 'rg_lb'), ('CN', 'rg_cn'), ('DS', 'rg_ds'), ('DT', 'rg_dt'), ('FO', 'rg_fo'), ('KS', 'rg_ks'), ('PG', 'rg_pg'), ('PI', 'rg_pi'), ('PU', 'rg_pu')):
            value = inputs.get(key, inputs.get(tag, ''))
            if value is not None and str(value) != '':
                cmd.extend(['--rg', f'{tag}:{value}'])

    @classmethod
    def _add_full_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._analysis_type(inputs) == 'simple':
            preset = str(inputs.get('preset', 'no_presets') or 'no_presets')
            if preset != 'no_presets':
                cmd.append(preset)
            return
        if str(inputs.get('input_options_selector', 'no') or 'no') == 'yes':
            for flag, key, default in (('--skip', 'skip', 0), ('--qupto', 'qupto', 100000000), ('--trim5', 'trim5', 0), ('--trim3', 'trim3', 0)):
                cmd.extend([flag, str(inputs.get(key, default))])
            cmd.append(str(inputs.get('qv_encoding', '--phred33') or '--phred33'))
            for key, flag in (('solexa_quals', '--solexa-quals'), ('int_quals', '--int-quals')):
                if inputs.get(key):
                    cmd.append(flag)
        if str(inputs.get('alignment_options_selector', 'no') or 'no') == 'yes':
            for flag, key, default in (('-N', 'N', 0), ('-L', 'seed_L', 22), ('-i', 'i', 'S,1,1.15'), ('--n-ceil', 'n_ceil', 'L,0,0.15'), ('--dpad', 'dpad', 15), ('--gbar', 'gbar', 4)):
                cmd.extend([flag, str(inputs.get(key, default))])
            for key, flag in (('ignore_quals', '--ignore-quals'), ('nofw', '--nofw'), ('norc', '--norc'), ('no_1mm_upfront', '--no-1mm-upfront')):
                if inputs.get(key):
                    cmd.append(flag)
            align_mode = str(inputs.get('align_mode_selector', 'end-to-end') or 'end-to-end')
            if align_mode == 'local':
                cmd.extend(['--local', '--score-min', str(inputs.get('score_min_loc', 'G,20,8'))])
            else:
                cmd.extend(['--end-to-end', '--score-min', str(inputs.get('score_min_ete', 'L,-0.6,-0.6'))])
        if str(inputs.get('scoring_options_selector', 'no') or 'no') == 'yes':
            if str(inputs.get('align_mode_selector', 'end-to-end') or 'end-to-end') == 'local':
                cmd.extend(['--ma', str(inputs.get('ma', 2))])
            cmd.extend(['--mp', str(inputs.get('mp', '6,2')), '--np', str(inputs.get('np', 1)), '--rdg', f"{inputs.get('rdg_read_open', 5)},{inputs.get('rdg_read_extend', 3)}", '--rfg', f"{inputs.get('rfg_ref_open', 5)},{inputs.get('rfg_ref_extend', 3)}"])
        reporting = str(inputs.get('reporting_options_selector', 'no') or 'no')
        if reporting == 'k':
            cmd.extend(['-k', str(inputs.get('k', 1))])
        elif reporting == 'a':
            cmd.append('-a')
        if str(inputs.get('effort_options_selector', 'no') or 'no') == 'yes':
            cmd.extend(['-D', str(inputs.get('D', 15)), '-R', str(inputs.get('R', 2))])
            if inputs.get('d'):
                cmd.append('-d')
        if str(inputs.get('other_options_selector', 'no') or 'no') == 'yes':
            if inputs.get('non_deterministic'):
                cmd.append('--non-deterministic')
            cmd.extend(['--seed', str(inputs.get('seed', 0))])

    @classmethod
    def _add_sam_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if str(inputs.get('sam_options_selector', 'no') or 'no') != 'yes':
            return
        for key, flag in (('no_unal', '--no-unal'), ('omit_sec_seq', '--omit-sec-seq'), ('sam_no_qname_trunc', '--sam-no-qname-trunc'), ('xeq', '--xeq'), ('soft_clipped_unmapped_tlen', '--soft-clipped-unmapped-tlen')):
            if inputs.get(key):
                cmd.append(flag)
        if cls._sam_output_format(inputs) == 'qname_input_sorted_bam':
            cmd.append('--reorder')

    @classmethod
    def _add_output(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if inputs.get('save_mapping_stats'):
            cmd.extend(['2>', f'{_out(inputs)}/mapping_stats.txt'])
        output_format = cls._sam_output_format(inputs)
        if output_format == 'sam':
            cmd.extend(['>', cls._out_alignments(inputs)])
        elif output_format == 'qname_input_sorted_bam':
            cmd.extend(['|', 'samtools', 'view', '--no-PG', '-b', '-o', cls._out_alignments(inputs)])
        else:
            cmd.extend(['|', 'samtools', 'sort', '-l', '0', '-T', '${TMPDIR:-.}', '-O', 'bam', '|', 'samtools', 'view', '--no-PG', '-O', 'bam', '-@', '${GALAXY_SLOTS:-1}', '-o', cls._out_alignments(inputs)])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        prelude, index_path = cls._reference_prelude_and_index(inputs)
        cmd = ['set', '-o', 'pipefail', '&&']
        cmd.extend(prelude)
        bowtie_cmd = ['bowtie2', '-p', '${GALAXY_SLOTS:-1}', '-x', index_path]
        cls._add_read_inputs(bowtie_cmd, inputs)
        cls._add_read_group(bowtie_cmd, inputs)
        cls._add_full_options(bowtie_cmd, inputs)
        cls._add_sam_options(bowtie_cmd, inputs)
        cls._add_output(bowtie_cmd, inputs)
        cmd.extend(bowtie_cmd)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / Path(cls._out_alignments({'output': str(out), **inputs})).name]
        if inputs.get('save_mapping_stats'):
            outputs.append(out / 'mapping_stats.txt')
        if cls._library_type(inputs) == 'single':
            if inputs.get('unaligned_file'):
                outputs.append(out / cls._read_pair_output_paths({'reads_format': cls._reads_format(inputs)}, 'unaligned_reads')[0].name.replace('.1.', '.'))
            if inputs.get('aligned_file'):
                outputs.append(out / cls._read_pair_output_paths({'reads_format': cls._reads_format(inputs)}, 'aligned_reads')[0].name.replace('.1.', '.'))
            return outputs
        if inputs.get('unaligned_file'):
            outputs.extend((out / path for path in cls._read_pair_output_paths(inputs, 'unaligned_reads')))
        if inputs.get('aligned_file'):
            outputs.extend((out / path for path in cls._read_pair_output_paths(inputs, 'aligned_reads')))
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, minimum: int) -> bool | str:
        if key not in inputs or inputs.get(key) in {None, ''}:
            return True
        try:
            value = int(inputs[key])
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if value < minimum:
            return f'{key} must be at least {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._ref_file(inputs).strip():
            return 'ref_file is required'
        if cls._library_type(inputs) not in cls.LIBRARY_TYPE_OPTIONS:
            return f"library_type must be one of: {', '.join(cls.LIBRARY_TYPE_OPTIONS)}"
        reads = [cls._single_read(inputs)] if cls._library_type(inputs) == 'single' else list(cls._paired_collection_reads(inputs))
        if not reads or not reads[0].strip():
            return 'input_1 is required'
        if cls._library_type(inputs) == 'paired_collection' and (len(reads) < 2 or not reads[1].strip()):
            return 'paired collection requires forward and reverse reads'
        if cls._reference_source(inputs) not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"reference_source_selector must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        if cls._analysis_type(inputs) not in cls.ANALYSIS_TYPE_OPTIONS:
            return f"analysis_type_selector must be one of: {', '.join(cls.ANALYSIS_TYPE_OPTIONS)}"
        preset = str(inputs.get('preset', 'no_presets') or 'no_presets')
        if preset not in cls.PRESET_OPTIONS:
            return f"preset must be one of: {', '.join(cls.PRESET_OPTIONS)}"
        if 'sam_output_format' in inputs and inputs.get('sam_output_format') not in {None, ''}:
            requested_output_format = str(inputs.get('sam_output_format') or '')
            if requested_output_format not in cls.SAM_OUTPUT_FORMAT_OPTIONS:
                return f"sam_output_format must be one of: {', '.join(cls.SAM_OUTPUT_FORMAT_OPTIONS)}"
        if cls._sam_output_format(inputs) not in cls.SAM_OUTPUT_FORMAT_OPTIONS:
            return f"sam_output_format must be one of: {', '.join(cls.SAM_OUTPUT_FORMAT_OPTIONS)}"
        if cls._reads_format(inputs) not in cls.READS_FORMAT_OPTIONS:
            return f"reads_format must be one of: {', '.join(cls.READS_FORMAT_OPTIONS)}"
        if cls._reads_compression(inputs) not in cls.READS_COMPRESSION_OPTIONS:
            return f"reads_compression must be one of: {', '.join(cls.READS_COMPRESSION_OPTIONS)}"
        if str(inputs.get('fr_rf_ff', '--fr') or '--fr') not in cls.PAIRED_ORIENTATION_OPTIONS:
            return f"fr_rf_ff must be one of: {', '.join(cls.PAIRED_ORIENTATION_OPTIONS)}"
        if str(inputs.get('qv_encoding', '--phred33') or '--phred33') not in cls.QV_ENCODING_OPTIONS:
            return f"qv_encoding must be one of: {', '.join(cls.QV_ENCODING_OPTIONS)}"
        if str(inputs.get('reporting_options_selector', 'no') or 'no') not in cls.REPORTING_OPTIONS:
            return f"reporting_options_selector must be one of: {', '.join(cls.REPORTING_OPTIONS)}"
        for key, minimum in cls.INT_MIN_KEYS.items():
            validation = cls._validate_int_min(inputs, key, minimum)
            if validation is not True:
                return validation
        if 'N' in inputs and inputs.get('N') not in {None, ''} and (int(inputs['N']) > 1):
            return 'N must be at most 1'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'ref_file': ('BOWTIE2_INDEX', {'description': 'Bowtie2 index prefix, or a FASTA when reference_source_selector is history'}), 'library_type': ('STRING', {'default': 'single', 'options': cls.LIBRARY_TYPE_OPTIONS, 'description': 'Single-end or paired collection input'}), 'input_1': ('FASTQ', {'description': 'Single reads, or a paired collection/dict with forward and reverse reads'})}, 'optional': {'reference_source_selector': ('STRING', {'default': 'indexed', 'options': cls.REFERENCE_SOURCE_OPTIONS, 'description': 'Use a built-in index or build from history FASTA'}), 'reads_format': ('STRING', {'default': 'fastq', 'options': cls.READS_FORMAT_OPTIONS, 'description': 'Treat reads as FASTQ or FASTA'}), 'reads_compression': ('STRING', {'default': '', 'options': cls.READS_COMPRESSION_OPTIONS, 'description': 'Compression mode for aligned/unaligned read outputs'}), 'unaligned_file': ('BOOLEAN', {'default': False, 'description': 'Write reads that fail to align'}), 'aligned_file': ('BOOLEAN', {'default': False, 'description': 'Write reads that align at least once'}), 'paired_options_selector': ('STRING', {'default': 'no', 'options': ['no', 'yes'], 'description': 'Enable paired-end fragment and orientation options'}), 'I': ('INT', {'default': 0, 'min': 0, 'advanced': True, 'description': 'Minimum paired-end fragment length'}), 'X': ('INT', {'default': 500, 'min': 0, 'advanced': True, 'description': 'Maximum paired-end fragment length'}), 'fr_rf_ff': ('STRING', {'default': '--fr', 'options': cls.PAIRED_ORIENTATION_OPTIONS, 'advanced': True}), 'no_mixed': ('BOOLEAN', {'default': False, 'advanced': True, 'description': 'Disable mixed alignments'}), 'no_discordant': ('BOOLEAN', {'default': False, 'advanced': True, 'description': 'Disable discordant alignments'}), 'dovetail': ('BOOLEAN', {'default': False, 'advanced': True, 'description': 'Allow dovetailing mates'}), 'no_contain': ('BOOLEAN', {'default': False, 'advanced': True, 'description': 'Disallow contained mate alignments'}), 'no_overlap': ('BOOLEAN', {'default': False, 'advanced': True, 'description': 'Disallow overlapping mates'}), 'analysis_type_selector': ('STRING', {'default': 'simple', 'options': cls.ANALYSIS_TYPE_OPTIONS, 'description': 'Simple presets or full Bowtie2 options'}), 'preset': ('STRING', {'default': 'no_presets', 'options': cls.PRESET_OPTIONS, 'description': 'Bowtie2 simple-mode preset'}), 'input_options_selector': ('STRING', {'default': 'no', 'options': ['no', 'yes'], 'advanced': True}), 'skip': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'qupto': ('INT', {'default': 100000000, 'min': 1, 'advanced': True}), 'trim5': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'trim3': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'qv_encoding': ('STRING', {'default': '--phred33', 'options': cls.QV_ENCODING_OPTIONS, 'advanced': True}), 'solexa_quals': ('BOOLEAN', {'default': False, 'advanced': True}), 'int_quals': ('BOOLEAN', {'default': False, 'advanced': True}), 'alignment_options_selector': ('STRING', {'default': 'no', 'options': ['no', 'yes'], 'advanced': True}), 'N': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True, 'description': 'Seed mismatches'}), 'seed_L': ('INT', {'default': 22, 'min': 0, 'max': 32, 'advanced': True, 'description': 'Seed length'}), 'i': ('STRING', {'default': 'S,1,1.15', 'advanced': True, 'description': 'Seed interval function'}), 'n_ceil': ('STRING', {'default': 'L,0,0.15', 'advanced': True, 'description': 'N-ceiling function'}), 'dpad': ('INT', {'default': 15, 'min': 0, 'advanced': True}), 'gbar': ('INT', {'default': 4, 'min': 0, 'advanced': True}), 'ignore_quals': ('BOOLEAN', {'default': False, 'advanced': True}), 'nofw': ('BOOLEAN', {'default': False, 'advanced': True}), 'norc': ('BOOLEAN', {'default': False, 'advanced': True}), 'no_1mm_upfront': ('BOOLEAN', {'default': False, 'advanced': True}), 'align_mode_selector': ('STRING', {'default': 'end-to-end', 'options': ['end-to-end', 'local'], 'advanced': True}), 'score_min_ete': ('STRING', {'default': 'L,-0.6,-0.6', 'advanced': True}), 'score_min_loc': ('STRING', {'default': 'G,20,8', 'advanced': True}), 'scoring_options_selector': ('STRING', {'default': 'no', 'options': ['no', 'yes'], 'advanced': True}), 'ma': ('INT', {'default': 2, 'min': 0, 'advanced': True}), 'mp': ('STRING', {'default': '6,2', 'advanced': True}), 'np': ('INT', {'default': 1, 'min': 0, 'advanced': True}), 'rdg_read_open': ('INT', {'default': 5, 'min': 0, 'advanced': True}), 'rdg_read_extend': ('INT', {'default': 3, 'min': 0, 'advanced': True}), 'rfg_ref_open': ('INT', {'default': 5, 'min': 0, 'advanced': True}), 'rfg_ref_extend': ('INT', {'default': 3, 'min': 0, 'advanced': True}), 'reporting_options_selector': ('STRING', {'default': 'no', 'options': cls.REPORTING_OPTIONS, 'advanced': True}), 'k': ('INT', {'default': 1, 'min': 1, 'advanced': True}), 'effort_options_selector': ('STRING', {'default': 'no', 'options': ['no', 'yes'], 'advanced': True}), 'D': ('INT', {'default': 15, 'min': 0, 'advanced': True}), 'R': ('INT', {'default': 2, 'min': 0, 'advanced': True}), 'd': ('BOOLEAN', {'default': False, 'advanced': True}), 'other_options_selector': ('STRING', {'default': 'no', 'options': ['no', 'yes'], 'advanced': True}), 'seed': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'non_deterministic': ('BOOLEAN', {'default': False, 'advanced': True}), 'rg_selector': ('STRING', {'default': 'do_not_set', 'options': ['do_not_set', 'set'], 'description': 'Set read group information'}), 'rg_id': ('STRING', {'default': '', 'description': 'Read group ID'}), 'rg_sm': ('STRING', {'default': '', 'description': 'Read group sample'}), 'rg_pl': ('STRING', {'default': '', 'description': 'Read group platform'}), 'rg_lb': ('STRING', {'default': '', 'description': 'Read group library'}), 'rg_cn': ('STRING', {'default': '', 'description': 'Read group sequencing center'}), 'rg_ds': ('STRING', {'default': '', 'advanced': True}), 'rg_dt': ('STRING', {'default': '', 'advanced': True}), 'rg_fo': ('STRING', {'default': '', 'advanced': True}), 'rg_ks': ('STRING', {'default': '', 'advanced': True}), 'rg_pg': ('STRING', {'default': '', 'advanced': True}), 'rg_pi': ('STRING', {'default': '', 'advanced': True}), 'rg_pu': ('STRING', {'default': '', 'advanced': True}), 'sam_options_selector': ('STRING', {'default': 'no', 'options': ['no', 'yes'], 'description': 'Enable SAM/BAM output options'}), 'sam_output_format': ('STRING', {'default': 'bam', 'options': cls.SAM_OUTPUT_FORMAT_OPTIONS, 'description': 'Alignment output format'}), 'no_unal': ('BOOLEAN', {'default': False, 'advanced': True}), 'omit_sec_seq': ('BOOLEAN', {'default': False, 'advanced': True}), 'sam_no_qname_trunc': ('BOOLEAN', {'default': False, 'advanced': True}), 'xeq': ('BOOLEAN', {'default': False, 'advanced': True}), 'soft_clipped_unmapped_tlen': ('BOOLEAN', {'default': False, 'advanced': True}), 'reorder': ('BOOLEAN', {'default': False, 'advanced': True}), 'save_mapping_stats': ('BOOLEAN', {'default': False, 'description': 'Save Bowtie2 mapping statistics from stderr'})}, 'hidden': {'output': ('STRING', {})}}
