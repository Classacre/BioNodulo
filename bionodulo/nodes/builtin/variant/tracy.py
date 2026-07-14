"""tracy — variant node(s). One tool per file (extracted from wrapped_taxonomy_humann.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class TracyDecomposeNode(CommandNode):
    """Decompose heterozygous Sanger chromatogram mutations with Tracy."""
    NODE_ID = 'tracy_decompose'
    DISPLAY_NAME = 'tracy Decompose'
    REQUIRED_CONDA_PACKAGES = ['tracy']
    CATEGORY = 'variant'
    DESCRIPTION = 'Decompose heterozygous Sanger chromatogram mutations and optionally call variants with Tracy.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Tracy', 'tracy Decompose', 'tracy heterozygous deconvolution', 'Sanger chromatogram variants', 'heterozygous mutations', 'trace deconvolution']
    RETURN_TYPES = ('FASTA', 'FASTA', 'FASTA', 'JSON', 'TSV', 'BCF')
    RETURN_NAMES = ('allele1', 'allele2', 'both_alleles', 'json', 'stats', 'variants')
    REQUIRED_EXECUTABLES = ['tracy', 'bgzip']
    DOCUMENTATION_URL = 'https://www.gear-genomics.com/docs/tracy/cli/#deconvolution-of-heterozygous-mutations'
    CITATION_DOIS = ['10.1186/s12864-020-6635-8']
    CITATION_URLS = [f'{DOI_URL}10.1186/s12864-020-6635-8']
    CITATION_TEXT = 'Tracy: basecalling, alignment, assembly and deconvolution of Sanger chromatogram trace files.'
    VERSION = '0.7.8'
    SHELL = True
    OPTIONAL_OUTPUTS = ['json', 'tabular']
    OPTION_DEFAULTS = TracyAlignNode.OPTION_DEFAULTS
    INT_MIN_OPTIONS = TracyAlignNode.INT_MIN_OPTIONS
    INT_MAX_OPTIONS = TracyAlignNode.INT_MAX_OPTIONS

    @classmethod
    def _optional_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        raw = inputs.get('optional_outputs')
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(',') if part.strip()]
        return _as_list(raw)

    @classmethod
    def _add_decompose_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        options = [('--pratio', 'pratio', 0.33), ('--kmer', 'kmer', cls.OPTION_DEFAULTS['kmer']), ('--support', 'support', cls.OPTION_DEFAULTS['support']), ('--maxindel', 'maxindel', cls.OPTION_DEFAULTS['maxindel']), ('--trim', 'trim', cls.OPTION_DEFAULTS['trim']), ('--trimLeft', 'trimLeft', cls.OPTION_DEFAULTS['trimLeft']), ('--trimRight', 'trimRight', cls.OPTION_DEFAULTS['trimRight']), ('--linelimit', 'linelimit', cls.OPTION_DEFAULTS['linelimit']), ('--gapopen', 'gapopen', cls.OPTION_DEFAULTS['gapopen']), ('--gapext', 'gapext', cls.OPTION_DEFAULTS['gapext']), ('--match', 'match', cls.OPTION_DEFAULTS['match']), ('--mismatch', 'mismatch', cls.OPTION_DEFAULTS['mismatch'])]
        for flag, name, default in options:
            cmd.extend([flag, str(inputs.get(name, default))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        genome = str(inputs.get('genome', ''))
        setup: list[str] = []
        if inputs.get('index_genome'):
            indexed_genome = f'{out}/genome.fasta.gz'
            setup = [f'bgzip -c {shlex.quote(genome)} > {shlex.quote(indexed_genome)}', _shell_join(['tracy', 'index', '-o', f'{out}/genome.fasta.fm9', indexed_genome])]
            genome = indexed_genome
        cmd = ['tracy', 'decompose', '--genome', genome]
        if inputs.get('callVariants'):
            cmd.append('--callVariants')
        cls._add_decompose_options(cmd, inputs)
        cmd.extend(['--output', out, str(inputs.get('tracefile', ''))])
        return ' && '.join([*setup, _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'out.align1', out / 'out.align2', out / 'out.align3']
        optional_outputs = cls._optional_outputs(inputs)
        if 'json' in optional_outputs:
            outputs.append(out / 'out.json')
        if 'tabular' in optional_outputs:
            outputs.append(out / 'out.abif')
        if inputs.get('callVariants'):
            outputs.append(out / 'out.bcf')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('genome', '')).strip():
            return 'genome is required'
        if not str(inputs.get('tracefile', '')).strip():
            return 'tracefile is required'
        try:
            pratio = float(inputs.get('pratio', 0.33))
        except (TypeError, ValueError):
            return 'pratio must be a number'
        if pratio < 0:
            return 'pratio must be >= 0'
        for name, minimum in cls.INT_MIN_OPTIONS.items():
            try:
                value = int(inputs.get(name, cls.OPTION_DEFAULTS[name]))
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < minimum:
                return f'{name} must be >= {minimum}'
        for name, maximum in cls.INT_MAX_OPTIONS.items():
            try:
                value = int(inputs.get(name, cls.OPTION_DEFAULTS[name]))
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value > maximum:
                return f'{name} must be <= {maximum}'
        unsupported = [output for output in cls._optional_outputs(inputs) if output not in cls.OPTIONAL_OUTPUTS]
        if unsupported:
            return f"optional_outputs contains unsupported values: {', '.join(unsupported)}"
        return super().VALIDATE_INPUTS(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'genome': ('FILE', {'description': 'FASTA, ABI, or SCF genome/reference sequence'}), 'tracefile': ('FILE', {'description': 'Sanger chromatogram trace file in AB1 or SCF format'})}, 'optional': {'index_genome': ('BOOLEAN', {'default': False, 'description': 'Pre-index large FASTA references with Tracy FM index'}), 'callVariants': ('BOOLEAN', {'default': False, 'description': 'Call variants in the chromatogram'}), 'pratio': ('FLOAT', {'default': 0.33, 'min': 0, 'description': 'Peak ratio threshold for calling a base'}), 'kmer': ('INT', {'default': 15, 'min': 1, 'description': 'K-mer size used to anchor the trace'}), 'support': ('INT', {'default': 3, 'min': 1, 'description': 'Minimum k-mer support'}), 'maxindel': ('INT', {'default': 1000, 'min': 1, 'description': 'Maximum indel size in the Sanger trace'}), 'trim': ('INT', {'default': 0, 'description': 'Trimming stringency; 0 uses trimLeft and trimRight'}), 'trimLeft': ('INT', {'default': 50, 'min': 0, 'description': 'Fixed bases to trim from the left'}), 'trimRight': ('INT', {'default': 50, 'min': 0, 'description': 'Fixed bases to trim from the right'}), 'linelimit': ('INT', {'default': 60, 'min': 1, 'description': 'Alignment line length'}), 'gapopen': ('INT', {'default': -10, 'max': 0, 'description': 'Gap open penalty'}), 'gapext': ('INT', {'default': -4, 'max': 0, 'description': 'Gap extension penalty'}), 'match': ('INT', {'default': 3, 'min': 0, 'description': 'Nucleotide match score'}), 'mismatch': ('INT', {'default': -5, 'max': 0, 'description': 'Mismatch penalty'}), 'optional_outputs': ('STRING', {'default': [], 'multiple': True, 'options': cls.OPTIONAL_OUTPUTS, 'description': 'Optional JSON and tabular statistics outputs'})}, 'hidden': {'output': ('STRING', {})}}
