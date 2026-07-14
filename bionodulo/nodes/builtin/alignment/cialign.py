"""cialign — alignment node(s). One tool per file (extracted from wrapped_sequence_visualization.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class CIAlignNode(CommandNode):
    """Clean, visualise, and interpret multiple sequence alignments with CIAlign."""
    NODE_ID = 'cialign'
    DISPLAY_NAME = 'CIAlign'
    REQUIRED_CONDA_PACKAGES = ['cialign']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Clean, visualise, and interpret multiple sequence alignments with CIAlign.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'CIAlign', 'cialign', 'multiple sequence alignment', 'MSA cleaning', 'alignment visualisation', 'alignment interpretation', 'sequence logo', 'consensus sequence', 'position weight matrix']
    RETURN_TYPES = ('FASTA', 'TXT', 'TXT', 'IMAGE', 'IMAGE', 'IMAGE', 'IMAGE', 'IMAGE', 'IMAGE', 'IMAGE', 'IMAGE', 'DIRECTORY', 'DIRECTORY', 'FASTA', 'FASTA', 'TXT', 'TXT', 'TXT', 'TXT', 'TXT', 'TXT', 'TXT', 'TXT', 'TXT', 'TXT', 'TSV', 'TSV', 'TSV', 'TSV', 'FASTA', 'FASTA', 'FASTA', 'FASTA', 'FASTA', 'FASTA')
    RETURN_NAMES = ('output_cleaned', 'output_removed', 'output_log', 'plot_input', 'plot_output', 'plot_markup', 'plot_markup_legend', 'plot_consensus_identity', 'plot_consensus_similarity', 'logo_bar', 'logo_text', 'plot_stats_input', 'plot_stats_outputs', 'output_consensus', 'output_with_consensus', 'pwm_input', 'ppm_input', 'pfm_input', 'ppm_meme_input', 'blamm_input', 'pwm_output', 'ppm_output', 'pfm_output', 'ppm_meme_output', 'blamm_output', 'input_similarity', 'output_similarity', 'output_output_column_stats', 'output_input_column_stats', 'U_input', 'T_input', 'U_output', 'T_output', 'unaligned_input', 'unaligned_output')
    REQUIRED_EXECUTABLES = ['CIAlign', 'gunzip']
    DOCUMENTATION_URL = 'https://github.com/KatyBrown/CIAlign'
    CITATION_DOIS = [CIALIGN_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CIALIGN_CITATION_DOI}']
    CITATION_TEXT = CIALIGN_CITATION_TEXT
    VERSION = '1.1.4+galaxy1'
    SHELL = True
    SEQUENCE_LOGO_TYPES = ['bar', 'text', 'both']
    CONSENSUS_TYPES = ['majority', 'majority_nongap']
    SIMMATRIX_KEEPGAPS = ['0', '1', '2']
    DUPORDERS = ['first', 'last']
    SUB_MATRIX_NAMES = ['BLOSUM62', 'NUC.4.4']
    PALETTES = ['CBS']
    PWM_FREQTYPES = ['user', 'equal', 'calc', 'calc2']
    PWM_ALPHATYPES = ['user', 'calc']

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {'', 'false', '0', 'no', 'off'}
        return bool(value)

    @staticmethod
    def _values(value: Any) -> list[str]:
        return _as_list(value)

    @classmethod
    def _add_bool(cls, cmd: list[str], inputs: dict[str, Any], key: str, flag: str | None=None) -> None:
        if cls._bool_flag(inputs.get(key, False)):
            cmd.append(flag or f'--{key}')

    @classmethod
    def _add_list(cls, cmd: list[str], inputs: dict[str, Any], key: str, flag: str) -> None:
        for value in cls._values(inputs.get(key)):
            cmd.extend([flag, value])

    @classmethod
    def _has_any(cls, inputs: dict[str, Any], keys: list[str]) -> bool:
        return any((cls._bool_flag(inputs.get(key, False)) for key in keys))

    @classmethod
    def _basic_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        for key in ['all', 'clean', 'visualise', 'interpret']:
            cls._add_bool(cmd, inputs, key)

    @classmethod
    def _cleaning_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._bool_flag(inputs.get('remove_divergent', False)):
            cmd.extend(['--remove_divergent', '--remove_divergent_minperc', str(inputs.get('remove_divergent_minperc', 0.65))])
            cls._add_list(cmd, inputs, 'remove_divergent_retain', '--remove_divergent_retain')
            cls._add_list(cmd, inputs, 'remove_divergent_retain_str', '--remove_divergent_retain_str')
        if cls._bool_flag(inputs.get('remove_insertions', False)):
            cmd.extend(['--remove_insertions', '--insertion_min_size', str(inputs.get('insertion_min_size', 3)), '--insertion_max_size', str(inputs.get('insertion_max_size', 200)), '--insertion_min_flank', str(inputs.get('insertion_min_flank', 5)), '--insertion_min_perc', str(inputs.get('insertion_min_perc', 0.5))])
        if cls._bool_flag(inputs.get('crop_ends', False)):
            cmd.extend(['--crop_ends', '--crop_ends_mingap_perc', str(inputs.get('crop_ends_mingap_perc', 0.05)), '--crop_ends_redefine_perc', str(inputs.get('crop_ends_redefine_perc', 0.1))])
            cls._add_list(cmd, inputs, 'crop_ends_retain', '--crop_ends_retain')
            cls._add_list(cmd, inputs, 'crop_ends_retain_str', '--crop_ends_retain_str')
        if cls._bool_flag(inputs.get('remove_short', False)):
            cmd.extend(['--remove_short', '--remove_min_length', str(inputs.get('remove_min_length', 50))])
            cls._add_list(cmd, inputs, 'remove_short_retain', '--remove_short_retain')
            cls._add_list(cmd, inputs, 'remove_short_retain_str', '--remove_short_retain_str')
        if cls._bool_flag(inputs.get('crop_divergent', False)):
            cmd.extend(['--crop_divergent', '--crop_divergent_min_prop_ident', str(inputs.get('crop_divergent_min_prop_ident', 0.5)), '--crop_divergent_min_prop_nongap', str(inputs.get('crop_divergent_min_prop_nongap', 0.5)), '--crop_divergent_buffer_size', str(inputs.get('crop_divergent_buffer_size', 5))])
        cls._add_list(cmd, inputs, 'retain', '--retain')
        cls._add_list(cmd, inputs, 'retain_str', '--retain_str')
        cls._add_bool(cmd, inputs, 'keep_gaponly')

    @classmethod
    def _visualisation_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        for key in ['plot_input', 'plot_output', 'plot_markup', 'plot_consensus_identity', 'plot_consensus_similarity']:
            cls._add_bool(cmd, inputs, key)
        if cls._bool_flag(inputs.get('output_settings', False)):
            cmd.extend(['--plot_width', str(inputs.get('plot_width', 5)), '--plot_height', str(inputs.get('plot_height', 3)), '--plot_dpi', str(inputs.get('plot_dpi', 300))])
            cls._add_bool(cmd, inputs, 'plot_keep_numbers')
            cls._add_bool(cmd, inputs, 'plot_force_numbers')
            cmd.extend(['--plot_identity_palette', str(inputs.get('plot_identity_palette', 'bone')), '--plot_identity_gap_col', str(inputs.get('plot_identity_gap_col', '#ffffff')), '--plot_similarity_palette', str(inputs.get('plot_similarity_palette', 'bone')), '--plot_similarity_gap_col', str(inputs.get('plot_similarity_gap_col', '#ffffff')), '--plot_sub_matrix_name', str(inputs.get('plot_sub_matrix_name', 'NUC.4.4')), '--palette', str(inputs.get('palette', 'CBS'))])
        if cls._bool_flag(inputs.get('make_sequence_logo', False)):
            cmd.extend(['--make_sequence_logo', '--sequence_logo_type', str(inputs.get('sequence_logo_type', 'text')), '--sequence_logo_dpi', str(inputs.get('sequence_logo_dpi', 300)), '--sequence_logo_font', str(inputs.get('sequence_logo_font', 'monospace')), '--sequence_logo_nt_per_row', str(inputs.get('sequence_logo_nt_per_row', 50))])
            _add_if_value(cmd, '--logo_start', inputs.get('logo_start'))
            _add_if_value(cmd, '--logo_end', inputs.get('logo_end'))
        stats_requested = cls._has_any(inputs, ['plot_stats_input', 'plot_stats_output'])
        cls._add_bool(cmd, inputs, 'plot_stats_input')
        cls._add_bool(cmd, inputs, 'plot_stats_output')
        if stats_requested:
            cmd.extend(['--plot_stats_dpi', str(inputs.get('plot_stats_dpi', 300)), '--plot_stats_height', str(inputs.get('plot_stats_width', 5)), '--plot_stats_width', str(inputs.get('plot_stats_height', 3)), '--plot_stats_colour', str(inputs.get('plot_stats_colour', '#0000ff'))])

    @classmethod
    def _interpretation_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._bool_flag(inputs.get('make_consensus', False)):
            cmd.extend(['--make_consensus', '--consensus_type', str(inputs.get('consensus_type', 'majority'))])
            cls._add_bool(cmd, inputs, 'consensus_keep_gaps')
        cls._add_bool(cmd, inputs, 'pwm_input')
        cls._add_bool(cmd, inputs, 'pwm_output')
        _add_if_value(cmd, '--pwm_start', inputs.get('pwm_start'))
        _add_if_value(cmd, '--pwm_end', inputs.get('pwm_end'))
        if cls._has_any(inputs, ['pwm_input', 'pwm_output']):
            cmd.extend(['--pwm_freqtype', str(inputs.get('pwm_freqtype', 'equal')), '--pwm_alphatype', str(inputs.get('pwm_alphatype', 'calc')), '--pwm_alphaval', str(inputs.get('pwm_alphaval', 1))])
        cls._add_bool(cmd, inputs, 'pwm_output_blamm')
        cls._add_bool(cmd, inputs, 'pwm_output_meme')
        sim_requested = cls._has_any(inputs, ['make_similarity_matrix_input', 'make_similarity_matrix_output'])
        cls._add_bool(cmd, inputs, 'make_similarity_matrix_input')
        cls._add_bool(cmd, inputs, 'make_similarity_matrix_output')
        if sim_requested:
            cmd.extend(['--make_simmatrix_keepgaps', str(inputs.get('make_simmatrix_keepgaps', '0')), '--make_simmatrix_dp', str(inputs.get('make_simmatrix_dp', 4)), '--make_simmatrix_minoverlap', str(inputs.get('make_simmatrix_minoverlap', 1))])

    @classmethod
    def _editing_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._bool_flag(inputs.get('get_section', False)):
            cmd.extend(['--get_section', '--section_start', str(inputs.get('section_start', '')), '--section_end', str(inputs.get('section_end', ''))])
        for key in ['replace_input_tu', 'replace_input_ut', 'replace_output_tu', 'replace_output_ut', 'unalign_input', 'unalign_output', 'deduplicate_ids']:
            cls._add_bool(cmd, inputs, key)
        if cls._bool_flag(inputs.get('deduplicate_ids', False)):
            cmd.extend(['--duporder', str(inputs.get('duporder', 'first'))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        setup = [_shell_join(['mkdir', '-p', out]), f'cd {shlex.quote(out)}']
        infile = str(inputs.get('input', ''))
        if cls._bool_flag(inputs.get('input_is_gz', False)):
            setup.append(f"{_shell_join(['gunzip', '-c', infile])} > input.fasta")
            infile = 'input.fasta'
        cmd = ['CIAlign', '--infile', infile, '--outfile_stem', 'output']
        cls._basic_args(cmd, inputs)
        cls._cleaning_args(cmd, inputs)
        cls._visualisation_args(cmd, inputs)
        cls._interpretation_args(cmd, inputs)
        cls._editing_args(cmd, inputs)
        setup.append(_shell_join(cmd))
        return ' && '.join(setup)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'output_cleaned.fasta', out / 'output_removed.txt']
        if cls._bool_flag(inputs.get('log_out', False)):
            outputs.append(out / 'output_log.txt')
        all_mode = cls._bool_flag(inputs.get('all', False))
        visualise = cls._bool_flag(inputs.get('visualise', False))
        interpret = cls._bool_flag(inputs.get('interpret', False))
        if cls._bool_flag(inputs.get('plot_input', False)) or visualise or all_mode:
            outputs.append(out / 'output_input.png')
        if cls._bool_flag(inputs.get('plot_output', False)) or visualise or all_mode:
            outputs.append(out / 'output_output.png')
        if cls._bool_flag(inputs.get('plot_markup', False)) or visualise or all_mode:
            outputs.extend([out / 'output_markup.png', out / 'output_markup_legend.png'])
        if cls._bool_flag(inputs.get('plot_consensus_identity', False)) or all_mode:
            outputs.append(out / 'output_consensus_identity.png')
        if cls._bool_flag(inputs.get('plot_consensus_similarity', False)):
            outputs.append(out / 'output_consensus_similarity.png')
        logo_type = str(inputs.get('sequence_logo_type', 'text') or 'text')
        if cls._bool_flag(inputs.get('make_sequence_logo', False)):
            if logo_type in {'bar', 'both'}:
                outputs.append(out / 'output_logo_bar.png')
            if logo_type in {'text', 'both'}:
                outputs.append(out / 'output_logo_text.png')
        if cls._bool_flag(inputs.get('plot_stats_input', False)) or interpret or all_mode:
            outputs.append(out / 'input_stats_plots')
        if cls._bool_flag(inputs.get('plot_stats_output', False)) or interpret or all_mode:
            outputs.append(out / 'output_stats_plots')
        if cls._bool_flag(inputs.get('make_consensus', False)) or interpret or all_mode:
            outputs.extend([out / 'output_consensus.fasta', out / 'output_with_consensus.fasta'])
        pwm_input = cls._bool_flag(inputs.get('pwm_input', False))
        pwm_output = cls._bool_flag(inputs.get('pwm_output', False))
        if pwm_input:
            outputs.extend([out / 'output_pwm_input.txt', out / 'output_ppm_input.txt', out / 'output_pfm_input.txt'])
            if cls._bool_flag(inputs.get('pwm_output_meme', False)):
                outputs.append(out / 'output_ppm_meme_input.txt')
            if cls._bool_flag(inputs.get('pwm_output_blamm', False)):
                outputs.append(out / 'output_pfm_blamm_input.txt')
        if pwm_output:
            outputs.extend([out / 'output_pwm_output.txt', out / 'output_ppm_output.txt', out / 'output_pfm_output.txt'])
            if cls._bool_flag(inputs.get('pwm_output_meme', False)):
                outputs.append(out / 'output_ppm_meme_output.txt')
            if cls._bool_flag(inputs.get('pwm_output_blamm', False)):
                outputs.append(out / 'output_pfm_blamm_output.txt')
        if cls._bool_flag(inputs.get('make_similarity_matrix_input', False)) or interpret or all_mode:
            outputs.append(out / 'output_input_similarity.tsv')
        if cls._bool_flag(inputs.get('make_similarity_matrix_output', False)) or interpret or all_mode:
            outputs.append(out / 'output_output_similarity.tsv')
        if interpret or all_mode:
            outputs.extend([out / 'output_output_column_stats.tsv', out / 'output_input_column_stats.tsv'])
        for key, filename in {'replace_input_tu': 'output_U_input.fasta', 'replace_input_ut': 'output_T_input.fasta', 'replace_output_tu': 'output_U_output.fasta', 'replace_output_ut': 'output_T_output.fasta', 'unalign_input': 'output_unaligned_input.fasta', 'unalign_output': 'output_unaligned_output.fasta'}.items():
            if cls._bool_flag(inputs.get(key, False)):
                outputs.append(out / filename)
        return outputs

    @classmethod
    def _validate_int_range(cls, inputs: dict[str, Any], key: str, default: int, minimum: int, maximum: int | None=None) -> bool | str:
        value = inputs.get(key, default)
        if str(value) == '':
            return f'{key} is required'
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if parsed < minimum:
            return f'{key} must be greater than or equal to {minimum}' if maximum is None else f'{key} must be between {minimum} and {maximum}'
        if maximum is not None and parsed > maximum:
            return f'{key} must be between {minimum} and {maximum}'
        return True

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], key: str, default: float, minimum: float, maximum: float) -> bool | str:
        try:
            value = float(inputs.get(key, default))
        except (TypeError, ValueError):
            return f'{key} must be numeric'
        if value < minimum or value > maximum:
            return f'{key} must be between {minimum:g} and {maximum:g}'
        return True

    @classmethod
    def _validate_options(cls, inputs: dict[str, Any], key: str, default: str, options: list[str]) -> bool | str:
        value = str(inputs.get(key, default) or default)
        if value not in options:
            return f"{key} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        for key, default, minimum, maximum in [('remove_divergent_minperc', 0.65, 0.0, 1.0), ('insertion_min_perc', 0.5, 0.0, 1.0), ('crop_ends_mingap_perc', 0.05, 0.0, 0.6), ('crop_ends_redefine_perc', 0.1, 0.0, 0.5), ('crop_divergent_min_prop_ident', 0.5, 0.01, 1.0), ('crop_divergent_min_prop_nongap', 0.5, 0.01, 1.0)]:
            result = cls._validate_float_range(inputs, key, default, minimum, maximum)
            if result is not True:
                return result
        for key, default, minimum, maximum in [('insertion_min_size', 3, 1, None), ('insertion_max_size', 200, 1, 10000), ('insertion_min_flank', 5, 0, None), ('remove_min_length', 50, 0, None), ('crop_divergent_buffer_size', 5, 1, None), ('plot_width', 5, 2, 20), ('plot_height', 3, 2, 15), ('plot_dpi', 300, 72, 1200), ('sequence_logo_dpi', 300, 72, 1200), ('sequence_logo_nt_per_row', 50, 1, None), ('plot_stats_dpi', 300, 72, 1200), ('plot_stats_width', 5, 2, 20), ('plot_stats_height', 3, 2, 15), ('pwm_alphaval', 1, 0, None), ('make_simmatrix_dp', 4, 0, 10), ('make_simmatrix_minoverlap', 1, 1, None)]:
            result = cls._validate_int_range(inputs, key, default, minimum, maximum)
            if result is not True:
                return result
        for key, options, default in [('sequence_logo_type', cls.SEQUENCE_LOGO_TYPES, 'text'), ('consensus_type', cls.CONSENSUS_TYPES, 'majority'), ('make_simmatrix_keepgaps', cls.SIMMATRIX_KEEPGAPS, '0'), ('duporder', cls.DUPORDERS, 'first'), ('plot_sub_matrix_name', cls.SUB_MATRIX_NAMES, 'NUC.4.4'), ('palette', cls.PALETTES, 'CBS'), ('pwm_freqtype', cls.PWM_FREQTYPES, 'equal'), ('pwm_alphatype', cls.PWM_ALPHATYPES, 'calc')]:
            result = cls._validate_options(inputs, key, default, options)
            if result is not True:
                return result
        if cls._bool_flag(inputs.get('get_section', False)):
            for key in ['section_start', 'section_end']:
                if str(inputs.get(key, '')).strip() == '':
                    return f'{key} is required when get_section is enabled'
                result = cls._validate_int_range(inputs, key, 1, 1)
                if result is not True:
                    return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTA', {'description': 'Multiple sequence alignment in FASTA or compressed FASTA format'})}, 'optional': {'input_is_gz': ('BOOLEAN', {'default': False, 'description': 'Input FASTA is gzip-compressed'}), 'all': ('BOOLEAN', {'default': False, 'description': 'Enable all CIAlign functions'}), 'clean': ('BOOLEAN', {'default': False, 'description': 'Enable all cleaning functions'}), 'visualise': ('BOOLEAN', {'default': False, 'description': 'Enable all visualisation functions'}), 'interpret': ('BOOLEAN', {'default': False, 'description': 'Enable all interpretation functions'}), 'log_out': ('BOOLEAN', {'default': False, 'description': 'Plan CIAlign log output'}), 'remove_divergent': ('BOOLEAN', {'default': False}), 'remove_divergent_minperc': ('FLOAT', {'default': 0.65, 'min': 0, 'max': 1}), 'remove_divergent_retain': ('STRING', {'default': [], 'is_list': True}), 'remove_divergent_retain_str': ('STRING', {'default': [], 'is_list': True}), 'remove_insertions': ('BOOLEAN', {'default': False}), 'insertion_min_size': ('INT', {'default': 3, 'min': 1}), 'insertion_max_size': ('INT', {'default': 200, 'min': 1, 'max': 10000}), 'insertion_min_flank': ('INT', {'default': 5, 'min': 0}), 'insertion_min_perc': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 1}), 'crop_ends': ('BOOLEAN', {'default': False}), 'crop_ends_mingap_perc': ('FLOAT', {'default': 0.05, 'min': 0, 'max': 0.6}), 'crop_ends_redefine_perc': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 0.5}), 'crop_ends_retain': ('STRING', {'default': [], 'is_list': True}), 'crop_ends_retain_str': ('STRING', {'default': [], 'is_list': True}), 'remove_short': ('BOOLEAN', {'default': False}), 'remove_min_length': ('INT', {'default': 50, 'min': 0}), 'remove_short_retain': ('STRING', {'default': [], 'is_list': True}), 'remove_short_retain_str': ('STRING', {'default': [], 'is_list': True}), 'crop_divergent': ('BOOLEAN', {'default': False}), 'crop_divergent_min_prop_ident': ('FLOAT', {'default': 0.5, 'min': 0.01, 'max': 1}), 'crop_divergent_min_prop_nongap': ('FLOAT', {'default': 0.5, 'min': 0.01, 'max': 1}), 'crop_divergent_buffer_size': ('INT', {'default': 5, 'min': 1}), 'retain': ('STRING', {'default': [], 'is_list': True}), 'retain_str': ('STRING', {'default': [], 'is_list': True}), 'keep_gaponly': ('BOOLEAN', {'default': False}), 'plot_input': ('BOOLEAN', {'default': False}), 'plot_output': ('BOOLEAN', {'default': False}), 'plot_markup': ('BOOLEAN', {'default': False}), 'plot_consensus_identity': ('BOOLEAN', {'default': False}), 'plot_consensus_similarity': ('BOOLEAN', {'default': False}), 'output_settings': ('BOOLEAN', {'default': False}), 'plot_width': ('INT', {'default': 5, 'min': 2, 'max': 20}), 'plot_height': ('INT', {'default': 3, 'min': 2, 'max': 15}), 'plot_dpi': ('INT', {'default': 300, 'min': 72, 'max': 1200}), 'plot_keep_numbers': ('BOOLEAN', {'default': False}), 'plot_force_numbers': ('BOOLEAN', {'default': False}), 'plot_identity_palette': ('STRING', {'default': 'bone'}), 'plot_identity_gap_col': ('STRING', {'default': '#ffffff'}), 'plot_similarity_palette': ('STRING', {'default': 'bone'}), 'plot_similarity_gap_col': ('STRING', {'default': '#ffffff'}), 'plot_sub_matrix_name': ('STRING', {'default': 'NUC.4.4', 'options': cls.SUB_MATRIX_NAMES}), 'palette': ('STRING', {'default': 'CBS', 'options': cls.PALETTES}), 'make_sequence_logo': ('BOOLEAN', {'default': False}), 'sequence_logo_type': ('STRING', {'default': 'text', 'options': cls.SEQUENCE_LOGO_TYPES}), 'sequence_logo_dpi': ('INT', {'default': 300, 'min': 72, 'max': 1200}), 'sequence_logo_font': ('STRING', {'default': 'monospace'}), 'sequence_logo_nt_per_row': ('INT', {'default': 50, 'min': 1}), 'logo_start': ('INT', {'default': '', 'min': 1}), 'logo_end': ('INT', {'default': '', 'min': 1}), 'plot_stats_input': ('BOOLEAN', {'default': False}), 'plot_stats_output': ('BOOLEAN', {'default': False}), 'plot_stats_dpi': ('INT', {'default': 300, 'min': 72, 'max': 1200}), 'plot_stats_width': ('INT', {'default': 5, 'min': 2, 'max': 20}), 'plot_stats_height': ('INT', {'default': 3, 'min': 2, 'max': 15}), 'plot_stats_colour': ('STRING', {'default': '#0000ff'}), 'make_consensus': ('BOOLEAN', {'default': False}), 'consensus_type': ('STRING', {'default': 'majority', 'options': cls.CONSENSUS_TYPES}), 'consensus_keep_gaps': ('BOOLEAN', {'default': False}), 'pwm_input': ('BOOLEAN', {'default': False}), 'pwm_output': ('BOOLEAN', {'default': False}), 'pwm_start': ('INT', {'default': '', 'min': 1}), 'pwm_end': ('INT', {'default': '', 'min': 1}), 'pwm_freqtype': ('STRING', {'default': 'equal', 'options': cls.PWM_FREQTYPES}), 'pwm_alphatype': ('STRING', {'default': 'calc', 'options': cls.PWM_ALPHATYPES}), 'pwm_alphaval': ('INT', {'default': 1, 'min': 0}), 'pwm_output_blamm': ('BOOLEAN', {'default': False}), 'pwm_output_meme': ('BOOLEAN', {'default': False}), 'make_similarity_matrix_input': ('BOOLEAN', {'default': False}), 'make_similarity_matrix_output': ('BOOLEAN', {'default': False}), 'make_simmatrix_keepgaps': ('STRING', {'default': '0', 'options': cls.SIMMATRIX_KEEPGAPS}), 'make_simmatrix_dp': ('INT', {'default': 4, 'min': 0, 'max': 10}), 'make_simmatrix_minoverlap': ('INT', {'default': 1, 'min': 1}), 'get_section': ('BOOLEAN', {'default': False}), 'section_start': ('INT', {'default': '', 'min': 1}), 'section_end': ('INT', {'default': '', 'min': 1}), 'replace_input_tu': ('BOOLEAN', {'default': False}), 'replace_input_ut': ('BOOLEAN', {'default': False}), 'replace_output_tu': ('BOOLEAN', {'default': False}), 'replace_output_ut': ('BOOLEAN', {'default': False}), 'unalign_input': ('BOOLEAN', {'default': False}), 'unalign_output': ('BOOLEAN', {'default': False}), 'deduplicate_ids': ('BOOLEAN', {'default': False}), 'duporder': ('STRING', {'default': 'first', 'options': cls.DUPORDERS})}, 'hidden': {'output': ('STRING', {})}}
