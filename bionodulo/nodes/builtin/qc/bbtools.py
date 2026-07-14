"""bbtools — qc node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BBToolsBBNormNode(CommandNode):
    """Normalize sequencing coverage with BBTools BBNorm."""
    NODE_ID = 'bbtools_bbnorm'
    DISPLAY_NAME = 'BBTools BBNorm'
    REQUIRED_CONDA_PACKAGES = ['bbmap', 'samtools']
    CATEGORY = 'qc'
    DESCRIPTION = 'Normalize sequencing coverage with BBNorm count-min-sketch k-mer depth estimates.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'BBTools', 'BBNorm', 'bbnorm', 'bbtools_bbnorm', 'coverage normalization', 'digital normalization', 'kmer depth', 'count-min sketch', 'read downsampling']
    RETURN_TYPES = ('FASTQ', 'FASTQ', 'FASTQ', 'FASTQ', 'TSV', 'TSV')
    RETURN_NAMES = ('normalised_R1', 'normalised_R2', 'normalised_pair', 'discarded_reads', 'kmer_hist_input', 'kmer_hist_output')
    REQUIRED_EXECUTABLES = ['bbnorm.sh']
    DOCUMENTATION_URL = 'https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/bbnorm-guide/'
    CITATION_DOIS = [BBTOOLS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{BBTOOLS_CITATION_DOI}']
    CITATION_TEXT = BBTOOLS_CITATION_TEXT
    VERSION = '39.08'
    SHELL = True
    INPUT_TYPES_ALLOWED = {'single_end', 'PE_1file', 'PE_2files', 'paired'}

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_type', 'PE_2files') or 'PE_2files')

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
        if input_type in {'PE_2files', 'paired'}:
            read2_file = f'{out}/reverse{cls._fastq_ext(read2)}'
            setup.append(f'ln -s {shlex.quote(read2)} {shlex.quote(read2_file)}')
        else:
            read2_file = ''
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 2)}}}"
        cmd = ['bbnorm.sh', 'tmpdir="$TMPDIR"', f't="{slots}"']
        if input_type == 'single_end':
            cmd.extend([f'in={read1_file}', 'interleaved=f'])
        elif input_type == 'PE_1file':
            cmd.extend([f'in={read1_file}', 'interleaved=t'])
        else:
            cmd.extend([f'in1={read1_file}', f'in2={read2_file}', 'interleaved=f'])
        cmd.append(f'out={out}/normalised_R1.fastq')
        if input_type in {'PE_2files', 'paired'}:
            cmd.append(f'out2={out}/normalised_R2.fastq')
        if inputs.get('save_discarded_reads'):
            cmd.append(f'outt={out}/discarded.fastq')
        cmd.append('touppercase=t')
        if inputs.get('save_kmer_hists'):
            cmd.extend([f'hist={out}/kmer_hist_input.tabular', f'histout={out}/kmer_hist_output.tabular'])
        cmd.extend([f"k={inputs.get('k', 31)}", f"bits={inputs.get('bits', 16)}", f"hashes={inputs.get('hashes', 3)}"])
        if inputs.get('prefilter'):
            cmd.extend(['prefilter=t', f"prehashes={inputs.get('prehashes', 2)}", f"prefilterbits={inputs.get('prefilterbits', 2)}", f"prefiltersize={inputs.get('prefiltersize', 0.35)}"])
        cmd.extend([f"buildpasses={inputs.get('buildpasses', 1)}", f"minq={inputs.get('minq', 6)}", f"minprob={inputs.get('minprob', 0.5)}", f"rdk={cls._bool_value(inputs, 'rdk', True)}", f"fixspikes={cls._bool_value(inputs, 'fixspikes', False)}", f"target={inputs.get('target', 100)}", f"maxdepth={inputs.get('maxdepth', -1)}", f"mindepth={inputs.get('mindepth', 5)}", f"minkmers={inputs.get('minkmers', 15)}", f"percentile={inputs.get('percentile', 54)}", f"uselowerdepth={cls._bool_value(inputs, 'uselowerdepth', True)}", f"deterministic={cls._bool_value(inputs, 'deterministic', True)}", f"passes={inputs.get('passes', 2)}", f"hdp={inputs.get('hdp', 90)}", f"ldp={inputs.get('ldp', 25)}", f"tossbadreads={cls._bool_value(inputs, 'tossbadreads', False)}", f"requirebothbad={cls._bool_value(inputs, 'requirebothbad', False)}", f"errordetectratio={inputs.get('errordetectratio', 125)}", f"highthresh={inputs.get('highthresh', 12)}", f"lowthresh={inputs.get('lowthresh', 3)}"])
        if inputs.get('ecc'):
            cmd.extend(['ecc=t', f"ecclimit={inputs.get('ecclimit', 3)}", f"errorcorrectratio={inputs.get('errorcorrectratio', 140)}", f"echighthresh={inputs.get('echighthresh', 22)}", f"eclowthresh={inputs.get('eclowthresh', 2)}", f"eccmaxqual={inputs.get('eccmaxqual', 127)}", f"meo={cls._bool_value(inputs, 'meo', False)}", f"mue={cls._bool_value(inputs, 'mue', True)}", f"overlap={cls._bool_value(inputs, 'overlap', False)}"])
        command = _shell_join(cmd)
        command = command.replace(shlex.quote('tmpdir="$TMPDIR"'), 'tmpdir="$TMPDIR"')
        command = command.replace(shlex.quote(f't="{slots}"'), f't="{slots}"')
        return ' && '.join(setup + [cls._java_memory_guard(inputs), command])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        input_type = cls._input_type(inputs)
        outputs = [out / 'normalised_R1.fastq']
        if input_type in {'PE_2files', 'paired'}:
            outputs.append(out / 'normalised_R2.fastq')
        if inputs.get('save_discarded_reads'):
            outputs.append(out / 'discarded.fastq')
        if inputs.get('save_kmer_hists'):
            outputs.extend([out / 'kmer_hist_input.tabular', out / 'kmer_hist_output.tabular'])
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        if input_type not in cls.INPUT_TYPES_ALLOWED:
            return 'input_type must be one of: single_end, PE_1file, PE_2files, paired'
        read1, read2 = cls._read_pair(inputs)
        if not read1:
            return 'read1 FASTQ is required'
        if input_type in {'PE_2files', 'paired'} and (not read2):
            return 'read2 FASTQ is required for paired input'
        min_one_keys = ('target', 'k', 'hashes', 'buildpasses', 'threads', 'memory_mb', 'prehashes', 'prefilterbits', 'passes')
        non_negative_keys = ('mindepth', 'minkmers', 'minq', 'hdp', 'ldp', 'errordetectratio', 'highthresh', 'lowthresh', 'ecclimit', 'errorcorrectratio', 'echighthresh', 'eclowthresh', 'eccmaxqual')
        defaults = {'target': 100, 'k': 31, 'hashes': 3, 'buildpasses': 1, 'threads': 2, 'memory_mb': 4096, 'prehashes': 2, 'prefilterbits': 2, 'passes': 2, 'mindepth': 5, 'minkmers': 15, 'minq': 6, 'hdp': 90, 'ldp': 25, 'errordetectratio': 125, 'highthresh': 12, 'lowthresh': 3, 'ecclimit': 3, 'errorcorrectratio': 140, 'echighthresh': 22, 'eclowthresh': 2, 'eccmaxqual': 127}
        for key in (*min_one_keys, *non_negative_keys):
            try:
                value = int(inputs.get(key, defaults[key]))
            except (TypeError, ValueError):
                return f'{key} must be an integer'
            if key in min_one_keys and value < 1:
                return f'{key} must be >= 1'
            if key in non_negative_keys and value < 0:
                return f'{key} must be >= 0'
        try:
            percentile = int(inputs.get('percentile', 54))
        except (TypeError, ValueError):
            return 'percentile must be an integer'
        if not 1 <= percentile <= 100:
            return 'percentile must be between 1 and 100'
        for key, default in (('minprob', 0.5), ('prefiltersize', 0.35)):
            try:
                value = float(inputs.get(key, default))
            except (TypeError, ValueError):
                return f'{key} must be a number'
            if not 0 <= value <= 1:
                return f'{key} must be between 0 and 1'
        for key in ('bits',):
            try:
                value = int(inputs.get(key, 16))
            except (TypeError, ValueError):
                return f'{key} must be an integer'
            if value not in {2, 4, 8, 16, 32}:
                return 'bits must be one of: 2, 4, 8, 16, 32'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_type': ('STRING', {'default': 'PE_2files', 'options': ['single_end', 'PE_1file', 'PE_2files', 'paired'], 'description': 'Galaxy input mode'}), 'read1': ('FASTQ', {'description': 'Single-end, interleaved, forward, or paired-collection forward FASTQ'})}, 'optional': {'read2': ('FASTQ', {'default': '', 'description': 'Reverse FASTQ reads for two-file paired input'}), 'reads_collection': ('FASTQ_LIST', {'default': '', 'description': 'Paired collection mapping or [forward, reverse]'}), 'target': ('INT', {'default': 100, 'min': 1, 'description': 'Target normalization k-mer depth'}), 'maxdepth': ('INT', {'default': -1, 'description': 'Disable downsampling below this k-mer depth'}), 'mindepth': ('INT', {'default': 5, 'min': 0, 'description': 'Ignore k-mers below this depth'}), 'minkmers': ('INT', {'default': 15, 'min': 0, 'description': 'Minimum retained k-mers over depth threshold'}), 'percentile': ('INT', {'default': 54, 'min': 1, 'max': 100, 'description': 'Percentile used to infer read depth'}), 'uselowerdepth': ('BOOLEAN', {'default': True, 'description': 'Use lower mate depth for pairs'}), 'deterministic': ('BOOLEAN', {'default': True, 'description': 'Generate random numbers deterministically'}), 'fixspikes': ('BOOLEAN', {'default': False, 'description': 'Correct high-depth Bloom-filter collision spikes'}), 'passes': ('INT', {'default': 2, 'min': 1, 'description': 'Normalization passes'}), 'k': ('INT', {'default': 31, 'min': 1, 'description': 'K-mer length'}), 'bits': ('INT', {'default': 16, 'options': [2, 4, 8, 16, 32], 'description': 'Bits per count-min-sketch cell'}), 'hashes': ('INT', {'default': 3, 'min': 1, 'description': 'Number of hashes per k-mer'}), 'prefilter': ('BOOLEAN', {'default': False, 'description': 'Enable low-depth k-mer prefilter'}), 'prehashes': ('INT', {'default': 2, 'min': 1, 'description': 'Prefilter hash count'}), 'prefilterbits': ('INT', {'default': 2, 'min': 1, 'description': 'Prefilter bits per cell'}), 'prefiltersize': ('FLOAT', {'default': 0.35, 'min': 0, 'max': 1, 'description': 'Prefilter memory fraction'}), 'buildpasses': ('INT', {'default': 1, 'min': 1, 'description': 'Hashtable build passes'}), 'minq': ('INT', {'default': 6, 'min': 0, 'description': 'Ignore k-mers containing lower-quality bases'}), 'minprob': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 1, 'description': 'Minimum k-mer correctness probability'}), 'rdk': ('BOOLEAN', {'default': True, 'description': 'Remove duplicate k-mers per read pair'}), 'hdp': ('INT', {'default': 90, 'min': 0, 'max': 100, 'description': 'High-depth percentile'}), 'ldp': ('INT', {'default': 25, 'min': 0, 'max': 100, 'description': 'Low-depth percentile'}), 'tossbadreads': ('BOOLEAN', {'default': False, 'description': 'Discard reads detected as erroneous'}), 'requirebothbad': ('BOOLEAN', {'default': False, 'description': 'Discard bad pairs only if both reads are bad'}), 'errordetectratio': ('INT', {'default': 125, 'min': 0, 'description': 'Error-detection depth ratio'}), 'highthresh': ('INT', {'default': 12, 'min': 0, 'description': 'High k-mer threshold'}), 'lowthresh': ('INT', {'default': 3, 'min': 0, 'description': 'Low k-mer threshold'}), 'ecc': ('BOOLEAN', {'default': False, 'description': 'Correct detected errors when possible'}), 'ecclimit': ('INT', {'default': 3, 'min': 1, 'description': 'Maximum corrected errors per read'}), 'errorcorrectratio': ('INT', {'default': 140, 'min': 0, 'description': 'Error-correction depth ratio'}), 'echighthresh': ('INT', {'default': 22, 'min': 0, 'description': 'High threshold for correction'}), 'eclowthresh': ('INT', {'default': 2, 'min': 0, 'description': 'Low threshold for correction'}), 'eccmaxqual': ('INT', {'default': 127, 'min': 0, 'description': 'Do not correct bases above this quality'}), 'meo': ('BOOLEAN', {'default': False, 'description': 'Mark errors only'}), 'mue': ('BOOLEAN', {'default': True, 'description': 'Mark errors only on uncorrectable reads'}), 'overlap': ('BOOLEAN', {'default': False, 'description': 'Correct errors using read overlap'}), 'save_discarded_reads': ('BOOLEAN', {'default': False, 'description': 'Return discarded reads'}), 'save_kmer_hists': ('BOOLEAN', {'default': False, 'description': 'Return input/output k-mer histograms'}), 'threads': ('INT', {'default': 2, 'min': 1, 'max': 128}), 'memory_mb': ('INT', {'default': 4096, 'min': 1, 'description': 'Fallback Java heap in MB'})}, 'hidden': {'output': ('STRING', {})}}
