"""gffread — annotation node(s). One tool per file (extracted from wrapped_beacon_ucsc.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *
class _Beacon2MultiInputBaseNode(CommandNode):
    """Shared command rendering for Beacon2 converters that symlink multi-input collections."""
    REQUIRED_CONDA_PACKAGES = ['beacon2-ri-tools', 'gzip']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/beacon2'
    CITATION_DOIS = [BEACON2_DOI]
    CITATION_URLS = [f'{DOI_URL}{BEACON2_DOI}']
    CITATION_TEXT = BEACON2_CITATION_TEXT
    VERSION = '2.0.0+galaxy0'
    SHELL = True
    INPUT_NAME = ''

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get(cls.INPUT_NAME))

    @classmethod
    def _staged_paths(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        labels = _as_list(inputs.get('element_identifiers'))
        staged: list[str] = []
        for index, input_file in enumerate(cls._input_files(inputs)):
            label = labels[index] if index < len(labels) and labels[index] else input_file
            staged.append(f'{out}/{_safe_element_identifier(label)}')
        return staged

    @classmethod
    def _symlink_commands(cls, inputs: dict[str, Any]) -> list[str]:
        return [_shell_join(['ln', '-s', input_file, staged_path]) for input_file, staged_path in zip(cls._input_files(inputs), cls._staged_paths(inputs), strict=False)]
class _UcscSingleFileUtilityNode(CommandNode):
    """Shared behavior for single-input UCSC Genome Browser utilities."""
    CATEGORY = 'genomics'
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('out',)
    DOCUMENTATION_URL = ''
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    TOOL_NAME = ''
    INPUT_NAME = ''
    OUTPUT_FILENAME = ''
    INPUT_DESCRIPTION = ''

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls.OUTPUT_FILENAME}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join([cls.TOOL_NAME, str(inputs.get(cls.INPUT_NAME, '')), cls._output_path(inputs)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get(cls.INPUT_NAME, '')).strip():
            return f'{cls.INPUT_NAME} is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {cls.INPUT_NAME: ('FILE', {'description': cls.INPUT_DESCRIPTION})}, 'hidden': {'output': ('STRING', {})}}


class GffReadNode(CommandNode):
    """Filter, convert, and extract sequence from GFF/GTF/BED annotations."""
    NODE_ID = 'gffread'
    DISPLAY_NAME = 'gffread'
    REQUIRED_CONDA_PACKAGES = ['gffread']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Filter, convert, cluster, and extract sequences from GFF3, GTF, or BED annotations.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'gffread', 'GffRead', 'GFF Utilities', 'GTF to GFF3', 'GFF3 to GTF', 'GFF to BED', 'annotation conversion', 'extract transcript FASTA', 'transcript clustering']
    RETURN_TYPES = ('GFF3', 'GTF', 'BED', 'FASTA', 'FASTA', 'FASTA', 'TXT')
    RETURN_NAMES = ('output_gff', 'output_gtf', 'output_bed', 'output_exons', 'output_cds', 'output_pep', 'output_dupinfo')
    REQUIRED_EXECUTABLES = ['gffread']
    DOCUMENTATION_URL = 'https://github.com/gpertea/gffread'
    CITATION_DOIS = [GFFREAD_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{GFFREAD_CITATION_DOI}']
    CITATION_TEXT = GFFREAD_CITATION_TEXT
    VERSION = '0.12.7'
    SHELL = True
    GFF_FORMATS = ['none', 'gff', 'gtf', 'bed']
    FILTERING_OPTIONS = ['-U', '-C', '-G', '-O', '--no-pseudo']
    REFERENCE_SOURCES = ['none', 'cached', 'history']
    REF_FILTERING_OPTIONS = ['-N', '-J', '-V', '-H']
    FA_OUTPUTS = ['exons', 'cds', 'pep', 'project_coords', 'stop_star']
    MERGE_SELS = ['none', 'merge', 'cluster']
    MERGE_OPTIONS = ['force_exons', 'merge_close_exons', 'collapse_contained', 'relaxed_containment', 'dupinfo']
    DUPINFO_TOKEN = '__GFFREAD_DUPINFO__'
    MERGE_OPTION_FLAGS = {'force_exons': '--force-exons', 'merge_close_exons': '-Z', 'collapse_contained': '-K', 'relaxed_containment': '-Q'}
    RANGE_PATTERN = re.compile('^([+-]?[\\w.-]+:)?\\d+\\.\\.\\d+$')

    @classmethod
    def _gff_fmt(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('gff_fmt', 'none') or 'none')

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        fmt = cls._gff_fmt(inputs)
        return 'gff' if fmt == 'none' else fmt

    @classmethod
    def _output_filename(cls, inputs: dict[str, Any]) -> str:
        return f'output.{cls._output_format(inputs)}'

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._output_filename(inputs)}'

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('reference_genome_source', 'none') or 'none')

    @classmethod
    def _dupinfo_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/dupinfo.txt'

    @classmethod
    def _quoted_dupinfo_option(cls, inputs: dict[str, Any]) -> str:
        return "'" + f'-d={cls._dupinfo_path(inputs)}'.replace("'", '\'"\'"\'') + "'"

    @classmethod
    def _selected_fa_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('fa_outputs'))

    @classmethod
    def _selected_merge_options(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('merge_options'))

    @classmethod
    def _add_reference(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        source = cls._reference_source(inputs)
        if source == 'history':
            cmd.extend(['-g', 'genomeref.fa'])
        elif source == 'cached':
            cmd.extend(['-g', str(inputs.get('fasta_index_path', inputs.get('fasta_index', '')))])
        if source != 'none':
            cmd.extend(_as_list(inputs.get('ref_filtering')))

    @classmethod
    def _add_merge_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        merge_sel = str(inputs.get('merge_sel', 'none') or 'none')
        if merge_sel == 'merge':
            cmd.append('--merge')
        elif merge_sel == 'cluster':
            cmd.append('--cluster-only')
        if merge_sel == 'none':
            return
        for option in cls._selected_merge_options(inputs):
            if option == 'dupinfo':
                cmd.append(cls.DUPINFO_TOKEN)
            else:
                cmd.append(cls.MERGE_OPTION_FLAGS[option])

    @classmethod
    def _add_fasta_outputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        out = _out(inputs)
        for value in cls._selected_fa_outputs(inputs):
            if value == 'exons':
                cmd.extend(['-w', f'{out}/exons.fa'])
            elif value == 'cds':
                cmd.extend(['-x', f'{out}/cds.fa'])
            elif value == 'pep':
                cmd.extend(['-y', f'{out}/pep.fa'])
            elif value == 'project_coords':
                cmd.append('-W')
            elif value == 'stop_star':
                cmd.append('-S')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['gffread', str(inputs.get('input', ''))]
        if str(inputs.get('input_format', '')).lower() == 'bed' or str(inputs.get('input', '')).lower().endswith('.bed'):
            cmd.append('--in-bed')
        cls._add_reference(cmd, inputs)
        cmd.extend(_as_list(inputs.get('filtering')))
        if str(inputs.get('maxintron', '')) not in {'', '0'}:
            cmd.extend(['-i', str(inputs.get('maxintron'))])
        if str(inputs.get('region_filter', 'none') or 'none') == 'filter':
            cmd.extend(['-r', str(inputs.get('range', ''))])
            if inputs.get('discard_partial'):
                cmd.append('-R')
        cls._add_merge_options(cmd, inputs)
        if inputs.get('chr_replace'):
            cmd.append(f"-m={inputs.get('chr_replace')}")
        if inputs.get('full_gff_attribute_preservation'):
            cmd.append('-F')
        if inputs.get('decode_url'):
            cmd.append('-D')
        if inputs.get('expose'):
            cmd.append('-E')
        cls._add_fasta_outputs(cmd, inputs)
        gff_fmt = cls._gff_fmt(inputs)
        if gff_fmt != 'none':
            if gff_fmt != 'bed' and inputs.get('tname'):
                cmd.extend(['-t', str(inputs.get('tname'))])
            if gff_fmt == 'gtf':
                cmd.append('-T')
            elif gff_fmt == 'bed':
                cmd.append('--bed')
            cmd.extend(['-o', cls._output_path(inputs)])
        elif not cls._selected_fa_outputs(inputs):
            cmd.extend(['-o', cls._output_path(inputs)])
        command = _shell_join(cmd).replace(cls.DUPINFO_TOKEN, cls._quoted_dupinfo_option(inputs))
        if cls._reference_source(inputs) == 'history':
            setup = _shell_join(['ln', '-s', str(inputs.get('genome_fasta', '')), 'genomeref.fa'])
            return f'{setup} && {command}'
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = [out / cls._output_filename(inputs)]
        fa_outputs = cls._selected_fa_outputs(inputs)
        if 'exons' in fa_outputs:
            outputs.append(out / 'exons.fa')
        if 'cds' in fa_outputs:
            outputs.append(out / 'cds.fa')
        if 'pep' in fa_outputs:
            outputs.append(out / 'pep.fa')
        if str(inputs.get('merge_sel', 'none') or 'none') != 'none' and 'dupinfo' in cls._selected_merge_options(inputs):
            outputs.append(out / 'dupinfo.txt')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        gff_fmt = cls._gff_fmt(inputs)
        if gff_fmt not in cls.GFF_FORMATS:
            return f"gff_fmt must be one of: {', '.join(cls.GFF_FORMATS)}"
        filtering = _as_list(inputs.get('filtering'))
        if any((value not in cls.FILTERING_OPTIONS for value in filtering)):
            return f"filtering values must be one of: {', '.join(cls.FILTERING_OPTIONS)}"
        ref_filtering = _as_list(inputs.get('ref_filtering'))
        if any((value not in cls.REF_FILTERING_OPTIONS for value in ref_filtering)):
            return f"ref_filtering values must be one of: {', '.join(cls.REF_FILTERING_OPTIONS)}"
        source = cls._reference_source(inputs)
        if source not in cls.REFERENCE_SOURCES:
            return f"reference_genome_source must be one of: {', '.join(cls.REFERENCE_SOURCES)}"
        if source == 'history' and (not str(inputs.get('genome_fasta', '')).strip()):
            return 'genome_fasta is required when reference_genome_source is history'
        if source == 'cached' and (not str(inputs.get('fasta_index_path', inputs.get('fasta_index', ''))).strip()):
            return 'fasta_index_path is required when reference_genome_source is cached'
        fa_outputs = cls._selected_fa_outputs(inputs)
        if any((value not in cls.FA_OUTPUTS for value in fa_outputs)):
            return f"fa_outputs values must be one of: {', '.join(cls.FA_OUTPUTS)}"
        if fa_outputs and source == 'none':
            return 'reference_genome_source cannot be none when FASTA outputs are requested'
        if ref_filtering and source == 'none':
            return 'reference_genome_source cannot be none when reference filters are requested'
        if str(inputs.get('region_filter', 'none') or 'none') == 'filter':
            region = str(inputs.get('range', '') or '')
            if not region:
                return 'range is required when region_filter is filter'
            if not cls.RANGE_PATTERN.match(region):
                return 'range must use gffread coordinate syntax like chr1:100..200'
        maxintron = inputs.get('maxintron', '')
        if str(maxintron) != '':
            try:
                maxintron_value = int(maxintron)
            except (TypeError, ValueError):
                return 'maxintron must be an integer'
            if maxintron_value < 0:
                return 'maxintron must be greater than or equal to 0'
        merge_sel = str(inputs.get('merge_sel', 'none') or 'none')
        if merge_sel not in cls.MERGE_SELS:
            return f"merge_sel must be one of: {', '.join(cls.MERGE_SELS)}"
        merge_options = cls._selected_merge_options(inputs)
        if any((value not in cls.MERGE_OPTIONS for value in merge_options)):
            return f"merge_options values must be one of: {', '.join(cls.MERGE_OPTIONS)}"
        if merge_sel == 'none' and merge_options:
            return 'merge_options can only be used when merge_sel is merge or cluster'
        if merge_sel == 'cluster':
            unsupported = [value for value in merge_options if value in {'collapse_contained', 'relaxed_containment', 'dupinfo'}]
            if unsupported:
                return 'cluster merge_options only supports force_exons and merge_close_exons'
        tname = str(inputs.get('tname', '') or '')
        if tname and (not re.fullmatch('\\w+', tname)):
            return 'tname must contain only letters, digits, and underscores'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('GFF_GTF', {'description': 'Input BED, GFF3, or GTF feature annotation file'})}, 'optional': {'gff_fmt': ('STRING', {'default': 'none', 'options': cls.GFF_FORMATS, 'description': 'Annotation output format'}), 'input_format': ('STRING', {'default': 'auto', 'options': ['auto', 'bed', 'gff', 'gtf'], 'description': 'Input format override'}), 'filtering': ('STRING', {'default': [], 'options': cls.FILTERING_OPTIONS, 'multiple': True, 'description': 'Transcript and feature filters'}), 'region_filter': ('STRING', {'default': 'none', 'options': ['none', 'filter'], 'description': 'Restrict output to a coordinate range'}), 'range': ('STRING', {'default': '', 'description': 'Coordinate range using gffread syntax such as chr1:100..200'}), 'discard_partial': ('BOOLEAN', {'default': False, 'description': 'Discard transcripts not fully contained in the coordinate range'}), 'maxintron': ('INT', {'default': '', 'min': 0, 'description': 'Discard transcripts with introns larger than this length'}), 'chr_replace': ('TSV', {'description': 'Two-column reference sequence replacement table'}), 'reference_genome_source': ('STRING', {'default': 'none', 'options': cls.REFERENCE_SOURCES, 'description': 'Reference genome source for FASTA outputs or reference-based filters'}), 'genome_fasta': ('FASTA', {'description': 'Reference FASTA selected from history'}), 'fasta_index_path': ('FASTA', {'description': 'Cached reference FASTA path'}), 'ref_filtering': ('STRING', {'default': [], 'options': cls.REF_FILTERING_OPTIONS, 'multiple': True, 'description': 'Reference-based CDS and splice-site filters'}), 'fa_outputs': ('STRING', {'default': [], 'options': cls.FA_OUTPUTS, 'multiple': True, 'description': 'FASTA sequence outputs and FASTA formatting flags'}), 'merge_sel': ('STRING', {'default': 'none', 'options': cls.MERGE_SELS, 'description': 'Transcript merge or cluster mode'}), 'merge_options': ('STRING', {'default': [], 'options': cls.MERGE_OPTIONS, 'multiple': True, 'description': 'Merge and cluster handling options'}), 'full_gff_attribute_preservation': ('BOOLEAN', {'default': False, 'description': 'Preserve all GFF attributes when possible'}), 'decode_url': ('BOOLEAN', {'default': False, 'description': 'Decode URL-encoded characters'}), 'expose': ('BOOLEAN', {'default': False, 'description': 'Expose warning diagnostics from gffread'}), 'tname': ('STRING', {'default': '', 'description': 'Track name to use in the second column of GFF output'})}, 'hidden': {'output': ('STRING', {})}}
