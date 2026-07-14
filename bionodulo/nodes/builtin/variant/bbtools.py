"""bbtools — variant node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BBToolsCallVariantsNode(CommandNode):
    """Call variants from BAM alignments with BBTools CallVariants."""
    NODE_ID = 'bbtools_callvariants'
    DISPLAY_NAME = 'BBTools CallVariants'
    REQUIRED_CONDA_PACKAGES = ['bbmap', 'samtools']
    CATEGORY = 'variant'
    DESCRIPTION = 'Call variants from aligned BAM files with BBTools CallVariants.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'BBTools', 'CallVariants', 'callvariants', 'bbtools_callvariants', 'variant caller', 'BAM variants', 'ploidy', 'variant score histogram']
    RETURN_TYPES = ('VCF', 'TSV', 'TSV', 'TSV')
    RETURN_NAMES = ('variants', 'score_histogram', 'zygosity_histogram', 'quality_histogram')
    REQUIRED_EXECUTABLES = ['callvariants.sh']
    DOCUMENTATION_URL = 'https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/callvariants-guide/'
    CITATION_DOIS = [BBTOOLS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{BBTOOLS_CITATION_DOI}']
    CITATION_TEXT = BBTOOLS_CITATION_TEXT
    VERSION = '39.08'
    SHELL = True
    OUTPUT_EXTENSIONS = {'vcf': '.vcf', 'gff': '.gff', 'txt': '.txt'}
    OUTPUT_ARGUMENTS = {'vcf': 'vcf=out.vcf', 'gff': 'outgff=out.gff', 'txt': 'out=output.txt'}
    OUTPUT_TEMP_FILES = {'vcf': 'out.vcf', 'gff': 'out.gff', 'txt': 'output.txt'}

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('output_format', 'vcf') or 'vcf')

    @classmethod
    def _variants_output(cls, inputs: dict[str, Any], output_dir: str | Path) -> Path:
        return Path(output_dir) / cls.NODE_ID / f"variants{cls.OUTPUT_EXTENSIONS.get(cls._output_format(inputs), '.vcf')}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        staged_input = f"{out}/{_safe_name(str(inputs.get('input', '')))}.bam"
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"
        output_format = cls._output_format(inputs)
        cmd = ['callvariants.sh', f'in={staged_input}', f'threads={slots}', f"ref={inputs.get('reference', '')}", f"ploidy={inputs.get('ploidy', 1)}"]
        if inputs.get('output_variant_score_hist'):
            cmd.append(f'shist={out}/score_histogram.tsv')
        if inputs.get('output_zygosity_hist'):
            cmd.append(f'zhist={out}/zygosity_histogram.tsv')
        if inputs.get('output_quality_hist'):
            cmd.append(f'qhist={out}/quality_histogram.tsv')
        cmd.append(cls.OUTPUT_ARGUMENTS.get(output_format, 'vcf=out.vcf'))
        command = _shell_join(cmd).replace(shlex.quote(f'threads={slots}'), f'threads={slots}')
        temp_output = cls.OUTPUT_TEMP_FILES.get(output_format, 'out.vcf')
        final_output = f"{out}/variants{cls.OUTPUT_EXTENSIONS.get(output_format, '.vcf')}"
        return f"ln -s {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(staged_input)} && {command} && mv {shlex.quote(temp_output)} {shlex.quote(final_output)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [cls._variants_output(inputs, output_dir)]
        if inputs.get('output_variant_score_hist'):
            outputs.append(out / 'score_histogram.tsv')
        if inputs.get('output_zygosity_hist'):
            outputs.append(out / 'zygosity_histogram.tsv')
        if inputs.get('output_quality_hist'):
            outputs.append(out / 'quality_histogram.tsv')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('input'):
            return 'input BAM is required'
        if not inputs.get('reference'):
            return 'reference FASTA is required'
        output_format = cls._output_format(inputs)
        if output_format not in cls.OUTPUT_EXTENSIONS:
            return 'output_format must be one of: vcf, gff, txt'
        for key, default in (('ploidy', 1), ('threads', 4)):
            try:
                value = int(inputs.get(key, default))
            except (TypeError, ValueError):
                return f'{key} must be an integer'
            if value < 1:
                return f'{key} must be >= 1'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('BAM', {'description': 'BAM alignment file; BBMap output is recommended'}), 'reference': ('FASTA', {'description': 'Reference genome FASTA'})}, 'optional': {'ploidy': ('INT', {'default': 1, 'min': 1, 'description': 'Sample ploidy'}), 'output_format': ('STRING', {'default': 'vcf', 'options': ['vcf', 'gff', 'txt'], 'description': 'Variant output format'}), 'output_variant_score_hist': ('BOOLEAN', {'default': False, 'description': 'Return variant score histogram'}), 'output_zygosity_hist': ('BOOLEAN', {'default': False, 'description': 'Return zygosity histogram'}), 'output_quality_hist': ('BOOLEAN', {'default': False, 'description': 'Return variant quality histogram'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}
