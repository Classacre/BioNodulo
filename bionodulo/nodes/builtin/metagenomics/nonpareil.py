"""nonpareil — metagenomics node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class NonpareilNode(CommandNode):
    """Estimate metagenomic coverage and redundancy with Nonpareil."""
    NODE_ID = 'nonpareil'
    DISPLAY_NAME = 'Nonpareil'
    REQUIRED_CONDA_PACKAGES = ['nonpareil']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Estimate metagenomic coverage and generate Nonpareil redundancy curves from FASTA or FASTQ reads.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Nonpareil', 'nonpareil', 'metagenomic coverage', 'redundancy curve', 'sequencing effort', 'library complexity']
    RETURN_TYPES = ('TSV', 'TSV', 'STATS_FILE', 'JSON', 'TSV')
    RETURN_NAMES = ('summary', 'all_data_output', 'log', 'json_output', 'mating_vector_output')
    REQUIRED_EXECUTABLES = ['nonpareil', 'NonpareilCurves.R']
    DOCUMENTATION_URL = 'https://nonpareil.readthedocs.io/'
    CITATION_DOIS = [NONPAREIL_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{NONPAREIL_CITATION_DOI}']
    CITATION_TEXT = NONPAREIL_CITATION_TEXT
    VERSION = '3.5.5'
    SHELL = True

    @classmethod
    def _summary_label(cls, inputs: dict[str, Any]) -> str:
        label = str(inputs.get('summary_label', Path(str(inputs.get('input', 'nonpareil'))).name) or 'nonpareil')
        return _safe_label(label)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        staged = f'{out}/input'
        summary_path = f'{out}/{cls._summary_label(inputs)}'
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 2)}}}"
        memory = f"${{NONPAREIL_MAX_MEMORY:-{inputs.get('max_memory', 1024)}}}"
        cmd = ['nonpareil', '-s', staged, '-T', str(inputs.get('algo', 'kmer')), '-f', str(inputs.get('input_format', 'fastq')), '-d', str(inputs.get('subsampling', 0.7)), '-n', str(inputs.get('subsample_per_point', 1024)), '-L', str(inputs.get('min_overlapping', 50)), '-X', str(inputs.get('max_query_reads', 1000)), '-R', memory, '-t', slots, '-b', f'{out}/output', '-a', f'{out}/all_data_output.tsv', '-C', f'{out}/mating_vector_output.tsv']
        if inputs.get('log_test'):
            cmd.extend(['-l', f'{out}/nonpareil.log'])
        cmd.extend(['-o', summary_path])
        if inputs.get('use_portion_in_output'):
            cmd.append('-F')
        cmd.extend(['-m', str(inputs.get('min_sampling_portion', 0)), '-M', str(inputs.get('max_sampling_portion', 1)), '-i', str(inputs.get('sampling_portion_interval', 0.01))])
        if inputs.get('use_rev_comp'):
            cmd.append('-c')
        if inputs.get('n_as_mismatches'):
            cmd.append('-N')
        if inputs.get('sim_thres') not in (None, ''):
            cmd.extend(['-S', str(inputs.get('sim_thres'))])
        cmd.extend(['-k', str(inputs.get('kmer_size', 24))])
        if inputs.get('proba') not in (None, ''):
            cmd.extend(['-x', str(inputs.get('proba'))])
        cmd.extend(['-r', str(inputs.get('seed', 1000))])
        command = _shell_join(cmd)
        command = command.replace(shlex.quote(memory), memory).replace(shlex.quote(slots), slots)
        parts = [f"ln -s {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(staged)}", command, f"cp {shlex.quote(summary_path)} {shlex.quote(f'{out}/summary.tsv')}"]
        if inputs.get('json_object'):
            parts.append(f"NonpareilCurves.R --json {shlex.quote(f'{out}/curves.json')} {shlex.quote(summary_path)}")
        return ' && '.join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'summary.tsv', out / 'all_data_output.tsv']
        if inputs.get('log_test'):
            outputs.append(out / 'nonpareil.log')
        if inputs.get('json_object'):
            outputs.append(out / 'curves.json')
        outputs.append(out / 'mating_vector_output.tsv')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('input'):
            return 'input sequences are required'
        algo = str(inputs.get('algo', 'kmer') or 'kmer')
        if algo not in {'alignment', 'kmer'}:
            return 'algo must be one of: alignment, kmer'
        input_format = str(inputs.get('input_format', 'fastq') or 'fastq')
        if input_format not in {'fasta', 'fastq'}:
            return 'input_format must be one of: fasta, fastq'
        for key in ('subsampling', 'min_sampling_portion', 'max_sampling_portion', 'sampling_portion_interval'):
            try:
                value = float(inputs.get(key, {'subsampling': 0.7, 'max_sampling_portion': 1, 'sampling_portion_interval': 0.01}.get(key, 0)))
            except (TypeError, ValueError):
                return f'{key} must be a number'
            if value < 0:
                return f'{key} must be >= 0'
        for key, default in (('subsample_per_point', 1024), ('max_query_reads', 1000), ('kmer_size', 24), ('seed', 1000), ('threads', 2), ('max_memory', 1024)):
            try:
                value = int(inputs.get(key, default))
            except (TypeError, ValueError):
                return f'{key} must be an integer'
            if value < 0:
                return f'{key} must be >= 0'
            if key in {'threads', 'max_memory'} and value < 1:
                return f'{key} must be >= 1'
        try:
            min_overlapping = int(inputs.get('min_overlapping', 50))
        except (TypeError, ValueError):
            return 'min_overlapping must be an integer'
        if not 0 <= min_overlapping <= 100:
            return 'min_overlapping must be between 0 and 100'
        for key in ('sim_thres', 'proba'):
            if inputs.get(key) in (None, ''):
                continue
            try:
                value = float(inputs.get(key))
            except (TypeError, ValueError):
                return f'{key} must be a number'
            if value < 0:
                return f'{key} must be >= 0'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTQ', {'description': 'Input FASTQ or FASTA sequences'}), 'algo': ('STRING', {'default': 'kmer', 'options': ['kmer', 'alignment'], 'description': 'Nonpareil algorithm'}), 'input_format': ('STRING', {'default': 'fastq', 'options': ['fastq', 'fasta'], 'description': 'Sequence file format'})}, 'optional': {'subsampling': ('FLOAT', {'default': 0.7, 'min': 0, 'description': 'Iterative subsampling factor'}), 'subsample_per_point': ('INT', {'default': 1024, 'min': 0, 'description': 'Subsamples per point'}), 'min_overlapping': ('INT', {'default': 50, 'min': 0, 'max': 100, 'description': 'Minimum aligned overlap percent'}), 'max_query_reads': ('INT', {'default': 1000, 'min': 0, 'description': 'Maximum query reads'}), 'use_portion_in_output': ('BOOLEAN', {'default': False, 'description': 'Report sampled portions as fractions'}), 'min_sampling_portion': ('FLOAT', {'default': 0, 'min': 0, 'advanced': True}), 'max_sampling_portion': ('FLOAT', {'default': 1, 'min': 0, 'advanced': True}), 'sampling_portion_interval': ('FLOAT', {'default': 0.01, 'min': 0, 'advanced': True}), 'use_rev_comp': ('BOOLEAN', {'default': False, 'description': 'Do not use reverse-complement matching'}), 'n_as_mismatches': ('BOOLEAN', {'default': False, 'description': 'Treat Ns as mismatches'}), 'sim_thres': ('FLOAT', {'default': '', 'min': 0, 'description': 'Similarity threshold'}), 'kmer_size': ('INT', {'default': 24, 'min': 0, 'description': 'K-mer size'}), 'proba': ('FLOAT', {'default': '', 'min': 0, 'description': 'Probability of using a sequence as query'}), 'seed': ('INT', {'default': 1000, 'min': 0, 'description': 'Random seed'}), 'threads': ('INT', {'default': 2, 'min': 1, 'max': 128}), 'max_memory': ('INT', {'default': 1024, 'min': 1, 'description': 'Fallback maximum memory in MB'}), 'log_test': ('BOOLEAN', {'default': False, 'description': 'Return Nonpareil log'}), 'json_object': ('BOOLEAN', {'default': False, 'description': 'Extract Nonpareil curve object as JSON'}), 'summary_label': ('STRING', {'default': '', 'advanced': True, 'description': 'Label used for intermediate summary file'})}, 'hidden': {'output': ('STRING', {})}}
