"""baredsc — single_cell node(s). One tool per file (extracted from wrapped_core_data.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *
class _DatamashBaseNode(CommandNode):
    """Shared metadata and helpers for GNU Datamash Galaxy wrappers."""
    REQUIRED_CONDA_PACKAGES = ['datamash']
    CATEGORY = 'data_transform'
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('out_file',)
    DOCUMENTATION_URL = DATAMASH_DOCUMENTATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [DATAMASH_CITATION_URL]
    CITATION_TEXT = DATAMASH_CITATION_TEXT
    VERSION = '1.9'
    SHELL = True
    INPUT_EXT_OPTIONS = ['tabular', 'tsv', 'csv']

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_ext', 'tabular') or 'tabular')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out_file.tsv'

    @classmethod
    def _separator_args(cls, inputs: dict[str, Any]) -> list[str]:
        return ['-t', ','] if cls._input_ext(inputs) == 'csv' else []

    @classmethod
    def _redirect_stdin_stdout(cls, cmd: list[str], inputs: dict[str, Any]) -> str:
        cmd.extend(['>', cls._output_path(inputs)])
        input_file = shlex.quote(str(inputs.get('in_file', '')))
        return _shell_join(cmd).replace(' > ', f' < {input_file} > ')

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out_file.tsv']

    @classmethod
    def _validate_common(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('in_file', '')).strip():
            return 'in_file is required'
        input_ext = cls._input_ext(inputs)
        if input_ext not in cls.INPUT_EXT_OPTIONS:
            return f"input_ext must be one of: {', '.join(cls.INPUT_EXT_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('TSV', {'description': 'Input tabular, TSV, or CSV dataset'})}, 'optional': {'input_ext': ('STRING', {'default': 'tabular', 'options': cls.INPUT_EXT_OPTIONS, 'description': 'Input file format'})}, 'hidden': {'output': ('STRING', {})}}


class Baredsc1DNode(CommandNode):
    """Estimate a one-dimensional baredSC expression distribution."""
    NODE_ID = 'baredsc_1d'
    DISPLAY_NAME = 'baredSC 1d'
    REQUIRED_CONDA_PACKAGES = ['baredsc', 'gzip']
    CATEGORY = 'single_cell'
    DESCRIPTION = 'Compute a one-dimensional baredSC expression distribution for a single gene.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'baredSC', 'baredsc_1d', 'baredSC 1d', 'single gene', 'single-cell expression distribution', 'Bayesian Approach', 'probability density function', 'MCMC']
    RETURN_TYPES = ('NPZ', 'TXT', 'DIRECTORY', 'TSV', 'IMAGE', 'DIRECTORY', 'TXT')
    RETURN_NAMES = ('output', 'neff', 'qc_plots', 'pdf', 'plot', 'other_outputs', 'logevidence')
    REQUIRED_EXECUTABLES = ['baredSC_1d', 'mkdir', 'mv', 'gunzip']
    DOCUMENTATION_URL = BAREDSC_DOCUMENTATION_URL
    CITATION_DOIS = [BAREDSC_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{BAREDSC_CITATION_DOI}']
    CITATION_TEXT = BAREDSC_CITATION_TEXT
    VERSION = '1.1.3+galaxy0'
    SHELL = True
    FILETYPES = ['tabular', 'anndata']
    FILTER_COUNTS = ['0', '1', '2', '3']
    SCALE_OPTIONS = ['Seurat', 'log']
    RESTART_OPTIONS = ['yes', 'no']
    IMAGE_FORMATS = ['png', 'svg', 'pdf']

    @classmethod
    def _image_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('image_file_format', 'png') or 'png')

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        return [out / 'output.npz', out / 'output' / 'baredSC_neff.txt', out / 'QC', out / 'output' / 'baredSC_pdf.txt', out / f'baredSC.{cls._image_format(inputs)}', out / 'other_outputs', out / 'logevidence.txt']

    @classmethod
    def _append_required_inputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        filetype = str(inputs.get('filetype', 'tabular') or 'tabular')
        if filetype == 'anndata':
            cmd.extend(['--inputAnnData', str(inputs.get('inputAnnData', '') or '')])
        else:
            cmd.extend(['--input', str(inputs.get('input', '') or '')])
        cmd.extend(['--geneColName', str(inputs.get('geneColName', '') or '')])

    @classmethod
    def _append_filters(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        count = int(str(inputs.get('filter_nb', '0') or '0'))
        for idx in range(1, count + 1):
            cmd.extend([f'--metadata{idx}ColName', str(inputs.get(f'metadata{idx}ColName', '') or ''), f'--metadata{idx}Values', str(inputs.get(f'metadata{idx}Values', '') or '')])

    @classmethod
    def _append_mcmc(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        scale = str(inputs.get('xscale', 'Seurat') or 'Seurat')
        cmd.extend(['--xmin', str(inputs.get('xmin', 0)), '--xmax', str(inputs.get('xmax', 2.5)), '--xscale', scale])
        if scale == 'Seurat':
            cmd.extend(['--targetSum', str(inputs.get('targetSum', 10000))])
        cmd.extend(['--nx', str(inputs.get('nx', 100)), '--minScale', str(inputs.get('minScalex', 0.1)), '--seed', str(inputs.get('seed', 1)), '--nnorm', str(inputs.get('nnorm', 2)), '--nsampMCMC', str(inputs.get('nsampMCMC', 100000))])
        if str(inputs.get('automatic_restart', 'yes') or 'yes') == 'yes':
            cmd.extend(['--minNeff', str(inputs.get('minNeff', 200))])

    @classmethod
    def _append_plots(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        title = str(inputs.get('title', '') or '')
        if title:
            cmd.extend(['--title', title])
        remove_first = int(inputs.get('removeFirstSamples', -1))
        if remove_first != -1:
            cmd.extend(['--removeFirstSamples', str(remove_first)])
        cmd.extend(['--nsampInPlot', str(inputs.get('nsampInPlot', 100000))])
        pretty_bins = int(inputs.get('prettyBins', -1))
        if pretty_bins != -1:
            cmd.extend(['--prettyBins', str(pretty_bins)])

    @classmethod
    def _append_advanced(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['--osampx', str(inputs.get('osampx', 10)), '--osampxpdf', str(inputs.get('osampxpdf', 5)), '--coviscale', str(inputs.get('coviscale', 1)), '--nis', str(inputs.get('nis', 1000))])
        if str(inputs.get('burn_custom', 'no') or 'no') == 'yes':
            nsamp_burn = int(inputs.get('nsampBurnMCMC', -1))
            if nsamp_burn != -1:
                cmd.extend(['--nsampBurnMCMC', str(nsamp_burn)])
            cmd.extend(['--T0BurnMCMC', str(inputs.get('T0BurnMCMC', 100))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        image_format = cls._image_format(inputs)
        cmd = ['baredSC_1d']
        cls._append_required_inputs(cmd, inputs)
        cls._append_filters(cmd, inputs)
        cls._append_mcmc(cmd, inputs)
        cls._append_plots(cmd, inputs)
        cls._append_advanced(cmd, inputs)
        cmd.extend(['--output', 'output', '--figure', f'baredSC.{image_format}', '--logevidence', 'logevidence.txt'])
        commands = [_shell_join(cmd), 'mkdir QC output', 'mv baredSC_convergence.* QC', f'mv baredSC_p.{shlex.quote(image_format)} QC', 'mv baredSC_corner.* QC', 'mv baredSC_neff.txt output', 'mv baredSC_pdf.txt output', f'mv baredSC.{shlex.quote(image_format)} baredSC', 'gunzip baredSC_means.txt.gz']
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / 'output').mkdir(parents=True, exist_ok=True)
        (out / 'QC').mkdir(parents=True, exist_ok=True)
        (out / 'other_outputs').mkdir(parents=True, exist_ok=True)
        return cls._output_paths(inputs, output_dir)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('geneColName', '')).strip():
            return 'geneColName is required'
        filetype = str(inputs.get('filetype', 'tabular') or 'tabular')
        if filetype == 'tabular' and (not str(inputs.get('input', '')).strip()):
            return 'input is required when filetype is tabular'
        if filetype not in cls.FILETYPES:
            return f"filetype must be one of: {', '.join(cls.FILETYPES)}"
        if filetype == 'anndata' and (not str(inputs.get('inputAnnData', '')).strip()):
            return 'inputAnnData is required when filetype is anndata'
        filter_nb = str(inputs.get('filter_nb', '0') or '0')
        if filter_nb not in cls.FILTER_COUNTS:
            return f"filter_nb must be one of: {', '.join(cls.FILTER_COUNTS)}"
        scale = str(inputs.get('xscale', 'Seurat') or 'Seurat')
        if scale not in cls.SCALE_OPTIONS:
            return f"xscale must be one of: {', '.join(cls.SCALE_OPTIONS)}"
        restart = str(inputs.get('automatic_restart', 'yes') or 'yes')
        if restart not in cls.RESTART_OPTIONS:
            return f"automatic_restart must be one of: {', '.join(cls.RESTART_OPTIONS)}"
        image_format = cls._image_format(inputs)
        if image_format not in cls.IMAGE_FORMATS:
            return f"image_file_format must be one of: {', '.join(cls.IMAGE_FORMATS)}"
        numeric_mins = {'nx': (1, int, 100), 'nnorm': (1, int, 2), 'nsampMCMC': (1, int, 100000), 'nsampInPlot': (1, int, 100000), 'osampx': (1, int, 10), 'osampxpdf': (1, int, 5)}
        for name, (minimum, caster, default) in numeric_mins.items():
            try:
                value = caster(inputs.get(name, default))
            except (TypeError, ValueError):
                return f'{name} must be numeric'
            if value < minimum:
                return f'{name} must be greater than or equal to {minimum}'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'geneColName': ('STRING', {'description': 'Name of the column with gene counts'})}, 'optional': {'filetype': ('STRING', {'default': 'tabular', 'options': cls.FILETYPES}), 'input': ('TSV', {'description': 'Input count table with one row per cell'}), 'inputAnnData': ('H5AD', {'description': 'AnnData file containing raw counts'}), 'filter_nb': ('STRING', {'default': '0', 'options': cls.FILTER_COUNTS}), 'metadata1ColName': ('STRING', {'default': ''}), 'metadata1Values': ('STRING', {'default': ''}), 'metadata2ColName': ('STRING', {'default': ''}), 'metadata2Values': ('STRING', {'default': ''}), 'metadata3ColName': ('STRING', {'default': ''}), 'metadata3Values': ('STRING', {'default': ''}), 'xmin': ('FLOAT', {'default': 0}), 'xmax': ('FLOAT', {'default': 2.5}), 'xscale': ('STRING', {'default': 'Seurat', 'options': cls.SCALE_OPTIONS}), 'targetSum': ('FLOAT', {'default': 10000}), 'nx': ('INT', {'default': 100, 'min': 1}), 'minScalex': ('FLOAT', {'default': 0.1}), 'seed': ('INT', {'default': 1}), 'nnorm': ('INT', {'default': 2, 'min': 1}), 'nsampMCMC': ('INT', {'default': 100000, 'min': 1}), 'automatic_restart': ('STRING', {'default': 'yes', 'options': cls.RESTART_OPTIONS}), 'minNeff': ('FLOAT', {'default': 200}), 'image_file_format': ('STRING', {'default': 'png', 'options': cls.IMAGE_FORMATS}), 'title': ('STRING', {'default': ''}), 'removeFirstSamples': ('INT', {'default': -1}), 'nsampInPlot': ('INT', {'default': 100000, 'min': 1}), 'prettyBins': ('INT', {'default': -1, 'min': -1}), 'osampx': ('INT', {'default': 10, 'min': 1, 'advanced': True}), 'osampxpdf': ('INT', {'default': 5, 'min': 1, 'advanced': True}), 'coviscale': ('FLOAT', {'default': 1, 'advanced': True}), 'nis': ('INT', {'default': 1000, 'advanced': True}), 'burn_custom': ('STRING', {'default': 'no', 'options': ['no', 'yes'], 'advanced': True}), 'nsampBurnMCMC': ('INT', {'default': -1, 'advanced': True}), 'T0BurnMCMC': ('FLOAT', {'default': 100, 'min': 1, 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
