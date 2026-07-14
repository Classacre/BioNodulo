"""abritamr — annotation node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class AbriTAMRNode(CommandNode):
    """Run abriTAMR antimicrobial resistance gene detection."""
    NODE_ID = 'abritamr'
    DISPLAY_NAME = 'abriTAMR'
    REQUIRED_CONDA_PACKAGES = ['abritamr']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Detect and collate antimicrobial resistance genes, partial genes, and virulence factors with abriTAMR.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'abriTAMR', 'abritamr', 'AMR gene detection', 'AMRFinderPlus', 'antimicrobial resistance', 'virulence summary']
    RETURN_TYPES = ('TSV', 'TSV', 'TSV', 'TSV', 'STATS_FILE')
    RETURN_NAMES = ('abriTAMR_output', 'matches_summary', 'partials_summary', 'virulence_summary', 'log')
    REQUIRED_EXECUTABLES = ['abritamr']
    DOCUMENTATION_URL = 'https://github.com/MDU-PHL/abritamr'
    CITATION_DOIS = [ABRITAMR_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{ABRITAMR_CITATION_DOI}']
    CITATION_TEXT = ABRITAMR_CITATION_TEXT
    VERSION = '1.3.0'
    SHELL = True
    VALID_SPECIES = {'Neisseria', 'Clostridioides_difficile', 'Acinetobacter_baumannii', 'Campylobacter', 'Enterococcus_faecalis', 'Enterococcus_faecium', 'Escherichia', 'Klebsiella', 'Salmonella', 'Staphylococcus_aureus', 'Staphylococcus_pseudintermedius', 'Streptococcus_agalactiae', 'Streptococcus_pneumoniae', 'Streptococcus_pyogenes'}

    @classmethod
    def _contigs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('contig'))

    @classmethod
    def _contig_labels(cls, inputs: dict[str, Any], contigs: list[str]) -> list[str]:
        labels = _as_list(inputs.get('contig_labels'))
        if len(labels) != len(contigs):
            return [Path(contig).name for contig in contigs]
        return labels

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        contigs = cls._contigs(inputs)
        labels = cls._contig_labels(inputs, contigs)
        manifest = f'{out}/input.tsv'
        printf_args = ['printf', '%s\\t%s\\n']
        for label, contig in zip(labels, contigs):
            printf_args.extend([label, contig])
        setup = f'{_shell_join(printf_args)} > {shlex.quote(manifest)}'
        slots = f"${{GALAXY_SLOTS:-{inputs.get('jobs', 4)}}}"
        cmd = ['abritamr', 'run', '--contigs', manifest]
        if inputs.get('species'):
            cmd.extend(['--species', str(inputs.get('species'))])
        if inputs.get('identity') not in (None, ''):
            cmd.extend(['--identity', str(inputs.get('identity'))])
        cmd.extend(['--jobs', slots])
        command = _shell_join(cmd).replace(shlex.quote(slots), slots)
        return f'{setup} && {command}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'abritamr.txt', out / 'summary_matches.txt', out / 'summary_partials.txt', out / 'summary_virulence.txt']
        if inputs.get('log_file'):
            outputs.append(out / 'abritamr.log')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._contigs(inputs):
            return 'at least one contig FASTA is required'
        if inputs.get('species') not in (None, '') and str(inputs.get('species')) not in cls.VALID_SPECIES:
            return 'species must be one of the supported abriTAMR species'
        if inputs.get('identity') not in (None, ''):
            try:
                identity = float(inputs.get('identity'))
            except (TypeError, ValueError):
                return 'identity must be a number'
            if not 0 <= identity <= 1:
                return 'identity must be between 0 and 1'
        try:
            jobs = int(inputs.get('jobs', 4))
        except (TypeError, ValueError):
            return 'jobs must be an integer'
        if jobs < 1:
            return 'jobs must be >= 1'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        species = sorted(cls.VALID_SPECIES)
        return {'required': {'contig': ('FASTA', {'list': True, 'description': 'One or more isolate contig FASTA files'})}, 'optional': {'species': ('STRING', {'default': '', 'options': species, 'description': 'Species for point-mutation resistance mechanisms'}), 'identity': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'description': 'Minimum AMRFinder identity threshold'}), 'log_file': ('BOOLEAN', {'default': False, 'description': 'Return the abriTAMR log file'}), 'jobs': ('INT', {'default': 4, 'min': 1, 'max': 128, 'description': 'Worker processes'}), 'contig_labels': ('STRING', {'default': '', 'list': True, 'advanced': True, 'description': 'Optional sample labels for the manifest'})}, 'hidden': {'output': ('STRING', {})}}
