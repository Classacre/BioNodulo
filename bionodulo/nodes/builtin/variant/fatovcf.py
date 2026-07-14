"""fatovcf — variant node(s). One tool per file (extracted from wrapped_beacon_ucsc.py)."""
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


class FaToVcfNode(CommandNode):
    """Convert FASTA alignments to VCF single-nucleotide differences."""
    NODE_ID = 'fatovcf'
    DISPLAY_NAME = 'faToVcf'
    REQUIRED_CONDA_PACKAGES = ['ucsc-fatovcf']
    CATEGORY = 'variant'
    DESCRIPTION = 'Convert a FASTA alignment file to Variant Call Format single-nucleotide differences.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'fatovcf', 'faToVcf', 'FASTA alignment to VCF', 'single-nucleotide diffs', 'ambiguous bases', 'mask sites']
    RETURN_TYPES = ('VCF',)
    RETURN_NAMES = ('out',)
    REQUIRED_EXECUTABLES = ['faToVcf']
    DOCUMENTATION_URL = 'https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/utils/faToVcf/faToVcf.c'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    REFERENCE_MODES = ['', 'customRef']
    AMBIGUOUS_MODES = ['', '-ambiguousToN', '-resolveAmbiguous']

    @classmethod
    def _reference_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('refSeq', '') or '')

    @classmethod
    def _ambiguous_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('ambiguous', '') or '')

    @classmethod
    def _staged_input_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/in.fa'

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out.vcf'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged_input = cls._staged_input_path(inputs)
        setup = _shell_join(['ln', '-s', str(inputs.get('in_fasta', '')), staged_input])
        cmd = ['faToVcf', staged_input, cls._output_path(inputs)]
        if cls._reference_mode(inputs) == 'customRef':
            cmd.append(f"-ref={inputs.get('ref', '')}")
        if (ambiguous := cls._ambiguous_mode(inputs)):
            cmd.append(ambiguous)
        if str(inputs.get('excludeFile', '')) != '':
            cmd.append(f"-excludeFile={inputs.get('excludeFile')}")
        cmd.append(f"-maxDiff={inputs.get('maxDiff', 0)}")
        if str(inputs.get('maskSites', '')) != '':
            cmd.append(f"-maskSites={inputs.get('maskSites')}")
        if int(inputs.get('windowSize', 0) or 0) > 0:
            cmd.append(f"-windowSize={inputs.get('windowSize')}")
            cmd.append(f"-minAmbigInWindow={inputs.get('minAmbigInWindow', 2)}")
        if inputs.get('includeNoAltN'):
            cmd.append('-includeNoAltN')
        cmd.append(f"-minAc={inputs.get('minAc', 0)}")
        cmd.append(f"-minAf={inputs.get('minAf', 0.0)}")
        if int(inputs.get('startOffset', 0) or 0) > 0:
            cmd.append(f"-startOffset={inputs.get('startOffset')}")
        if inputs.get('includeRef'):
            cmd.append('-includeRef')
        if inputs.get('noGenotypes'):
            cmd.append('-noGenotypes')
        if str(inputs.get('vcfChrom', '')) != '':
            cmd.append(f"-vcfChrom={inputs.get('vcfChrom')}")
        return f'{setup} && {_shell_join(cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out.vcf']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('in_fasta', '')).strip():
            return 'in_fasta is required'
        reference_mode = cls._reference_mode(inputs)
        if reference_mode not in cls.REFERENCE_MODES:
            return f"refSeq must be one of: {', '.join(cls.REFERENCE_MODES)}"
        if reference_mode == 'customRef' and (not str(inputs.get('ref', '')).strip()):
            return 'ref is required when refSeq is customRef'
        ambiguous = cls._ambiguous_mode(inputs)
        if ambiguous not in cls.AMBIGUOUS_MODES:
            return f"ambiguous must be one of: {', '.join(cls.AMBIGUOUS_MODES)}"
        minimums = {'maxDiff': 0, 'windowSize': 0, 'minAmbigInWindow': 1, 'minAc': 0, 'startOffset': 0}
        for name, minimum in minimums.items():
            value = inputs.get(name, '')
            if str(value) != '' and int(value) < minimum:
                return f'{name} must be greater than or equal to {minimum}'
        min_af = inputs.get('minAf', '')
        if str(min_af) != '' and (not 0.0 <= float(min_af) <= 1.0):
            return 'minAf must be between 0.0 and 1.0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_fasta': ('FASTA', {'description': 'FASTA alignment with same-length sequences'})}, 'optional': {'refSeq': ('STRING', {'default': '', 'options': cls.REFERENCE_MODES, 'description': 'Use the first sequence or a custom sequence as the reference'}), 'ref': ('STRING', {'default': '', 'description': 'Reference sequence name used when refSeq is customRef'}), 'ambiguous': ('STRING', {'default': '', 'options': cls.AMBIGUOUS_MODES, 'description': 'Treat IUPAC ambiguous bases as no-calls or resolve compatible ambiguous calls'}), 'excludeFile': ('FILE', {'description': 'Optional file listing sequence names to exclude'}), 'maxDiff': ('INT', {'default': 0, 'min': 0, 'description': 'Exclude sequences with more than this many mismatches'}), 'maskSites': ('VCF', {'description': 'Optional VCF of positions to mask'}), 'windowSize': ('INT', {'default': 0, 'min': 0, 'description': 'Window radius used for ambiguity masking'}), 'minAmbigInWindow': ('INT', {'default': 2, 'min': 1, 'description': 'Minimum ambiguous bases in a window before masking'}), 'includeNoAltN': ('BOOLEAN', {'default': False, 'description': 'Include no-alternate positions with missing calls'}), 'minAc': ('INT', {'default': 0, 'min': 0, 'description': 'Minimum alternate allele count'}), 'minAf': ('FLOAT', {'default': 0.0, 'min': 0.0, 'max': 1.0, 'description': 'Minimum alternate allele frequency'}), 'startOffset': ('INT', {'default': 0, 'min': 0, 'description': 'Offset added to each VCF position'}), 'includeRef': ('BOOLEAN', {'default': False, 'description': 'Include the reference sequence in genotype columns'}), 'noGenotypes': ('BOOLEAN', {'default': False, 'description': 'Output an 8-column VCF without genotype columns'}), 'vcfChrom': ('STRING', {'default': '', 'description': 'Sequence name to use in the VCF CHROM column'})}, 'hidden': {'output': ('STRING', {})}}
