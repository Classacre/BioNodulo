"""cherri — rna_seq node(s). One tool per file (extracted from wrapped_assembly_typing.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class CheRRIEvalNode(CommandNode):
    """Evaluate RNA-RNA interaction sites with CheRRI."""
    NODE_ID = 'cherri_eval'
    DISPLAY_NAME = 'Evaluation of RRIs using CheRRI'
    REQUIRED_CONDA_PACKAGES = ['cherri']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Evaluate RNA-RNA interaction sites with a trained CheRRI model.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'CheRRI', 'cherri_eval', 'cherri eval', 'RNA-RNA interaction', 'RRI evaluation', 'interaction site filtering', 'IntaRNA']
    RETURN_TYPES = ('CSV',)
    RETURN_NAMES = ('eval_out',)
    REQUIRED_EXECUTABLES = ['cherri', 'tar']
    DOCUMENTATION_URL = CHERRI_DOCUMENTATION_URL
    CITATION_URLS = [CHERRI_CITATION_URL]
    CITATION_TEXT = CHERRI_CITATION_TEXT
    VERSION = '0.7'
    SHELL = True

    @classmethod
    def _on_off(cls, value: Any, default: bool) -> str:
        if value is None:
            return 'on' if default else 'off'
        if isinstance(value, str):
            return 'off' if value.lower() in {'false', '0', 'no', 'off', ''} else 'on'
        return 'on' if bool(value) else 'off'

    @classmethod
    def _context(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('context', 150))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ['cherri', 'eval', '-i1', str(inputs.get('rris_table', '')), '-g', 'genome.fa', '-l', str(inputs.get('chrom_len_file', '')), '-o', '.', '-on', cls.NODE_ID, '-c', cls._context(inputs), '-st', cls._on_off(inputs.get('use_structure'), True), '-hf', cls._on_off(inputs.get('hand_feat'), False), '-m', 'model_dir/final_full.model', '-mp', 'model_dir/features.npz']
        _add_if_value(cmd, '-i2', inputs.get('occupied_regions'))
        _add_if_value(cmd, '-p', inputs.get('intarna_param_file'))
        setup = [_shell_join(['mkdir', '-p', out]), f'cd {shlex.quote(out)}', 'export PYTHONHASHSEED=31337', _shell_join(['ln', '-s', str(inputs.get('genome_fasta', '')), 'genome.fa']), _shell_join(['mkdir', 'model_dir']), f"{_shell_join(['tar', '-C', 'model_dir', '-xvf', str(inputs.get('model_tar', ''))])} > /dev/null", _shell_join(cmd)]
        return ' && '.join(setup)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / cls.NODE_ID / 'evaluation'
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'evaluation_results_eval_rri.csv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'rris_table': ('CSV', {'description': 'CSV table of RNA-RNA interactions'}), 'genome_fasta': ('FASTA', {'description': 'Reference genome FASTA'}), 'chrom_len_file': ('TSV', {'description': 'Two-column chromosome length table'}), 'model_tar': ('FILE', {'description': 'CheRRI model and feature files tarball'})}, 'optional': {'context': ('INT', {'default': 150, 'min': 0}), 'use_structure': ('BOOLEAN', {'default': True}), 'hand_feat': ('BOOLEAN', {'default': False}), 'occupied_regions': ('FILE', {'default': '', 'description': 'Optional occupied-region Python object file'}), 'intarna_param_file': ('TXT', {'default': '', 'description': 'Optional IntaRNA parameter file'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for required in ('rris_table', 'genome_fasta', 'chrom_len_file', 'model_tar'):
            if not str(inputs.get(required, '')).strip():
                return f'{required} is required'
        try:
            context = int(inputs.get('context', 150))
        except (TypeError, ValueError):
            return 'context must be an integer'
        if context < 0:
            return 'context must be greater than or equal to 0'
        return True


class CheRRITrainNode(CommandNode):
    """Train a CheRRI model from RNA-RNA interaction summary files."""
    NODE_ID = 'cherri_train'
    DISPLAY_NAME = 'Train a CheRRI model using RRIs'
    REQUIRED_CONDA_PACKAGES = ['cherri']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Train a CheRRI model from RNA-RNA interaction summary files.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'CheRRI', 'cherri_train', 'cherri train', 'RNA-RNA interaction', 'RRI model training', 'ChiRA interaction summary', 'mixed model', 'IntaRNA']
    RETURN_TYPES = ('TGZ',)
    RETURN_NAMES = ('out_model',)
    REQUIRED_EXECUTABLES = ['cherri', 'tar']
    DOCUMENTATION_URL = CHERRI_DOCUMENTATION_URL
    CITATION_URLS = [CHERRI_CITATION_URL]
    CITATION_TEXT = CHERRI_CITATION_TEXT
    VERSION = '0.7+galaxy0'
    SHELL = True

    @classmethod
    def _context(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('context', 150))

    @classmethod
    def _run_time(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('run_time', 43200))

    @classmethod
    def _on_off(cls, value: Any, default: bool) -> str:
        return CheRRIEvalNode._on_off(value, default)

    @classmethod
    def _safe_experiment_name(cls, value: Any) -> str:
        name = re.sub('[^0-9A-Za-z_]', '_', str(value or 'myExperiment'))
        return name or 'myExperiment'

    @classmethod
    def _experiments(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        experiments = inputs.get('experiments')
        if isinstance(experiments, str) and experiments.strip():
            parsed = json.loads(experiments)
            if isinstance(parsed, list):
                experiments = parsed
        if isinstance(experiments, (list, tuple)) and experiments:
            normalized: list[dict[str, Any]] = []
            for index, experiment in enumerate(experiments):
                if isinstance(experiment, dict):
                    normalized.append(dict(experiment))
                else:
                    normalized.append({'exp_name': f'experiment_{index + 1}', 'rep_samples': [str(experiment)]})
            return normalized
        return [{'exp_name': inputs.get('experiment_name', 'myExperiment'), 'genome_fasta': inputs.get('genome_fasta', ''), 'chrom_len_file': inputs.get('chrom_len_file', ''), 'rep_samples': inputs.get('rep_samples', []), 'occupied_regions': inputs.get('occupied_regions', '')}]

    @classmethod
    def _common_params(cls, inputs: dict[str, Any]) -> list[str]:
        cmd: list[str] = []
        _add_if_value(cmd, '-p', inputs.get('intarna_param_file'))
        cmd.extend(['-c', cls._context(inputs), '-st', cls._on_off(inputs.get('use_structure'), True), '-t', cls._run_time(inputs), '-me', '${GALAXY_MEMORY_MB_PER_SLOT:-8000}', '-j', '${GALAXY_SLOTS:-1}'])
        if cls._on_off(inputs.get('filter_hybrid'), False) == 'on':
            cmd.extend(['-f', 'on'])
        return cmd

    @classmethod
    def _experiment_commands(cls, experiment: dict[str, Any], inputs: dict[str, Any], mixed: bool) -> tuple[str, list[str]]:
        exp_name = cls._safe_experiment_name(experiment.get('exp_name', experiment.get('experiment_name', 'myExperiment')))
        rep_samples = _as_list(experiment.get('rep_samples', experiment.get('samples', experiment.get('files'))))
        commands = [_shell_join(['mkdir', exp_name]), _shell_join(['mkdir', f'{exp_name}/tmp']), _shell_join(['ln', '-s', str(experiment.get('genome_fasta', '')), f'{exp_name}/genome.fa'])]
        replicate_names: list[str] = []
        for index, sample in enumerate(rep_samples):
            replicate_name = f'{index}.tabular'
            replicate_names.append(replicate_name)
            commands.append(_shell_join(['ln', '-s', sample, f'{exp_name}/{replicate_name}']))
        cmd = ['cherri', 'train', '-i1', exp_name, '-r', *replicate_names, '-g', f'{exp_name}/genome.fa', '-l', str(experiment.get('chrom_len_file', '')), '-n', exp_name]
        _add_if_value(cmd, '-i2', experiment.get('occupied_regions'))
        cmd.extend(['-o', '.', '-on', exp_name, '-tp', f'{exp_name}/tmp'])
        cmd.extend(cls._common_params(inputs))
        commands.append(_shell_join(cmd).replace("'${GALAXY_MEMORY_MB_PER_SLOT:-8000}'", '${GALAXY_MEMORY_MB_PER_SLOT:-8000}').replace("'${GALAXY_SLOTS:-1}'", '${GALAXY_SLOTS:-1}'))
        if mixed:
            commands.extend([_shell_join(['mkdir', '-p', 'mixed_model']), _shell_join(['ln', '-s', f'../{exp_name}', f'mixed_model/{exp_name}'])])
        return (exp_name, commands)

    @classmethod
    def _single_model_links(cls, exp_name: str, inputs: dict[str, Any]) -> list[str]:
        context = cls._context(inputs)
        commands = [_shell_join(['ln', '-s', f'{exp_name}/model/optimized/full_{exp_name}_context_{context}.model', 'final_full.model'])]
        if cls._on_off(inputs.get('use_structure'), True) == 'off':
            feature_path = f'{exp_name}/model/features/{exp_name}_context_{context}.npz'
        else:
            feature_path = f'{exp_name}/feature_files/training_data_{exp_name}_context_{context}.npz'
        commands.append(_shell_join(['ln', '-s', feature_path, 'features.npz']))
        return commands

    @classmethod
    def _mixed_model_commands(cls, exp_names: list[str], inputs: dict[str, Any]) -> list[str]:
        context = cls._context(inputs)
        cmd = ['cherri', 'train', '-mi', 'on', '-i1', 'mixed_model', '-r', *exp_names, '-g', '/not/needed/', '-l', '/not/needed/', '-n', 'mixed', '-o', '.', '-on', 'mixed_model', '-tp', 'mixed_model/tmp']
        cmd.extend(cls._common_params(inputs))
        command = _shell_join(cmd).replace("'${GALAXY_MEMORY_MB_PER_SLOT:-8000}'", '${GALAXY_MEMORY_MB_PER_SLOT:-8000}').replace("'${GALAXY_SLOTS:-1}'", '${GALAXY_SLOTS:-1}')
        commands = [_shell_join(['mkdir', 'mixed_model/tmp']), command]
        commands.append(_shell_join(['ln', '-s', f'mixed_model/mixed/model/optimized/full_mixed_context_{context}.model', 'final_full.model']))
        if cls._on_off(inputs.get('use_structure'), True) == 'off':
            feature_path = f'mixed_model/mixed/model/features/mixed_context_{context}.npz'
        else:
            feature_path = f'mixed_model/mixed/feature_files/training_data_mixed_context_{context}.npz'
        commands.append(_shell_join(['ln', '-s', feature_path, 'features.npz']))
        return commands

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        experiments = cls._experiments(inputs)
        mixed = len(experiments) > 1
        commands = [_shell_join(['mkdir', '-p', out]), f'cd {shlex.quote(out)}', 'export PYTHONHASHSEED=31337']
        exp_names: list[str] = []
        for experiment in experiments:
            exp_name, experiment_commands = cls._experiment_commands(experiment, inputs, mixed)
            exp_names.append(exp_name)
            commands.extend(experiment_commands)
        if mixed:
            commands.extend(cls._mixed_model_commands(exp_names, inputs))
        else:
            commands.extend(cls._single_model_links(exp_names[0], inputs))
        commands.append(_shell_join(['tar', '-zhcvf', 'model.tgz', 'final_full.model', 'features.npz']))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'model.tgz']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'optional': {'experiments': ('JSON', {'default': [], 'is_list': True, 'description': 'Experiment objects with exp_name, genome_fasta, chrom_len_file, rep_samples, and optional occupied_regions'}), 'experiment_name': ('STRING', {'default': 'myExperiment'}), 'genome_fasta': ('FASTA', {'default': ''}), 'chrom_len_file': ('TSV', {'default': ''}), 'rep_samples': ('TSV', {'default': [], 'is_list': True}), 'occupied_regions': ('BED', {'default': ''}), 'context': ('INT', {'default': 150, 'min': 0}), 'intarna_param_file': ('TXT', {'default': ''}), 'use_structure': ('BOOLEAN', {'default': True}), 'run_time': ('INT', {'default': 43200, 'min': 0}), 'filter_hybrid': ('BOOLEAN', {'default': False})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        try:
            experiments = cls._experiments(inputs)
        except json.JSONDecodeError:
            return 'experiments must be valid JSON'
        for index, experiment in enumerate(experiments):
            prefix = f'experiments[{index}].' if inputs.get('experiments') else ''
            if not str(experiment.get('genome_fasta', '')).strip():
                return f'{prefix}genome_fasta is required'
            if not str(experiment.get('chrom_len_file', '')).strip():
                return f'{prefix}chrom_len_file is required'
            if not _as_list(experiment.get('rep_samples', experiment.get('samples', experiment.get('files')))):
                return f'{prefix}at least one rep_samples value is required'
        for name, default in {'context': 150, 'run_time': 43200}.items():
            try:
                value = int(inputs.get(name, default))
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < 0:
                return f'{name} must be greater than or equal to 0'
        return True
