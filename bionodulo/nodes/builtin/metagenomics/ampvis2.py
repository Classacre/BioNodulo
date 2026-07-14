"""ampvis2 — metagenomics node(s). One tool per file (extracted from wrapped_amplicon_trimming.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class Ampvis2AlphaDiversityNode(CommandNode):
    """Calculate ampvis2 alpha-diversity tables and plots."""
    NODE_ID = 'ampvis2_alpha_diversity'
    DISPLAY_NAME = 'ampvis2 alpha diversity'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Calculate alpha-diversity indices for samples in an ampvis2 RDS dataset.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 alpha diversity', 'amp_alphadiv', 'alpha-diversity indices', 'microbiome alpha diversity', 'vegan diversity', 'rarefaction']
    RETURN_TYPES = ('TSV', 'PDF')
    RETURN_NAMES = ('alphadiv', 'alphadiv_plot')
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_alphadiv.html'
    CITATION_DOIS = AMPVIS2_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in AMPVIS2_CITATION_DOIS]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    MEASURE_OPTIONS = ['uniqueotus', 'shannon', 'simpson', 'invsimpson']
    DEFAULT_MEASURES = ['uniqueotus', 'shannon', 'simpson', 'invsimpson']
    OUT_FORMATS = ['pdf', 'png', 'svg']

    @classmethod
    def _measures(cls, inputs: dict[str, Any]) -> list[str]:
        measures = _as_list(inputs.get('measure'))
        return measures if measures else cls.DEFAULT_MEASURES.copy()

    @classmethod
    def _r_bool(cls, value: Any, default: bool=False) -> str:
        if value in (None, ''):
            value = default
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no'} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        return out_format if out_format in cls.OUT_FORMATS else 'pdf'

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        measures = ', '.join((f'"{measure}"' for measure in cls._measures(inputs)))
        rarefy = inputs.get('rarefy')
        rarefy_line = f'\n    , rarefy = {rarefy}' if rarefy not in (None, '') else ''
        out_format = cls._out_format(inputs)
        ggsave_options = [f'    device = "{out_format}"']
        for name, option in (('plot_width', 'width'), ('plot_height', 'height')):
            value = inputs.get(name)
            if value not in (None, ''):
                ggsave_options.append(f'    , {option} = {value}')
        return '\n'.join(['library(ampvis2, quietly = TRUE)', '', f'''d <- readRDS("{inputs.get('data', '')}")''', 'table <- amp_alphadiv(d,', f'    measure = c({measures}),', f"    richness = {cls._r_bool(inputs.get('richness'), False)}{rarefy_line}", ')', 'plot <- amp_alphadiv(d,', f'    measure = c({measures}),', f"    richness = {cls._r_bool(inputs.get('richness'), False)}{rarefy_line},", '    plot = TRUE,', f'''    plot_group_by = "{inputs.get('group_by', '')}",''', f"    plot_scatter = {cls._r_bool(inputs.get('plot_scatter'), False)}", ')', f"write.table(table, file='{out}/alphadiv.tsv', quote=FALSE, sep='\\t', row.names=FALSE)", f'ggsave("{out}/alphadiv_plot.{out_format}",', '    plot = plot,', ',\n'.join(ggsave_options), ')'])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/alpha_diversity.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'alphadiv.tsv', out / f'alphadiv_plot.{cls._out_format(inputs)}']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        measures = _as_list(inputs.get('measure'))
        if 'measure' in inputs and (not measures):
            return 'at least one alpha-diversity measure is required'
        unsupported_measures = [measure for measure in measures if measure not in cls.MEASURE_OPTIONS]
        if unsupported_measures:
            return f"measure contains unsupported values: {', '.join(unsupported_measures)}"
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        if out_format not in cls.OUT_FORMATS:
            return f"out_format must be one of: {', '.join(cls.OUT_FORMATS)}"
        for name, minimum, default in (('rarefy', 0, None), ('plot_width', 1, None), ('plot_height', 1, None)):
            raw = inputs.get(name, default)
            if raw in (None, ''):
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return f'{name} must be a number'
            if value < minimum:
                return f'{name} must be >= {minimum}'
            if name == 'rarefy' and (not float(value).is_integer()):
                return 'rarefy must be an integer'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'})}, 'optional': {'measure': ('STRING_LIST', {'default': cls.DEFAULT_MEASURES.copy(), 'multiple': True, 'options': cls.MEASURE_OPTIONS, 'description': 'Alpha-diversity measures to include'}), 'richness': ('BOOLEAN', {'default': False, 'description': 'Calculate Chao1 and ACE sample richness estimates'}), 'rarefy': ('INT', {'default': '', 'min': 0, 'description': 'Rarefy species richness to this value before calculating indices'}), 'group_by': ('STRING', {'default': '', 'description': 'Metadata field for grouping the plot'}), 'plot_scatter': ('BOOLEAN', {'default': False, 'description': 'Generate a scatter plot instead of a boxplot'}), 'out_format': ('STRING', {'default': 'pdf', 'options': cls.OUT_FORMATS, 'description': 'Plot output format'}), 'plot_width': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot width in cm'}), 'plot_height': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot height in cm'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2BoxplotNode(CommandNode):
    """Generate ampvis2 boxplots of abundant taxa."""
    NODE_ID = 'ampvis2_boxplot'
    DISPLAY_NAME = 'ampvis2 boxplot'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Generate boxplots of abundant taxa from an ampvis2 RDS dataset.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 boxplot', 'amp_boxplot', 'taxa boxplot', 'abundant taxa', 'microbiome boxplot', 'amplicon abundance plot']
    RETURN_TYPES = ('PDF',)
    RETURN_NAMES = ('plot',)
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_boxplot.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    TAX_LEVELS = ['OTU', 'Species', 'Genus', 'Family', 'Order', 'Class', 'Phylum', 'Kingdom']
    SORT_OPTIONS = ['median', 'mean', 'sum']
    PLOT_TYPES = ['boxplot', 'point']
    TAX_SHOW_MODES = ['number', 'explicit']
    TAX_EMPTY_OPTIONS = ['remove', 'best', 'OTU']
    OUT_FORMATS = ['pdf', 'png', 'svg']

    @classmethod
    def _r_bool(cls, value: Any, default: bool=False) -> str:
        if value in (None, ''):
            value = default
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no'} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return 'c(' + ', '.join((f'"{value}"' for value in values)) + ')'

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        return out_format if out_format in cls.OUT_FORMATS else 'pdf'

    @classmethod
    def _tax_show(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get('tax_show_mode', 'number') or 'number') == 'explicit':
            return cls._r_vector(_as_list(inputs.get('tax_show')))
        return str(inputs.get('tax_show', 20) or 20)

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        tax_add = _as_list(inputs.get('tax_add'))
        ggsave_options = [f'    device = "{out_format}"']
        for name, option in (('plot_width', 'width'), ('plot_height', 'height')):
            value = inputs.get(name)
            if value not in (None, ''):
                ggsave_options.append(f'    , {option} = {value}')
        lines = ['library(ampvis2, quietly = TRUE)', f'''d <- readRDS("{inputs.get('data', '')}")''', 'plot <- amp_boxplot(', '    d,']
        if str(inputs.get('group_by', '')).strip():
            lines.append(f'''    group_by = "{inputs.get('group_by')}",''')
        lines.extend([f'''    sort_by = "{inputs.get('sort_by', 'median') or 'median'}",''', f'''    plot_type = "{inputs.get('plot_type', 'boxplot') or 'boxplot'}",''', f"    point_size = {inputs.get('point_size', 1)},", f'''    tax_aggregate = "{inputs.get('tax_aggregate', 'Genus') or 'Genus'}",''', f"    tax_add = {(cls._r_vector(tax_add) if tax_add else 'NULL')},", f'    tax_show = {cls._tax_show(inputs)},', f'''    tax_empty = "{inputs.get('tax_empty', 'best') or 'best'}",''', f"    plot_flip = {cls._r_bool(inputs.get('plot_flip'), False)},", f"    plot_log = {cls._r_bool(inputs.get('plot_log'), False)},"])
        if inputs.get('adjust_zero') not in (None, ''):
            lines.append(f"    adjust_zero = {inputs.get('adjust_zero')},")
        lines.extend([f"    normalise = {cls._r_bool(inputs.get('normalise'), False)}", ')', f'ggsave("{out}/plot.{out_format}",', '    print(plot),', ',\n'.join(ggsave_options), ')'])
        return '\n'.join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/boxplot.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f'plot.{cls._out_format(inputs)}']

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float, default: Any) -> bool | str:
        raw = inputs.get(name, default)
        if raw in (None, ''):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f'{name} must be a number'
        if value < minimum:
            return f'{name} must be >= {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        for name, options, default in (('sort_by', cls.SORT_OPTIONS, 'median'), ('plot_type', cls.PLOT_TYPES, 'boxplot'), ('tax_aggregate', cls.TAX_LEVELS, 'Genus'), ('tax_show_mode', cls.TAX_SHOW_MODES, 'number'), ('tax_empty', cls.TAX_EMPTY_OPTIONS, 'best'), ('out_format', cls.OUT_FORMATS, 'pdf')):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        unsupported_tax_add = [level for level in _as_list(inputs.get('tax_add')) if level not in cls.TAX_LEVELS]
        if unsupported_tax_add:
            return f"tax_add contains unsupported values: {', '.join(unsupported_tax_add)}"
        if str(inputs.get('tax_show_mode', 'number') or 'number') == 'explicit':
            if not _as_list(inputs.get('tax_show')):
                return 'tax_show must include at least one taxon when tax_show_mode is explicit'
        else:
            validation = cls._validate_number(inputs, 'tax_show', 1, 20)
            if validation is not True:
                return validation
        for name, minimum, default in (('point_size', 0, 1), ('adjust_zero', 1, None), ('plot_width', 1, None), ('plot_height', 1, None)):
            validation = cls._validate_number(inputs, name, minimum, default)
            if validation is not True:
                return validation
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'})}, 'optional': {'metadata_list': ('TSV', {'default': '', 'description': 'Metadata list generated by ampvis2: load'}), 'group_by': ('STRING', {'default': '', 'description': 'Discrete metadata variable used to group samples'}), 'sort_by': ('STRING', {'default': 'median', 'options': cls.SORT_OPTIONS, 'description': 'Statistic used to sort boxplots'}), 'plot_type': ('STRING', {'default': 'boxplot', 'options': cls.PLOT_TYPES, 'description': 'Plot geometry'}), 'point_size': ('INT', {'default': 1, 'min': 0, 'description': 'Point size'}), 'tax_aggregate': ('STRING', {'default': 'Genus', 'options': cls.TAX_LEVELS, 'description': 'Taxonomic level used to aggregate OTUs'}), 'tax_add': ('STRING_LIST', {'default': [], 'multiple': True, 'options': cls.TAX_LEVELS, 'description': 'Additional taxonomic levels to display'}), 'tax_show_mode': ('STRING', {'default': 'number', 'options': cls.TAX_SHOW_MODES, 'description': 'Limit displayed taxa by count or explicit list'}), 'taxonomy_list': ('TSV', {'default': '', 'description': 'Taxonomy list generated by ampvis2: load for explicit taxon selection'}), 'tax_show': ('STRING', {'default': 20, 'description': 'Number of taxa or explicit taxa to display'}), 'tax_empty': ('STRING', {'default': 'best', 'options': cls.TAX_EMPTY_OPTIONS, 'description': 'How to show OTUs without taxonomy'}), 'plot_flip': ('BOOLEAN', {'default': False, 'description': 'Flip plot axes'}), 'plot_log': ('BOOLEAN', {'default': False, 'description': 'Use log10 scale'}), 'adjust_zero': ('INT', {'default': '', 'min': 1, 'description': 'Value added to abundances before median calculations'}), 'normalise': ('BOOLEAN', {'default': False, 'description': 'Transform OTU read counts to percent per sample'}), 'out_format': ('STRING', {'default': 'pdf', 'options': cls.OUT_FORMATS, 'description': 'Plot output format'}), 'plot_width': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot width in cm'}), 'plot_height': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot height in cm'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2CoreNode(CommandNode):
    """Create ampvis2 core community plots."""
    NODE_ID = 'ampvis2_core'
    DISPLAY_NAME = 'ampvis2 core community analysis'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Create core-community plots for grouped ampvis2 samples.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 core community analysis', 'amp_core', 'core community plot', 'core taxa', 'abundant OTUs', 'microbiome core community']
    RETURN_TYPES = ('PDF',)
    RETURN_NAMES = ('plot',)
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_core.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    MARGIN_PLOT_OPTIONS = ['x', 'y', 'xy', '']
    OUT_FORMATS = ['pdf', 'png', 'svg']

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return 'c(' + ', '.join((f'"{value}"' for value in values)) + ')'

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        return out_format if out_format in cls.OUT_FORMATS else 'pdf'

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        ggsave_options = [f'    device = "{out_format}"']
        for name, option in (('plot_width', 'width'), ('plot_height', 'height')):
            value = inputs.get(name)
            if value not in (None, ''):
                ggsave_options.append(f'    , {option} = {value}')
        return '\n'.join(['library(ampvis2, quietly = TRUE)', f'''data <- readRDS("{inputs.get('data', '')}")''', 'plot <- amp_core(', '    data,', f"    group_by = {cls._r_vector(_as_list(inputs.get('group_by')))},", f"    core_pct = {inputs.get('core_pct', 80)},", f'''    margin_plots = "{(inputs.get('margin_plots', 'xy') if inputs.get('margin_plots', 'xy') is not None else 'xy')}",''', f"    margin_plot_values_size = {inputs.get('margin_plot_values_size', 3)},", f"    widths = c({inputs.get('widths', 5)}, 1),", f"    heights = c(1, {inputs.get('heights', 5)})", ')', f'ggsave("{out}/plot.{out_format}",', '    print(plot),', ',\n'.join(ggsave_options), ')'])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/core.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f'plot.{cls._out_format(inputs)}']

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float, default: Any, maximum: int | float | None=None) -> bool | str:
        raw = inputs.get(name, default)
        if raw in (None, ''):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f'{name} must be a number'
        if value < minimum or (maximum is not None and value > maximum):
            if maximum is not None:
                return f'{name} must be between {minimum} and {maximum}'
            return f'{name} must be >= {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        if not _as_list(inputs.get('group_by')):
            return 'at least one group_by metadata variable is required'
        margin_plots = str(inputs.get('margin_plots', 'xy') or '')
        if margin_plots not in cls.MARGIN_PLOT_OPTIONS:
            return f"margin_plots must be one of: {', '.join(cls.MARGIN_PLOT_OPTIONS)}"
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        if out_format not in cls.OUT_FORMATS:
            return f"out_format must be one of: {', '.join(cls.OUT_FORMATS)}"
        for name, minimum, default, maximum in (('core_pct', 0, 80, 100), ('margin_plot_values_size', 0, 3, None), ('widths', 1, 5, None), ('heights', 1, 5, None), ('plot_width', 1, None, None), ('plot_height', 1, None, None)):
            validation = cls._validate_number(inputs, name, minimum, default, maximum)
            if validation is not True:
                return validation
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'}), 'group_by': ('STRING_LIST', {'multiple': True, 'description': 'Metadata variables containing the desired grouping of samples'})}, 'optional': {'metadata_list': ('TSV', {'default': '', 'description': 'Metadata list generated by ampvis2: load'}), 'core_pct': ('FLOAT', {'default': 80, 'min': 0, 'max': 100, 'description': 'Percent threshold for defining abundant core OTUs'}), 'margin_plots': ('STRING', {'default': 'xy', 'options': cls.MARGIN_PLOT_OPTIONS, 'description': 'Margin plots to show'}), 'margin_plot_values_size': ('INT', {'default': 3, 'min': 0, 'description': 'Value label size in margin plots; 0 disables labels'}), 'widths': ('INT', {'default': 5, 'min': 1, 'description': 'Relative width of main and y margin plots'}), 'heights': ('INT', {'default': 5, 'min': 1, 'description': 'Relative height of main and x margin plots'}), 'out_format': ('STRING', {'default': 'pdf', 'options': cls.OUT_FORMATS, 'description': 'Plot output format'}), 'plot_width': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot width in cm'}), 'plot_height': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot height in cm'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2ExportFastaNode(CommandNode):
    """Export sequences from ampvis2 datasets as FASTA."""
    NODE_ID = 'ampvis2_export_fasta'
    DISPLAY_NAME = 'ampvis2 export fasta'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Export sequences from an ampvis2 RDS dataset as FASTA.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 export fasta', 'amp_export_fasta', 'export FASTA', 'amplicon sequences', 'taxonomy FASTA headers']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_export_fasta.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True

    @classmethod
    def _r_bool(cls, value: Any, default: bool=False) -> str:
        if value in (None, ''):
            value = default
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no'} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output.fasta'

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        return '\n'.join(['library(ampvis2, quietly = TRUE)', f'''data <- readRDS("{inputs.get('data', '')}")''', f'''amp_export_fasta(data, filename = "{cls._output_path(inputs)}", tax = {cls._r_bool(inputs.get('tax'), False)})'''])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/export_fasta.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output.fasta']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset containing sequence information'})}, 'optional': {'tax': ('BOOLEAN', {'default': False, 'description': 'Append taxonomic strings to FASTA headers'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2ExportOtuNode(CommandNode):
    """Export OTU, taxonomy, metadata, and phyloseq artifacts from ampvis2."""
    NODE_ID = 'ampvis2_export_otu'
    DISPLAY_NAME = 'ampvis2 export otu'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Export OTU, taxonomy, metadata, and phyloseq tables from an ampvis2 object.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 export otu', 'amp_export_otutable', 'OTU table export', 'taxonomy mapping', 'metadata mapping', 'phyloseq object']
    RETURN_TYPES = ('TSV', 'TSV', 'TSV', 'TSV', 'FILE')
    RETURN_NAMES = ('otu_long', 'otu_short', 'tax', 'meta', 'phyloseq')
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_export_otutable.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    OUTPUT_OPTIONS = ['otu_long', 'otu_short', 'tax', 'meta', 'phyloseq']
    DEFAULT_OUTPUTS = ['otu_short', 'tax', 'meta']
    OUTPUT_FILES = {'otu_long': 'otu_long.tsv', 'otu_short': 'otu_short.tsv', 'tax': 'tax.tsv', 'meta': 'meta.tsv', 'phyloseq': 'phyloseq.rds'}

    @classmethod
    def _r_bool(cls, value: Any, default: bool=False) -> str:
        if value in (None, ''):
            value = default
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no'} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        outputs = _as_list(inputs.get('output_selection'))
        return outputs if outputs else cls.DEFAULT_OUTPUTS.copy()

    @classmethod
    def _path(cls, inputs: dict[str, Any], output_name: str) -> str:
        return f'{_out(inputs)}/{cls.OUTPUT_FILES[output_name]}'

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        norm = cls._r_bool(inputs.get('norm'), False)
        otu_source = 'data_norm$abund' if norm == 'TRUE' else 'data$abund'
        norm_lines = ['data_norm <- normaliseTo100(data)'] if norm == 'TRUE' else []
        return '\n'.join(['library(ampvis2, quietly = TRUE)', 'library(phyloseq)', 'library(tibble)', '', f'''data <- readRDS("{inputs.get('data', '')}")''', '', f'amp_export_otutable(data, filename = "tmp_otu", sep = "\\t", extension = "tsv", normalise = {norm})', '', 'tax_table <- data$tax', 'tax_table <- tax_table[,c(8,(ncol(tax_table)-6):(ncol(tax_table) - 1))]', f'''write.table(tax_table, "{cls._path(inputs, 'tax')}", sep = "\\t", row.names=FALSE, quote = FALSE)''', '', *norm_lines, f'otu_table <- {otu_source}', 'otu_table <- cbind(OTU = rownames(otu_table), otu_table)', f'''write.table(otu_table, "{cls._path(inputs, 'otu_short')}", sep = "\\t", row.names=FALSE, quote = FALSE)''', '', 'meta_data = data$metadata', f'''write.table(meta_data, "{cls._path(inputs, 'meta')}", sep = "\\t", row.names = FALSE, quote = FALSE)''', '', 'otu_table <- apply(otu_table, 2, as.numeric)', 'meta_data[] <- lapply(meta_data, as.character)', 'OTU <- otu_table(otu_table, taxa_are_rows = TRUE)', 'TAX <- tax_table(tax_table)', 'META <- sample_data(meta_data)', 'colnames(TAX) <- c("Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species")', 'physeq <- phyloseq(OTU, TAX, META)', f'''saveRDS(physeq, "{cls._path(inputs, 'phyloseq')}")'''])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/export_otu.R'
        commands = [f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs)}\nRSCRIPT", _shell_join(['Rscript', script_path]), _shell_join(['mv', 'tmp_otu.tsv', cls._path(inputs, 'otu_long')])]
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILES[output] for output in cls._selected_outputs(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        outputs = _as_list(inputs.get('output_selection'))
        if 'output_selection' in inputs and (not outputs):
            return 'at least one output_selection value is required'
        unsupported_outputs = [output for output in outputs if output not in cls.OUTPUT_OPTIONS]
        if unsupported_outputs:
            return f"output_selection contains unsupported values: {', '.join(unsupported_outputs)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset'})}, 'optional': {'norm': ('BOOLEAN', {'default': False, 'description': 'Transform OTU read counts to percent per sample'}), 'output_selection': ('STRING_LIST', {'default': cls.DEFAULT_OUTPUTS.copy(), 'multiple': True, 'options': cls.OUTPUT_OPTIONS, 'description': 'Output files to emit'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2FrequencyNode(CommandNode):
    """Generate ampvis2 frequency versus read-abundance plots."""
    NODE_ID = 'ampvis2_frequency'
    DISPLAY_NAME = 'ampvis2 frequency plot'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Generate frequency versus read-abundance barplots from an ampvis2 RDS dataset.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 frequency plot', 'amp_frequency', 'frequency plot', 'read abundance frequency', 'microbiome frequency']
    RETURN_TYPES = ('PDF',)
    RETURN_NAMES = ('plot',)
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_frequency.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    TAX_LEVELS = ['OTU', 'Species', 'Genus', 'Family', 'Order', 'Class', 'Phylum', 'Kingdom']
    TAX_EMPTY_OPTIONS = ['remove', 'best', 'OTU']
    OUT_FORMATS = ['pdf', 'png', 'svg']

    @classmethod
    def _r_bool(cls, value: Any, default: bool=False) -> str:
        if value in (None, ''):
            value = default
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no'} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        return out_format if out_format in cls.OUT_FORMATS else 'pdf'

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        ggsave_options = [f'    device = "{out_format}"']
        for name, option in (('plot_width', 'width'), ('plot_height', 'height')):
            value = inputs.get(name)
            if value not in (None, ''):
                ggsave_options.append(f'    , {option} = {value}')
        lines = ['library(ampvis2, quietly = TRUE)', f'''data <- readRDS("{inputs.get('data', '')}")''', 'plot <- amp_frequency(', '    data,']
        if str(inputs.get('group_by', '')).strip():
            lines.append(f'''    group_by = "{inputs.get('group_by')}",''')
        lines.extend([f'''    tax_empty = "{inputs.get('tax_empty', 'best') or 'best'}",''', f'''    tax_aggregate = "{inputs.get('tax_aggregate', 'OTU') or 'OTU'}",''', f"    weight = {cls._r_bool(inputs.get('weight'), True)},", f"    normalise = {cls._r_bool(inputs.get('normalise'), True)},", '    detailed_output = FALSE', ')', f'ggsave("{out}/plot.{out_format}",', '    print(plot),', ',\n'.join(ggsave_options), ')'])
        return '\n'.join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/frequency.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f'plot.{cls._out_format(inputs)}']

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float) -> bool | str:
        raw = inputs.get(name)
        if raw in (None, ''):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f'{name} must be a number'
        if value < minimum:
            return f'{name} must be >= {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        for name, options, default in (('tax_empty', cls.TAX_EMPTY_OPTIONS, 'best'), ('tax_aggregate', cls.TAX_LEVELS, 'OTU'), ('out_format', cls.OUT_FORMATS, 'pdf')):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        for name in ('plot_width', 'plot_height'):
            validation = cls._validate_number(inputs, name, 1)
            if validation is not True:
                return validation
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'})}, 'optional': {'metadata_list': ('TSV', {'default': '', 'description': 'Metadata list generated by ampvis2: load'}), 'group_by': ('STRING', {'default': '', 'description': 'Discrete metadata variable used to group samples'}), 'tax_empty': ('STRING', {'default': 'best', 'options': cls.TAX_EMPTY_OPTIONS, 'description': 'How to show OTUs without taxonomy'}), 'tax_aggregate': ('STRING', {'default': 'OTU', 'options': cls.TAX_LEVELS, 'description': 'Taxonomic level used to aggregate OTUs'}), 'weight': ('BOOLEAN', {'default': True, 'description': 'Weight the frequency by abundance'}), 'normalise': ('BOOLEAN', {'default': True, 'description': 'Transform OTU read counts to percent per sample'}), 'out_format': ('STRING', {'default': 'pdf', 'options': cls.OUT_FORMATS, 'description': 'Plot output format'}), 'plot_width': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot width in cm'}), 'plot_height': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot height in cm'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2HeatmapNode(CommandNode):
    """Generate ampvis2 heatmaps from grouped metadata and taxonomy."""
    NODE_ID = 'ampvis2_heatmap'
    DISPLAY_NAME = 'ampvis2 heatmap'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Generate ampvis2 heatmaps from metadata-grouped samples and aggregated OTUs.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 heatmap', 'amp_heatmap', 'microbiome heatmap', 'amplicon heatmap', 'taxonomy abundance heatmap']
    RETURN_TYPES = ('PDF', 'TSV')
    RETURN_NAMES = ('plot', 'plot_raw')
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_heatmap.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    TAX_LEVELS = ['OTU', 'Species', 'Genus', 'Family', 'Order', 'Class', 'Phylum', 'Kingdom']
    TAX_EMPTY_OPTIONS = ['remove', 'best', 'OTU']
    TAX_SHOW_MODES = ['number', 'explicit']
    NORMALISE_BY_MODES = ['no', 'variable', 'sample']
    SORT_BY_MODES = ['no', 'group', 'sample']
    PLOT_FUNCTIONS_MODES = ['no', 'midasfieldguide', 'file']
    PLOT_COLOR_SCALES = ['sqrt', 'log10']
    MEASURE_OPTIONS = ['mean', 'max', 'median']
    OUT_FORMATS = ['pdf', 'png', 'svg', 'tabular']
    MIDAS_FUNCTIONS = ['MiDAS', 'Filamentous', 'AOB', 'NOB', 'GAO']

    @classmethod
    def _r_bool(cls, value: Any, default: bool=False) -> str:
        if value in (None, ''):
            value = default
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no'} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return 'c(' + ', '.join((f'"{value}"' for value in values)) + ')'

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        return out_format if out_format in cls.OUT_FORMATS else 'pdf'

    @classmethod
    def _tax_show(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get('tax_show_mode', 'number') or 'number') == 'explicit':
            return cls._r_vector(_as_list(inputs.get('tax_show')))
        return str(inputs.get('tax_show', 10) or 10)

    @classmethod
    def _plot_functions(cls, inputs: dict[str, Any]) -> list[str]:
        mode = str(inputs.get('plot_functions_mode', 'no') or 'no')
        if mode == 'midasfieldguide':
            functions = _as_list(inputs.get('functions'))
            return functions if functions else cls.MIDAS_FUNCTIONS.copy()
        if mode == 'file':
            return _as_list(inputs.get('functions'))
        return []

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        output_name = 'raw' if out_format == 'tabular' else 'plot'
        ggsave_options = [f'    device = "{out_format}"']
        for name, option in (('plot_width', 'width'), ('plot_height', 'height')):
            value = inputs.get(name)
            if value not in (None, ''):
                ggsave_options.append(f'    , {option} = {value}')
        lines = ['library(ampvis2, quietly = TRUE)', f'''d <- readRDS("{inputs.get('data', '')}")''', f'{output_name} <- amp_heatmap(', '    d,']
        if str(inputs.get('group_by', '')).strip():
            lines.append(f'''    group_by = "{inputs.get('group_by')}",''')
        if str(inputs.get('facet_by', '')).strip():
            lines.append(f'''    facet_by = "{inputs.get('facet_by')}",''')
        tax_add = _as_list(inputs.get('tax_add'))
        lines.extend([f"    normalise = {cls._r_bool(inputs.get('normalise'), True)},", f'''    tax_aggregate = "{inputs.get('tax_aggregate', 'Phylum') or 'Phylum'}",''', f"    tax_add = {(cls._r_vector(tax_add) if tax_add else 'NULL')},", f'    tax_show = {cls._tax_show(inputs)},', f"    showRemainingTaxa = {cls._r_bool(inputs.get('showRemainingTaxa'), False)},", f'''    tax_empty = "{inputs.get('tax_empty', 'best') or 'best'}",'''])
        if inputs.get('order_x_by'):
            lines.append('    order_x_by = "cluster",')
        if inputs.get('order_y_by'):
            lines.append('    order_y_by = "cluster",')
        plot_values = cls._r_bool(inputs.get('plot_values'), True)
        lines.append(f'    plot_values = {plot_values},')
        if plot_values == 'TRUE':
            lines.append(f"    plot_values_size = {inputs.get('plot_values_size', 4) or 4},")
        lines.extend([f'''    plot_colorscale = "{inputs.get('plot_colorscale', 'log10') or 'log10'}",''', f"    plot_na = {cls._r_bool(inputs.get('plot_na'), False)},", f'''    measure = "{inputs.get('measure', 'mean') or 'mean'}",'''])
        if inputs.get('min_abundance') not in (None, ''):
            lines.append(f"    min_abundance = {inputs.get('min_abundance')},")
        else:
            lines.append('    min_abundance = 0.1,')
        if inputs.get('max_abundance') not in (None, ''):
            lines.append(f"    max_abundance = {inputs.get('max_abundance')},")
        if str(inputs.get('sort_by_mode', 'no') or 'no') != 'no' and str(inputs.get('sort_by', '')).strip():
            lines.append(f'''    sort_by = "{inputs.get('sort_by')}",''')
        if str(inputs.get('normalise_by_mode', 'no') or 'no') == 'no':
            lines.append('    normalise_by = NULL,')
        elif str(inputs.get('normalise_by', '')).strip():
            lines.append(f'''    normalise_by = "{inputs.get('normalise_by')}",''')
        if str(inputs.get('scale_by', '')).strip():
            lines.append(f'''    scale_by = "{inputs.get('scale_by')}",''')
        lines.extend([f'''    color_vector = c("{inputs.get('color_palette_start', '') or ''}", "{inputs.get('color_palette_end', '') or ''}"),''', f"    textmap = {('TRUE' if out_format == 'tabular' else 'FALSE')},"])
        plot_functions_mode = str(inputs.get('plot_functions_mode', 'no') or 'no')
        if plot_functions_mode != 'no':
            lines.append('    plot_functions = TRUE,')
            if plot_functions_mode == 'file':
                lines.append(f'''    function_data = read.table("{inputs.get('function_data', '')}", header = TRUE, sep = "\\t"),''')
            lines.append(f'    functions = {cls._r_vector(cls._plot_functions(inputs))},')
        lines.extend(['    rel_widths = c(0.75, 0.25)', ')'])
        if out_format == 'tabular':
            lines.append(f'write.table(raw, file = "{out}/plot_raw.tsv", sep = "\\t")')
        else:
            lines.extend([f'ggsave("{out}/plot.{out_format}",', '    print(plot),', ',\n'.join(ggsave_options), ')'])
        return '\n'.join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/heatmap.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        out_format = cls._out_format(inputs)
        if out_format == 'tabular':
            return [out / 'plot_raw.tsv']
        return [out / f'plot.{out_format}']

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float, default: Any=None) -> bool | str:
        raw = inputs.get(name, default)
        if raw in (None, ''):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f'{name} must be a number'
        if value < minimum:
            return f'{name} must be >= {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        for name, options, default in (('normalise_by_mode', cls.NORMALISE_BY_MODES, 'no'), ('tax_aggregate', cls.TAX_LEVELS, 'Phylum'), ('tax_show_mode', cls.TAX_SHOW_MODES, 'number'), ('tax_empty', cls.TAX_EMPTY_OPTIONS, 'best'), ('plot_colorscale', cls.PLOT_COLOR_SCALES, 'log10'), ('measure', cls.MEASURE_OPTIONS, 'mean'), ('sort_by_mode', cls.SORT_BY_MODES, 'no'), ('plot_functions_mode', cls.PLOT_FUNCTIONS_MODES, 'no'), ('out_format', cls.OUT_FORMATS, 'pdf')):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        unsupported_tax_add = [level for level in _as_list(inputs.get('tax_add')) if level not in cls.TAX_LEVELS]
        if unsupported_tax_add:
            return f"tax_add contains unsupported values: {', '.join(unsupported_tax_add)}"
        if str(inputs.get('tax_show_mode', 'number') or 'number') == 'explicit':
            if not _as_list(inputs.get('tax_show')):
                return 'tax_show must include at least one taxon when tax_show_mode is explicit'
        else:
            validation = cls._validate_number(inputs, 'tax_show', 1, 10)
            if validation is not True:
                return validation
        for name, minimum, default in (('plot_values_size', 1, 4), ('min_abundance', 0, 0.1), ('max_abundance', 0, None), ('plot_width', 1, None), ('plot_height', 1, None)):
            validation = cls._validate_number(inputs, name, minimum, default)
            if validation is not True:
                return validation
        plot_functions_mode = str(inputs.get('plot_functions_mode', 'no') or 'no')
        if plot_functions_mode == 'file':
            if not str(inputs.get('function_data', '')).strip():
                return 'function_data is required when plot_functions_mode is file'
            if not _as_list(inputs.get('functions')):
                return 'functions must include at least one value when plot_functions_mode is file'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'})}, 'optional': {'metadata_list': ('TSV', {'default': '', 'description': 'Metadata list generated by ampvis2: load'}), 'group_by': ('STRING', {'default': '', 'description': 'Categorical metadata variable used to group samples'}), 'facet_by': ('STRING', {'default': '', 'description': 'Categorical metadata variable used to facet samples'}), 'normalise': ('BOOLEAN', {'default': True, 'description': 'Transform OTU read counts to percent per sample'}), 'normalise_by_mode': ('STRING', {'default': 'no', 'options': cls.NORMALISE_BY_MODES, 'description': 'Normalise by no value, a metadata value, or a sample'}), 'normalise_by': ('STRING', {'default': '', 'description': 'Metadata value or sample used for normalising counts'}), 'tax_aggregate': ('STRING', {'default': 'Phylum', 'options': cls.TAX_LEVELS, 'description': 'Taxonomic level used to aggregate OTUs'}), 'tax_add': ('STRING_LIST', {'default': [], 'multiple': True, 'options': cls.TAX_LEVELS, 'description': 'Additional taxonomic levels to display'}), 'tax_show_mode': ('STRING', {'default': 'number', 'options': cls.TAX_SHOW_MODES, 'description': 'Limit displayed taxa by count or explicit list'}), 'taxonomy_list': ('TSV', {'default': '', 'description': 'Taxonomy list generated by ampvis2: load for explicit taxon selection'}), 'tax_show': ('STRING', {'default': 10, 'description': 'Number of taxa or explicit taxa to show'}), 'showRemainingTaxa': ('BOOLEAN', {'default': False, 'description': 'Display a row with the sum of taxa outside the selected taxa'}), 'tax_empty': ('STRING', {'default': 'best', 'options': cls.TAX_EMPTY_OPTIONS, 'description': 'How to show OTUs without taxonomy'}), 'order_x_by': ('BOOLEAN', {'default': False, 'description': 'Cluster the heatmap x axis'}), 'order_y_by': ('BOOLEAN', {'default': False, 'description': 'Cluster the heatmap y axis'}), 'plot_values': ('BOOLEAN', {'default': True, 'description': 'Plot abundance values on the heatmap'}), 'plot_values_size': ('INT', {'default': 4, 'min': 1, 'description': 'Size of plotted abundance values'}), 'plot_colorscale': ('STRING', {'default': 'log10', 'options': cls.PLOT_COLOR_SCALES, 'description': 'Scale used for coloring abundances'}), 'plot_na': ('BOOLEAN', {'default': False, 'description': 'Color missing values with the lowest color in the scale'}), 'measure': ('STRING', {'default': 'mean', 'options': cls.MEASURE_OPTIONS, 'description': 'Statistic shown across sample groups'}), 'min_abundance': ('FLOAT', {'default': 0.1, 'min': 0, 'description': 'Lower abundance color clamp'}), 'max_abundance': ('FLOAT', {'default': '', 'min': 0, 'description': 'Upper abundance color clamp'}), 'sort_by_mode': ('STRING', {'default': 'no', 'options': cls.SORT_BY_MODES, 'description': 'Sort heatmap by no value, group, or sample'}), 'sort_by': ('STRING', {'default': '', 'description': 'Group or sample used to sort most abundant taxa'}), 'color_palette_start': ('STRING', {'default': '', 'description': 'Start color for the heatmap'}), 'color_palette_end': ('STRING', {'default': '', 'description': 'End color for the heatmap'}), 'scale_by': ('STRING', {'default': '', 'description': 'Metadata variable used to scale abundances'}), 'plot_functions_mode': ('STRING', {'default': 'no', 'options': cls.PLOT_FUNCTIONS_MODES, 'description': 'Show Genus-level functional information from MiDAS or a table'}), 'function_data': ('TSV', {'default': '', 'description': 'Functional information table with Genus in the first column'}), 'functions': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Function columns to display next to Genus-level OTUs'}), 'out_format': ('STRING', {'default': 'pdf', 'options': cls.OUT_FORMATS, 'description': 'Plot or table output format'}), 'plot_width': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot width in cm'}), 'plot_height': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot height in cm'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2LoadNode(CommandNode):
    """Load OTU, ASV, BIOM, or phyloseq data into an ampvis2 object."""
    NODE_ID = 'ampvis2_load'
    DISPLAY_NAME = 'ampvis2 load'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Load OTU, ASV, BIOM, or phyloseq data into an ampvis2 RDS object.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 load', 'amp_load', 'OTU table', 'ASV table', 'BIOM', 'phyloseq', 'metadata list', 'taxonomy list']
    RETURN_TYPES = ('FILE', 'TSV', 'TSV')
    RETURN_NAMES = ('ampvis', 'metadata_list_out', 'taxonomy_list_out')
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_load.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    OTUTABLE_TYPES = ['tabular', 'dada2_sequencetable', 'biom1', 'biom2', 'phyloseq']
    WRITE_LIST_OPTIONS = ['tax', 'metadata']
    DEFAULT_WRITE_LISTS = ['tax', 'metadata']
    LIST_OUTPUT_FILES = {'tax': 'taxonomy_list.tsv', 'metadata': 'metadata_list.tsv'}

    @classmethod
    def _r_bool(cls, value: Any, default: bool=False) -> str:
        if value in (None, ''):
            value = default
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no'} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _otutable_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('otutable_type', 'tabular') or 'tabular')

    @classmethod
    def _selected_write_lists(cls, inputs: dict[str, Any]) -> list[str]:
        if 'write_lists' in inputs:
            return _as_list(inputs.get('write_lists'))
        return cls.DEFAULT_WRITE_LISTS.copy()

    @classmethod
    def _staging_commands(cls, inputs: dict[str, Any]) -> list[str]:
        otutable_type = cls._otutable_type(inputs)
        commands = []
        if otutable_type in {'biom1', 'biom2'}:
            commands.append(_shell_join(['ln', '-s', str(inputs.get('otutable', '')), 'otutable.biom']))
        elif otutable_type != 'phyloseq':
            if inputs.get('asv_otu_col_empty'):
                commands.append(_shell_join(['sed', '-e', '1 s/^\\t/ASV\\t/', str(inputs.get('otutable', '')), '>', 'otutable.tsv']))
            else:
                commands.append(_shell_join(['ln', '-s', str(inputs.get('otutable', '')), 'otutable.tsv']))
        if str(inputs.get('taxonomy', '')).strip():
            if inputs.get('asv_otu_col_empty'):
                commands.append(_shell_join(['sed', '-e', '1 s/^\\t/ASV\\t/', str(inputs.get('taxonomy', '')), '>', 'taxonomy.tsv']))
            else:
                commands.append(_shell_join(['ln', '-s', str(inputs.get('taxonomy', '')), 'taxonomy.tsv']))
        return commands

    @classmethod
    def _metadata_lines(cls, inputs: dict[str, Any]) -> list[str]:
        metadata = str(inputs.get('metadata', '')).strip()
        if not metadata:
            return []
        return [f'metadata <- read.table("{metadata}", header = TRUE, sep = "\\t", colClasses = "character", check.names=F)', 'if(colnames(metadata)[1] == ""){', '    colnames(metadata)[1] <- "SampleID"', '}', 'if(exists("SampleID", where = metadata)){', '    rownames(metadata) <- metadata[["SampleID"]]', '}else{', '    rownames(metadata) <- metadata[[1]]', '}', '']

    @classmethod
    def _amp_load_otutable_line(cls, inputs: dict[str, Any]) -> str:
        otutable_type = cls._otutable_type(inputs)
        if otutable_type == 'phyloseq':
            return '    otutable = otutable,'
        if otutable_type in {'biom1', 'biom2'}:
            return '    otutable = "otutable.biom",'
        return '    otutable = "otutable.tsv",'

    @classmethod
    def _amp_load_lines(cls, inputs: dict[str, Any]) -> list[str]:
        lines = ['data <- amp_load(', cls._amp_load_otutable_line(inputs)]
        if str(inputs.get('metadata', '')).strip():
            lines.append('    metadata = metadata,')
        if str(inputs.get('taxonomy', '')).strip():
            lines.append('    taxonomy = "taxonomy.tsv",')
        if str(inputs.get('fasta', '')).strip():
            lines.append(f'''    fasta = "{inputs.get('fasta')}",''')
        if str(inputs.get('tree', '')).strip():
            lines.append(f'''    tree = "{inputs.get('tree')}",''')
        if str(inputs.get('otutable_OTUcolname', '')).strip():
            lines.append(f'''    otutable_OTUcolname = c("{inputs.get('otutable_OTUcolname')}"),''')
        if str(inputs.get('taxonomy_OTUcolname', '')).strip():
            lines.append(f'''    taxonomy_OTUcolname = c("{inputs.get('taxonomy_OTUcolname')}"),''')
        lines.extend([f"    pruneSingletons = {cls._r_bool(inputs.get('pruneSingletons'), False)}", ')'])
        return lines

    @classmethod
    def _asv_sequence_lines(cls, inputs: dict[str, Any]) -> list[str]:
        if not inputs.get('asv_sequences'):
            return []
        return ['', 'library(ape, quietly = TRUE)', '', 'seq <- as.DNAbin(strsplit(rownames(data$abund), ""))', 'names(seq) <- paste0("ASV", seq_along(seq))', 'data$refseq <- seq', 'data <- matchOTUs(data, seq)']

    @classmethod
    def _metadata_list_lines(cls, out: str) -> list[str]:
        return ['classes <- sapply(data$metadata, class)', 'data$metadata[is.na(data$metadata)] <- "NA"', 'for(name in names(data$metadata)){', '    if(classes[[name]] == "character" && all(data$metadata[[name]] == rownames(data$metadata))){', '        sample_names <- TRUE;', '    }else{', '        sample_names <- FALSE;', '    }', '    for(m in unique(data$metadata[[name]])){', f'        write(paste(name, m, sample_names, classes[[name]], sep="\\t"), file="{out}/metadata_list.tsv", append=T);', '    }', '}']

    @classmethod
    def _taxonomy_list_lines(cls, out: str) -> list[str]:
        return ['for(level in colnames(data$tax)){', '    for(u in unique(data$tax[level])){', f'        write(paste(u, level, sep="\\t"), file="{out}/taxonomy_list.tsv", append=T)', '    }', '}']

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        lines = ['library(ampvis2, quietly = TRUE)', 'library(readr, quietly = TRUE)', '', *cls._metadata_lines(inputs)]
        if cls._otutable_type(inputs) == 'phyloseq':
            lines.extend([f'''otutable <- readRDS("{inputs.get('otutable', '')}")''', 'print(class(otutable))', ''])
        lines.extend(cls._amp_load_lines(inputs))
        lines.extend(cls._asv_sequence_lines(inputs))
        if cls._r_bool(inputs.get('guess_column_types'), True) == 'TRUE':
            lines.extend(['', 'data$metadata <- readr::type_convert(data$metadata, guess_integer=TRUE)'])
        lines.extend(['', f'saveRDS(data, "{out}/ampvis.rds")'])
        for list_name in cls._selected_write_lists(inputs):
            if list_name == 'metadata':
                lines.extend(['', *cls._metadata_list_lines(out)])
            elif list_name == 'tax':
                lines.extend(['', *cls._taxonomy_list_lines(out)])
        lines.extend(['', 'data'])
        return '\n'.join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/load.R'
        commands = [*cls._staging_commands(inputs), f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT", _shell_join(['Rscript', script_path])]
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'ampvis.rds']
        selected_lists = set(cls._selected_write_lists(inputs))
        outputs.extend((out / cls.LIST_OUTPUT_FILES[list_name] for list_name in ('metadata', 'tax') if list_name in selected_lists))
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('otutable', '')).strip():
            return 'otutable is required'
        otutable_type = cls._otutable_type(inputs)
        if otutable_type not in cls.OTUTABLE_TYPES:
            return f"otutable_type must be one of: {', '.join(cls.OTUTABLE_TYPES)}"
        unsupported_lists = [name for name in _as_list(inputs.get('write_lists')) if name not in cls.WRITE_LIST_OPTIONS]
        if unsupported_lists:
            return f"write_lists contains unsupported values: {', '.join(unsupported_lists)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'otutable': ('FILE', {'description': 'OTU, ASV, BIOM, or phyloseq dataset'})}, 'optional': {'otutable_type': ('STRING', {'default': 'tabular', 'options': cls.OTUTABLE_TYPES, 'description': 'Galaxy datatype of the OTU table input'}), 'asv_sequences': ('BOOLEAN', {'default': False, 'description': 'Treat ASV identifiers as ASV sequences and store them in the ampvis2 object'}), 'metadata': ('TSV', {'default': '', 'description': 'Optional sample metadata table'}), 'guess_column_types': ('BOOLEAN', {'default': True, 'description': 'Guess metadata column types with readr::type_convert'}), 'taxonomy': ('TSV', {'default': '', 'description': 'Optional taxonomy table'}), 'fasta': ('FASTA', {'default': '', 'description': 'Optional FASTA file containing OTU or ASV sequences'}), 'tree': ('FILE', {'default': '', 'description': 'Optional phylogenetic tree in Newick format'}), 'pruneSingletons': ('BOOLEAN', {'default': False, 'description': 'Remove singleton OTUs'}), 'write_lists': ('STRING_LIST', {'default': cls.DEFAULT_WRITE_LISTS.copy(), 'multiple': True, 'options': cls.WRITE_LIST_OPTIONS, 'description': 'Auxiliary metadata and taxonomy list outputs for downstream ampvis2 tools'}), 'asv_otu_col_empty': ('BOOLEAN', {'default': False, 'description': 'Replace an empty OTU/ASV column header with ASV before loading'}), 'otutable_OTUcolname': ('STRING', {'default': '', 'description': 'OTU column name in the OTU table'}), 'taxonomy_OTUcolname': ('STRING', {'default': '', 'description': 'OTU column name in the taxonomy table'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2MergeAmpvis2Node(CommandNode):
    """Merge multiple ampvis2 RDS datasets into one ampvis2 object."""
    NODE_ID = 'ampvis2_merge_ampvis2'
    DISPLAY_NAME = 'ampvis2 merge ampvis2 data sets'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Merge multiple ampvis2 RDS datasets into a single ampvis2 object.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 merge ampvis2 data sets', 'amp_merge_ampvis2', 'merge ampvis2 objects', 'RDS merge', 'by reference sequence', 'DNA reference sequences']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_merge_ampvis2.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True

    @classmethod
    def _r_bool(cls, value: Any, default: bool=False) -> str:
        if value in (None, ''):
            value = default
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no'} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _data_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('data'))

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output.rds'

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        data_lines = [f'    readRDS("{data_file}"),' for data_file in cls._data_files(inputs)]
        return '\n'.join(['library(ampvis2, quietly = TRUE)', 'merged <- amp_merge_ampvis2(', *data_lines, f"    by_refseq = {cls._r_bool(inputs.get('by_refseq'), True)}", ')', f'saveRDS(merged, "{cls._output_path(inputs)}")', 'merged'])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/merge_ampvis2.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output.rds']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._data_files(inputs):
            return 'at least one ampvis2 data set is required'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'multiple': True, 'description': 'Ampvis2 RDS datasets generated with ampvis2: load'})}, 'optional': {'by_refseq': ('BOOLEAN', {'default': True, 'description': 'Merge by exact DNA reference sequence matches and use those sequences as output names'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2MergeReplicatesNode(CommandNode):
    """Merge replicate samples in an ampvis2 object by metadata group."""
    NODE_ID = 'ampvis2_mergereplicates'
    DISPLAY_NAME = 'ampvis2 merge replicates'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Merge replicate samples in an ampvis2 RDS dataset by averaging OTU abundances.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 merge replicates', 'amp_mergereplicates', 'amp_merge_replicates', 'replicate samples', 'average OTU abundances', 'metadata groups']
    RETURN_TYPES = ('FILE', 'TSV')
    RETURN_NAMES = ('ampvis', 'metadata_list_out')
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_merge_replicates.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    ROUND_OPTIONS = ['', 'up', 'down']

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        round_value = str(inputs.get('round', '') or '')
        lines = ['library(ampvis2, quietly = TRUE)', f'''data <- readRDS("{inputs.get('data', '')}")''', 'data <- amp_mergereplicates(', '    data,', f'''    merge_var = "{inputs.get('merge_var', '')}"{(',' if round_value else '')}''']
        if round_value:
            lines.append(f'    round = "{round_value}"')
        lines.extend([')', f'saveRDS(data, "{out}/ampvis.rds")', *Ampvis2LoadNode._metadata_list_lines(out), 'data'])
        return '\n'.join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/mergereplicates.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'ampvis.rds', out / 'metadata_list.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        if not str(inputs.get('metadata_list', '')).strip():
            return 'metadata_list is required'
        if not str(inputs.get('merge_var', '')).strip():
            return 'merge_var is required'
        round_value = str(inputs.get('round', '') or '')
        if round_value not in cls.ROUND_OPTIONS:
            return f"round must be one of: {', '.join(cls.ROUND_OPTIONS)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'}), 'metadata_list': ('TSV', {'description': 'Metadata list generated by ampvis2: load'}), 'merge_var': ('STRING', {'description': 'Discrete metadata variable defining replicate sample groups'})}, 'optional': {'round': ('STRING', {'default': '', 'options': cls.ROUND_OPTIONS, 'description': 'Round merged read count decimals up, down, or not at all'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2OctaveNode(CommandNode):
    """Generate ampvis2 octave plots for sequencing-depth assessment."""
    NODE_ID = 'ampvis2_octave'
    DISPLAY_NAME = 'ampvis2 octave plot'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Generate octave plots to assess alpha diversity sequencing depth.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 octave plot', 'amp_octave', 'octave plot', 'alpha diversity', 'sequencing depth', 'read count bins', 'microbiome diversity']
    RETURN_TYPES = ('PDF',)
    RETURN_NAMES = ('plot',)
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_octave.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    TAX_LEVELS = ['OTU', 'Species', 'Genus', 'Family', 'Order', 'Class', 'Phylum', 'Kingdom']
    SCALE_OPTIONS = ['fixed', 'free', 'free_x', 'free_y']
    OUT_FORMATS = ['pdf', 'png', 'svg']

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        return out_format if out_format in cls.OUT_FORMATS else 'pdf'

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        ggsave_options = [f'    device = "{out_format}"']
        for name, option in (('plot_width', 'width'), ('plot_height', 'height')):
            value = inputs.get(name)
            if value not in (None, ''):
                ggsave_options.append(f'    , {option} = {value}')
        lines = ['library(ampvis2, quietly = TRUE)', f'''d <- readRDS("{inputs.get('data', '')}")''', 'plot <- amp_octave(', '    d,', f'''    tax_aggregate = "{inputs.get('tax_aggregate', 'OTU') or 'OTU'}",''']
        if str(inputs.get('group_by', '')).strip():
            lines.extend([f'''    group_by = "{inputs.get('group_by')}",''', f'''    scales = "{inputs.get('scales', 'fixed') or 'fixed'}",'''])
        lines.extend(['    num_threads = 1', ')', f'ggsave("{out}/plot.{out_format}",', '    print(plot),', ',\n'.join(ggsave_options), ')'])
        return '\n'.join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/octave.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f'plot.{cls._out_format(inputs)}']

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float) -> bool | str:
        raw = inputs.get(name)
        if raw in (None, ''):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f'{name} must be a number'
        if value < minimum:
            return f'{name} must be >= {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        for name, options, default in (('tax_aggregate', cls.TAX_LEVELS, 'OTU'), ('scales', cls.SCALE_OPTIONS, 'fixed'), ('out_format', cls.OUT_FORMATS, 'pdf')):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        for name in ('plot_width', 'plot_height'):
            validation = cls._validate_number(inputs, name, 1)
            if validation is not True:
                return validation
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'})}, 'optional': {'metadata_list': ('TSV', {'default': '', 'description': 'Metadata list generated by ampvis2: load'}), 'tax_aggregate': ('STRING', {'default': 'OTU', 'options': cls.TAX_LEVELS, 'description': 'Taxonomic level used to aggregate OTUs'}), 'group_by': ('STRING', {'default': '', 'description': 'Discrete metadata variable used to group samples'}), 'scales': ('STRING', {'default': 'fixed', 'options': cls.SCALE_OPTIONS, 'description': 'Facet axis scale behavior when grouping samples'}), 'out_format': ('STRING', {'default': 'pdf', 'options': cls.OUT_FORMATS, 'description': 'Plot output format'}), 'plot_width': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot width in cm'}), 'plot_height': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot height in cm'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2OrdinateNode(CommandNode):
    """Generate ampvis2 ordination plots for microbial community comparisons."""
    NODE_ID = 'ampvis2_ordinate'
    DISPLAY_NAME = 'ampvis2 ordination plot'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Generate ampvis2 ordination plots for comparing microbial communities.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 ordination plot', 'amp_ordinate', 'ordination', 'vegan ordination', 'PCA', 'RDA', 'CCA', 'NMDS', 'PCoA', 'microbial communities']
    RETURN_TYPES = ('PDF', 'PDF')
    RETURN_NAMES = ('plot', 'screeplot')
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_ordinate.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    TYPE_OPTIONS = ['PCA', 'RDA', 'CA', 'CCA', 'DCA', 'NMDS', 'MMDS']
    DISTMEASURE_OPTIONS = ['wunifrac', 'unifrac', 'jsd', 'manhattan', 'euclidean', 'canberra', 'bray', 'kulczynski', 'jaccard', 'gower', 'altGower', 'morisita', 'horn', 'mountford', 'raup', 'binomial', 'chao', 'cao', 'mahalanobis', 'clark', 'chisq', 'chord', 'hellinger', 'aitchison', 'robust.aitchison']
    TRANSFORM_OPTIONS = ['none', 'total', 'max', 'freq', 'normalize', 'range', 'standardize', 'pa', 'chi.square', 'hellinger', 'log', 'sqrt']
    TAX_LEVELS = ['OTU', 'Species', 'Genus', 'Family', 'Order', 'Class', 'Phylum', 'Kingdom']
    TAX_EMPTY_OPTIONS = ['remove', 'best', 'OTU']
    OUT_FORMATS = ['pdf', 'png', 'svg']

    @classmethod
    def _r_bool(cls, value: Any, default: bool=False) -> str:
        if value in (None, ''):
            value = default
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no'} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return 'c(' + ', '.join((f'"{value}"' for value in values)) + ')'

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        return out_format if out_format in cls.OUT_FORMATS else 'pdf'

    @classmethod
    def _type(cls, inputs: dict[str, Any]) -> str:
        value = str(inputs.get('type', 'PCA') or 'PCA')
        return value if value in cls.TYPE_OPTIONS else 'PCA'

    @classmethod
    def _transform(cls, inputs: dict[str, Any]) -> str:
        transform = str(inputs.get('transform', '') or '')
        if transform:
            return transform
        if cls._type(inputs) in {'NMDS', 'MMDS'}:
            return 'none'
        return 'hellinger'

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float, default: Any=None, maximum: int | float | None=None) -> bool | str:
        raw = inputs.get(name, default)
        if raw in (None, ''):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f'{name} must be a number'
        if value < minimum:
            return f'{name} must be >= {minimum}'
        if maximum is not None and value > maximum:
            return f'{name} must be <= {maximum}'
        return True

    @classmethod
    def _add_optional_string_line(cls, lines: list[str], inputs: dict[str, Any], name: str) -> None:
        value = str(inputs.get(name, '') or '')
        if value.strip():
            lines.append(f'    {name} = "{value}",')

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        ordination_type = cls._type(inputs)
        ggsave_options = [f'    device = "{out_format}"']
        for name, option in (('plot_width', 'width'), ('plot_height', 'height')):
            value = inputs.get(name)
            if value not in (None, ''):
                ggsave_options.append(f'    , {option} = {value}')
        lines = ['library(ampvis2, quietly = TRUE)', f'''data <- readRDS("{inputs.get('data', '')}")''', 'details <- amp_ordinate(', '    data,', f"    filter_species = {(inputs.get('filter_species', 0.1) if inputs.get('filter_species') not in (None, '') else 0.1)},", f'    type = "{ordination_type}",']
        if ordination_type in {'MMDS', 'NMDS'}:
            lines.append(f'''    distmeasure = "{inputs.get('distmeasure', 'bray') or 'bray'}",''')
        lines.append(f'    transform = "{cls._transform(inputs)}",')
        if ordination_type in {'RDA', 'CCA'}:
            lines.append(f"    constrain = {cls._r_vector(_as_list(inputs.get('constrain')))},")
        lines.append(f"    print_caption = {cls._r_bool(inputs.get('print_caption'), False)},")
        for name in ('sample_color_by', 'sample_shape_by', 'sample_colorframe', 'sample_colorframe_label', 'sample_label_by'):
            cls._add_optional_string_line(lines, inputs, name)
        if str(inputs.get('sample_trajectory', '') or '').strip():
            lines.append(f'''    sample_trajectory = "{inputs.get('sample_trajectory')}",''')
        cls._add_optional_string_line(lines, inputs, 'sample_trajectory_group')
        if cls._r_bool(inputs.get('species_plot'), False) == 'TRUE':
            lines.extend(['    species_plot = TRUE,', f"    species_nlabels = {inputs.get('species_nlabels', 10) or 10},", f'''    species_label_taxonomy = "{inputs.get('species_label_taxonomy', 'Genus') or 'Genus'}",''', f"    species_label_size = {inputs.get('species_label_size', 3) or 3},"])
        cls._add_optional_string_line(lines, inputs, 'envfit_factor')
        cls._add_optional_string_line(lines, inputs, 'envfit_numeric')
        lines.extend([f"    envfit_signif_level = {(inputs.get('envfit_signif_level', 0.005) if inputs.get('envfit_signif_level') not in (None, '') else 0.005)},", f"    repel_labels = {cls._r_bool(inputs.get('repel_labels'), False)},", f"    opacity = {(inputs.get('opacity', 0.8) if inputs.get('opacity') not in (None, '') else 0.8)},", f'''    tax_empty = "{inputs.get('tax_empty', 'best') or 'best'}",''', '    detailed_output = TRUE', ')', 'plot <- details$plot', f'ggsave("{out}/plot.{out_format}",', '    print(plot),', ',\n'.join(ggsave_options), ')'])
        if inputs.get('output_screeplot'):
            lines.append(f'ggsave("{out}/screeplot.{out_format}", print(details$screeplot), device = "{out_format}")')
        return '\n'.join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/ordinate.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        out_format = cls._out_format(inputs)
        outputs = [out / f'plot.{out_format}']
        if inputs.get('output_screeplot'):
            outputs.append(out / f'screeplot.{out_format}')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        for name, options, default in (('type', cls.TYPE_OPTIONS, 'PCA'), ('distmeasure', cls.DISTMEASURE_OPTIONS, 'bray'), ('transform', cls.TRANSFORM_OPTIONS, cls._transform(inputs)), ('species_label_taxonomy', cls.TAX_LEVELS, 'Genus'), ('tax_empty', cls.TAX_EMPTY_OPTIONS, 'best'), ('out_format', cls.OUT_FORMATS, 'pdf')):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        if cls._type(inputs) in {'RDA', 'CCA'} and (not _as_list(inputs.get('constrain'))):
            return 'constrain must include at least one metadata variable for RDA/CCA'
        for name, minimum, default, maximum in (('filter_species', 0, 0.1, None), ('species_nlabels', 1, 10, None), ('species_label_size', 1, 3, None), ('envfit_signif_level', 0, 0.005, 1), ('opacity', 0, 0.8, 1), ('plot_width', 1, None, None), ('plot_height', 1, None, None)):
            validation = cls._validate_number(inputs, name, minimum, default, maximum)
            if validation is not True:
                return validation
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'})}, 'optional': {'metadata_list': ('TSV', {'default': '', 'description': 'Metadata list generated by ampvis2: load'}), 'filter_species': ('FLOAT', {'default': 0.1, 'min': 0, 'description': 'Remove low-abundance OTUs below this percent threshold'}), 'type': ('STRING', {'default': 'PCA', 'options': cls.TYPE_OPTIONS, 'description': 'Ordination method'}), 'distmeasure': ('STRING', {'default': 'bray', 'options': cls.DISTMEASURE_OPTIONS, 'description': 'Distance measure for NMDS/MMDS'}), 'transform': ('STRING', {'default': '', 'options': cls.TRANSFORM_OPTIONS, 'description': "Abundance transformation before ordination; blank uses Galaxy's method-specific default"}), 'constrain': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Metadata variables constraining RDA/CCA analyses'}), 'print_caption': ('BOOLEAN', {'default': False, 'description': 'Auto-generate a figure caption'}), 'sample_color_by': ('STRING', {'default': '', 'description': 'Metadata variable used to color sample points'}), 'sample_shape_by': ('STRING', {'default': '', 'description': 'Metadata variable used to shape sample points'}), 'sample_colorframe': ('STRING', {'default': '', 'description': 'Metadata variable used to frame sample points'}), 'sample_colorframe_label': ('STRING', {'default': '', 'description': 'Metadata variable used to label sample frames'}), 'sample_label_by': ('STRING', {'default': '', 'description': 'Metadata variable used to label sample points'}), 'sample_trajectory': ('STRING', {'default': '', 'description': 'Metadata variable used to draw sample trajectories'}), 'sample_trajectory_group': ('STRING', {'default': '', 'description': 'Metadata variable grouping sample trajectories'}), 'species_plot': ('BOOLEAN', {'default': False, 'description': 'Plot species points'}), 'species_nlabels': ('INT', {'default': 10, 'min': 1, 'description': 'Number of extreme species labels to plot'}), 'species_label_taxonomy': ('STRING', {'default': 'Genus', 'options': cls.TAX_LEVELS, 'description': 'Taxonomic level used to label species points'}), 'species_label_size': ('INT', {'default': 3, 'min': 1, 'description': 'Species label text size'}), 'envfit_factor': ('STRING', {'default': '', 'description': 'Categorical metadata variable to fit onto the ordination'}), 'envfit_numeric': ('STRING', {'default': '', 'description': 'Numeric metadata variable to fit as arrows'}), 'envfit_signif_level': ('FLOAT', {'default': 0.005, 'min': 0, 'max': 1, 'description': 'Significance threshold for envfit results'}), 'repel_labels': ('BOOLEAN', {'default': False, 'description': 'Repel labels to reduce overlap'}), 'opacity': ('FLOAT', {'default': 0.8, 'min': 0, 'max': 1, 'description': 'Point and color-frame opacity'}), 'tax_empty': ('STRING', {'default': 'best', 'options': cls.TAX_EMPTY_OPTIONS, 'description': 'How to show OTUs without taxonomy'}), 'out_format': ('STRING', {'default': 'pdf', 'options': cls.OUT_FORMATS, 'description': 'Plot output format'}), 'plot_width': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot width in cm'}), 'plot_height': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot height in cm'}), 'output_screeplot': ('BOOLEAN', {'default': False, 'description': 'Also output the ordination screeplot'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2OtuNetworkNode(CommandNode):
    """Generate ampvis2 OTU network plots connecting taxa and samples."""
    NODE_ID = 'ampvis2_otu_network'
    DISPLAY_NAME = 'ampvis2 OTU network plot'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Generate network plots connecting taxa and samples from an ampvis2 RDS dataset.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 OTU network plot', 'amp_otu_network', 'OTU network', 'taxa sample network', 'ggnet2', 'microbiome network']
    RETURN_TYPES = ('PDF',)
    RETURN_NAMES = ('plot',)
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_otu_network.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    TAX_LEVELS = ['OTU', 'Species', 'Genus', 'Family', 'Order', 'Class', 'Phylum', 'Kingdom']
    TAX_EMPTY_OPTIONS = ['remove', 'best', 'OTU']
    TAX_SHOW_MODES = ['number', 'explicit']
    OUT_FORMATS = ['pdf', 'png', 'svg']

    @classmethod
    def _r_bool(cls, value: Any, default: bool=False) -> str:
        if value in (None, ''):
            value = default
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no'} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return 'c(' + ', '.join((f'"{value}"' for value in values)) + ')'

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        return out_format if out_format in cls.OUT_FORMATS else 'pdf'

    @classmethod
    def _tax_show(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get('tax_show_mode', 'number') or 'number') == 'explicit':
            return cls._r_vector(_as_list(inputs.get('tax_show')))
        return str(inputs.get('tax_show', 10) or 10)

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        tax_add = _as_list(inputs.get('tax_add'))
        ggsave_options = [f'    device = "{out_format}"']
        for name, option in (('plot_width', 'width'), ('plot_height', 'height')):
            value = inputs.get(name)
            if value not in (None, ''):
                ggsave_options.append(f'    , {option} = {value}')
        lines = ['library(ampvis2, quietly = TRUE)', f'''data <- readRDS("{inputs.get('data', '')}")''', 'plot <- amp_otu_network(', '    data,', f"    min_abundance = {(inputs.get('min_abundance', 0) if inputs.get('min_abundance') not in (None, '') else 0)},"]
        if str(inputs.get('color_by', '') or '').strip():
            lines.append(f'''    color_by = "{inputs.get('color_by')}",''')
        lines.extend([f'''    tax_aggregate = "{inputs.get('tax_aggregate', 'Phylum') or 'Phylum'}",''', f"    tax_add = {(cls._r_vector(tax_add) if tax_add else 'NULL')},", f'    tax_show = {cls._tax_show(inputs)},', '    tax_class = NULL,', f'''    tax_empty = "{inputs.get('tax_empty', 'best') or 'best'}",''', f"    normalise = {cls._r_bool(inputs.get('normalise'), True)}", ')', f'ggsave("{out}/plot.{out_format}",', '    print(plot),', ',\n'.join(ggsave_options), ')'])
        return '\n'.join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/otu_network.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f'plot.{cls._out_format(inputs)}']

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float, default: Any=None) -> bool | str:
        raw = inputs.get(name, default)
        if raw in (None, ''):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f'{name} must be a number'
        if value < minimum:
            return f'{name} must be >= {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        for name, options, default in (('tax_aggregate', cls.TAX_LEVELS, 'Phylum'), ('tax_show_mode', cls.TAX_SHOW_MODES, 'number'), ('tax_empty', cls.TAX_EMPTY_OPTIONS, 'best'), ('out_format', cls.OUT_FORMATS, 'pdf')):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        unsupported_tax_add = [level for level in _as_list(inputs.get('tax_add')) if level not in cls.TAX_LEVELS]
        if unsupported_tax_add:
            return f"tax_add contains unsupported values: {', '.join(unsupported_tax_add)}"
        if str(inputs.get('tax_show_mode', 'number') or 'number') == 'explicit':
            if not _as_list(inputs.get('tax_show')):
                return 'tax_show must include at least one taxon when tax_show_mode is explicit'
        else:
            validation = cls._validate_number(inputs, 'tax_show', 1, 10)
            if validation is not True:
                return validation
        for name, minimum, default in (('min_abundance', 0, 0), ('plot_width', 1, None), ('plot_height', 1, None)):
            validation = cls._validate_number(inputs, name, minimum, default)
            if validation is not True:
                return validation
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'})}, 'optional': {'metadata_list': ('TSV', {'default': '', 'description': 'Metadata list generated by ampvis2: load'}), 'min_abundance': ('FLOAT', {'default': 0, 'min': 0, 'description': 'Minimum per-sample taxa abundance'}), 'color_by': ('STRING', {'default': '', 'description': 'Metadata variable used to color samples'}), 'tax_aggregate': ('STRING', {'default': 'Phylum', 'options': cls.TAX_LEVELS, 'description': 'Taxonomic level used to aggregate OTUs'}), 'tax_add': ('STRING_LIST', {'default': [], 'multiple': True, 'options': cls.TAX_LEVELS, 'description': 'Additional taxonomic levels to display'}), 'tax_show_mode': ('STRING', {'default': 'number', 'options': cls.TAX_SHOW_MODES, 'description': 'Limit displayed taxa by count or explicit list'}), 'taxonomy_list': ('TSV', {'default': '', 'description': 'Taxonomy list generated by ampvis2: load for explicit taxon selection'}), 'tax_show': ('STRING', {'default': 10, 'description': 'Number of taxa or explicit taxa to display'}), 'tax_empty': ('STRING', {'default': 'best', 'options': cls.TAX_EMPTY_OPTIONS, 'description': 'How to show OTUs without taxonomy'}), 'normalise': ('BOOLEAN', {'default': True, 'description': 'Transform OTU read counts to percent per sample'}), 'out_format': ('STRING', {'default': 'pdf', 'options': cls.OUT_FORMATS, 'description': 'Plot output format'}), 'plot_width': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot width in cm'}), 'plot_height': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot height in cm'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2RankAbundanceNode(CommandNode):
    """Generate ampvis2 rank-abundance curves by sample group."""
    NODE_ID = 'ampvis2_rankabundance'
    DISPLAY_NAME = 'ampvis2 rank abundance plot'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Generate rank-abundance curves from grouped ampvis2 samples.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 rank abundance plot', 'amp_rankabundance', 'rank abundance curve', 'cumulative read abundance', 'OTU rank abundance', 'microbiome diversity']
    RETURN_TYPES = ('PDF',)
    RETURN_NAMES = ('plot',)
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_rankabundance.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    OUT_FORMATS = ['pdf', 'png', 'svg']

    @classmethod
    def _r_bool(cls, value: Any, default: bool=False) -> str:
        if value in (None, ''):
            value = default
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no'} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        return out_format if out_format in cls.OUT_FORMATS else 'pdf'

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        ggsave_options = [f'    device = "{out_format}"']
        for name, option in (('plot_width', 'width'), ('plot_height', 'height')):
            value = inputs.get(name)
            if value not in (None, ''):
                ggsave_options.append(f'    , {option} = {value}')
        return '\n'.join(['library(ampvis2, quietly = TRUE)', f'''data <- readRDS("{inputs.get('data', '')}")''', 'plot <- amp_rankabundance(', '    data,', f'''    group_by = "{inputs.get('group_by', '')}",''', f"    showSD = {cls._r_bool(inputs.get('showSD'), True)},", f"    log10_x = {cls._r_bool(inputs.get('log10_x'), True)}", ')', f'ggsave("{out}/plot.{out_format}",', '    print(plot),', ',\n'.join(ggsave_options), ')'])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/rankabundance.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f'plot.{cls._out_format(inputs)}']

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float) -> bool | str:
        raw = inputs.get(name)
        if raw in (None, ''):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f'{name} must be a number'
        if value < minimum:
            return f'{name} must be >= {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        if not str(inputs.get('metadata_list', '')).strip():
            return 'metadata_list is required'
        if not str(inputs.get('group_by', '')).strip():
            return 'group_by is required'
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        if out_format not in cls.OUT_FORMATS:
            return f"out_format must be one of: {', '.join(cls.OUT_FORMATS)}"
        for name in ('plot_width', 'plot_height'):
            validation = cls._validate_number(inputs, name, 1)
            if validation is not True:
                return validation
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'}), 'metadata_list': ('TSV', {'description': 'Metadata list generated by ampvis2: load'}), 'group_by': ('STRING', {'description': 'Discrete metadata variable used to group samples'})}, 'optional': {'showSD': ('BOOLEAN', {'default': True, 'description': 'Show standard deviation from mean intervals'}), 'log10_x': ('BOOLEAN', {'default': True, 'description': 'Log10-transform the x axis to emphasize abundant OTUs'}), 'out_format': ('STRING', {'default': 'pdf', 'options': cls.OUT_FORMATS, 'description': 'Plot output format'}), 'plot_width': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot width in cm'}), 'plot_height': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot height in cm'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2RarecurveNode(CommandNode):
    """Generate ampvis2 rarefaction curves for observed OTUs per sample."""
    NODE_ID = 'ampvis2_rarecurve'
    DISPLAY_NAME = 'ampvis2 rarefaction curve'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Generate rarefaction curves showing reads versus observed OTUs for ampvis2 samples.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 rarefaction curve', 'amp_rarecurve', 'amp_rarefaction_curve', 'rarefaction curve', 'observed OTUs', 'reads versus observed OTUs', 'microbiome rarefaction']
    RETURN_TYPES = ('PDF',)
    RETURN_NAMES = ('plot',)
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_rarecurve.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    FACET_SCALE_OPTIONS = ['fixed', 'free', 'free_x', 'free_y']
    OUT_FORMATS = ['pdf', 'png', 'svg']

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        return out_format if out_format in cls.OUT_FORMATS else 'pdf'

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        ggsave_options = [f'    device = "{out_format}"']
        for name, option in (('plot_width', 'width'), ('plot_height', 'height')):
            value = inputs.get(name)
            if value not in (None, ''):
                ggsave_options.append(f'    {option} = {value}')
        args = ['    data', f"    stepsize = {(inputs.get('stepsize', 1000) if inputs.get('stepsize') not in (None, '') else 1000)}"]
        if str(inputs.get('color_by', '') or '').strip():
            args.append(f'''    color_by = "{inputs.get('color_by')}"''')
        if str(inputs.get('facet_by', '') or '').strip():
            args.append(f'''    facet_by = "{inputs.get('facet_by')}"''')
            if str(inputs.get('facet_scales', '') or '').strip():
                args.append(f'''    facet_scales = "{inputs.get('facet_scales')}"''')
        lines = ['library(ampvis2, quietly = TRUE)', f'''data <- readRDS("{inputs.get('data', '')}")''', 'plot <- amp_rarecurve(', ',\n'.join(args)]
        lines.extend([')', f'ggsave("{out}/plot.{out_format}",', '    print(plot),', ',\n'.join(ggsave_options), ')'])
        return '\n'.join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/rarecurve.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f'plot.{cls._out_format(inputs)}']

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float, default: Any=None) -> bool | str:
        raw = inputs.get(name, default)
        if raw in (None, ''):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f'{name} must be a number'
        if value < minimum:
            return f'{name} must be >= {minimum}'
        return True

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        for name, options, default in (('facet_scales', cls.FACET_SCALE_OPTIONS, 'fixed'), ('out_format', cls.OUT_FORMATS, 'pdf')):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        for name, minimum, default in (('stepsize', 1, 1000), ('plot_width', 1, None), ('plot_height', 1, None)):
            validation = cls._validate_number(inputs, name, minimum, default)
            if validation is not True:
                return validation
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'})}, 'optional': {'metadata_list': ('TSV', {'default': '', 'description': 'Metadata list generated by ampvis2: load'}), 'stepsize': ('INT', {'default': 1000, 'min': 1, 'description': 'Read-count increment between rarefaction points'}), 'color_by': ('STRING', {'default': '', 'description': 'Metadata variable used to color sample curves'}), 'facet_by': ('STRING', {'default': '', 'description': 'Metadata variable used to split curves into panels'}), 'facet_scales': ('STRING', {'default': 'fixed', 'options': cls.FACET_SCALE_OPTIONS, 'description': 'Axis scaling mode for faceted panels'}), 'out_format': ('STRING', {'default': 'pdf', 'options': cls.OUT_FORMATS, 'description': 'Plot output format'}), 'plot_width': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot width in cm'}), 'plot_height': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot height in cm'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2SetMetadataNode(CommandNode):
    """Set ampvis2 metadata column classes and regenerate metadata selectors."""
    NODE_ID = 'ampvis2_setmetadata'
    DISPLAY_NAME = 'ampvis2 set metadata'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq', 'r-lubridate']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Manually set ampvis2 sample metadata column types and regenerate the metadata list.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 set metadata', 'metadata type conversion', 'metadata classes', 'as.numeric metadata', 'as.integer metadata', 'lubridate as_date', 'sample metadata list']
    RETURN_TYPES = ('FILE', 'TSV')
    RETURN_NAMES = ('ampvis', 'metadata_list_out')
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/blob/main/tools/ampvis2/setmetadata.xml'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    TYPE_INPUTS = ('character', 'numbers', 'integers', 'dates')

    @classmethod
    def _column_names(cls, inputs: dict[str, Any], name: str) -> list[str]:
        return [str(value).strip() for value in _as_list(inputs.get(name)) if str(value).strip()]

    @classmethod
    def _raw_column_names(cls, value: Any) -> list[str]:
        if value is None or value == '':
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value]
        return [str(value).strip()]

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        lines = ['library(lubridate, quietly = TRUE)', f'''data <- readRDS("{inputs.get('data', '')}")''']
        for column in cls._column_names(inputs, 'character'):
            lines.append(f'data$metadata${column} <- as.character(data$metadata${column})')
        for column in cls._column_names(inputs, 'numbers'):
            lines.append(f'data$metadata${column} <- as.numeric(data$metadata${column})')
        for column in cls._column_names(inputs, 'integers'):
            lines.append(f'data$metadata${column} <- as.integer(data$metadata${column})')
        for column in cls._column_names(inputs, 'dates'):
            lines.append(f'data$metadata${column} <- as_date(data$metadata${column})')
        lines.extend([f'saveRDS(data, "{out}/ampvis.rds")', *Ampvis2LoadNode._metadata_list_lines(out), 'data'])
        return '\n'.join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/setmetadata.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'ampvis.rds', out / 'metadata_list.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        if not str(inputs.get('metadata_list', '')).strip():
            return 'metadata_list is required'
        raw_values = [column for name in cls.TYPE_INPUTS for column in cls._raw_column_names(inputs.get(name))]
        if any((not column for column in raw_values)):
            return 'metadata column names must be non-empty'
        seen: set[str] = set()
        duplicates: list[str] = []
        for column in raw_values:
            if column in seen and column not in duplicates:
                duplicates.append(column)
            seen.add(column)
        if duplicates:
            return f"metadata columns can only be assigned to one type: {', '.join(duplicates)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'}), 'metadata_list': ('TSV', {'description': 'Metadata list generated by ampvis2: load'})}, 'optional': {'character': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Metadata variables to keep or cast as character values'}), 'numbers': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Metadata variables to cast with as.numeric'}), 'integers': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Discrete numerical metadata variables to cast with as.integer'}), 'dates': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Date metadata variables to cast with lubridate::as_date'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2SubsetSamplesNode(CommandNode):
    """Subset ampvis2 samples by metadata variable values."""
    NODE_ID = 'ampvis2_subset_samples'
    DISPLAY_NAME = 'ampvis2 subset samples'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Subset ampvis2 samples by sample metadata values.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 subset samples', 'amp_subset_samples', 'amp_filter_samples', 'sample metadata filtering', 'metadata values', 'rarefy samples', 'remove absent OTUs']
    RETURN_TYPES = ('FILE', 'TSV')
    RETURN_NAMES = ('ampvis', 'metadata_list_out')
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_filter_samples.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True

    @classmethod
    def _r_bool(cls, value: Any, default: bool=False) -> str:
        if value in (None, ''):
            value = default
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no'} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _raw_values(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value]
        text = str(value).strip()
        if not text:
            return []
        return [part.strip() for part in text.split(',')]

    @classmethod
    def _values(cls, inputs: dict[str, Any]) -> list[str]:
        return [value for value in cls._raw_values(inputs.get('vals')) if value]

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return 'c(' + ', '.join((f'"{value}"' for value in values)) + ')'

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float, default: Any=None) -> bool | str:
        raw = inputs.get(name, default)
        if raw in (None, ''):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f'{name} must be a number'
        if value < minimum:
            return f'{name} must be >= {minimum}'
        return True

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        values = cls._values(inputs)
        invert = '! ' if inputs.get('invert') else ''
        lines = ['library(ampvis2, quietly = TRUE)', f'''data <- readRDS("{inputs.get('data', '')}")''', 'data <- amp_subset_samples(', '    data,', f"    {invert}{inputs.get('var', '')} %in% {cls._r_vector(values)},", f"    minreads = {(inputs.get('minreads', 0) if inputs.get('minreads') not in (None, '') else 0)},"]
        if inputs.get('rarefy') not in (None, ''):
            lines.append(f"    rarefy = {inputs.get('rarefy')},")
        lines.extend([f"    normalise = {cls._r_bool(inputs.get('normalise'), False)},", f"    removeAbsents = {cls._r_bool(inputs.get('removeAbsents'), True)}", ')', f'saveRDS(data, "{out}/ampvis.rds")', *Ampvis2LoadNode._metadata_list_lines(out), 'data'])
        return '\n'.join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/subset_samples.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'ampvis.rds', out / 'metadata_list.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        if not str(inputs.get('metadata_list', '')).strip():
            return 'metadata_list is required'
        if not str(inputs.get('var', '')).strip():
            return 'var is required'
        raw_values = cls._raw_values(inputs.get('vals'))
        if not raw_values:
            return 'vals must include at least one metadata value'
        if any((not value for value in raw_values)):
            return 'metadata values must be non-empty'
        for name, minimum, default in (('minreads', 0, 0), ('rarefy', 0, None)):
            validation = cls._validate_number(inputs, name, minimum, default)
            if validation is not True:
                return validation
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'}), 'metadata_list': ('TSV', {'description': 'Metadata list generated by ampvis2: load'}), 'var': ('STRING', {'description': 'Metadata variable used to select samples'}), 'vals': ('STRING_LIST', {'multiple': True, 'description': 'Metadata values to include or exclude'})}, 'optional': {'invert': ('BOOLEAN', {'default': False, 'description': 'Invert the metadata value selection'}), 'minreads': ('INT', {'default': 0, 'min': 0, 'description': 'Minimum reads per sample before filtering'}), 'rarefy': ('INT', {'default': '', 'min': 0, 'description': 'Optional rarefaction depth after minreads filtering'}), 'normalise': ('BOOLEAN', {'default': False, 'description': 'Transform OTU read counts to percent per sample'}), 'removeAbsents': ('BOOLEAN', {'default': True, 'description': 'Remove OTUs absent after sample filtering'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2SubsetTaxaNode(CommandNode):
    """Subset ampvis2 data by taxonomy vector or selected taxa file."""
    NODE_ID = 'ampvis2_subset_taxa'
    DISPLAY_NAME = 'ampvis2 subset data'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Subset ampvis2 data by matching taxa across taxonomy ranks.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 subset data', 'ampvis2 subset taxa', 'amp_subset_taxa', 'amp_filter_taxa', 'taxonomy filtering', 'selected taxonomy list', 'remove taxa']
    RETURN_TYPES = ('FILE', 'TSV')
    RETURN_NAMES = ('ampvis', 'taxonomy_list_out')
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_filter_taxa.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    SELECT_OPTIONS = ['option_input_file', 'option_input_selected_file']

    @classmethod
    def _r_bool(cls, value: Any, default: bool=False) -> str:
        if value in (None, ''):
            value = default
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no'} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _raw_values(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value]
        text = str(value).strip()
        if not text:
            return []
        return [part.strip() for part in text.split(',')]

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return 'c(' + ', '.join((f'"{value}"' for value in values if value)) + ')'

    @classmethod
    def _select_param(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('select_param', 'option_input_file') or 'option_input_file')

    @classmethod
    def _tax_vector_lines(cls, inputs: dict[str, Any]) -> list[str]:
        if cls._select_param(inputs) == 'option_input_selected_file':
            return [f'''file_path <- "{inputs.get('selected_taxonomy_list', '')}"''', 'lines <- readLines(file_path)', 'tax_vector <- trimws(lines)']
        return [f"tax_vector <- {cls._r_vector(cls._raw_values(inputs.get('tax_vector')))}"]

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        lines = ['library(ampvis2, quietly = TRUE)', f'''data <- readRDS("{inputs.get('data', '')}")''', '', *cls._tax_vector_lines(inputs), 'data <- amp_subset_taxa(', '    data,', '    tax_vector = tax_vector,', f"    normalise = {cls._r_bool(inputs.get('normalise'), False)},", f"    remove = {cls._r_bool(inputs.get('remove'), False)}", ')', '', f'saveRDS(data, "{out}/ampvis.rds")', *Ampvis2LoadNode._taxonomy_list_lines(out), 'data']
        return '\n'.join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/subset_taxa.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'ampvis.rds', out / 'taxonomy_list.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        select_param = cls._select_param(inputs)
        if select_param not in cls.SELECT_OPTIONS:
            return f"select_param must be one of: {', '.join(cls.SELECT_OPTIONS)}"
        if select_param == 'option_input_selected_file':
            if not str(inputs.get('selected_taxonomy_list', '')).strip():
                return 'selected_taxonomy_list is required when select_param is option_input_selected_file'
        else:
            if not str(inputs.get('taxonomy_list', '')).strip():
                return 'taxonomy_list is required when select_param is option_input_file'
            tax_values = cls._raw_values(inputs.get('tax_vector'))
            if not tax_values:
                return 'tax_vector must include at least one taxon'
            if any((not value for value in tax_values)):
                return 'tax_vector values must be non-empty'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'}), 'select_param': ('STRING', {'default': 'option_input_file', 'options': cls.SELECT_OPTIONS, 'description': 'Choose taxa from an ampvis2 taxonomy list or from an uploaded selected-taxa file'})}, 'optional': {'taxonomy_list': ('TSV', {'default': '', 'description': 'Taxonomy list generated by ampvis2: load'}), 'tax_vector': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Taxa to keep or remove when using the taxonomy list'}), 'selected_taxonomy_list': ('TSV', {'default': '', 'description': 'File containing selected taxa, one taxon per line'}), 'normalise': ('BOOLEAN', {'default': False, 'description': 'Transform OTU read counts to percent per sample'}), 'remove': ('BOOLEAN', {'default': False, 'description': 'Remove selected taxa instead of keeping only them'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2TimeseriesNode(CommandNode):
    """Generate ampvis2 time-series abundance plots."""
    NODE_ID = 'ampvis2_timeseries'
    DISPLAY_NAME = 'ampvis2 timeseries plot'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Generate ampvis2 time-series plots of relative read abundance over time.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 timeseries plot', 'amp_timeseries', 'time-series abundance', 'relative read abundance over time', 'date metadata', 'taxon facets', 'microbiome time series']
    RETURN_TYPES = ('PDF',)
    RETURN_NAMES = ('plot',)
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_timeseries.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    TAX_LEVELS = ['OTU', 'Species', 'Genus', 'Family', 'Order', 'Class', 'Phylum', 'Kingdom']
    TAX_EMPTY_OPTIONS = ['remove', 'best', 'OTU']
    TAX_SHOW_MODES = ['number', 'explicit']
    SCALE_OPTIONS = ['fixed', 'free', 'free_x', 'free_y']
    OUT_FORMATS = ['pdf', 'png', 'svg']

    @classmethod
    def _r_bool(cls, value: Any, default: bool=False) -> str:
        if value in (None, ''):
            value = default
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no'} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return 'c(' + ', '.join((f'"{value}"' for value in values)) + ')'

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        return out_format if out_format in cls.OUT_FORMATS else 'pdf'

    @classmethod
    def _tax_show(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get('tax_show_mode', 'number') or 'number') == 'explicit':
            return cls._r_vector(_as_list(inputs.get('tax_show')))
        return str(inputs.get('tax_show', 6) or 6)

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        tax_add = _as_list(inputs.get('tax_add'))
        ggsave_options = [f'    device = "{out_format}"']
        for name, option in (('plot_width', 'width'), ('plot_height', 'height')):
            value = inputs.get(name)
            if value not in (None, ''):
                ggsave_options.append(f'    {option} = {value}')
        lines = ['library(ampvis2, quietly = TRUE)', f'''data <- readRDS("{inputs.get('data', '')}")''', 'plot <- amp_timeseries(', '    data,', f'''    time_variable = "{inputs.get('time_variable', '')}",''']
        if str(inputs.get('group_by', '') or '').strip():
            lines.append(f'''    group_by = "{inputs.get('group_by')}",''')
        lines.extend([f'''    tax_aggregate = "{inputs.get('tax_aggregate', 'OTU') or 'OTU'}",''', f"    tax_add = {(cls._r_vector(tax_add) if tax_add else 'NULL')},", f'    tax_show = {cls._tax_show(inputs)},', '    tax_class = NULL,', f'''    tax_empty = "{inputs.get('tax_empty', 'best') or 'best'}",''', f"    split = {cls._r_bool(inputs.get('split'), False)},", f'''    scales = "{inputs.get('scales', 'free_y') or 'free_y'}",''', f"    normalise = {cls._r_bool(inputs.get('normalise'), True)},", '    plotly = FALSE,', '    format = "%Y-%m-%d"', ')', f'ggsave("{out}/plot.{out_format}",', '    print(plot),', ',\n'.join(ggsave_options), ')'])
        return '\n'.join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/timeseries.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f'plot.{cls._out_format(inputs)}']

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float, default: Any=None) -> bool | str:
        raw = inputs.get(name, default)
        if raw in (None, ''):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f'{name} must be a number'
        if value < minimum:
            return f'{name} must be >= {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        if not str(inputs.get('time_variable', '')).strip():
            return 'time_variable is required'
        for name, options, default in (('tax_aggregate', cls.TAX_LEVELS, 'OTU'), ('tax_show_mode', cls.TAX_SHOW_MODES, 'number'), ('tax_empty', cls.TAX_EMPTY_OPTIONS, 'best'), ('scales', cls.SCALE_OPTIONS, 'free_y'), ('out_format', cls.OUT_FORMATS, 'pdf')):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        unsupported_tax_add = [level for level in _as_list(inputs.get('tax_add')) if level not in cls.TAX_LEVELS]
        if unsupported_tax_add:
            return f"tax_add contains unsupported values: {', '.join(unsupported_tax_add)}"
        if str(inputs.get('tax_show_mode', 'number') or 'number') == 'explicit':
            if not _as_list(inputs.get('tax_show')):
                return 'tax_show must include at least one taxon when tax_show_mode is explicit'
        else:
            validation = cls._validate_number(inputs, 'tax_show', 1, 6)
            if validation is not True:
                return validation
        for name in ('plot_width', 'plot_height'):
            validation = cls._validate_number(inputs, name, 1, None)
            if validation is not True:
                return validation
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'}), 'time_variable': ('STRING', {'description': 'Date-compatible metadata variable used for the x axis'})}, 'optional': {'metadata_list': ('TSV', {'default': '', 'description': 'Metadata list generated by ampvis2: load'}), 'group_by': ('STRING', {'default': '', 'description': 'Discrete metadata variable used to group samples'}), 'tax_aggregate': ('STRING', {'default': 'OTU', 'options': cls.TAX_LEVELS, 'description': 'Taxonomic level used to aggregate OTUs'}), 'tax_add': ('STRING_LIST', {'default': [], 'multiple': True, 'options': cls.TAX_LEVELS, 'description': 'Additional taxonomic levels to display'}), 'tax_show_mode': ('STRING', {'default': 'number', 'options': cls.TAX_SHOW_MODES, 'description': 'Limit displayed taxa by count or explicit list'}), 'taxonomy_list': ('TSV', {'default': '', 'description': 'Taxonomy list generated by ampvis2: load for explicit taxon selection'}), 'tax_show': ('STRING', {'default': 6, 'description': 'Number of taxa or explicit taxa to display'}), 'tax_empty': ('STRING', {'default': 'best', 'options': cls.TAX_EMPTY_OPTIONS, 'description': 'How to show OTUs without taxonomy'}), 'split': ('BOOLEAN', {'default': False, 'description': 'Create a facet for each taxon'}), 'scales': ('STRING', {'default': 'free_y', 'options': cls.SCALE_OPTIONS, 'description': 'Axis scaling mode for facets'}), 'normalise': ('BOOLEAN', {'default': True, 'description': 'Transform OTU read counts to percent per sample'}), 'out_format': ('STRING', {'default': 'pdf', 'options': cls.OUT_FORMATS, 'description': 'Plot output format'}), 'plot_width': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot width in cm'}), 'plot_height': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot height in cm'})}, 'hidden': {'output': ('STRING', {})}}


class Ampvis2VennNode(CommandNode):
    """Generate ampvis2 Venn diagrams of shared core OTUs."""
    NODE_ID = 'ampvis2_venn'
    DISPLAY_NAME = 'ampvis2 venn diagram'
    REQUIRED_CONDA_PACKAGES = ['r-ampvis2', 'r-readr', 'bioconductor-phyloseq']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Generate ampvis2 Venn diagrams of core OTUs shared across sample groups.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ampvis2', 'ampvis2 venn diagram', 'amp_venn', 'Venn diagram', 'core OTUs', 'shared OTUs', 'sample group overlap', 'microbiome core community']
    RETURN_TYPES = ('PDF',)
    RETURN_NAMES = ('plot',)
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://kasperskytte.github.io/ampvis2/reference/amp_venn.html'
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}']
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = '2.8.11+galaxy2'
    SHELL = True
    OUT_FORMATS = ['pdf', 'png', 'svg']

    @classmethod
    def _r_bool(cls, value: Any, default: bool=False) -> str:
        if value in (None, ''):
            value = default
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no'} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        return out_format if out_format in cls.OUT_FORMATS else 'pdf'

    @classmethod
    def _number_value(cls, inputs: dict[str, Any], name: str, default: int | float) -> Any:
        value = inputs.get(name, default)
        return default if value in (None, '') else value

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        ggsave_options = [f'    device = "{out_format}"']
        for name, option in (('plot_width', 'width'), ('plot_height', 'height')):
            value = inputs.get(name)
            if value not in (None, ''):
                ggsave_options.append(f'    {option} = {value}')
        lines = ['library(ampvis2, quietly = TRUE)', f'''data <- readRDS("{inputs.get('data', '')}")''', 'plot <- amp_venn(', '    data,']
        if str(inputs.get('group_by', '') or '').strip():
            lines.append(f'''    group_by = "{inputs.get('group_by')}",''')
        lines.extend([f"    cut_a = {cls._number_value(inputs, 'cut_a', 0.1)},", f"    cut_f = {cls._number_value(inputs, 'cut_f', 80)},", f"    text_size = {cls._number_value(inputs, 'text_size', 5)},", f"    normalise = {cls._r_bool(inputs.get('normalise'), False)}", ')', f'ggsave("{out}/plot.{out_format}",', '    print(plot),', ',\n'.join(ggsave_options), ')'])
        return '\n'.join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f'{out}/venn.R'
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f'plot.{cls._out_format(inputs)}']

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float | None=None, maximum: int | float | None=None, default: Any=None) -> bool | str:
        raw = inputs.get(name, default)
        if raw in (None, ''):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f'{name} must be a number'
        if minimum is not None and value < minimum:
            return f'{name} must be >= {minimum}'
        if maximum is not None and value > maximum:
            return f'{name} must be <= {maximum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        for name in ('cut_a', 'cut_f'):
            validation = cls._validate_number(inputs, name, 0, 100)
            if validation is not True:
                return validation
        validation = cls._validate_number(inputs, 'text_size', 1, None)
        if validation is not True:
            return validation
        group_by = str(inputs.get('group_by', '') or '').strip()
        if group_by:
            groups = [value.strip() for value in group_by.split(',') if value.strip()]
            if len(groups) > 3:
                return 'group_by supports at most 3 groups'
        out_format = str(inputs.get('out_format', 'pdf') or 'pdf')
        if out_format not in cls.OUT_FORMATS:
            return f"out_format must be one of: {', '.join(cls.OUT_FORMATS)}"
        for name in ('plot_width', 'plot_height'):
            validation = cls._validate_number(inputs, name, 1, None)
            if validation is not True:
                return validation
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('FILE', {'description': 'Ampvis2 RDS dataset generated with ampvis2: load'})}, 'optional': {'metadata_list': ('TSV', {'default': '', 'description': 'Metadata list generated by ampvis2: load'}), 'group_by': ('STRING', {'default': '', 'description': 'Discrete metadata variable used to group samples, with at most 3 groups'}), 'cut_a': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 100, 'description': 'Exclude OTUs below this abundance percentage'}), 'cut_f': ('FLOAT', {'default': 80, 'min': 0, 'max': 100, 'description': 'Frequency percentage threshold for core OTUs'}), 'text_size': ('INT', {'default': 5, 'min': 1, 'description': 'Size of plotted text labels'}), 'normalise': ('BOOLEAN', {'default': False, 'description': 'Transform OTU read counts to percent per sample'}), 'out_format': ('STRING', {'default': 'pdf', 'options': cls.OUT_FORMATS, 'description': 'Plot output format'}), 'plot_width': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot width in cm'}), 'plot_height': ('FLOAT', {'default': '', 'min': 1, 'description': 'Optional plot height in cm'})}, 'hidden': {'output': ('STRING', {})}}
