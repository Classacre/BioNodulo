"""gffcompare — annotation node(s). One tool per file (extracted from wrapped_beacon_ucsc.py)."""
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


class GffCompareNode(CommandNode):
    """Compare and track GFF/GTF transcript annotations."""
    NODE_ID = 'gffcompare'
    DISPLAY_NAME = 'GffCompare'
    REQUIRED_CONDA_PACKAGES = ['gffcompare', 'samtools']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Compare, classify, merge, and track GFF/GTF transcript annotations.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'gffcompare', 'GffCompare', 'GFF Utilities', 'CuffCompare', 'transcript tracking', 'transcript classification', 'GTF comparison', 'GFF comparison', 'annotation mode', 'RefMap', 'TMAP']
    RETURN_TYPES = ('GTF', 'GTF', 'TXT', 'TSV', 'TSV', 'TSV', 'TSV')
    RETURN_NAMES = ('transcripts_annotated', 'transcripts_combined', 'transcripts_stats', 'transcripts_loci', 'transcripts_tracking', 'tmap_output', 'refmap_output')
    REQUIRED_EXECUTABLES = ['gffcompare', 'samtools']
    DOCUMENTATION_URL = 'https://github.com/gpertea/gffcompare'
    CITATION_DOIS = [GFFREAD_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{GFFREAD_CITATION_DOI}']
    CITATION_TEXT = GFFREAD_CITATION_TEXT
    VERSION = '0.12.10'
    SHELL = True
    YES_NO_OPTIONS = ['no', 'yes']
    SOURCES = ['history', 'cached']
    DISCARD_SINGLE_EXON_OPTIONS = ['', '-M', '-N']
    DUPLICATION_OPTIONS = ['', '-D']

    @classmethod
    def _gffinputs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('gffinputs'))

    @classmethod
    def _staged_input_names(cls, inputs: dict[str, Any]) -> list[str]:
        labels = _as_list(inputs.get('element_identifiers'))
        names: list[str] = []
        seen: dict[str, int] = {}
        for index, input_path in enumerate(cls._gffinputs(inputs)):
            label = labels[index] if index < len(labels) and labels[index] else input_path
            name = _safe_element_identifier(label).replace('.', '_')
            if not name:
                name = f'input_{index + 1}'
            count = seen.get(name, 0)
            seen[name] = count + 1
            if count:
                name = f'{name}_{count}'
            names.append(name)
        return names

    @classmethod
    def _annotation_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('annotation_selector', 'no') or 'no')

    @classmethod
    def _ref_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('ref_source', 'history') or 'history')

    @classmethod
    def _seq_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('seq_selector', 'no') or 'no')

    @classmethod
    def _seq_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('seq_source', 'history') or 'history')

    @classmethod
    def _out_prefix(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/gffcmp'

    @classmethod
    def _uses_annotation_mode(cls, inputs: dict[str, Any]) -> bool:
        return len(cls._gffinputs(inputs)) == 1 and cls._annotation_selector(inputs) == 'yes' and (not inputs.get('A')) and (not inputs.get('C')) and (not inputs.get('X')) and (cls._duplication_selector(inputs) == '') and (not inputs.get('S'))

    @classmethod
    def _duplication_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('duplication_selector', '') or '')

    @classmethod
    def _refmap_tmap(cls, inputs: dict[str, Any]) -> bool:
        return bool(inputs.get('refmap_tmap', True))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        setup = [_shell_join(['mkdir', '-p', out])]
        staged_names = cls._staged_input_names(inputs)
        for source, staged_name in zip(cls._gffinputs(inputs), staged_names, strict=False):
            setup.append(_shell_join(['ln', '-s', source, staged_name]))
        if cls._annotation_selector(inputs) == 'yes':
            ref = inputs.get('reference_annotation') if cls._ref_source(inputs) == 'history' else inputs.get('reference_index_path', inputs.get('reference_index'))
            setup.append(_shell_join(['ln', '-s', str(ref or ''), 'reference_annotation']))
        if cls._seq_selector(inputs) == 'yes':
            seq = inputs.get('ref_genome') if cls._seq_source(inputs) == 'history' else inputs.get('seq_index_path', inputs.get('seq_index'))
            setup.append(_shell_join(['ln', '-s', str(seq or ''), 'ref_seq.fa']))
            if cls._seq_source(inputs) == 'history':
                setup.append(_shell_join(['samtools', 'faidx', 'ref_seq.fa']))
        cmd = ['gffcompare', '-V', '-o', cls._out_prefix(inputs)]
        if cls._annotation_selector(inputs) == 'yes':
            cmd.extend(['-r', 'reference_annotation'])
            if inputs.get('R'):
                cmd.append('-R')
            if inputs.get('Q'):
                cmd.append('-Q')
            if inputs.get('strict_match'):
                cmd.extend(['--strict-match', '-e', str(inputs.get('e', 100))])
            discard_single_exon = str(inputs.get('discard_single_exon', '') or '')
            if discard_single_exon:
                cmd.append(discard_single_exon)
            duplication_selector = cls._duplication_selector(inputs)
            if duplication_selector:
                cmd.append(duplication_selector)
                if inputs.get('S'):
                    cmd.append('-S')
            if inputs.get('no_merge'):
                cmd.append('--no-merge')
        if not cls._refmap_tmap(inputs):
            cmd.append('-T')
        if cls._seq_selector(inputs) == 'yes':
            cmd.extend(['-s', 'ref_seq.fa'])
        cmd.extend(['-d', str(inputs.get('max_dist_group', 100))])
        if inputs.get('chr_stats'):
            cmd.append('--chr-stats')
        cmd.extend(['-p', str(inputs.get('p', 'TCONS') or 'TCONS')])
        for flag in ('A', 'C', 'X', 'K'):
            if inputs.get(flag):
                cmd.append(f'-{flag}')
        cmd.extend(staged_names)
        return ' && '.join([*setup, _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / ('gffcmp.annotated.gtf' if cls._uses_annotation_mode(inputs) else 'gffcmp.combined.gtf'), out / 'gffcmp.stats', out / 'gffcmp.loci', out / 'gffcmp.tracking']
        if cls._refmap_tmap(inputs):
            staged_names = cls._staged_input_names(inputs)
            if len(staged_names) == 1:
                outputs.append(out / 'output.tmap')
                if cls._annotation_selector(inputs) == 'yes':
                    outputs.append(out / 'output.refmap')
            else:
                for staged_name in staged_names:
                    outputs.append(out / f'gffcmp.{staged_name}.tmap')
                if cls._annotation_selector(inputs) == 'yes':
                    for staged_name in staged_names:
                        outputs.append(out / f'gffcmp.{staged_name}.refmap')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._gffinputs(inputs):
            return 'at least one gffinputs value is required'
        annotation_selector = cls._annotation_selector(inputs)
        if annotation_selector not in cls.YES_NO_OPTIONS:
            return f"annotation_selector must be one of: {', '.join(cls.YES_NO_OPTIONS)}"
        ref_source = cls._ref_source(inputs)
        if ref_source not in cls.SOURCES:
            return f"ref_source must be one of: {', '.join(cls.SOURCES)}"
        if annotation_selector == 'yes':
            if ref_source == 'history' and (not str(inputs.get('reference_annotation', '')).strip()):
                return 'reference_annotation is required when ref_source is history'
            reference_index = str(inputs.get('reference_index_path', inputs.get('reference_index', ''))).strip()
            if ref_source == 'cached' and (not reference_index):
                return 'reference_index_path is required when ref_source is cached'
        seq_selector = cls._seq_selector(inputs)
        if seq_selector not in cls.YES_NO_OPTIONS:
            return f"seq_selector must be one of: {', '.join(cls.YES_NO_OPTIONS)}"
        seq_source = cls._seq_source(inputs)
        if seq_source not in cls.SOURCES:
            return f"seq_source must be one of: {', '.join(cls.SOURCES)}"
        if seq_selector == 'yes':
            if seq_source == 'history' and (not str(inputs.get('ref_genome', '')).strip()):
                return 'ref_genome is required when seq_source is history'
            seq_index = str(inputs.get('seq_index_path', inputs.get('seq_index', ''))).strip()
            if seq_source == 'cached' and (not seq_index):
                return 'seq_index_path is required when seq_source is cached'
        discard_single_exon = str(inputs.get('discard_single_exon', '') or '')
        if discard_single_exon not in cls.DISCARD_SINGLE_EXON_OPTIONS:
            return f"discard_single_exon must be one of: {', '.join(cls.DISCARD_SINGLE_EXON_OPTIONS)}"
        duplication_selector = cls._duplication_selector(inputs)
        if duplication_selector not in cls.DUPLICATION_OPTIONS:
            return f"duplication_selector must be one of: {', '.join(cls.DUPLICATION_OPTIONS)}"
        for name in ('e', 'max_dist_group'):
            value = inputs.get(name, '')
            if str(value) == '':
                continue
            try:
                number = int(value)
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if number < 0:
                return f'{name} must be greater than or equal to 0'
        prefix = str(inputs.get('p', 'TCONS') or 'TCONS')
        if not re.fullmatch('[0-9A-Za-z_-]+', prefix):
            return 'p must contain only letters, digits, underscores, and hyphens'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'gffinputs': ('GFF_GTF', {'multiple': True, 'description': 'One or more GTF/GFF3 transcript annotations to compare'})}, 'optional': {'element_identifiers': ('STRING', {'default': [], 'multiple': True, 'description': 'Optional Galaxy collection labels for stable query filenames'}), 'annotation_selector': ('STRING', {'default': 'no', 'options': cls.YES_NO_OPTIONS, 'description': 'Use a reference annotation for classification'}), 'ref_source': ('STRING', {'default': 'history', 'options': cls.SOURCES, 'description': 'Reference annotation source'}), 'reference_annotation': ('GFF_GTF', {'description': 'Reference annotation from history'}), 'reference_index_path': ('GFF_GTF', {'description': 'Cached reference annotation path'}), 'R': ('BOOLEAN', {'default': False, 'description': 'Apply Sn correction using only overlapped reference transcripts'}), 'Q': ('BOOLEAN', {'default': False, 'description': 'Apply Sp correction using only query transcripts overlapping references'}), 'strict_match': ('BOOLEAN', {'default': False, 'description': 'Require stricter transcript-level matching'}), 'e': ('INT', {'default': 100, 'min': 0, 'description': 'Allowed terminal exon end variation for strict matching'}), 'discard_single_exon': ('STRING', {'default': '', 'options': cls.DISCARD_SINGLE_EXON_OPTIONS, 'description': 'Discard single-exon transfrags or reference transcripts'}), 'duplication_selector': ('STRING', {'default': '', 'options': cls.DUPLICATION_OPTIONS, 'description': 'Discard duplicate query transfrags'}), 'S': ('BOOLEAN', {'default': False, 'description': 'Use strict duplicate checking when duplicate filtering is enabled'}), 'no_merge': ('BOOLEAN', {'default': False, 'description': 'Disable close-exon merging'}), 'seq_selector': ('STRING', {'default': 'no', 'options': cls.YES_NO_OPTIONS, 'description': 'Use genomic sequence data for repeat classification'}), 'seq_source': ('STRING', {'default': 'history', 'options': cls.SOURCES, 'description': 'Reference sequence source'}), 'ref_genome': ('FASTA', {'description': 'Reference genome FASTA from history'}), 'seq_index_path': ('FASTA', {'description': 'Cached reference genome FASTA path'}), 'max_dist_group': ('INT', {'default': 100, 'min': 0, 'description': 'Maximum distance for grouping transcript start sites'}), 'chr_stats': ('BOOLEAN', {'default': False, 'description': 'Report stats per reference contig or chromosome'}), 'refmap_tmap': ('BOOLEAN', {'default': True, 'description': 'Generate TMAP and RefMap files for each input'}), 'p': ('STRING', {'default': 'TCONS', 'description': 'Name prefix for consensus transcripts'}), 'A': ('BOOLEAN', {'default': False, 'description': 'Discard contained transfrags except alternate TSS cases'}), 'C': ('BOOLEAN', {'default': False, 'description': 'Discard matching and contained transfrags'}), 'X': ('BOOLEAN', {'default': False, 'description': 'Discard contained transfrags with ends inside container introns'}), 'K': ('BOOLEAN', {'default': False, 'description': 'Keep redundant transfrags matching a reference when using -C/-A/-X'})}, 'hidden': {'output': ('STRING', {})}}
