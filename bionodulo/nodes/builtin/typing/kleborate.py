"""kleborate — typing node(s). One tool per file (extracted from wrapped_assembly_typing.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class KleborateNode(CommandNode):
    """Screen Klebsiella assemblies with Kleborate."""
    NODE_ID = 'kleborate'
    DISPLAY_NAME = 'Kleborate'
    REQUIRED_CONDA_PACKAGES = ['kleborate', 'kaptive']
    CATEGORY = 'typing'
    DESCRIPTION = 'Screen Klebsiella genome assemblies for species, MLST, virulence, resistance, and K/O loci.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Kleborate', 'kleborate', 'Klebsiella', 'Klebsiella pneumoniae', 'KpSC', 'MLST', 'virulence score', 'resistance score', 'Kaptive', 'K locus', 'O locus']
    RETURN_TYPES = ('TSV', 'TSV', 'TSV', 'TSV')
    RETURN_NAMES = ('concise', 'full', 'kaptive_k', 'kaptive_o')
    REQUIRED_EXECUTABLES = ['kleborate']
    DOCUMENTATION_URL = 'https://github.com/klebgenomics/Kleborate'
    CITATION_DOIS = ['10.1038/s41467-021-24448-3', '10.1099/mgen.0.000102']
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CITATION_DOIS]
    CITATION_TEXT = 'A genomic surveillance framework and genotyping tool for Klebsiella pneumoniae and its related species complex; Kaptive: identification of Klebsiella capsule synthesis loci from whole genome data.'
    VERSION = '2.3.2+galaxy1'
    SHELL = True

    @classmethod
    def _assemblies(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('assemblies'))

    @classmethod
    def _staged_assemblies(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        assemblies = cls._assemblies(inputs)
        labels = _as_list(inputs.get('assembly_labels'))
        staged: list[tuple[str, str]] = []
        for index, assembly in enumerate(assemblies):
            label = labels[index] if index < len(labels) else Path(assembly).name
            staged.append((assembly, _safe_identifier(label)))
        return staged

    @classmethod
    def _format_int(cls, inputs: dict[str, Any], key: str, default: int) -> str:
        return str(int(inputs.get(key, default) if inputs.get(key, default) not in (None, '') else default))

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any]) -> dict[str, str]:
        out = _out(inputs)
        return {'concise': f'{out}/kleborate_concise_results.tsv', 'full': f'{out}/kleborate_results.tsv', 'kaptive_k': f'{out}/kleborate_kaptive_k_results.tsv', 'kaptive_o': f'{out}/kleborate_kaptive_o_results.tsv'}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged = cls._staged_assemblies(inputs)
        paths = cls._output_paths(inputs)
        commands = [_shell_join(['ln', '-s', source, staged_name]) for source, staged_name in staged]
        cmd = ['kleborate']
        if inputs.get('resistance', True):
            cmd.append('--resistance')
        cmd.extend(['-o', paths['full']])
        if inputs.get('kaptive_k'):
            cmd.extend(['--kaptive_k', '--kaptive_k_outfile', paths['kaptive_k']])
        if inputs.get('kaptive_o'):
            cmd.extend(['--kaptive_o', '--kaptive_o_outfile', paths['kaptive_o']])
        cmd.extend(['--min_identity', cls._format_int(inputs, 'min_identity', 90), '--min_coverage', cls._format_int(inputs, 'min_coverage', 80), '--min_spurious_identity', cls._format_int(inputs, 'min_spurious_identity', 80), '--min_spurious_coverage', cls._format_int(inputs, 'min_spurious_coverage', 40), '--assemblies'])
        cmd.extend((staged_name for _, staged_name in staged))
        cmd.extend(['>', paths['concise']])
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'kleborate_concise_results.tsv', out / 'kleborate_results.tsv']
        if inputs.get('kaptive_k'):
            outputs.append(out / 'kleborate_kaptive_k_results.tsv')
        if inputs.get('kaptive_o'):
            outputs.append(out / 'kleborate_kaptive_o_results.tsv')
        return outputs

    @classmethod
    def _validate_percent(cls, inputs: dict[str, Any], key: str, default: int) -> bool | str:
        try:
            value = int(inputs.get(key, default) if inputs.get(key, default) not in (None, '') else default)
        except (TypeError, ValueError):
            return f'{key} must be a number'
        if value < 0 or value > 100:
            return f'{key} must be between 0 and 100'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        assemblies = cls._assemblies(inputs)
        if not assemblies:
            return 'at least one assembly FASTA is required'
        labels = _as_list(inputs.get('assembly_labels'))
        if labels and len(labels) != len(assemblies):
            return 'assembly_labels must match the number of assemblies'
        for key, default in {'min_identity': 90, 'min_coverage': 80, 'min_spurious_identity': 80, 'min_spurious_coverage': 40}.items():
            result = cls._validate_percent(inputs, key, default)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'assemblies': ('FASTA', {'multiple': True, 'description': 'FASTA assembly file or files to screen with Kleborate'})}, 'optional': {'resistance': ('BOOLEAN', {'default': True, 'description': 'Turn on acquired resistance and resistance score screening'}), 'kaptive_k': ('BOOLEAN', {'default': False, 'description': 'Run Kaptive K-locus capsule typing'}), 'kaptive_o': ('BOOLEAN', {'default': False, 'description': 'Run Kaptive O-locus lipopolysaccharide typing'}), 'min_identity': ('INT', {'default': 90, 'min': 0, 'max': 100, 'description': 'Minimum alignment percent identity for main results'}), 'min_coverage': ('INT', {'default': 80, 'min': 0, 'max': 100, 'description': 'Minimum alignment percent coverage for main results'}), 'min_spurious_identity': ('INT', {'default': 80, 'min': 0, 'max': 100, 'description': 'Minimum identity for spurious hit reporting'}), 'min_spurious_coverage': ('INT', {'default': 40, 'min': 0, 'max': 100, 'description': 'Minimum coverage for spurious hit reporting'}), 'assembly_labels': ('STRING', {'default': [], 'multiple': True, 'description': 'Optional Galaxy element identifiers used in the output table'})}, 'hidden': {'output': ('STRING', {})}}
