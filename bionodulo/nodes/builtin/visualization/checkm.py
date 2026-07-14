"""checkm — visualization node(s). One tool per file (extracted from wrapped_assembly_typing.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class CheckMPlotNode(CommandNode):
    """Generate CheckM genome-bin quality assessment plots."""
    NODE_ID = 'checkm_plot'
    DISPLAY_NAME = 'CheckM plot'
    REQUIRED_CONDA_PACKAGES = ['checkm-genome']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Generate CheckM genome-bin quality assessment plots.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'checkm', 'CheckM', 'checkm plot', 'genome bin plots', 'GC plot', 'coding density plot', 'tetranucleotide distance plot', 'marker gene position plot']
    RETURN_TYPES = ('DIRECTORY', 'DIRECTORY', 'DIRECTORY', 'DIRECTORY', 'DIRECTORY', 'DIRECTORY', 'DIRECTORY')
    RETURN_NAMES = ('gc_plot', 'coding_plot', 'tetra_plot', 'dist_plot', 'nx_plot', 'len_hist', 'marker_plot')
    REQUIRED_EXECUTABLES = ['checkm']
    DOCUMENTATION_URL = 'https://github.com/Ecogenomics/CheckM'
    CITATION_DOIS = ['10.1101/gr.186072.114']
    CITATION_URLS = [f'{DOI_URL}10.1101/gr.186072.114']
    CITATION_TEXT = 'CheckM assesses genome completeness and contamination using lineage-specific marker sets.'
    VERSION = '1.2.5+galaxy0'
    SHELL = True
    INPUT_MODES = CheckMLineageWFNode.INPUT_MODES
    PLOT_COMMANDS = ['gc_plot', 'coding_plot', 'tetra_plot', 'dist_plot', 'nx_plot', 'len_hist', 'marker_plot']
    IMAGE_TYPES = ['eps', 'pdf', 'png', 'svg']
    DIST_VALUE_MODES = {'gc_plot', 'coding_plot', 'tetra_plot', 'dist_plot'}
    GFF_MODES = {'coding_plot', 'tetra_plot', 'dist_plot'}
    TETRA_PROFILE_MODES = {'tetra_plot', 'dist_plot'}
    OUTPUT_DIRECTORIES = {'gc_plot': 'gc_plot', 'coding_plot': 'coding_plot', 'tetra_plot': 'tetra_plot', 'dist_plot': 'dist_plot', 'nx_plot': 'nx_plot', 'len_hist': 'len_hist', 'marker_plot': 'marker_plot'}

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return CheckMLineageWFNode._input_files(inputs)

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        return CheckMLineageWFNode._element_identifiers(inputs, input_files)

    @classmethod
    def _link_name(cls, input_mode: str, identifier: str) -> str:
        return CheckMLineageWFNode._link_name(input_mode, identifier)

    @classmethod
    def _as_csv_list(cls, inputs: dict[str, Any], name: str) -> list[str]:
        return CheckMQANode._as_csv_list(inputs, name)

    @classmethod
    def _element_ids_for_files(cls, inputs: dict[str, Any], files: list[str], key: str) -> list[str]:
        return CheckMQANode._element_identifiers(inputs, files, key)

    @classmethod
    def _stage_bins(cls, cmd: list[str], inputs: dict[str, Any], bins_dir: str, output_dir: str) -> None:
        input_files = cls._input_files(inputs)
        input_mode = str(inputs.get('input_mode', inputs.get('select', 'individual')) or 'individual')
        identifiers = cls._element_identifiers(inputs, input_files)
        cmd.extend(['mkdir', '-p', bins_dir, output_dir])
        for input_file, identifier in zip(input_files, identifiers, strict=True):
            cmd.extend(['&&', 'ln', '-sf', input_file, f'{bins_dir}/{cls._link_name(input_mode, identifier)}'])

    @classmethod
    def _stage_gff_inputs(cls, cmd: list[str], inputs: dict[str, Any], inputs_dir: str) -> None:
        gff_files = cls._as_csv_list(inputs, 'gff')
        identifiers = cls._element_ids_for_files(inputs, gff_files, 'gff_element_identifiers')
        for input_file, identifier in zip(gff_files, identifiers, strict=True):
            bin_dir = f'{inputs_dir}/bins/{identifier}'
            cmd.extend(['&&', 'mkdir', '-p', bin_dir, '&&', 'ln', '-sf', input_file, f'{bin_dir}/genes.gff'])

    @classmethod
    def _stage_marker_inputs(cls, cmd: list[str], inputs: dict[str, Any], inputs_dir: str) -> None:
        cmd.extend(['&&', 'mkdir', '-p', f'{inputs_dir}/storage', '&&', 'cp', str(inputs.get('marker_gene_stats', '')), f'{inputs_dir}/storage/marker_gene_stats.tsv', '&&', 'cp', str(inputs.get('bin_stats_ext', '')), f'{inputs_dir}/storage/bin_stats_ext.tsv'])
        genes_files = cls._as_csv_list(inputs, 'genes_fna')
        identifiers = cls._element_ids_for_files(inputs, genes_files, 'genes_element_identifiers')
        for input_file, identifier in zip(genes_files, identifiers, strict=True):
            bin_dir = f'{inputs_dir}/bins/{identifier}'
            cmd.extend(['&&', 'mkdir', '-p', bin_dir, '&&', 'cp', input_file, f'{bin_dir}/genes.faa'])

    @classmethod
    def _add_plot_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['--extension', 'fasta', '--image_type', str(inputs.get('image_type', 'png')), '--dpi', str(inputs.get('dpi', 600)), '--font_size', str(inputs.get('font_size', 8)), '--width', str(inputs.get('width', 6.5)), '--height', str(inputs.get('height', 3.5))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        bins_dir = f'{out}/bins'
        checkm_out = f'{out}/output'
        inputs_dir = f'{out}/inputs'
        plot_command = str(inputs.get('plot_command', inputs.get('command', 'gc_plot')) or 'gc_plot')
        cmd: list[str] = []
        cls._stage_bins(cmd, inputs, bins_dir, checkm_out)
        if plot_command in cls.GFF_MODES:
            cls._stage_gff_inputs(cmd, inputs, inputs_dir)
        elif plot_command == 'marker_plot':
            cls._stage_marker_inputs(cmd, inputs, inputs_dir)
        cmd.extend(['&&', 'checkm', plot_command])
        if plot_command in {'coding_plot', 'tetra_plot', 'dist_plot', 'marker_plot'}:
            cmd.append(inputs_dir)
        cmd.extend([bins_dir, checkm_out])
        if plot_command in {'tetra_plot', 'dist_plot'}:
            cmd.append(str(inputs.get('tetra_profile', '')))
        if plot_command in cls.DIST_VALUE_MODES and str(inputs.get('dist_value', '')) != '':
            cmd.append(str(inputs.get('dist_value')))
        cls._add_plot_options(cmd, inputs)
        if plot_command == 'coding_plot':
            cmd.extend(['--cd_window_size', str(inputs.get('cd_window_size', 10000))])
            cmd.extend(['--cd_bin_width', str(inputs.get('cd_bin_width', 0.01))])
        elif plot_command == 'tetra_plot':
            cmd.extend(['--td_window_size', str(inputs.get('td_window_size', 5000))])
            cmd.extend(['--td_bin_width', str(inputs.get('td_bin_width', 0.01))])
        elif plot_command == 'dist_plot':
            cmd.extend(['--gc_window_size', str(inputs.get('gc_window_size', 5000))])
            cmd.extend(['--gc_bin_width', str(inputs.get('gc_bin_width', 0.01))])
            cmd.extend(['--cd_window_size', str(inputs.get('cd_window_size', 10000))])
            cmd.extend(['--cd_bin_width', str(inputs.get('cd_bin_width', 0.01))])
            cmd.extend(['--td_window_size', str(inputs.get('td_window_size', 5000))])
            cmd.extend(['--td_bin_width', str(inputs.get('td_bin_width', 0.01))])
        elif plot_command == 'nx_plot':
            cmd.extend(['--step_size', str(inputs.get('step_size', 0.05))])
        elif plot_command == 'marker_plot':
            cmd.extend(['--fig_padding', str(inputs.get('fig_padding', 0.2))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        plot_command = str(inputs.get('plot_command', inputs.get('command', 'gc_plot')) or 'gc_plot')
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        directory = out / cls.OUTPUT_DIRECTORIES.get(plot_command, plot_command)
        directory.mkdir(parents=True, exist_ok=True)
        return [directory]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bins': ('FASTA_LIST', {'multiple': True, 'min_items': 1, 'description': 'Genome-bin FASTA files to plot'}), 'plot_command': ('STRING', {'default': 'gc_plot', 'options': cls.PLOT_COMMANDS, 'description': 'CheckM plot command to run'})}, 'optional': {'input_mode': ('STRING', {'default': 'individual', 'options': cls.INPUT_MODES, 'description': 'Galaxy bin input structure used for naming symlinks'}), 'element_identifiers': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Optional Galaxy collection element identifiers for bins'}), 'gff': ('GFF_LIST', {'default': [], 'multiple': True, 'description': 'Gene feature files for coding, tetra, and distribution plots'}), 'gff_element_identifiers': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Optional identifiers for gff entries'}), 'tetra_profile': ('TSV', {'default': '', 'description': 'Tetranucleotide profile from CheckM tetra'}), 'genes_fna': ('FASTA_LIST', {'default': [], 'multiple': True, 'description': 'Nucleotide gene sequences for marker plots'}), 'genes_element_identifiers': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Optional identifiers for genes_fna entries'}), 'marker_gene_stats': ('TSV', {'default': '', 'description': 'Marker gene stats for marker plots'}), 'bin_stats_ext': ('TSV', {'default': '', 'description': 'Extended bin stats for marker plots'}), 'dist_value': ('INT', {'default': '', 'min': 0, 'max': 100, 'description': 'Reference distribution to plot'}), 'image_type': ('STRING', {'default': 'png', 'options': cls.IMAGE_TYPES, 'description': 'Image type'}), 'dpi': ('INT', {'default': 600, 'min': 0, 'description': 'DPI of output image'}), 'font_size': ('INT', {'default': 8, 'min': 0, 'description': 'Font size'}), 'width': ('FLOAT', {'default': 6.5, 'min': 0, 'description': 'Output image width'}), 'height': ('FLOAT', {'default': 3.5, 'min': 0, 'description': 'Output image height'}), 'gc_window_size': ('INT', {'default': 5000, 'min': 0, 'description': 'GC histogram window size'}), 'gc_bin_width': ('FLOAT', {'default': 0.01, 'min': 0, 'description': 'GC histogram bin width'}), 'cd_window_size': ('INT', {'default': 10000, 'min': 0, 'description': 'Coding-density window size'}), 'cd_bin_width': ('FLOAT', {'default': 0.01, 'min': 0, 'description': 'Coding-density bin width'}), 'td_window_size': ('INT', {'default': 5000, 'min': 0, 'description': 'Tetranucleotide-distance window size'}), 'td_bin_width': ('FLOAT', {'default': 0.01, 'min': 0, 'description': 'Tetranucleotide-distance bin width'}), 'step_size': ('FLOAT', {'default': 0.05, 'min': 0, 'description': 'Nx plot step size'}), 'fig_padding': ('FLOAT', {'default': 0.2, 'min': 0, 'description': 'White space around figure in inches'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def _validate_numeric(cls, inputs: dict[str, Any], name: str, default: Any, *, integer: bool) -> bool | str:
        raw = inputs.get(name, default)
        if raw == '':
            return True
        try:
            value = int(raw) if integer else float(raw)
        except (TypeError, ValueError):
            return f"{name} must be {('an integer' if integer else 'a number')}"
        if value < 0:
            return f'{name} must be >= 0'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return 'at least one bins value is required'
        plot_command = str(inputs.get('plot_command', inputs.get('command', 'gc_plot')) or 'gc_plot')
        if plot_command not in cls.PLOT_COMMANDS:
            return f"plot_command must be one of: {', '.join(cls.PLOT_COMMANDS)}"
        input_mode = str(inputs.get('input_mode', inputs.get('select', 'individual')) or 'individual')
        if input_mode not in cls.INPUT_MODES:
            return f"input_mode must be one of: {', '.join(cls.INPUT_MODES)}"
        if plot_command in cls.GFF_MODES and (not cls._as_csv_list(inputs, 'gff')):
            return f'at least one gff value is required for {plot_command}'
        if plot_command in cls.TETRA_PROFILE_MODES and (not str(inputs.get('tetra_profile', '')).strip()):
            return f'tetra_profile is required for {plot_command}'
        if plot_command == 'marker_plot':
            if not cls._as_csv_list(inputs, 'genes_fna'):
                return 'at least one genes_fna value is required for marker_plot'
            for required in ('marker_gene_stats', 'bin_stats_ext'):
                if not str(inputs.get(required, '')).strip():
                    return f'{required} is required for marker_plot'
        image_type = str(inputs.get('image_type', 'png') or 'png')
        if image_type not in cls.IMAGE_TYPES:
            return f"image_type must be one of: {', '.join(cls.IMAGE_TYPES)}"
        for name, default in {'dist_value': '', 'dpi': 600, 'font_size': 8, 'gc_window_size': 5000, 'cd_window_size': 10000, 'td_window_size': 5000}.items():
            result = cls._validate_numeric(inputs, name, default, integer=True)
            if result is not True:
                return result
        for name, default in {'width': 6.5, 'height': 3.5, 'gc_bin_width': 0.01, 'cd_bin_width': 0.01, 'td_bin_width': 0.01, 'step_size': 0.05, 'fig_padding': 0.2}.items():
            result = cls._validate_numeric(inputs, name, default, integer=False)
            if result is not True:
                return result
        return True
