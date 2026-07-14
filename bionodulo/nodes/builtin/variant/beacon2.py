"""beacon2 — variant node(s). One tool per file (extracted from wrapped_beacon_ucsc.py)."""
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


class Beacon2Vcf2BffNode(CommandNode):
    """Convert annotated VCF files to Beacon v2 genomic variations JSON."""
    NODE_ID = 'beacon2_vcf2bff'
    DISPLAY_NAME = 'Beacon2 VCF2BFF'
    REQUIRED_CONDA_PACKAGES = ['beacon2-ri-tools', 'gzip']
    CATEGORY = 'variant'
    DESCRIPTION = 'Convert annotated VCF files to Beacon v2 genomic variations JSON.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Beacon2', 'Beacon v2', 'beacon2_vcf2bff', 'vcf2bff.pl', 'annotated VCF', 'Beacon Friendly Format', 'genomicVariations', 'genomicVariationsVcf']
    RETURN_TYPES = ('JSON',)
    RETURN_NAMES = ('genomicVariationsVcf',)
    REQUIRED_EXECUTABLES = ['vcf2bff.pl', 'gunzip']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/beacon2'
    CITATION_DOIS = [BEACON2_DOI]
    CITATION_URLS = [f'{DOI_URL}{BEACON2_DOI}']
    CITATION_TEXT = BEACON2_CITATION_TEXT
    VERSION = '2.0.0+galaxy0'
    SHELL = True
    FORMATS = ['bff', 'hash', 'json']

    @classmethod
    def _format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('format', 'bff') or 'bff')

    @classmethod
    def _staged_input(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/sample.vcf.gz'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        staged_input = cls._staged_input(inputs)
        setup = _shell_join(['ln', '-s', str(inputs.get('input', '')), staged_input])
        cmd = ['vcf2bff.pl', '--input', staged_input, '--format', cls._format(inputs), '--project-dir', out, '--dataset-id', str(inputs.get('dataset_id', '')), '--genome', str(inputs.get('genome', ''))]
        return f"{setup} && {_shell_join(cmd)} && {_shell_join(['gunzip', f'{out}/genomicVariationsVcf.json.gz'])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'genomicVariationsVcf.json']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input VCF.GZ is required'
        output_format = cls._format(inputs)
        if output_format not in cls.FORMATS:
            return f"format must be one of: {', '.join(cls.FORMATS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FILE', {'description': 'Annotated compressed VCF produced by bcftools, SnpEff, or SnpSift'})}, 'optional': {'format': ('STRING', {'default': 'bff', 'options': cls.FORMATS, 'description': 'Beacon2 output representation requested from vcf2bff.pl'}), 'dataset_id': ('STRING', {'default': '', 'description': 'Dataset ID assigned to generated genomic variations records'}), 'genome': ('STRING', {'default': '', 'description': 'Reference genome label used to annotate the VCF, such as hs37 or hg38'})}, 'hidden': {'output': ('STRING', {})}}
