"""metaphlan — metagenomics node(s). One tool per file (extracted from metagenomics.py)."""
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


class MetaPhlAnNode(CommandNode):
    """Taxonomic profiling with MetaPhlAn."""
    NODE_ID = 'metaphlan'
    DISPLAY_NAME = 'MetaPhlAn'
    REQUIRED_CONDA_PACKAGES = ['metaphlan']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Profile microbial community composition with MetaPhlAn 4 marker genes.'
    SEARCH_ALIASES = ['BioNodulo builtin', 'MetaPhlAn', 'metagenomic profiling', 'relative abundance', 'marker abundance', 'VSC breadth', 'Krona', 'BIOM']
    RETURN_TYPES = ('METAPHLAN_PROFILE', 'TSV', 'SAM', 'BIOM', 'DIRECTORY', 'TSV', 'TSV', 'FASTQ', 'DIRECTORY')
    RETURN_NAMES = ('profile', 'mapout', 'sam_output', 'biom_output', 'split_levels', 'krona_output', 'vsc_breadth_coverage', 'subsampled_reads', 'subsampled_paired_reads')
    REQUIRED_EXECUTABLES = ['metaphlan']
    DOCUMENTATION_URL = 'https://github.com/biobakery/MetaPhlAn'
    CITATION_DOIS = [METAPHLAN_DOI]
    CITATION_URLS = [f'{DOI_URL}{METAPHLAN_DOI}']
    CITATION_TEXT = METAPHLAN_CITATION_TEXT
    VERSION = '4.2.4'
    SHELL = True

    @classmethod
    def _out(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('output', '.'))

    @classmethod
    def _input_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_selector', inputs.get('input_type', 'raw')))

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        input_ext = str(inputs.get('input_ext', inputs.get('input_type', 'fastq'))).lower()
        if input_ext.endswith('.gz'):
            input_ext = input_ext.removesuffix('.gz')
        elif input_ext.endswith('.bz2'):
            input_ext = input_ext.removesuffix('.bz2')
        return 'fasta' if input_ext.startswith('fasta') else 'fastq' if input_ext.startswith('fastq') else input_ext

    @classmethod
    def _raw_selector(cls, inputs: dict[str, Any], reads: list[str]) -> str:
        if inputs.get('raw_selector'):
            return str(inputs['raw_selector'])
        if inputs.get('paired', False):
            return 'paired'
        if len(reads) > 1:
            return 'multiple'
        return 'single'

    @classmethod
    def _profile_path(cls, out: str) -> str:
        return f'{out}/profile.metaphlan.tsv'

    @classmethod
    def _mapout_path(cls, out: str) -> str:
        return f'{out}/mapout.tsv'

    @classmethod
    def _sam_path(cls, out: str) -> str:
        return f'{out}/sam_output.sam'

    @classmethod
    def _biom_path(cls, out: str) -> str:
        return f'{out}/biom_output.biom'

    @classmethod
    def _split_levels_path(cls, out: str) -> str:
        return f'{out}/split_levels'

    @classmethod
    def _krona_path(cls, out: str) -> str:
        return f'{out}/krona_output.tsv'

    @classmethod
    def _vsc_path(cls, out: str) -> str:
        return f'{out}/vsc_breadth_coverage.tsv'

    @classmethod
    def _subsampled_reads_path(cls, out: str) -> str:
        return f'{out}/subsampled.fastq'

    @classmethod
    def _subsampled_paired_path(cls, out: str) -> str:
        return f'{out}/subsampled_paired_reads'

    @classmethod
    def _formatoutput_script(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('formatoutput_script', 'formatoutput.py'))

    @classmethod
    def _customizemetadata_script(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('customizemetadata_script', 'customizemetadata.py'))

    @classmethod
    def _prepare_raw_input(cls, inputs: dict[str, Any], reads: list[str]) -> tuple[list[str], list[str], str, str]:
        raw_selector = cls._raw_selector(inputs, reads)
        input_ext = str(inputs.get('input_ext', inputs.get('input_type', 'fastq'))).lower()
        commands: list[str] = []
        file_arg = ''
        if raw_selector == 'single':
            read = reads[0] if reads else ''
            if input_ext.endswith('gz'):
                commands.append(_shell_join(['zcat', read, '>', 'in']))
                file_arg = 'in'
            elif input_ext.endswith('bz2'):
                commands.append(_shell_join(['bzcat', read, '>', 'in']))
                file_arg = 'in'
            else:
                file_arg = read
        elif raw_selector == 'multiple':
            prepared: list[str] = []
            for index, read in enumerate(reads):
                name = f'input_{index}'
                if input_ext.endswith('gz'):
                    commands.append(_shell_join(['zcat', read, '>', name]))
                    prepared.append(name)
                elif input_ext.endswith('bz2'):
                    commands.append(_shell_join(['bzcat', read, '>', name]))
                    prepared.append(name)
                else:
                    prepared.append(read)
            file_arg = ','.join(prepared)
        elif raw_selector in {'paired', 'paired_collection'}:
            forward = reads[0] if reads else ''
            reverse = reads[1] if len(reads) > 1 else ''
            if input_ext.endswith('gz'):
                commands.append(_shell_join(['zcat', forward, '>', 'in_f']))
                commands.append(_shell_join(['zcat', reverse, '>', 'in_r']))
            elif input_ext.endswith('bz2'):
                commands.append(_shell_join(['bzcat', forward, '>', 'in_f']))
                commands.append(_shell_join(['bzcat', reverse, '>', 'in_r']))
            else:
                commands.append(_shell_join(['ln', '-s', forward, 'in_f']))
                commands.append(_shell_join(['ln', '-s', reverse, 'in_r']))
            file_arg = '-1 in_f -2 in_r' if str(inputs.get('subsample_mode', 'no')) == 'paired' else 'in_f,in_r'
        return (commands, file_arg.split(), cls._input_ext(inputs), raw_selector)

    @classmethod
    def _database_setup(cls, inputs: dict[str, Any]) -> tuple[list[str], list[str]]:
        if str(inputs.get('db_selector', 'cached')) != 'history':
            return ([], ['--db_dir', str(inputs.get('bt2_db', '')), '--index', str(inputs.get('index', 'mpa_vJun23_CHOCOPhlAnSGB_202403'))])
        setup = [_shell_join(['mkdir', 'ref_db']), shlex.join(['bowtie2-build', '--large-index', str(inputs.get('custom_marker_sequences', '')), 'ref_db/custom_db']), shlex.join(['python', cls._customizemetadata_script(inputs), 'transform_json_to_pkl', '--json', str(inputs.get('custom_marker_metadata', '')), '--pkl', 'ref_db/custom_db.pkl'])]
        return (setup, ['--db_dir', 'ref_db/', '--index', 'custom_db'])

    @classmethod
    def _analysis_args(cls, inputs: dict[str, Any]) -> list[str]:
        analysis_type = str(inputs.get('analysis_type', 'rel_ab'))
        args = ['-t', analysis_type]
        if analysis_type in {'rel_ab', 'rel_ab_w_read_stats'}:
            args.extend(['--tax_lev', str(inputs.get('tax_lev', 'a'))])
        elif analysis_type == 'marker_ab_table' and inputs.get('nreads') not in {None, ''}:
            args.extend(['--nreads', str(inputs.get('nreads'))])
        elif analysis_type == 'marker_pres_table' and inputs.get('pres_th') not in {None, ''}:
            args.extend(['--pres_th', str(inputs.get('pres_th'))])
        if inputs.get('min_alignment_len') not in {None, ''}:
            args.extend(['--min_alignment_len', str(inputs.get('min_alignment_len'))])
        for option in _as_list(inputs.get('organism_profiling')):
            args.append(f'--{option}')
        args.extend(['--stat', str(inputs.get('stat', 'tavg_g')), '--stat_q', str(inputs.get('stat_q', 0.2)), '--perc_nonzero', str(inputs.get('perc_nonzero', 0.33))])
        if inputs.get('ignore_markers'):
            args.extend(['--ignore_markers', str(inputs.get('ignore_markers'))])
        if bool(inputs.get('avoid_disqm', True)):
            args.append('--avoid_disqm')
        return args

    @classmethod
    def _output_args(cls, inputs: dict[str, Any], out: str) -> list[str]:
        output_file = cls._biom_path(out) if inputs.get('biom_format_output', False) else cls._profile_path(out)
        args = ['--sample_id_key', str(inputs.get('sample_id_key', 'SampleID')), '--sample_id', str(inputs.get('sample_id', 'Metaphlan_Analysis'))]
        if inputs.get('use_group_representative', False):
            args.append('--use_group_representative')
        if inputs.get('CAMI_format_output', False):
            args.append('--CAMI_format_output')
        if inputs.get('skip_unclassified_estimation', False):
            args.append('--skip_unclassified_estimation')
        args.extend(['-o', output_file, '--mapout', 'mapout', '-s', cls._sam_path(out), '--nproc', str(inputs.get('threads', 8))])
        return args

    @classmethod
    def _subsampling_args(cls, inputs: dict[str, Any]) -> list[str]:
        mode = str(inputs.get('subsample_mode', 'no'))
        args: list[str] = []
        if mode == 'single':
            args.extend(['--subsampling', str(inputs.get('subsampling', ''))])
        elif mode == 'paired':
            args.extend(['--subsampling_paired', str(inputs.get('subsampling_paired', ''))])
        if mode != 'no':
            if inputs.get('mapping_subsampling', False):
                args.append('--mapping_subsampling')
            if inputs.get('subsampling_seed') not in {None, ''}:
                args.extend(['--subsampling_seed', str(inputs.get('subsampling_seed'))])
            args.extend(['--subsampling_output', 'subsampled.out'])
        return args

    @classmethod
    def _postprocessing_commands(cls, inputs: dict[str, Any], out: str, raw_input: bool) -> list[str]:
        commands: list[str] = []
        if raw_input:
            commands.append(_shell_join(['mv', 'mapout', cls._mapout_path(out)]))
        if str(inputs.get('analysis_type', 'rel_ab')) in {'rel_ab', 'rel_ab_w_read_stats'} and str(inputs.get('tax_lev', 'a')) == 'a' and inputs.get('split_levels', False):
            commands.extend([_shell_join(['mkdir', 'split_levels']), shlex.join(['python', cls._formatoutput_script(inputs), 'split_levels', '--metaphlan_output', cls._profile_path(out), '--outdir', 'split_levels']), _shell_join(['mv', 'split_levels', cls._split_levels_path(out)])])
        if inputs.get('krona_output', False):
            commands.append(shlex.join(['python', cls._formatoutput_script(inputs), 'format_for_krona', '--metaphlan_output', cls._profile_path(out), '--krona_output', cls._krona_path(out)]))
        return commands

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        reads = _as_list(inputs.get('reads'))
        selector = cls._input_selector(inputs)
        raw_selector = cls._raw_selector(inputs, reads)
        if not reads:
            return "Required input 'reads' is missing"
        if selector == 'raw' and raw_selector in {'paired', 'paired_collection'} and (len(reads) < 2):
            return 'Paired MetaPhlAn input requires two read files'
        if str(inputs.get('db_selector', 'cached')) == 'history':
            if not inputs.get('custom_marker_sequences'):
                return 'custom_marker_sequences is required when db_selector is history'
            if not inputs.get('custom_marker_metadata'):
                return 'custom_marker_metadata is required when db_selector is history'
        elif not inputs.get('bt2_db'):
            return 'bt2_db is required when db_selector is cached'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = cls._out(inputs)
        reads = _as_list(inputs.get('reads'))
        selector = cls._input_selector(inputs)
        setup_commands: list[str] = []
        file_tokens: list[str]
        input_type: str
        if selector == 'raw':
            raw_setup, file_tokens, input_type, _raw_selector = cls._prepare_raw_input(inputs, reads)
            setup_commands.extend(raw_setup)
        else:
            read = reads[0] if reads else ''
            input_type = selector
            file_tokens = [read]
        db_setup, db_args = cls._database_setup(inputs)
        setup_commands.extend(db_setup)
        cmd = ['metaphlan', *file_tokens, '--input_type', input_type]
        if selector == 'raw':
            cmd.extend(['--read_min_len', str(inputs.get('read_min_len', 70)), '--bt2_ps', str(inputs.get('bt2_ps', 'very-sensitive')), '--min_mapq_val', str(inputs.get('min_mapq_val', 5))])
        elif selector == 'sam':
            cmd.extend(['--nreads', f"$(cat {shlex.quote(file_tokens[0])} | grep -c -v '^@')"])
        cmd.extend(db_args)
        if inputs.get('profile_vsc', False):
            cmd.extend(['--profile_vsc', '--vsc_out', cls._vsc_path(out), '--vsc_breadth', str(inputs.get('vsc_breadth', 0.75))])
        cmd.extend(cls._analysis_args(inputs))
        cmd.extend(cls._output_args(inputs, out))
        cmd.extend(cls._subsampling_args(inputs))
        if inputs.get('offline', False):
            cmd.append('--offline')
        commands = [*setup_commands, _shell_join_allow_substitution(cmd)]
        commands.extend(cls._postprocessing_commands(inputs, out, selector == 'raw'))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'profile.metaphlan.tsv']
        if cls._input_selector(inputs) == 'raw':
            outputs.extend([out / 'mapout.tsv', out / 'sam_output.sam'])
        if inputs.get('biom_format_output', False):
            outputs.append(out / 'biom_output.biom')
        if str(inputs.get('analysis_type', 'rel_ab')) in {'rel_ab', 'rel_ab_w_read_stats'} and str(inputs.get('tax_lev', 'a')) == 'a' and inputs.get('split_levels', False):
            outputs.append(out / 'split_levels')
        if inputs.get('krona_output', False):
            outputs.append(out / 'krona_output.tsv')
        if inputs.get('profile_vsc', False):
            outputs.append(out / 'vsc_breadth_coverage.tsv')
        if str(inputs.get('subsample_mode', 'no')) == 'single':
            outputs.append(out / 'subsampled.fastq')
        if str(inputs.get('subsample_mode', 'no')) == 'paired':
            outputs.append(out / 'subsampled_paired_reads')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ_LIST', {'description': 'Metagenomic reads (single or paired-end)'}), 'bt2_db': ('DIRECTORY', {'description': 'MetaPhlAn Bowtie2 database directory'}), 'index': ('STRING', {'default': 'mpa_vJun23_CHOCOPhlAnSGB_202403'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'input_selector': ('STRING', {'default': 'raw', 'options': ['raw', 'sam', 'mapout'], 'description': 'Raw reads, SAM, or MetaPhlAn mapout input'}), 'raw_selector': ('STRING', {'default': 'single', 'options': ['single', 'multiple', 'paired', 'paired_collection'], 'description': 'Raw input layout'}), 'input_type': ('STRING', {'default': 'fastq', 'options': ['fastq', 'fasta', 'sam', 'mapout'], 'advanced': True}), 'input_ext': ('STRING', {'default': 'fastq', 'description': 'Original raw input extension, including .gz or .bz2 when compressed'}), 'paired': ('BOOLEAN', {'default': False, 'label': 'Paired-end reads', 'advanced': True}), 'db_selector': ('STRING', {'default': 'cached', 'options': ['cached', 'history'], 'description': 'Use cached database or custom history files'}), 'custom_marker_sequences': ('FASTA', {'default': '', 'description': 'Custom marker FASTA for history database mode'}), 'custom_marker_metadata': ('JSON', {'default': '', 'description': 'Custom marker metadata JSON for history database mode'}), 'customizemetadata_script': ('FILE', {'default': 'customizemetadata.py', 'advanced': True}), 'formatoutput_script': ('FILE', {'default': 'formatoutput.py', 'advanced': True}), 'read_min_len': ('INT', {'default': 70, 'min': 1, 'description': 'Minimum read length for raw input'}), 'bt2_ps': ('STRING', {'default': 'very-sensitive', 'options': ['sensitive', 'very-sensitive', 'sensitive-local', 'very-sensitive-local'], 'description': 'BowTie2 preset for raw FASTA input'}), 'min_mapq_val': ('INT', {'default': 5, 'min': 0, 'description': 'Minimum MAPQ value'}), 'profile_vsc': ('BOOLEAN', {'default': False, 'description': 'Profile viruses with VSCs'}), 'vsc_breadth': ('FLOAT', {'default': 0.75, 'min': 0, 'max': 1, 'description': 'Minimum VSC breadth of coverage'}), 'analysis_type': ('STRING', {'default': 'rel_ab', 'options': ['rel_ab', 'rel_ab_w_read_stats', 'clade_profiles', 'marker_ab_table', 'marker_pres_table'], 'label': 'Analysis Type'}), 'tax_lev': ('STRING', {'default': 'a', 'options': ['a', 'k', 'p', 'c', 'o', 'f', 'g', 's'], 'label': 'Taxonomic Level'}), 'split_levels': ('BOOLEAN', {'default': False, 'description': 'Generate one report per taxonomic level'}), 'nreads': ('INT', {'default': '', 'description': 'Original read count for marker abundance normalization'}), 'pres_th': ('INT', {'default': '', 'description': 'Presence threshold for marker_pres_table'}), 'min_alignment_len': ('INT', {'default': '', 'description': 'Discard alignments below this length'}), 'organism_profiling': ('STRING', {'default': [], 'multiple': True, 'options': ['ignore_eukaryotes', 'ignore_bacteria', 'ignore_archaea', 'ignore_ksgbs', 'ignore_usgbs'], 'description': 'Organism groups to ignore'}), 'stat': ('STRING', {'default': 'tavg_g', 'options': ['avg_g', 'avg_l', 'tavg_g', 'tavg_l', 'wavg_g', 'wavg_l', 'med'], 'description': 'Marker aggregation statistic'}), 'stat_q': ('FLOAT', {'default': 0.2, 'description': 'Quantile for robust statistics'}), 'perc_nonzero': ('FLOAT', {'default': 0.33, 'description': 'Minimum nonzero marker fraction'}), 'ignore_markers': ('TEXT', {'default': '', 'description': 'File containing markers to ignore'}), 'avoid_disqm': ('BOOLEAN', {'default': True, 'description': 'Deactivate disambiguation of quasi-markers'}), 'subsample_mode': ('STRING', {'default': 'no', 'options': ['no', 'single', 'paired'], 'description': 'Optional subsampling mode'}), 'subsampling': ('INT', {'default': '', 'min': 1, 'description': 'Number of reads for single-end subsampling'}), 'subsampling_paired': ('INT', {'default': '', 'min': 1, 'description': 'Number of paired reads for paired subsampling'}), 'mapping_subsampling': ('BOOLEAN', {'default': False, 'description': 'Subsample mapping results instead of reads'}), 'subsampling_seed': ('INT', {'default': '', 'min': 0, 'description': 'Subsampling seed'}), 'sample_id_key': ('STRING', {'default': 'SampleID', 'description': 'Sample ID metadata key'}), 'sample_id': ('STRING', {'default': 'Metaphlan_Analysis', 'description': 'Sample ID value'}), 'use_group_representative': ('BOOLEAN', {'default': False, 'description': 'Use species as representative for species groups'}), 'CAMI_format_output': ('BOOLEAN', {'default': False, 'description': 'Report using CAMI format'}), 'skip_unclassified_estimation': ('BOOLEAN', {'default': False, 'description': 'Do not estimate unclassified taxa'}), 'biom_format_output': ('BOOLEAN', {'default': False, 'description': 'Write BIOM output'}), 'krona_output': ('BOOLEAN', {'default': False, 'description': 'Write Krona-compatible output'}), 'offline': ('BOOLEAN', {'default': True, 'description': 'Run without downloading reference data'})}, 'hidden': {'output': ('STRING', {})}}
