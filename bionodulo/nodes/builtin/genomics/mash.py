"""mash — genomics node(s). One tool per file (extracted from wrapped_hyphy_metagenomics.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class MashDistNode(CommandNode):
    """Estimate Mash distances between reference and query sequences."""
    NODE_ID = 'mash_dist'
    DISPLAY_NAME = 'Mash Dist'
    REQUIRED_CONDA_PACKAGES = ['mash']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Estimate genome or metagenome distances from FASTA/FASTQ files or Mash sketches.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'mash', 'mash dist', 'minhash', 'genome distance', 'metagenome distance']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('distances',)
    REQUIRED_EXECUTABLES = ['mash']
    DOCUMENTATION_URL = 'https://mash.readthedocs.io/en/latest/distances.html'
    CITATION_DOIS = ['10.1186/s13059-016-0997-x']
    CITATION_URLS = [f'{DOI_URL}10.1186/s13059-016-0997-x']
    CITATION_TEXT = 'Mash: fast genome and metagenome distance estimation using MinHash.'
    VERSION = '2.3'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ['mash', 'dist']
        if inputs.get('table_output', True):
            cmd.append('-t')
        cmd.extend(['-p', str(inputs.get('threads', 1))])
        _add_if_value(cmd, '-v', inputs.get('pvalue', 1.0))
        _add_if_value(cmd, '-d', inputs.get('distance', 1.0))
        cmd.extend([str(inputs.get('reference', '')), str(inputs.get('query', ''))])
        _add_shell_redirect(cmd, f'{out}/distances.tsv')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'distances.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reference': ('FASTA', {'description': 'Reference FASTA/FASTQ or Mash sketch'}), 'query': ('FASTA', {'description': 'Query FASTA/FASTQ or Mash sketch'})}, 'optional': {'table_output': ('BOOLEAN', {'default': True, 'description': 'Use Mash table output (-t)'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'}), 'pvalue': ('FLOAT', {'default': 1.0, 'min': 0, 'max': 1}), 'distance': ('FLOAT', {'default': 1.0, 'min': 0, 'max': 1})}, 'hidden': {'output': ('STRING', {})}}


class MashSketchNode(CommandNode):
    """Create Mash MinHash sketches from reads or assemblies."""
    NODE_ID = 'mash_sketch'
    DISPLAY_NAME = 'Mash Sketch'
    REQUIRED_CONDA_PACKAGES = ['mash']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Create reduced MinHash sequence sketches from FASTA/FASTQ reads or assemblies with Mash.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'mash', 'mash sketch', 'minhash', 'sketch', 'msh', 'genome sketch', 'metagenome sketch']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('sketch',)
    REQUIRED_EXECUTABLES = ['mash']
    DOCUMENTATION_URL = 'https://mash.readthedocs.io/en/latest/sketches.html'
    CITATION_DOIS = ['10.1186/s13059-016-0997-x']
    CITATION_URLS = [f'{DOI_URL}10.1186/s13059-016-0997-x']
    CITATION_TEXT = 'Mash: fast genome and metagenome distance estimation using MinHash.'
    VERSION = '2.3'
    SHELL = True

    @classmethod
    def _linked_name(cls, value: Any) -> str:
        return _safe_name(str(value or 'input'))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        mode = str(inputs.get('reads_assembly_selector', inputs.get('mode', 'reads')))
        prelude = ''
        input_name = ''
        if mode == 'assembly':
            source = str(inputs.get('assembly', ''))
            input_name = cls._linked_name(source)
            prelude = f'ln -sf {shlex.quote(source)} {shlex.quote(input_name)}'
        else:
            reads_input = str(inputs.get('reads_input_selector', 'single'))
            if reads_input == 'paired':
                read1 = str(inputs.get('reads_1', ''))
                read2 = str(inputs.get('reads_2', ''))
                input_name = cls._linked_name(read1)
                prelude = f'cat {shlex.quote(read1)} {shlex.quote(read2)} > {shlex.quote(input_name)}'
            elif reads_input == 'paired_collection':
                reads = inputs.get('reads', {})
                if isinstance(reads, dict):
                    read1 = str(reads.get('forward', reads.get('reads_1', '')))
                    read2 = str(reads.get('reverse', reads.get('reads_2', '')))
                    label = str(reads.get('name', read1 or 'paired_reads'))
                else:
                    pair = _as_list(reads)
                    read1 = pair[0] if pair else ''
                    read2 = pair[1] if len(pair) > 1 else ''
                    label = read1 or 'paired_reads'
                input_name = cls._linked_name(label)
                prelude = f'cat {shlex.quote(read1)} {shlex.quote(read2)} > {shlex.quote(input_name)}'
            else:
                source = str(inputs.get('reads', ''))
                input_name = cls._linked_name(source)
                prelude = f'ln -sf {shlex.quote(source)} {shlex.quote(input_name)}'
        cmd = ['mash', 'sketch', '-s', str(inputs.get('sketch_size', 1000)), '-k', str(inputs.get('kmer_size', 21)), '-w', str(inputs.get('prob_threshold', 0.01))]
        if mode == 'assembly':
            cmd.extend(['-p', str(inputs.get('threads', 1))])
            if inputs.get('individual_sequences'):
                cmd.append('-i')
        else:
            cmd.extend(['-m', str(inputs.get('minimum_kmer_copies', 1)), '-r'])
            _add_if_value(cmd, '-c', inputs.get('target_coverage'))
            _add_if_value(cmd, '-g', inputs.get('genome_size'))
        cmd.extend([input_name, '-o', f'{out}/sketch'])
        return f'{prelude} && {shlex.join(cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'sketch.msh']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads_assembly_selector': ('STRING', {'default': 'reads', 'options': ['reads', 'assembly'], 'description': 'Sketch reads or assembly input'}), 'reads_input_selector': ('STRING', {'default': 'single', 'options': ['paired', 'single', 'paired_collection'], 'description': 'Read input layout'}), 'reads': ('FASTQ', {'description': 'Single-end reads or paired collection'}), 'reads_1': ('FASTQ', {'description': 'Forward reads for paired mode'}), 'reads_2': ('FASTQ', {'description': 'Reverse reads for paired mode'}), 'assembly': ('FASTA', {'description': 'Assembly FASTA for assembly mode'})}, 'optional': {'minimum_kmer_copies': ('INT', {'default': 1, 'min': 1, 'max': 1000, 'description': 'Minimum copies of each k-mer for read noise filtering'}), 'target_coverage': ('INT', {'default': '', 'min': 0, 'max': 500, 'description': 'Stop sketching when this estimated coverage is reached'}), 'genome_size': ('INT', {'default': '', 'min': 1000, 'description': 'Genome size used for p-value calculations'}), 'individual_sequences': ('BOOLEAN', {'default': False, 'description': 'Sketch individual sequences rather than whole assembly files'}), 'sketch_size': ('INT', {'default': 1000, 'min': 10, 'max': 1000000, 'description': 'Maximum non-redundant min-hashes per sketch'}), 'kmer_size': ('INT', {'default': 21, 'min': 1, 'max': 32, 'description': 'k-mer size'}), 'prob_threshold': ('FLOAT', {'default': 0.01, 'min': 0, 'max': 1, 'description': 'Warning threshold for low k-mer size'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class MashPasteNode(CommandNode):
    """Create a single Mash sketch file from multiple sketch files."""
    NODE_ID = 'mash_paste'
    DISPLAY_NAME = 'Mash Paste'
    REQUIRED_CONDA_PACKAGES = ['mash']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Create a single Mash sketch file from multiple Mash sketch files.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'mash', 'mash paste', 'minhash', 'sketch merge', 'merge sketches', 'msh']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('sketch',)
    REQUIRED_EXECUTABLES = ['mash']
    DOCUMENTATION_URL = 'https://mash.readthedocs.io/en/latest/sketches.html'
    CITATION_DOIS = ['10.1186/s13059-016-0997-x']
    CITATION_URLS = [f'{DOI_URL}10.1186/s13059-016-0997-x']
    CITATION_TEXT = 'Mash: fast genome and metagenome distance estimation using MinHash.'
    VERSION = '2.3'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        sketch_files = _as_list(inputs.get('msh_files'))
        linked_files = [_safe_name(path) for path in sketch_files]
        link_commands = [f'ln -sf {shlex.quote(path)} {shlex.quote(linked)}' for path, linked in zip(sketch_files, linked_files, strict=False)]
        cmd = ['mash', 'paste', f'{out}/sketch', *linked_files]
        return ' && '.join([*link_commands, shlex.join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'sketch.msh']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'msh_files': ('FILE', {'list': True, 'description': 'Mash sketch files to merge'})}, 'hidden': {'output': ('STRING', {})}}


class MashScreenNode(CommandNode):
    """Estimate how well Mash sketch queries are contained in a read pool."""
    NODE_ID = 'mash_screen'
    DISPLAY_NAME = 'Mash Screen'
    REQUIRED_CONDA_PACKAGES = ['mash']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Screen reads against a Mash sketch database to estimate sequence containment.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'mash', 'mash screen', 'containment', 'metagenome screen', 'genome discovery', 'read screening', 'minhash']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('screen',)
    REQUIRED_EXECUTABLES = ['mash']
    DOCUMENTATION_URL = 'https://mash.readthedocs.io/en/latest/tutorials.html#screening-a-read-set-for-containment-of-refseq-genomes'
    CITATION_DOIS = ['10.1186/s13059-019-1841-x', '10.1186/s13059-016-0997-x']
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CITATION_DOIS]
    CITATION_TEXT = 'Mash Screen: high-throughput sequence containment estimation for genome discovery; Mash: fast genome and metagenome distance estimation using MinHash.'
    VERSION = '2.3'
    SHELL = True

    @classmethod
    def _pool_files(cls, inputs: dict[str, Any]) -> list[str]:
        mode = str(inputs.get('pool_input_selector', inputs.get('reads_input_selector', 'single')))
        if mode == 'paired':
            return [str(inputs.get('pool_1', inputs.get('reads_1', ''))), str(inputs.get('pool_2', inputs.get('reads_2', '')))]
        if mode == 'paired_collection':
            pool = inputs.get('pool', inputs.get('reads', {}))
            if isinstance(pool, dict):
                return [str(pool.get('forward', pool.get('reads_1', ''))), str(pool.get('reverse', pool.get('reads_2', '')))]
            paired = _as_list(pool)
            return paired[:2]
        return [str(inputs.get('pool', inputs.get('reads', '')))]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        queries = str(inputs.get('queries', inputs.get('query_sketch', '')))
        cmd = ['mash', 'screen']
        if inputs.get('winner_takes_all', True):
            cmd.append('-w')
        cmd.extend(['-i', str(inputs.get('minimum_identity_to_report', inputs.get('minimum_identity', 0.0))), '-v', str(inputs.get('maximum_p_value_to_report', inputs.get('maximum_p_value', 1.0))), 'queries.msh', *cls._pool_files(inputs)])
        return f"ln -sf {shlex.quote(queries)} queries.msh && {shlex.join(cmd)} > {shlex.quote(f'{out}/screen.tsv')}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'screen.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'queries': ('FILE', {'description': 'Mash sketch database containing query genomes or sequences'}), 'pool_input_selector': ('STRING', {'default': 'single', 'options': ['paired', 'single', 'paired_collection'], 'description': 'Read input layout'}), 'pool': ('FASTQ', {'description': 'Single-end reads or paired collection to screen'}), 'pool_1': ('FASTQ', {'description': 'Forward reads for paired mode'}), 'pool_2': ('FASTQ', {'description': 'Reverse reads for paired mode'})}, 'optional': {'winner_takes_all': ('BOOLEAN', {'default': True, 'description': 'Use winner-takes-all mode to reduce redundant matches'}), 'minimum_identity_to_report': ('FLOAT', {'default': 0.0, 'min': -1.0, 'max': 1.0, 'description': 'Minimum identity to report'}), 'maximum_p_value_to_report': ('FLOAT', {'default': 1.0, 'min': 0.0, 'max': 1.0, 'description': 'Maximum p-value to report'})}, 'hidden': {'output': ('STRING', {})}}
