"""gtftobed12 — genomics node(s). One tool per file (extracted from wrapped_beacon_ucsc.py)."""
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


class GtfToBed12Node(CommandNode):
    """Convert GTF gene annotations to BED12."""
    NODE_ID = 'gtftobed12'
    DISPLAY_NAME = 'Convert GTF to BED12'
    REQUIRED_CONDA_PACKAGES = ['ucsc-gtftogenepred', 'ucsc-genepredtobed']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Convert a GTF gene annotation to blocked BED12 using UCSC gtfToGenePred and genePredToBed.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'gtfToBed12', 'gtftobed12', 'GTF to BED12', 'gtfToGenePred', 'genePredToBed', 'gene annotation conversion', 'transcript info']
    RETURN_TYPES = ('BED', 'TSV')
    RETURN_NAMES = ('bed_file', 'transcript_info_file')
    REQUIRED_EXECUTABLES = ['gtfToGenePred', 'genePredToBed']
    DOCUMENTATION_URL = 'https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/utils/gtfToGenePred/gtfToGenePred.c'
    CITATION_DOIS = [UCSC_GENOME_BROWSER_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_GENOME_BROWSER_CITATION_DOI}']
    CITATION_TEXT = UCSC_GENOME_BROWSER_CITATION_TEXT
    VERSION = '357'
    SHELL = True
    ADVANCED_OPTIONS = ['default', 'advanced']
    FLAG_INPUTS = (('ignoreGroupsWithoutExons', '-ignoreGroupsWithoutExons'), ('simple', '-simple'), ('allErrors', '-allErrors'), ('impliedStopAfterCds', '-impliedStopAfterCds'), ('includeVersion', '-includeVersion'))

    @classmethod
    def _advanced_options_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('advanced_options_selector', 'default') or 'default')

    @classmethod
    def _bed_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/converted.bed'

    @classmethod
    def _genepred_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/temp.genePred'

    @classmethod
    def _transcript_info_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/transcript_info.tsv'

    @classmethod
    def _writes_transcript_info(cls, inputs: dict[str, Any]) -> bool:
        return cls._advanced_options_selector(inputs) == 'advanced' and bool(inputs.get('infoOut', False))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        gtf_cmd = ['gtfToGenePred']
        if cls._advanced_options_selector(inputs) == 'advanced':
            for name, flag in cls.FLAG_INPUTS:
                if inputs.get(name):
                    gtf_cmd.append(flag)
            if inputs.get('infoOut'):
                gtf_cmd.append(f'-infoOut={cls._transcript_info_path(inputs)}')
            for prefix in _as_list(inputs.get('sourcePrefixes')):
                gtf_cmd.append(f'-sourcePrefix={prefix}')
        gtf_cmd.extend([str(inputs.get('gtf_file', '')), cls._genepred_path(inputs)])
        bed_cmd = ['genePredToBed', cls._genepred_path(inputs), cls._bed_path(inputs)]
        return f'{_shell_join(gtf_cmd)} && {_shell_join(bed_cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'converted.bed']
        if cls._writes_transcript_info(inputs):
            outputs.append(out / 'transcript_info.tsv')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('gtf_file', '')).strip():
            return 'gtf_file is required'
        selector = cls._advanced_options_selector(inputs)
        if selector not in cls.ADVANCED_OPTIONS:
            return f"advanced_options_selector must be one of: {', '.join(cls.ADVANCED_OPTIONS)}"
        prefixes = _as_list(inputs.get('sourcePrefixes'))
        if selector != 'advanced' and prefixes:
            return 'sourcePrefixes can only be used when advanced_options_selector is advanced'
        if any((not prefix.strip() for prefix in prefixes)):
            return 'sourcePrefixes cannot contain blank values'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'gtf_file': ('GTF', {'description': 'GTF gene annotation file to convert to BED12'})}, 'optional': {'advanced_options_selector': ('STRING', {'default': 'default', 'options': cls.ADVANCED_OPTIONS, 'description': 'Use default conversion settings or expose gtfToGenePred advanced options'}), 'sourcePrefixes': ('STRING', {'default': [], 'multiple': True, 'description': 'Only process GTF entries whose source field starts with one of these prefixes'}), 'ignoreGroupsWithoutExons': ('BOOLEAN', {'default': False, 'description': 'Skip transcript groups that do not contain exons'}), 'simple': ('BOOLEAN', {'default': False, 'description': 'Check only column validity instead of the full GTF hierarchy'}), 'allErrors': ('BOOLEAN', {'default': False, 'description': 'Skip groups with errors rather than aborting at the first error'}), 'impliedStopAfterCds': ('BOOLEAN', {'default': False, 'description': 'Assume an implied stop codon after the CDS'}), 'includeVersion': ('BOOLEAN', {'default': False, 'description': 'Include gene_version and transcript_version attributes in output identifiers'}), 'infoOut': ('BOOLEAN', {'default': False, 'description': 'Write a transcript information table from gtfToGenePred'})}, 'hidden': {'output': ('STRING', {})}}
