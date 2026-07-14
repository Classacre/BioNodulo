"""bbtools — trimming node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BBToolsBBDukNode(CommandNode):
    """Filter, trim, and mask reads with BBTools BBDuk."""
    NODE_ID = 'bbtools_bbduk'
    DISPLAY_NAME = 'BBTools BBDuk'
    REQUIRED_CONDA_PACKAGES = ['bbmap', 'samtools']
    CATEGORY = 'trimming'
    DESCRIPTION = 'Filter, trim, and mask FASTQ reads with k-mer matching, entropy filtering, and BBDuk statistics.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'BBTools', 'BBDuk', 'bbduk', 'bbtools_bbduk', 'kmer decontamination', 'adapter trimming', 'entropy filtering', 'FASTQ filtering', 'quality histograms']
    RETURN_TYPES = ('FASTQ', 'FASTQ', 'FASTQ', 'FASTQ', 'FASTQ', 'TSV', 'TSV', 'TSV', 'FASTA', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'STATS_FILE')
    RETURN_NAMES = ('forward_unmatched', 'reverse_unmatched', 'forward_matched', 'reverse_matched', 'singletons', 'stats', 'refstats', 'rpkm', 'dump', 'base_composition_histogram', 'quality_histogram', 'quality_count_histogram', 'average_quality_histogram', 'boxplot_quality_histogram', 'read_length_histogram', 'polymer_length_histogram', 'gc_histogram', 'entropy_histogram', 'log')
    REQUIRED_EXECUTABLES = ['bbduk.sh']
    DOCUMENTATION_URL = 'https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/bbduk-guide/'
    CITATION_DOIS = [BBTOOLS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{BBTOOLS_CITATION_DOI}']
    CITATION_TEXT = BBTOOLS_CITATION_TEXT
    VERSION = '39.08'
    SHELL = True
    STAT_OUTPUTS = {'stats': ('stats', 'stats.tsv'), 'ref': ('refstats', 'refstats.tsv'), 'rpkm': ('rpkm', 'rpkm.tsv'), 'dump': ('dump', 'kmer_dump.fasta')}
    HIST_OUTPUTS = {'bhist': ('bhist', 'base_composition_histogram.tsv'), 'quhist': ('qhist', 'quality_histogram.tsv'), 'quchist': ('qchist', 'quality_count_histogram.tsv'), 'aqhist': ('aqhist', 'average_quality_histogram.tsv'), 'bqhist': ('bqhist', 'boxplot_quality_histogram.tsv'), 'lhist': ('lhist', 'read_length_histogram.tsv'), 'phist': ('phist', 'polymer_length_histogram.tsv'), 'gchist': ('gchist', 'gc_histogram.tsv'), 'enthist': ('enthist', 'entropy_histogram.tsv')}

    @classmethod
    def _read_pair(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        input_type = cls._input_type(inputs)
        if input_type == 'paired':
            collection = inputs.get('reads_collection')
            if isinstance(collection, dict):
                return (str(collection.get('forward', '')), str(collection.get('reverse', '')))
            reads = _as_list(collection or inputs.get('reads'))
            return (reads[0] if reads else '', reads[1] if len(reads) > 1 else '')
        return (str(inputs.get('read1', '')), str(inputs.get('read2', '')))

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        input_type = str(inputs.get('input_type', 'single') or 'single')
        return input_type if input_type in {'single', 'pair', 'paired'} else 'single'

    @classmethod
    def _fastq_ext(cls, path: str) -> str:
        return '.fastq.gz' if str(path).endswith('.gz') else '.fastq'

    @classmethod
    def _selected(cls, inputs: dict[str, Any], key: str, default: str | None=None) -> set[str]:
        values = [default] if key not in inputs and default else _as_list(inputs.get(key))
        selected: set[str] = set()
        for value in values:
            selected.update((part.strip() for part in str(value).split(',') if part.strip()))
        return selected

    @classmethod
    def _bool_value(cls, inputs: dict[str, Any], key: str, default: bool) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            return value if value in {'t', 'f'} else 't' if value.lower() in {'true', 'yes', '1'} else 'f'
        return 't' if bool(value) else 'f'

    @classmethod
    def _stage_references(cls, inputs: dict[str, Any], out: str) -> tuple[list[str], str]:
        reference_type = str(inputs.get('reference_type', 'no_reference') or 'no_reference')
        if reference_type == 'keywords':
            return ([], ','.join(_as_list(inputs.get('reference'))))
        if reference_type != 'files':
            return ([], '')
        setup: list[str] = []
        staged_refs: list[str] = []
        for ref in _as_list(inputs.get('reference')):
            staged = f'{out}/{Path(ref).name}.fa'
            staged_refs.append(staged)
            if ref.endswith('.gz'):
                setup.append(f'gunzip -c {shlex.quote(ref)} > {shlex.quote(staged)}')
            else:
                setup.append(f'ln -s {shlex.quote(ref)} {shlex.quote(staged)}')
        return (setup, ','.join(staged_refs))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_type = cls._input_type(inputs)
        read1, read2 = cls._read_pair(inputs)
        read1_file = f'{out}/forward{cls._fastq_ext(read1)}'
        setup = [f'ln -s {shlex.quote(read1)} {shlex.quote(read1_file)}']
        if input_type in {'pair', 'paired'}:
            read2_file = f'{out}/reverse{cls._fastq_ext(read1)}'
            setup.append(f'ln -s {shlex.quote(read2)} {shlex.quote(read2_file)}')
        else:
            read2_file = ''
        ref_setup, refs = cls._stage_references(inputs, out)
        setup.extend(ref_setup)
        outputs_select = cls._selected(inputs, 'outputs_select', 'outu')
        cmd = ['bbduk.sh', f'in={read1_file}']
        if input_type in {'pair', 'paired'}:
            cmd.append(f'in2={read2_file}')
        if 'outu' in outputs_select:
            cmd.append(f'out={out}/forward_unmatched.fastq')
            if input_type in {'pair', 'paired'}:
                cmd.append(f'out2={out}/reverse_unmatched.fastq')
        if 'outm' in outputs_select:
            cmd.append(f'outm={out}/forward_matched.fastq')
            if input_type in {'pair', 'paired'}:
                cmd.append(f'outm2={out}/reverse_matched.fastq')
        if 'outs' in outputs_select:
            cmd.append(f'outs={out}/singletons.fastq')
        if refs:
            cmd.append(f'ref={refs}')
            cmd.append(f"k={inputs.get('k', 27)}")
            if inputs.get('ktrim') not in (None, '', 'no'):
                cmd.append(f"ktrim={inputs.get('ktrim')}")
                cmd.append(f"minlength={inputs.get('minlength', 10)}")
        for key, default in (('rcomp', True), ('maskmiddle', True), ('minkmerhits', 1), ('minkmerfraction', 0), ('mincovfraction', 0), ('hammingdistance', 0), ('qhdist', 0), ('editdistance', 0), ('forbidn', False), ('trimfailures', False), ('findbestmatch', False), ('skipr1', False), ('skipr2', False)):
            if isinstance(default, bool):
                cmd.append(f'{key}={cls._bool_value(inputs, key, default)}')
            else:
                cmd.append(f'{key}={inputs.get(key, default)}')
        if float(inputs.get('entropy', 0) or 0) > 0:
            cmd.append(f"entropy={inputs.get('entropy')}")
            cmd.append(f"entropymask={inputs.get('entropymask', 'f')}")
            cmd.append(f"entropywindow={inputs.get('entropywindow', 50)}")
            cmd.append(f"entropyk={inputs.get('entropyk', 5)}")
        for selected, (argument, filename) in cls.STAT_OUTPUTS.items():
            if selected in cls._selected(inputs, 'output_stats_select'):
                cmd.append(f'{argument}={out}/{filename}')
        for selected, (argument, filename) in cls.HIST_OUTPUTS.items():
            if selected in cls._selected(inputs, 'output_hists_select'):
                cmd.append(f'{argument}={out}/{filename}')
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"
        cmd.append(f't={slots}')
        command = _shell_join(cmd).replace(shlex.quote(f't={slots}'), f't={slots}')
        if inputs.get('log_file'):
            command = f"{command} 2> >(tee {shlex.quote(f'{out}/bbduk.log')} >&2)"
        return ' && '.join(setup + [command])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        input_type = cls._input_type(inputs)
        outputs: list[Path] = []
        outputs_select = cls._selected(inputs, 'outputs_select', 'outu')
        if 'outu' in outputs_select:
            outputs.append(out / 'forward_unmatched.fastq')
            if input_type in {'pair', 'paired'}:
                outputs.append(out / 'reverse_unmatched.fastq')
        if 'outm' in outputs_select:
            outputs.append(out / 'forward_matched.fastq')
            if input_type in {'pair', 'paired'}:
                outputs.append(out / 'reverse_matched.fastq')
        if 'outs' in outputs_select:
            outputs.append(out / 'singletons.fastq')
        for selected, (_argument, filename) in cls.STAT_OUTPUTS.items():
            if selected in cls._selected(inputs, 'output_stats_select'):
                outputs.append(out / filename)
        for selected, (_argument, filename) in cls.HIST_OUTPUTS.items():
            if selected in cls._selected(inputs, 'output_hists_select'):
                outputs.append(out / filename)
        if inputs.get('log_file'):
            outputs.append(out / 'bbduk.log')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        read1, read2 = cls._read_pair(inputs)
        if not read1:
            return 'read1 FASTQ is required'
        if input_type in {'pair', 'paired'} and (not read2):
            return 'read2 FASTQ is required for paired input'
        reference_type = str(inputs.get('reference_type', 'no_reference') or 'no_reference')
        if reference_type == 'files' and (not _as_list(inputs.get('reference'))):
            return 'at least one reference FASTA is required when reference_type is files'
        if reference_type == 'keywords' and (not _as_list(inputs.get('reference'))):
            return 'at least one reference keyword is required when reference_type is keywords'
        if not cls._selected(inputs, 'outputs_select', 'outu'):
            return 'at least one read output must be selected'
        for key in ('k', 'minkmerhits', 'entropywindow', 'entropyk', 'threads'):
            try:
                value = int(inputs.get(key, {'k': 27, 'minkmerhits': 1, 'entropywindow': 50, 'entropyk': 5, 'threads': 4}[key]))
            except (TypeError, ValueError):
                return f'{key} must be an integer'
            if value < 1:
                return f'{key} must be >= 1'
        for key in ('hammingdistance', 'qhdist', 'editdistance', 'minlength'):
            if inputs.get(key) in (None, ''):
                continue
            try:
                value = int(inputs.get(key))
            except (TypeError, ValueError):
                return f'{key} must be an integer'
            if value < 0:
                return f'{key} must be >= 0'
        for key in ('minkmerfraction', 'mincovfraction'):
            try:
                value = float(inputs.get(key, 0))
            except (TypeError, ValueError):
                return f'{key} must be a number'
            if value < 0:
                return f'{key} must be >= 0'
        try:
            entropy = float(inputs.get('entropy', 0) or 0)
        except (TypeError, ValueError):
            return 'entropy must be a number'
        if not 0 <= entropy <= 1:
            return 'entropy must be between 0 and 1'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_type': ('STRING', {'default': 'single', 'options': ['single', 'pair', 'paired'], 'description': 'Galaxy input mode'}), 'read1': ('FASTQ', {'description': 'Single, forward, or paired-collection forward FASTQ reads'})}, 'optional': {'read2': ('FASTQ', {'default': '', 'description': 'Reverse FASTQ reads for paired input'}), 'reads_collection': ('FASTQ_LIST', {'default': '', 'description': 'Paired collection mapping or [forward, reverse]'}), 'reference_type': ('STRING', {'default': 'no_reference', 'options': ['no_reference', 'files', 'keywords'], 'description': 'Reference source'}), 'reference': ('STRING_LIST', {'default': [], 'options': ['adapters', 'artifacts', 'phix', 'lambda', 'pjet', 'mtst', 'kapa'], 'description': 'Reference FASTA paths or BBDuk keyword references'}), 'outputs_select': ('STRING_LIST', {'default': ['outu'], 'options': ['outu', 'outm', 'outs'], 'description': 'Read outputs to write'}), 'output_stats_select': ('STRING_LIST', {'default': [], 'options': list(cls.STAT_OUTPUTS), 'description': 'Optional statistics outputs'}), 'output_hists_select': ('STRING_LIST', {'default': [], 'options': list(cls.HIST_OUTPUTS), 'description': 'Optional histogram outputs'}), 'k': ('INT', {'default': 27, 'min': 1, 'description': 'K-mer length used for contaminant matching'}), 'ktrim': ('STRING', {'default': '', 'options': ['', 'r', 'l'], 'description': 'Trim to the right or left after reference k-mer hits'}), 'minlength': ('INT', {'default': 10, 'min': 0, 'description': 'Minimum read length after k-trimming'}), 'rcomp': ('BOOLEAN', {'default': True, 'description': 'Search reverse-complement k-mers'}), 'maskmiddle': ('BOOLEAN', {'default': True, 'description': 'Treat middle k-mer base as wildcard'}), 'minkmerhits': ('INT', {'default': 1, 'min': 1, 'description': 'Minimum matching k-mers'}), 'minkmerfraction': ('FLOAT', {'default': 0, 'min': 0, 'description': 'Minimum fraction of k-mers matching'}), 'mincovfraction': ('FLOAT', {'default': 0, 'min': 0, 'description': 'Minimum base coverage by reference k-mers'}), 'hammingdistance': ('INT', {'default': 0, 'min': 0, 'description': 'Reference k-mer Hamming distance'}), 'qhdist': ('INT', {'default': 0, 'min': 0, 'description': 'Query k-mer Hamming distance'}), 'editdistance': ('INT', {'default': 0, 'min': 0, 'description': 'Reference k-mer edit distance'}), 'forbidn': ('BOOLEAN', {'default': False, 'description': 'Reject k-mers containing N'}), 'trimfailures': ('BOOLEAN', {'default': False, 'description': 'Trim failed reads to 1bp instead of discarding'}), 'findbestmatch': ('BOOLEAN', {'default': False, 'description': 'Associate reads with best matching reference'}), 'skipr1': ('BOOLEAN', {'default': False, 'description': 'Skip read 1 for k-mer operations'}), 'skipr2': ('BOOLEAN', {'default': False, 'description': 'Skip read 2 for k-mer operations'}), 'entropy': ('FLOAT', {'default': 0, 'min': 0, 'max': 1, 'description': 'Entropy threshold'}), 'entropymask': ('STRING', {'default': 'f', 'options': ['f', 't', 'lc'], 'description': 'Entropy mask mode'}), 'entropywindow': ('INT', {'default': 50, 'min': 1, 'description': 'Sliding entropy window'}), 'entropyk': ('INT', {'default': 5, 'min': 1, 'description': 'Entropy k-mer size'}), 'log_file': ('BOOLEAN', {'default': False, 'description': 'Return BBDuk log output'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}


class BBToolsBBMergeNode(CommandNode):
    """Merge paired reads with BBTools BBMerge."""
    NODE_ID = 'bbtools_bbmerge'
    DISPLAY_NAME = 'BBTools BBMerge'
    REQUIRED_CONDA_PACKAGES = ['bbmap', 'samtools']
    CATEGORY = 'trimming'
    DESCRIPTION = 'Merge overlapping paired-end reads with BBMerge and report unmerged reads plus insert-length histograms.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'BBTools', 'BBMerge', 'bbmerge', 'bbtools_bbmerge', 'overlapping mates', 'paired-end merge', 'read merging', 'insert length histogram', 'error correction']
    RETURN_TYPES = ('FASTQ', 'FASTQ', 'TSV')
    RETURN_NAMES = ('merged_reads', 'unmerged_reads', 'insert_length_histogram')
    REQUIRED_EXECUTABLES = ['bbmerge.sh']
    DOCUMENTATION_URL = 'https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/bbmerge-guide/'
    CITATION_DOIS = [BBTOOLS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{BBTOOLS_CITATION_DOI}']
    CITATION_TEXT = BBTOOLS_CITATION_TEXT
    VERSION = '39.08'
    SHELL = True
    STRICTNESS_OPTIONS = {'xstrict', 'ustrict', 'vstrict', 'strict', 'default', 'loose', 'vloose', 'uloose', 'xloose', 'fast'}

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_type', 'single') or 'single')

    @classmethod
    def _read_pair(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        input_type = cls._input_type(inputs)
        if input_type == 'paired':
            collection = inputs.get('reads_collection')
            if isinstance(collection, dict):
                return (str(collection.get('forward', '')), str(collection.get('reverse', '')))
            reads = _as_list(collection or inputs.get('reads'))
            return (reads[0] if reads else '', reads[1] if len(reads) > 1 else '')
        return (str(inputs.get('read1', '')), str(inputs.get('read2', '')))

    @classmethod
    def _fastq_ext(cls, path: str) -> str:
        return '.fastq.gz' if str(path).endswith('.gz') else '.fastq'

    @classmethod
    def _bool_value(cls, inputs: dict[str, Any], key: str, default: bool) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            if value in {'t', 'f'}:
                return value
            return 't' if value.lower() in {'true', 'yes', '1'} else 'f'
        return 't' if bool(value) else 'f'

    @classmethod
    def _java_memory_guard(cls, inputs: dict[str, Any]) -> str:
        memory = inputs.get('memory_mb', 4096)
        return f'if [[ "${{_JAVA_OPTIONS}}" != *-Xmx* && "${{JAVA_TOOL_OPTIONS}}" != *-Xmx* ]]; then export _JAVA_OPTIONS="${{_JAVA_OPTIONS}} -Xmx${{GALAXY_MEMORY_MB:-{memory}}}m -Xms256m"; fi'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_type = cls._input_type(inputs)
        read1, read2 = cls._read_pair(inputs)
        read1_file = f'{out}/forward{cls._fastq_ext(read1)}'
        setup = [f'ln -s {shlex.quote(read1)} {shlex.quote(read1_file)}']
        if input_type in {'pair', 'paired'}:
            read2_file = f'{out}/reverse{cls._fastq_ext(read1)}'
            setup.append(f'ln -s {shlex.quote(read2)} {shlex.quote(read2_file)}')
        else:
            read2_file = ''
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 2)}}}"
        cmd = ['bbmerge.sh', 'tmpdir="$TMPDIR"', f't="{slots}"']
        if input_type == 'single':
            cmd.extend([f'in={read1_file}', 'interleaved=t'])
        else:
            cmd.extend([f'in1={read1_file}', f'in2={read2_file}', 'interleaved=f'])
        cmd.extend([f'out={out}/merged.fastq', f'outu={out}/unmerged.fastq', f'ihist={out}/ihist.tabular', 'touppercase=t', f"qtrim={inputs.get('qtrim', 'f')}", f"trimq={inputs.get('trimq', 6)}", f"minlength={inputs.get('minlength_after_trim', 60)}", f"usequality={cls._bool_value(inputs, 'qt_usequality', True)}", 'usejni=f', f"ecco={cls._bool_value(inputs, 'ecco', False)}", f"trimnonoverlapping={cls._bool_value(inputs, 'trimnonoverlapping', False)}", f"mininsert={inputs.get('mininsert', 35)}", f"minoverlap={inputs.get('minoverlap', 12)}", f"minq={inputs.get('minq', 9)}", f"maxq={inputs.get('maxq', 41)}", f"entropy={cls._bool_value(inputs, 'entropy', True)}", f"efilter={inputs.get('efilter', 6)}", f"pfilter={inputs.get('pfilter', '0.00004')}", f"kfilter={inputs.get('kfilter', 41)}", f"usequality={cls._bool_value(inputs, 'merge_usequality', True)}"])
        if inputs.get('adapter1') not in (None, '') or inputs.get('adapter2') not in (None, ''):
            cmd.extend([f"adapter1={inputs.get('adapter1', '')}", f"adapter2={inputs.get('adapter2', '')}"])
        if str(inputs.get('merge_mode', 'Ratio mode')) == 'Flat mode':
            cmd.extend([f"margin={inputs.get('margin', 2)}", f"mismatches={inputs.get('mismatches', 3)}", f"requireratiomatch={cls._bool_value(inputs, 'requireratiomatch', False)}"])
        else:
            cmd.extend([f"maxratio={inputs.get('maxratio', 0.09)}", f"ratiomargin={inputs.get('ratiomargin', 5.5)}", f"ratiooffset={inputs.get('ratiooffset', 0.55)}", f"maxmismatches={inputs.get('maxmismatches', 20)}", 'ratiominoverlapreduction=0', f"minsecondratio={inputs.get('minsecondratio', 0.1)}"])
        cmd.append(f"{inputs.get('strictness', 'default')}=t")
        command = _shell_join(cmd)
        command = command.replace(shlex.quote('tmpdir="$TMPDIR"'), 'tmpdir="$TMPDIR"')
        command = command.replace(shlex.quote(f't="{slots}"'), f't="{slots}"')
        return ' && '.join(setup + [cls._java_memory_guard(inputs), command])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'merged.fastq', out / 'unmerged.fastq', out / 'ihist.tabular']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        if input_type not in {'single', 'pair', 'paired'}:
            return 'input_type must be one of: single, pair, paired'
        read1, read2 = cls._read_pair(inputs)
        if not read1:
            return 'read1 FASTQ is required'
        if input_type in {'pair', 'paired'} and (not read2):
            return 'read2 FASTQ is required for paired input'
        if str(inputs.get('strictness', 'default')) not in cls.STRICTNESS_OPTIONS:
            return 'strictness must be one of the BBMerge strictness modes'
        for key, default in (('threads', 2), ('memory_mb', 4096), ('trimq', 6), ('minlength_after_trim', 60), ('mininsert', 35), ('minoverlap', 12), ('minq', 9), ('maxq', 41), ('efilter', 6), ('kfilter', 41), ('maxmismatches', 20), ('margin', 2), ('mismatches', 3)):
            try:
                value = int(inputs.get(key, default))
            except (TypeError, ValueError):
                return f'{key} must be an integer'
            if value < 1 and key in {'threads', 'memory_mb', 'minoverlap'}:
                return f'{key} must be >= 1'
            if value < 0 and key not in {'efilter'}:
                return f'{key} must be >= 0'
        for key, default in (('pfilter', 4e-05), ('maxratio', 0.09), ('ratiomargin', 5.5), ('ratiooffset', 0.55), ('minsecondratio', 0.1)):
            try:
                value = float(inputs.get(key, default))
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
        return {'required': {'input_type': ('STRING', {'default': 'single', 'options': ['single', 'pair', 'paired'], 'description': 'Galaxy input mode'}), 'read1': ('FASTQ', {'description': 'Single interleaved, forward, or paired-collection forward FASTQ'})}, 'optional': {'read2': ('FASTQ', {'default': '', 'description': 'Reverse FASTQ reads for paired input'}), 'reads_collection': ('FASTQ_LIST', {'default': '', 'description': 'Paired collection mapping or [forward, reverse]'}), 'qtrim': ('STRING', {'default': 'f', 'options': ['f', 'l', 'r', 'lr'], 'description': 'Quality trim mode'}), 'trimq': ('INT', {'default': 6, 'min': 0, 'description': 'Trim below this average quality'}), 'minlength_after_trim': ('INT', {'default': 60, 'min': 0, 'description': 'Minimum length after trimming'}), 'qt_usequality': ('BOOLEAN', {'default': True, 'description': 'Use quality scores for trimming seeds'}), 'ecco': ('BOOLEAN', {'default': False, 'description': 'Error-correct overlapping portions without merging'}), 'trimnonoverlapping': ('BOOLEAN', {'default': False, 'description': 'Trim all non-overlapping sequence'}), 'mininsert': ('INT', {'default': 35, 'min': 0, 'description': 'Minimum insert size'}), 'minoverlap': ('INT', {'default': 12, 'min': 1, 'description': 'Minimum overlap length'}), 'minq': ('INT', {'default': 9, 'min': 0, 'description': 'Ignore bases below this quality'}), 'maxq': ('INT', {'default': 41, 'min': 0, 'description': 'Cap output qualities'}), 'entropy': ('BOOLEAN', {'default': True, 'description': 'Increase overlap requirement for low-complexity reads'}), 'efilter': ('INT', {'default': 6, 'description': 'Expected-error overlap filter; -1 disables'}), 'pfilter': ('FLOAT', {'default': 4e-05, 'min': 0, 'description': 'Probability filter for improbable overlaps'}), 'kfilter': ('INT', {'default': 41, 'min': 0, 'description': 'Low-count k-mer overlap filter'}), 'merge_usequality': ('BOOLEAN', {'default': True, 'description': 'Use quality values in overlap detection'}), 'adapter1': ('STRING', {'default': '', 'description': 'Left adapter sequence'}), 'adapter2': ('STRING', {'default': '', 'description': 'Right adapter sequence'}), 'merge_mode': ('STRING', {'default': 'Ratio mode', 'options': ['Ratio mode', 'Flat mode'], 'description': 'Overlap scoring mode'}), 'maxratio': ('FLOAT', {'default': 0.09, 'min': 0, 'description': 'Ratio-mode maximum error rate'}), 'ratiomargin': ('FLOAT', {'default': 5.5, 'min': 0, 'description': 'Ratio-mode margin'}), 'ratiooffset': ('FLOAT', {'default': 0.55, 'min': 0, 'description': 'Ratio-mode offset'}), 'maxmismatches': ('INT', {'default': 20, 'min': 0, 'description': 'Ratio-mode maximum mismatches'}), 'minsecondratio': ('FLOAT', {'default': 0.1, 'min': 0, 'description': 'Ratio-mode second-best cutoff'}), 'margin': ('INT', {'default': 2, 'min': 0, 'description': 'Flat-mode best-overlap margin'}), 'mismatches': ('INT', {'default': 3, 'min': 0, 'description': 'Flat-mode maximum mismatches'}), 'requireratiomatch': ('BOOLEAN', {'default': False, 'description': 'Require ratio and flat modes to agree'}), 'strictness': ('STRING', {'default': 'default', 'options': sorted(cls.STRICTNESS_OPTIONS), 'description': 'BBMerge strictness preset'}), 'threads': ('INT', {'default': 2, 'min': 1, 'max': 128}), 'memory_mb': ('INT', {'default': 4096, 'min': 1, 'description': 'Fallback Java heap in MB'})}, 'hidden': {'output': ('STRING', {})}}
