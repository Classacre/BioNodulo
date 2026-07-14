"""circos — visualization node(s). One tool per file (extracted from wrapped_sequence_visualization.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class CircosNode(CommandNode):
    """Render Galaxy IUC Circos plots from karyotype, data, and link tracks."""
    NODE_ID = 'circos'
    DISPLAY_NAME = 'Circos'
    REQUIRED_CONDA_PACKAGES = ['circos', 'bcbiogff', 'biopython', 'pybigwig', 'circos-tools', 'grep', 'tar']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Visualize genomic data in a circular layout with the Galaxy IUC Circos wrapper.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Circos', 'circos', 'circular layout', 'circular genome plot', 'karyotype', '2D data tracks', 'link tracks', 'comparative genomics']
    RETURN_TYPES = ('IMAGE', 'IMAGE', 'TAR', 'TSV')
    RETURN_NAMES = ('output_png', 'output_svg', 'output_tar', 'karyotype_txt')
    REQUIRED_EXECUTABLES = ['python', 'grep', 'cp', 'ln', 'head', 'tar', 'circos']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos'
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = '0.69.8+galaxy12'
    SHELL = True
    REFERENCE_SOURCES = ['preset', 'history', 'cached', 'karyotype', 'lengths']
    UNITS = ['bases', 'kb', 'mb', 'gb']
    PRESET_KARYOTYPES = ['karyotype.arabidopsis.tair10.txt', 'karyotype.chimp.pt4.txt', 'karyotype.drosophila.dm6.hires.txt', 'karyotype.drosophila.hires.dm3.txt', 'karyotype.human.hg38.txt', 'karyotype.human.hg19.txt', 'karyotype.human.hg18.txt', 'karyotype.human.hg17.txt', 'karyotype.human.hg16.txt', 'karyotype.mouse.mm10.txt', 'karyotype.mouse.mm9.txt', 'karyotype.oryzasativa.txt', 'karyotype.rat.rn4.txt', 'karyotype.sorghum.txt', 'karyotype.yeast.txt', 'karyotype.zeamays.txt']
    LIMIT_DEFAULTS = {'max_ticks': 5000, 'max_ideograms': 200, 'max_links': 25000, 'max_points_per_track': 25000}
    LIMIT_MINIMUM = 200

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('reference_source', 'preset') or 'preset')

    @classmethod
    def _output_enabled(cls, inputs: dict[str, Any], key: str) -> bool:
        if key not in inputs:
            return key == 'output_png'
        return bool(inputs.get(key))

    @classmethod
    def _outputs_plot(cls, inputs: dict[str, Any]) -> bool:
        return cls._output_enabled(inputs, 'output_png') or cls._output_enabled(inputs, 'output_svg')

    @classmethod
    def _outputs_karyotype(cls, inputs: dict[str, Any]) -> bool:
        return cls._reference_source(inputs) not in {'karyotype', 'preset'}

    @classmethod
    def _conf_dir(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/circos/conf'

    @classmethod
    def _data_dir(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/circos/data'

    @classmethod
    def _karyotype_path(cls, inputs: dict[str, Any]) -> str:
        return f'{cls._conf_dir(inputs)}/karyotype.txt'

    @classmethod
    def _reference_commands(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        karyotype = cls._karyotype_path(inputs)
        source = cls._reference_source(inputs)
        if source == 'history':
            genome_ref = f'{out}/genomeref.fa'
            return [_shell_join(['ln', '-s', str(inputs.get('genome_fasta', '') or ''), genome_ref]), f"{_shell_join(['python', 'karyotype-from-fasta.py', genome_ref])} > {shlex.quote(karyotype)}"]
        if source == 'lengths':
            return f"{_shell_join(['python', 'karyotype-from-lengths.py', str(inputs.get('input_lengths', '') or '')])} > {shlex.quote(karyotype)}".split(' && ')
        if source == 'cached':
            lengths = str(inputs.get('cached_lengths', '') or '')
            if inputs.get('limit_chromosomes'):
                length_source = lengths
            else:
                length_source = f'<(head -n 50 {shlex.quote(lengths)})'
            return [f"{_shell_join(['python', 'karyotype-from-lengths.py', length_source])} > {shlex.quote(karyotype)}"]
        if source == 'karyotype':
            return [_shell_join(['cp', str(inputs.get('input_karyotype', '') or ''), karyotype])]
        return [_shell_join(['cp', f"karyotype/{str(inputs.get('preset_karyotype', 'karyotype.human.hg38.txt') or 'karyotype.human.hg38.txt')}", karyotype])]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        karyotype = cls._karyotype_path(inputs)
        commands = [_shell_join(['mkdir', '-p', cls._conf_dir(inputs), cls._data_dir(inputs)]), *cls._reference_commands(inputs), f"python karyotype-colors.py `grep -c '^chr\\s' {shlex.quote(karyotype)}` > {shlex.quote(f'{cls._conf_dir(inputs)}/karyotype-colors.conf')}", _shell_join(['touch', f'{cls._conf_dir(inputs)}/karyotype-colors.conf'])]
        if str(inputs.get('colour_profile', '') or '') == 'cg':
            commands.append(f"cat colours/cg.conf >> {shlex.quote(f'{cls._conf_dir(inputs)}/karyotype-colors.conf')}")
        if cls._outputs_karyotype(inputs):
            commands.append(_shell_join(['cp', karyotype, f'{out}/karyotype.txt']))
        for source, target in [('circos.conf', 'circos.conf'), ('ticks.conf', 'ticks.conf'), ('ideogram.conf', 'ideogram.conf'), ('data.conf', 'data.conf'), ('links.conf', 'links.conf'), ('galaxy_test_case.json', 'galaxy_test_case.json')]:
            commands.append(_shell_join(['cp', source, f'{cls._conf_dir(inputs)}/{target}']))
        for idx, track in enumerate(_as_list(inputs.get('data_tracks'))):
            commands.append(_shell_join(['cp', track, f'{cls._data_dir(inputs)}/data-{idx}.txt']))
        for idx, track in enumerate(_as_list(inputs.get('link_tracks'))):
            commands.append(_shell_join(['cp', track, f'{cls._data_dir(inputs)}/links-{idx}.txt']))
        if cls._output_enabled(inputs, 'output_tar'):
            commands.append(_shell_join(['tar', '-czf', f'{out}/circos.tar.gz', '-C', out, 'circos']))
        if cls._outputs_plot(inputs):
            commands.append(_shell_join(['cd', out]))
            commands.append(_shell_join(['circos', '-conf', 'circos/conf/circos.conf', '-noparanoid']))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        if cls._output_enabled(inputs, 'output_png'):
            outputs.append(out / 'circos.png')
        if cls._output_enabled(inputs, 'output_svg'):
            outputs.append(out / 'circos.svg')
        if cls._output_enabled(inputs, 'output_tar'):
            outputs.append(out / 'circos.tar.gz')
        if cls._outputs_karyotype(inputs):
            outputs.append(out / 'karyotype.txt')
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int=0) -> bool | str:
        value = inputs.get(key, default)
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if parsed < minimum:
            return f'{key} must be greater than or equal to {minimum}'
        return True

    @classmethod
    def _validate_track_list(cls, inputs: dict[str, Any], key: str) -> bool | str:
        raw = inputs.get(key)
        if isinstance(raw, (list, tuple)) and any((str(value) == '' for value in raw)):
            return f'{key} values must not be empty'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        source = cls._reference_source(inputs)
        if source not in cls.REFERENCE_SOURCES:
            return f"reference_source must be one of: {', '.join(cls.REFERENCE_SOURCES)}"
        required_by_source = {'history': 'genome_fasta', 'cached': 'cached_lengths', 'karyotype': 'input_karyotype', 'lengths': 'input_lengths'}
        required = required_by_source.get(source)
        if required and (not str(inputs.get(required, '') or '').strip()):
            return f'{required} is required when reference_source is {source}'
        preset = str(inputs.get('preset_karyotype', 'karyotype.human.hg38.txt') or 'karyotype.human.hg38.txt')
        if source == 'preset' and preset not in cls.PRESET_KARYOTYPES:
            return f"preset_karyotype must be one of: {', '.join(cls.PRESET_KARYOTYPES)}"
        if not any([cls._output_enabled(inputs, 'output_png'), cls._output_enabled(inputs, 'output_svg'), cls._output_enabled(inputs, 'output_tar'), cls._outputs_karyotype(inputs)]):
            return 'at least one of output_png, output_svg, output_tar, or generated karyotype_txt must be selected'
        units = str(inputs.get('units', 'mb') or 'mb')
        if units not in cls.UNITS:
            return f"units must be one of: {', '.join(cls.UNITS)}"
        for key, default in cls.LIMIT_DEFAULTS.items():
            validation = cls._validate_int_min(inputs, key, default, cls.LIMIT_MINIMUM)
            if validation is not True:
                return validation
        for key in ('data_tracks', 'link_tracks'):
            validation = cls._validate_track_list(inputs, key)
            if validation is not True:
                return validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reference_source': ('STRING', {'default': 'preset', 'options': cls.REFERENCE_SOURCES})}, 'optional': {'preset_karyotype': ('STRING', {'default': 'karyotype.human.hg38.txt', 'options': cls.PRESET_KARYOTYPES, 'description': 'Bundled Circos karyotype preset'}), 'genome_fasta': ('FASTA', {'default': '', 'description': 'Reference FASTA for history mode'}), 'input_karyotype': ('TSV', {'default': '', 'description': 'Custom Circos karyotype table'}), 'input_lengths': ('TSV', {'default': '', 'description': 'Sequence lengths table'}), 'cached_lengths': ('TSV', {'default': '', 'description': 'Cached reference lengths table'}), 'limit_chromosomes': ('STRING', {'default': '', 'description': 'Limit, filter, and order chromosomes'}), 'chromosomes_reverse': ('STRING', {'default': '', 'description': 'Chromosomes to draw in reverse order'}), 'units': ('STRING', {'default': 'mb', 'options': cls.UNITS}), 'data_tracks': ('TSV', {'default': [], 'is_list': True, 'description': '2D Circos data tracks'}), 'link_tracks': ('TSV', {'default': [], 'is_list': True, 'description': 'Six-column Circos link tracks'}), 'output_png': ('BOOLEAN', {'default': True, 'description': 'Output PNG plot'}), 'output_svg': ('BOOLEAN', {'default': False, 'description': 'Output SVG plot'}), 'output_tar': ('BOOLEAN', {'default': False, 'description': 'Output configuration archive'}), 'colour_profile': ('STRING', {'default': '', 'options': ['', 'cg']}), 'image_radius': ('INT', {'default': 1500, 'min': 500, 'max': 5000}), 'ideogram_radius': ('FLOAT', {'default': 0.9, 'min': 0}), 'ideogram_thickness': ('FLOAT', {'default': 30, 'min': 0}), 'angle_offset': ('INT', {'default': -90, 'min': -180, 'max': 180}), 'max_ticks': ('INT', {'default': 5000, 'min': cls.LIMIT_MINIMUM}), 'max_ideograms': ('INT', {'default': 200, 'min': cls.LIMIT_MINIMUM}), 'max_links': ('INT', {'default': 25000, 'min': cls.LIMIT_MINIMUM}), 'max_points_per_track': ('INT', {'default': 25000, 'min': cls.LIMIT_MINIMUM})}, 'hidden': {'output': ('STRING', {})}}


class CircosResampleNode(CommandNode):
    """Reduce dense Circos data tracks with the Circos tools resample utility."""
    NODE_ID = 'circos_resample'
    DISPLAY_NAME = 'Circos: Resample 1/2D data'
    REQUIRED_CONDA_PACKAGES = ['circos', 'circos-tools']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Reduce dense 1D/2D Circos data tracks before plotting.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Circos', 'circos_resample', 'resample', 'downsample', '1D track', '2D track', 'bin size', 'comparative genomics']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['resample', 'sed']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos'
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = '0.69.8+galaxy12'
    SHELL = True
    METHODS = ['-avg', '-min', '-max', '-sum', '-count']

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/resampled.tabular'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['resample', '-bin', str(inputs.get('bins', 1000000)), str(inputs.get('method', '-avg') or '-avg')]
        return f"{_shell_join(cmd)} < {shlex.quote(str(inputs.get('input', '')))} | sed 's/ /\\t/g' > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'resampled.tabular']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        try:
            bins = int(inputs.get('bins', 1000000))
        except (TypeError, ValueError):
            return 'bins must be an integer'
        if bins < 1:
            return 'bins must be greater than or equal to 1'
        method = str(inputs.get('method', '-avg') or '-avg')
        if method not in cls.METHODS:
            return f"method must be one of: {', '.join(cls.METHODS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('TSV', {'description': '1D/2D Circos data track'})}, 'optional': {'bins': ('INT', {'default': 1000000, 'min': 1, 'description': 'Bin size for resampling'}), 'method': ('STRING', {'default': '-avg', 'options': cls.METHODS})}, 'hidden': {'output': ('STRING', {})}}


class CircosGCSkewNode(CommandNode):
    """Calculate GC skew over a reference genome for Circos BigWig tracks."""
    NODE_ID = 'circos_gc_skew'
    DISPLAY_NAME = 'GC Skew'
    REQUIRED_CONDA_PACKAGES = ['circos', 'pybigwig', 'biopython']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Calculate GC skew over genomic sequences for Circos tracks.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Circos', 'GC skew', 'circos_gc_skew', 'genomic sequences', 'BigWig', 'comparative genomics']
    RETURN_TYPES = ('BIGWIG',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['python', 'ln']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos'
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = '0.69.8+galaxy12'
    SHELL = True
    REFERENCE_SOURCES = ['history', 'builtin']

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('reference_genome_source', 'history') or 'history')

    @classmethod
    def _reference_path(cls, inputs: dict[str, Any]) -> str:
        if cls._reference_source(inputs) == 'builtin':
            return str(inputs.get('builtin_path', inputs.get('builtin', '')) or '')
        return str(inputs.get('history_item', '') or '')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/gc_skew.bw'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        reference = cls._reference_path(inputs)
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {_shell_join(['ln', '-s', '-f', reference, 'reference.fa'])} && {_shell_join(['python', 'gc_skew.py', 'reference.fa', str(inputs.get('window', 100000)), cls._output_path(inputs)])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'gc_skew.bw']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        source = cls._reference_source(inputs)
        if source not in cls.REFERENCE_SOURCES:
            return f"reference_genome_source must be one of: {', '.join(cls.REFERENCE_SOURCES)}"
        if not cls._reference_path(inputs).strip():
            key = 'builtin_path' if source == 'builtin' else 'history_item'
            return f'{key} is required when reference_genome_source is {source}'
        try:
            window = int(inputs.get('window', 100000))
        except (TypeError, ValueError):
            return 'window must be an integer'
        if window < 1:
            return 'window must be greater than or equal to 1'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reference_genome_source': ('STRING', {'default': 'history', 'options': cls.REFERENCE_SOURCES})}, 'optional': {'history_item': ('FASTA', {'default': '', 'description': 'Reference genome FASTA from history'}), 'builtin_path': ('FASTA', {'default': '', 'description': 'Built-in reference genome FASTA path'}), 'window': ('INT', {'default': 100000, 'min': 1, 'description': 'Window size for GC skew'})}, 'hidden': {'output': ('STRING', {})}}


class CircosWiggleToScatterNode(CommandNode):
    """Convert bigWig intervals into Circos scatter track rows."""
    NODE_ID = 'circos_wiggle_to_scatter'
    DISPLAY_NAME = 'Circos: bigWig to Scatter'
    REQUIRED_CONDA_PACKAGES = ['circos', 'pybigwig']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Convert bigWig data into Circos scatter, line, or histogram tracks.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Circos', 'bigWig', 'scatter', 'line plot', 'histogram', 'wiggle', '2D track']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos'
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = '0.69.8+galaxy12'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/scatter.tabular'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['python', 'scatter-from-wiggle.py', str(inputs.get('input', ''))]
        return f'{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'scatter.tabular']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('BIGWIG', {'description': 'bigWig data file to convert'})}, 'hidden': {'output': ('STRING', {})}}


class CircosIntervalToTextNode(CommandNode):
    """Convert BED6+ or GFF3 intervals into Circos text label rows."""
    NODE_ID = 'circos_interval_to_text'
    DISPLAY_NAME = 'Circos: Interval to Circos Text Labels'
    REQUIRED_CONDA_PACKAGES = ['circos', 'bcbiogff', 'biopython']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Convert BED6+ or GFF3 intervals into Circos text-label tracks.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Circos', 'text labels', 'interval labels', 'BED6', 'GFF3', 'annotation labels']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos'
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = '0.69.8+galaxy12'
    SHELL = True
    REF_SOURCES = ['bed', 'gff3']

    @classmethod
    def _ref_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('ref_source', 'bed') or 'bed')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/text_labels.tabular'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        if cls._ref_source(inputs) == 'gff3':
            cmd = ['python', 'text-from-gff3.py', str(inputs.get('input', '')), str(inputs.get('attr', ''))]
        else:
            cmd = ['python', 'text-from-bed.py', str(inputs.get('input', ''))]
        return f'{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'text_labels.tabular']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        ref_source = cls._ref_source(inputs)
        if ref_source not in cls.REF_SOURCES:
            return f"ref_source must be one of: {', '.join(cls.REF_SOURCES)}"
        if ref_source == 'gff3' and (not str(inputs.get('attr', '')).strip()):
            return 'attr is required when ref_source is gff3'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'ref_source': ('STRING', {'default': 'bed', 'options': cls.REF_SOURCES})}, 'optional': {'input': ('FILE', {'default': '', 'description': 'BED6+ or GFF3 interval file'}), 'attr': ('STRING', {'default': '', 'description': 'GFF3 attribute to use as the text label'})}, 'hidden': {'output': ('STRING', {})}}


class CircosIntervalToTileNode(CommandNode):
    """Convert BED3+ or GFF3 intervals into Circos tile track rows."""
    NODE_ID = 'circos_interval_to_tile'
    DISPLAY_NAME = 'Circos: Interval to Tiles'
    REQUIRED_CONDA_PACKAGES = ['circos', 'bcbiogff', 'biopython']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Convert BED3+ or GFF3 intervals into Circos tile tracks.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Circos', 'tile tracks', 'interval tiles', 'BED3', 'BED6', 'GFF3', 'annotation tiles']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos'
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = '0.69.8+galaxy12'
    SHELL = True
    REF_SOURCES = ['bed', 'gff3']

    @classmethod
    def _ref_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('ref_source', 'bed') or 'bed')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/tiles.tabular'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        if cls._ref_source(inputs) == 'gff3':
            cmd = ['python', 'tiles-from-gff3.py', str(inputs.get('input', '')), str(inputs.get('attr', ''))]
        else:
            cmd = ['python', 'tiles-from-bed.py', str(inputs.get('input', ''))]
        return f'{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'tiles.tabular']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        ref_source = cls._ref_source(inputs)
        if ref_source not in cls.REF_SOURCES:
            return f"ref_source must be one of: {', '.join(cls.REF_SOURCES)}"
        if ref_source == 'gff3' and (not str(inputs.get('attr', '')).strip()):
            return 'attr is required when ref_source is gff3'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'ref_source': ('STRING', {'default': 'bed', 'options': cls.REF_SOURCES})}, 'optional': {'input': ('FILE', {'default': '', 'description': 'BED3+ or GFF3 interval file'}), 'attr': ('STRING', {'default': '', 'description': 'GFF3 attribute to use as tile name'})}, 'hidden': {'output': ('STRING', {})}}


class CircosAlignmentsToLinksNode(CommandNode):
    """Convert multiple-alignment blocks into Circos link track rows."""
    NODE_ID = 'circos_aln_to_links'
    DISPLAY_NAME = 'Circos: Alignments to links'
    REQUIRED_CONDA_PACKAGES = ['circos', 'biopython']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Convert MAF, XMFA, or Stockholm alignments into Circos link tracks.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Circos', 'circos_aln_to_links', 'alignments to links', 'alignment links', 'MAF', 'XMFA', 'Stockholm', 'comparative genomics']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos'
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = '0.69.8+galaxy12'
    SHELL = True
    INPUT_EXTENSIONS = ['maf', 'xmfa', 'stockholm']

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_ext', 'maf') or 'maf')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/links.tabular'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['python', 'alignments-to-links.py', str(inputs.get('input', '')), cls._input_ext(inputs)]
        return f'{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'links.tabular']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        input_ext = cls._input_ext(inputs)
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f"input_ext must be one of: {', '.join(cls.INPUT_EXTENSIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FILE', {'description': 'Alignment file in MAF, XMFA, or Stockholm format'})}, 'optional': {'input_ext': ('STRING', {'default': 'maf', 'options': cls.INPUT_EXTENSIONS})}, 'hidden': {'output': ('STRING', {})}}


class CircosBinlinksNode(CommandNode):
    """Reduce Circos links into binned density track rows."""
    NODE_ID = 'circos_binlinks'
    DISPLAY_NAME = 'Circos: Link Density Track'
    REQUIRED_CONDA_PACKAGES = ['circos', 'circos-tools']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Reduce Circos links to binned density tracks.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Circos', 'circos_binlinks', 'binlinks', 'link density', 'density track', 'stacked histogram', 'comparative genomics']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('outfile',)
    REQUIRED_EXECUTABLES = ['binlinks', 'sed']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos'
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = '0.69.8+galaxy12'
    SHELL = True
    LINK_END_OPTIONS = ['', '0', '1', '2']
    OUTPUT_STYLE_OPTIONS = ['', '0', '1', '2', '3']

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/link_density.tabular'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['binlinks', '-bin_size', str(inputs.get('bin_size', 1000000))]
        _add_if_value(cmd, '-link_end', inputs.get('link_end'))
        _add_if_value(cmd, '-output_style', inputs.get('output_style'))
        if inputs.get('num'):
            cmd.append('-num')
        if inputs.get('log'):
            cmd.append('-log')
        if inputs.get('normalize'):
            cmd.append('-normalize')
        return f"{_shell_join(cmd)} < {shlex.quote(str(inputs.get('linksfile', '')))} | sed 's/ /\\t/g' > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'link_density.tabular']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('linksfile', '')).strip():
            return 'linksfile is required'
        try:
            bin_size = int(inputs.get('bin_size', 1000000))
        except (TypeError, ValueError):
            return 'bin_size must be an integer'
        if bin_size < 0:
            return 'bin_size must be greater than or equal to 0'
        link_end = str(inputs.get('link_end', '') or '')
        if link_end not in cls.LINK_END_OPTIONS:
            return f"link_end must be one of: {', '.join(cls.LINK_END_OPTIONS)}"
        output_style = str(inputs.get('output_style', '') or '')
        if output_style not in cls.OUTPUT_STYLE_OPTIONS:
            return f"output_style must be one of: {', '.join(cls.OUTPUT_STYLE_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'linksfile': ('TSV', {'description': 'Six-column Circos links table'})}, 'optional': {'bin_size': ('INT', {'default': 1000000, 'min': 0, 'description': 'Bin size'}), 'link_end': ('STRING', {'default': '', 'options': cls.LINK_END_OPTIONS}), 'output_style': ('STRING', {'default': '', 'options': cls.OUTPUT_STYLE_OPTIONS}), 'num': ('BOOLEAN', {'default': False, 'description': 'Use number of links rather than sum'}), 'log': ('BOOLEAN', {'default': False, 'description': 'Calculate log10 of values'}), 'normalize': ('BOOLEAN', {'default': False, 'description': 'Normalize stacked histograms'})}, 'hidden': {'output': ('STRING', {})}}


class CircosBundlelinksNode(CommandNode):
    """Bundle adjacent Circos links into reduced link rows."""
    NODE_ID = 'circos_bundlelinks'
    DISPLAY_NAME = 'Circos: Bundle Links'
    REQUIRED_CONDA_PACKAGES = ['circos', 'circos-tools']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Bundle adjacent Circos links before plotting.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Circos', 'circos_bundlelinks', 'bundlelinks', 'bundle links', 'ribbon', 'link reduction', 'comparative genomics']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('outfile',)
    REQUIRED_EXECUTABLES = ['bundlelinks', 'sed']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos'
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = '0.69.8+galaxy12'
    SHELL = True
    OPTIONAL_INT_MINIMUMS = {'max_gap': 1, 'min_bundle_extent': 0, 'min_bundle_size': 0}

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/bundled_links.tabular'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['bundlelinks']
        _add_if_value(cmd, '-max_gap', inputs.get('max_gap'))
        cmd.extend(['-min_bundle_membership', str(inputs.get('min_bundle_membership', 0))])
        _add_if_value(cmd, '-min_bundle_extent', inputs.get('min_bundle_extent'))
        _add_if_value(cmd, '-min_bundle_size', inputs.get('min_bundle_size'))
        _add_if_value(cmd, '-min_bundle_identity', inputs.get('min_bundle_identity'))
        return f"{_shell_join(cmd)} < {shlex.quote(str(inputs.get('linksfile', '')))} | sed 's/ /\\t/g' > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'bundled_links.tabular']

    @classmethod
    def _validate_optional_int_min(cls, inputs: dict[str, Any], key: str, minimum: int) -> bool | str:
        value = inputs.get(key)
        if value is None or str(value) == '':
            return True
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if parsed < minimum:
            return f'{key} must be greater than or equal to {minimum}'
        return True

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], key: str, minimum: float, maximum: float) -> bool | str:
        value = inputs.get(key)
        if value is None or str(value) == '':
            return True
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return f'{key} must be a number'
        if parsed < minimum or parsed > maximum:
            return f'{key} must be between {minimum:g} and {maximum:g}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('linksfile', '')).strip():
            return 'linksfile is required'
        validation = cls._validate_optional_int_min(inputs, 'min_bundle_membership', 0)
        if validation is not True:
            return validation
        for key, minimum in cls.OPTIONAL_INT_MINIMUMS.items():
            validation = cls._validate_optional_int_min(inputs, key, minimum)
            if validation is not True:
                return validation
        return cls._validate_float_range(inputs, 'min_bundle_identity', 0, 1)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'linksfile': ('TSV', {'description': 'Six-column Circos links table'})}, 'optional': {'max_gap': ('INT', {'default': '', 'min': 1, 'description': 'Maximum gap between adjacent links'}), 'min_bundle_membership': ('INT', {'default': 0, 'min': 0, 'description': 'Minimum number of links in a bundle'}), 'min_bundle_extent': ('INT', {'default': '', 'min': 0, 'description': 'Minimum bundle extent'}), 'min_bundle_size': ('INT', {'default': '', 'min': 0, 'description': 'Minimum bundle size'}), 'min_bundle_identity': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'description': 'Minimum bundle identity'})}, 'hidden': {'output': ('STRING', {})}}


class CircosWiggleToStackedNode(CommandNode):
    """Convert bigWig tracks into Circos stacked histogram rows."""
    NODE_ID = 'circos_wiggle_to_stacked'
    DISPLAY_NAME = 'Circos: Stack bigWigs as Histogram'
    REQUIRED_CONDA_PACKAGES = ['circos', 'pybigwig']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Convert multiple bigWig tracks into Circos stacked-histogram rows.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Circos', 'circos_wiggle_to_stacked', 'stacked histogram', 'bigWig', 'histogram', 'track stacking', 'comparative genomics']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos'
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = '0.69.8+galaxy12'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/stacked_histogram.tabular'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['python', 'stack-histogram.py', *_as_list(inputs.get('input'))]
        return f'{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'stacked_histogram.tabular']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        raw_input = inputs.get('input')
        input_files = _as_list(raw_input)
        if not input_files:
            return 'at least one input value is required'
        if isinstance(raw_input, (list, tuple)) and any((str(value) == '' for value in raw_input)):
            return 'input values must not be empty'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('BIGWIG', {'is_list': True, 'description': 'bigWig files with identical chromosomes and intervals'})}, 'hidden': {'output': ('STRING', {})}}


class CircosTableviewerNode(CommandNode):
    """Create Circos tableviewer plots from tabular matrix data."""
    NODE_ID = 'circos_tableviewer'
    DISPLAY_NAME = 'Circos: Table viewer'
    REQUIRED_CONDA_PACKAGES = ['circos', 'circos-tools', 'tar']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Create Circos tableviewer plots from tabular matrix data.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Circos', 'circos_tableviewer', 'tableviewer', 'table viewer', 'matrix table', 'ribbon plot', 'comparative genomics']
    RETURN_TYPES = ('IMAGE', 'IMAGE', 'TAR')
    RETURN_NAMES = ('output_png', 'output_svg', 'output_tar')
    REQUIRED_EXECUTABLES = ['parse-table', 'make-conf', 'circos', 'tar']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos'
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = '0.69.8+galaxy12'
    SHELL = True
    FONT_OPTIONS = ['light', 'normal', 'default', 'semibold', 'bold', 'italic', 'bolditalic', 'italicbold']
    LIMIT_DEFAULTS = {'max_ticks': 5000, 'max_ideograms': 200, 'max_links': 25000, 'max_points_per_track': 25000}
    LIMIT_MINIMUM = 200

    @classmethod
    def _output_enabled(cls, inputs: dict[str, Any], key: str) -> bool:
        if key not in inputs:
            return key == 'output_png'
        return bool(inputs.get(key))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(['mkdir', '-p', f'{out}/circos/data', f'{out}/circos/etc']), _shell_join(['cp', 'circos_tableviewer.conf', f'{out}/circos/etc/circos.conf']), f"{_shell_join(['parse-table', '-file', str(inputs.get('table', '')), '-conf', 'circos_tableviewer_parse_table.conf'])} > {shlex.quote(f'{out}/tmp')}", f"{_shell_join(['make-conf', '-dir', f'{out}/circos/data'])} < {shlex.quote(f'{out}/tmp')}", _shell_join(['tar', '-czf', f'{out}/circos.tar.gz', '-C', out, 'circos']), _shell_join(['cd', f'{out}/circos']), _shell_join(['circos', '-conf', 'etc/circos.conf'])]
        if cls._output_enabled(inputs, 'output_png'):
            commands.append(_shell_join(['mv', 'circos.png', '../circos.png']))
        if cls._output_enabled(inputs, 'output_svg'):
            commands.append(_shell_join(['mv', 'circos.svg', '../circos.svg']))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        if cls._output_enabled(inputs, 'output_png'):
            outputs.append(out / 'circos.png')
        if cls._output_enabled(inputs, 'output_svg'):
            outputs.append(out / 'circos.svg')
        if cls._output_enabled(inputs, 'output_tar'):
            outputs.append(out / 'circos.tar.gz')
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int=0) -> bool | str:
        value = inputs.get(key, default)
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if parsed < minimum:
            return f'{key} must be greater than or equal to {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('table', '')).strip():
            return 'table is required'
        if not any((cls._output_enabled(inputs, key) for key in ('output_png', 'output_svg', 'output_tar'))):
            return 'at least one of output_png, output_svg, or output_tar must be selected'
        for key, default in cls.LIMIT_DEFAULTS.items():
            validation = cls._validate_int_min(inputs, key, default, cls.LIMIT_MINIMUM)
            if validation is not True:
                return validation
        for key, default in (('segment_label_size', 50), ('tick_label_size', 24)):
            validation = cls._validate_int_min(inputs, key, default, 0)
            if validation is not True:
                return validation
        for key in ('segment_font', 'tick_font'):
            font = str(inputs.get(key, 'bold' if key == 'segment_font' else 'normal') or '')
            if font not in cls.FONT_OPTIONS:
                return f"{key} must be one of: {', '.join(cls.FONT_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'table': ('TSV', {'description': 'Tableviewer matrix with header row and column'})}, 'optional': {'output_png': ('BOOLEAN', {'default': True, 'description': 'Output PNG plot'}), 'output_svg': ('BOOLEAN', {'default': False, 'description': 'Output SVG plot'}), 'output_tar': ('BOOLEAN', {'default': False, 'description': 'Output configuration archive'}), 'segment_show_label': ('BOOLEAN', {'default': True, 'description': 'Show segment labels'}), 'segment_parallel': ('BOOLEAN', {'default': False, 'description': 'Draw segment labels parallel'}), 'segment_label_size': ('INT', {'default': 50, 'min': 0, 'description': 'Segment label font size'}), 'segment_font': ('STRING', {'default': 'bold', 'options': cls.FONT_OPTIONS}), 'segment_color': ('STRING', {'default': '#000000', 'description': 'Segment label color'}), 'tick_show_label': ('BOOLEAN', {'default': True, 'description': 'Show tick labels'}), 'tick_parallel': ('BOOLEAN', {'default': False, 'description': 'Draw tick labels parallel'}), 'tick_label_size': ('INT', {'default': 24, 'min': 0, 'description': 'Tick label font size'}), 'tick_font': ('STRING', {'default': 'normal', 'options': cls.FONT_OPTIONS}), 'tick_color': ('STRING', {'default': '#000000', 'description': 'Tick label color'}), 'max_ticks': ('INT', {'default': 5000, 'min': cls.LIMIT_MINIMUM}), 'max_ideograms': ('INT', {'default': 200, 'min': cls.LIMIT_MINIMUM}), 'max_links': ('INT', {'default': 25000, 'min': cls.LIMIT_MINIMUM}), 'max_points_per_track': ('INT', {'default': 25000, 'min': cls.LIMIT_MINIMUM})}, 'hidden': {'output': ('STRING', {})}}
