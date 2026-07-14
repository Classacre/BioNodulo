"""ucsc — genomics node(s). One tool per file (extracted from wrapped_beacon_ucsc.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *
class _Beacon2MultiInputBaseNode(CommandNode):
    """Shared command rendering for Beacon2 converters that symlink multi-input collections."""
    REQUIRED_CONDA_PACKAGES = ['beacon2-ri-tools', 'gzip']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/beacon2'
    CITATION_DOIS = [BEACON2_DOI]
    CITATION_URLS = [f'{DOI_URL}{BEACON2_DOI}']
    CITATION_TEXT = BEACON2_CITATION_TEXT
    VERSION = '2.0.0+galaxy0'
    SHELL = True
    INPUT_NAME = ''

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get(cls.INPUT_NAME))

    @classmethod
    def _staged_paths(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        labels = _as_list(inputs.get('element_identifiers'))
        staged: list[str] = []
        for index, input_file in enumerate(cls._input_files(inputs)):
            label = labels[index] if index < len(labels) and labels[index] else input_file
            staged.append(f'{out}/{_safe_element_identifier(label)}')
        return staged

    @classmethod
    def _symlink_commands(cls, inputs: dict[str, Any]) -> list[str]:
        return [_shell_join(['ln', '-s', input_file, staged_path]) for input_file, staged_path in zip(cls._input_files(inputs), cls._staged_paths(inputs), strict=False)]
class _UcscSingleFileUtilityNode(CommandNode):
    """Shared behavior for single-input UCSC Genome Browser utilities."""
    CATEGORY = 'genomics'
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('out',)
    DOCUMENTATION_URL = ''
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    TOOL_NAME = ''
    INPUT_NAME = ''
    OUTPUT_FILENAME = ''
    INPUT_DESCRIPTION = ''

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls.OUTPUT_FILENAME}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join([cls.TOOL_NAME, str(inputs.get(cls.INPUT_NAME, '')), cls._output_path(inputs)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get(cls.INPUT_NAME, '')).strip():
            return f'{cls.INPUT_NAME} is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {cls.INPUT_NAME: ('FILE', {'description': cls.INPUT_DESCRIPTION})}, 'hidden': {'output': ('STRING', {})}}


class UcscNetChainSubsetNode(CommandNode):
    """Extract the subset of chains referenced by a UCSC net file."""
    NODE_ID = 'ucsc_netchainsubset'
    DISPLAY_NAME = 'netChainSubset'
    REQUIRED_CONDA_PACKAGES = ['ucsc-netchainsubset']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Create a UCSC chain file containing only chains that appear in a net file.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_netchainsubset', 'netChainSubset', 'UCSC net', 'UCSC chain', 'liftOver', 'chain subset']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('out',)
    REQUIRED_EXECUTABLES = ['netChainSubset']
    DOCUMENTATION_URL = 'https://genome.ucsc.edu/goldenPath/help/net.html'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    FLAG_INPUTS = (('splitOnInsert', '-splitOnInsert'), ('wholeChains', '-wholeChains'), ('skipMissing', '-skipMissing'))

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out.chain'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['netChainSubset', str(inputs.get('in_net', '')), str(inputs.get('in_chain', '')), cls._output_path(inputs)]
        for name, flag in cls.FLAG_INPUTS:
            if inputs.get(name):
                cmd.append(flag)
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out.chain']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('in_net', '')).strip():
            return 'in_net is required'
        if not str(inputs.get('in_chain', '')).strip():
            return 'in_chain is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_net': ('FILE', {'description': 'UCSC net file identifying chains to keep'}), 'in_chain': ('FILE', {'description': 'UCSC chain file to subset'})}, 'optional': {'splitOnInsert': ('BOOLEAN', {'default': False, 'description': 'Split chains when an insertion of another chain is encountered'}), 'wholeChains': ('BOOLEAN', {'default': False, 'description': 'Write entire referenced chains instead of splitting high-level nets'}), 'skipMissing': ('BOOLEAN', {'default': False, 'description': 'Skip chains that are not found instead of failing'})}, 'hidden': {'output': ('STRING', {})}}


class UcscNetFilterNode(CommandNode):
    """Filter a UCSC net file."""
    NODE_ID = 'ucsc_netfilter'
    DISPLAY_NAME = 'netFilter'
    REQUIRED_CONDA_PACKAGES = ['ucsc-netfilter']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Filter out parts of a UCSC net alignment file.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_netfilter', 'netFilter', 'UCSC net', 'net file', 'synteny filter', 'minimum gap']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('out',)
    REQUIRED_EXECUTABLES = ['netFilter']
    DOCUMENTATION_URL = 'https://genome.ucsc.edu/goldenPath/help/net.html'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    SYN_FILTERS = ['skipsyn', 'filtersyn']
    SYN_TYPES = ['-syn', '-chimpSyn', '-nonsyn']
    NONNEGATIVE_THRESHOLDS = ('minSynSize', 'minSynAli', 'minGap')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out.ucsc.net'

    @classmethod
    def _syn_filter(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('syn_filter', 'skipsyn') or 'skipsyn')

    @classmethod
    def _syn_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('syntype', '-syn') or '-syn')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['netFilter', str(inputs.get('in_net', ''))]
        if cls._syn_filter(inputs) == 'filtersyn':
            cmd.append(cls._syn_type(inputs))
            for name in ('minSynScore', 'minSynSize', 'minSynAli'):
                if str(inputs.get(name, '')) != '':
                    cmd.append(f'-{name}={inputs.get(name)}')
        if str(inputs.get('minGap', '')) != '':
            cmd.append(f"-minGap={inputs.get('minGap')}")
        return f'{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out.ucsc.net']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('in_net', '')).strip():
            return 'in_net is required'
        syn_filter = cls._syn_filter(inputs)
        if syn_filter not in cls.SYN_FILTERS:
            return f"syn_filter must be one of: {', '.join(cls.SYN_FILTERS)}"
        syntype = cls._syn_type(inputs)
        if syntype not in cls.SYN_TYPES:
            return f"syntype must be one of: {', '.join(cls.SYN_TYPES)}"
        for name in cls.NONNEGATIVE_THRESHOLDS:
            value = inputs.get(name, '')
            if str(value) != '' and int(value) < 0:
                return f'{name} must be greater than or equal to 0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_net': ('FILE', {'description': 'UCSC net alignment file to filter'})}, 'optional': {'syn_filter': ('STRING', {'default': 'skipsyn', 'options': cls.SYN_FILTERS, 'description': 'Enable synteny-based filtering'}), 'syntype': ('STRING', {'default': '-syn', 'options': cls.SYN_TYPES, 'description': 'Synteny filter mode used when synteny filtering is enabled'}), 'minSynScore': ('INT', {'default': '', 'description': 'Minimum syntenic block score'}), 'minSynSize': ('INT', {'default': '', 'min': 0, 'description': 'Minimum syntenic block size'}), 'minSynAli': ('INT', {'default': '', 'min': 0, 'description': 'Minimum syntenic alignment size'}), 'minGap': ('INT', {'default': '', 'min': 0, 'description': 'Minimum gap size to keep'})}, 'hidden': {'output': ('STRING', {})}}


class UcscChainPreNetNode(CommandNode):
    """Remove chains unlikely to be netted."""
    NODE_ID = 'ucsc_chainprenet'
    DISPLAY_NAME = 'chainPreNet'
    REQUIRED_CONDA_PACKAGES = ['ucsc-chainprenet']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Remove UCSC chains that do not have a chance of being netted.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_chainprenet', 'chainPreNet', 'UCSC chain', 'UCSC net', 'netted chains', 'chrom sizes', 'haplotype pseudochromosomes']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('out',)
    REQUIRED_EXECUTABLES = ['chainPreNet']
    DOCUMENTATION_URL = 'https://genome.ucsc.edu/goldenPath/help/chain.html'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    REFERENCE_SOURCE_OPTIONS = ['cached', 'history']

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out.chain'

    @classmethod
    def _source(cls, inputs: dict[str, Any], prefix: str) -> str:
        return str(inputs.get(f'{prefix}_reference_index_source_selector', 'history') or 'history')

    @classmethod
    def _index_path(cls, inputs: dict[str, Any], prefix: str) -> str:
        source = cls._source(inputs, prefix)
        if prefix == 'target':
            return str(inputs.get('tar_ref_index_path' if source == 'cached' else 'in_tar_ref_index', ''))
        return str(inputs.get('que_ref_index_path' if source == 'cached' else 'in_que_ref_index', ''))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['chainPreNet', str(inputs.get('in_chain', '')), cls._index_path(inputs, 'target'), cls._index_path(inputs, 'query'), cls._output_path(inputs)]
        if str(inputs.get('pad', '')) != '':
            cmd.append(f"-pad={inputs.get('pad')}")
        if inputs.get('inclHap'):
            cmd.append('-inclHap')
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out.chain']

    @classmethod
    def _validate_index(cls, inputs: dict[str, Any], prefix: str) -> bool | str:
        selector_name = f'{prefix}_reference_index_source_selector'
        source = cls._source(inputs, prefix)
        if source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"{selector_name} must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        if prefix == 'target':
            required_name = 'tar_ref_index_path' if source == 'cached' else 'in_tar_ref_index'
        else:
            required_name = 'que_ref_index_path' if source == 'cached' else 'in_que_ref_index'
        if not cls._index_path(inputs, prefix).strip():
            return f'{required_name} is required'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('in_chain', '')).strip():
            return 'in_chain is required'
        for prefix in ('target', 'query'):
            index_validation = cls._validate_index(inputs, prefix)
            if index_validation is not True:
                return index_validation
        if str(inputs.get('pad', '')) != '' and int(inputs.get('pad')) < 0:
            return 'pad must be greater than or equal to 0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_chain': ('FILE', {'description': 'UCSC chain alignment file to pre-filter before netting'})}, 'optional': {'target_reference_index_source_selector': ('STRING', {'default': 'history', 'options': cls.REFERENCE_SOURCE_OPTIONS, 'description': 'Use a cached or history target genome index'}), 'in_tar_ref_index': ('FILE', {'description': 'History target chrom sizes or FASTA index file'}), 'tar_ref_index_path': ('STRING', {'default': '', 'description': 'Path to cached target chrom sizes or FASTA index file'}), 'query_reference_index_source_selector': ('STRING', {'default': 'history', 'options': cls.REFERENCE_SOURCE_OPTIONS, 'description': 'Use a cached or history query genome index'}), 'in_que_ref_index': ('FILE', {'description': 'History query chrom sizes or FASTA index file'}), 'que_ref_index_path': ('STRING', {'default': '', 'description': 'Path to cached query chrom sizes or FASTA index file'}), 'pad': ('INT', {'default': '', 'min': 0, 'description': 'Extra bases to pad around blocks to decrease trash'}), 'inclHap': ('BOOLEAN', {'default': False, 'description': 'Include query sequences named *_hap* or *_alt*'})}, 'hidden': {'output': ('STRING', {})}}


class UcscNetToAxtNode(CommandNode):
    """Convert UCSC net and chain alignments to AXT."""
    NODE_ID = 'ucsc_nettoaxt'
    DISPLAY_NAME = 'netToAxt'
    REQUIRED_CONDA_PACKAGES = ['ucsc-nettoaxt']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Convert UCSC net and chain alignments to AXT format.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_nettoaxt', 'netToAxt', 'UCSC net', 'UCSC chain', 'net to AXT', 'pairwise alignment']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('out',)
    REQUIRED_EXECUTABLES = ['netToAxt']
    DOCUMENTATION_URL = 'https://genome.ucsc.edu/goldenPath/help/axt.html'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out.axt'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['netToAxt', str(inputs.get('in_net', '')), str(inputs.get('in_chain', '')), str(inputs.get('in_target', '')), str(inputs.get('in_query', '')), cls._output_path(inputs)]
        if inputs.get('qChain'):
            cmd.append('-qChain')
        if str(inputs.get('maxGap', '')) != '':
            cmd.append(f"-maxGap={inputs.get('maxGap')}")
        if inputs.get('noSplit'):
            cmd.append('-noSplit')
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out.axt']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ('in_net', 'in_chain', 'in_target', 'in_query'):
            if not str(inputs.get(name, '')).strip():
                return f'{name} is required'
        if str(inputs.get('maxGap', '')) != '' and int(inputs.get('maxGap')) < 0:
            return 'maxGap must be greater than or equal to 0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_net': ('FILE', {'description': 'UCSC net alignment file'}), 'in_chain': ('FILE', {'description': 'UCSC chain alignment file'}), 'in_target': ('FILE', {'description': 'TwoBit file containing the target sequence'}), 'in_query': ('FILE', {'description': 'TwoBit file containing the query sequence'})}, 'optional': {'qChain': ('BOOLEAN', {'default': False, 'description': 'Treat the net as being with respect to the query side of chains'}), 'maxGap': ('INT', {'default': '', 'min': 0, 'description': 'Maximum gap size before breaking alignment blocks'}), 'noSplit': ('BOOLEAN', {'default': False, 'description': 'Do not split chains at insertions of another chain'})}, 'hidden': {'output': ('STRING', {})}}


class UcscTwoBitToFaNode(CommandNode):
    """Convert UCSC TwoBit sequence files to FASTA."""
    NODE_ID = 'ucsc-twobittofa'
    DISPLAY_NAME = 'twoBitToFa'
    REQUIRED_CONDA_PACKAGES = ['ucsc-twobittofa']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Convert all or part of a TwoBit sequence file to FASTA.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc-twobittofa', 'twoBitToFa', 'TwoBit', '2bit to FASTA', 'sequence range', 'seqList']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('fasta_output',)
    REQUIRED_EXECUTABLES = ['twoBitToFa']
    DOCUMENTATION_URL = 'https://genome.ucsc.edu/goldenpath/help/twoBit.html'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482'

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/fasta_output.fa'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['twoBitToFa', str(inputs.get('twobit_input', '')), cls._output_path(inputs)]
        if str(inputs.get('seq', '')) != '':
            cmd.append(f"-seq={inputs.get('seq')}")
        if str(inputs.get('start', '')) != '':
            cmd.append(f"-start={inputs.get('start')}")
        if str(inputs.get('end', '')) != '':
            cmd.append(f"-end={inputs.get('end')}")
        if str(inputs.get('seqList', '')) != '':
            cmd.append(f"-seqList={inputs.get('seqList')}")
        if inputs.get('noMask'):
            cmd.append('-noMask')
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'fasta_output.fa']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('twobit_input', '')).strip():
            return 'twobit_input is required'
        for name in ('start', 'end'):
            value = inputs.get(name, '')
            if str(value) != '' and int(value) < 0:
                return f'{name} must be greater than or equal to 0'
        if str(inputs.get('start', '')) != '' and str(inputs.get('end', '')) != '':
            if int(inputs.get('end')) < int(inputs.get('start')):
                return 'end must be greater than or equal to start'
        if str(inputs.get('seq', '')) != '' and str(inputs.get('seqList', '')) != '':
            return 'seq and seqList cannot both be set'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'twobit_input': ('FILE', {'description': 'Input UCSC TwoBit sequence file'})}, 'optional': {'seq': ('STRING', {'default': '', 'description': 'Restrict conversion to one sequence name'}), 'start': ('INT', {'default': '', 'min': 0, 'description': 'Zero-based start position within the selected sequence'}), 'end': ('INT', {'default': '', 'min': 0, 'description': 'Non-inclusive end position within the selected sequence'}), 'seqList': ('FILE', {'description': 'Text file with sequence names or seqSpec:start-end ranges to extract'}), 'noMask': ('BOOLEAN', {'default': False, 'description': 'Convert masked sequence to uppercase'})}, 'hidden': {'output': ('STRING', {})}}


class UcscWigToBigWigNode(CommandNode):
    """Convert Wiggle or bedGraph data to bigWig."""
    NODE_ID = 'ucsc_wigtobigwig'
    DISPLAY_NAME = 'wigtobigwig'
    REQUIRED_CONDA_PACKAGES = ['ucsc-wigtobigwig', 'grep']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Convert bedGraph or Wiggle data to an indexed bigWig track.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_wigtobigwig', 'wigtobigwig', 'wigToBigWig', 'bigWig', 'bedGraph', 'Wiggle', 'genome browser track']
    RETURN_TYPES = ('BIGWIG',)
    RETURN_NAMES = ('out_file1',)
    REQUIRED_EXECUTABLES = ['grep', 'wigToBigWig']
    DOCUMENTATION_URL = 'https://genome.ucsc.edu/goldenPath/help/bigWig.html'
    CITATION_DOIS = [BBG_TO_BIGWIG_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{BBG_TO_BIGWIG_CITATION_DOI}']
    CITATION_TEXT = BBG_TO_BIGWIG_CITATION_TEXT
    VERSION = '482+galaxy0'
    GENOME_SOURCE_OPTIONS = ['indexed', 'history']
    SETTINGS_OPTIONS = ['preset', 'full']

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out_file1.bw'

    @classmethod
    def _trackless_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/trackless'

    @classmethod
    def _genome_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('genome_type_select', 'indexed') or 'indexed')

    @classmethod
    def _settings_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('settingsType', 'preset') or 'preset')

    @classmethod
    def _chrom_sizes(cls, inputs: dict[str, Any]) -> str:
        if cls._genome_source(inputs) == 'history':
            return str(inputs.get('chromfile', ''))
        return str(inputs.get('index_len_path', ''))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out_dir = _out(inputs)
        trackless = cls._trackless_path(inputs)
        setup = _shell_join(['mkdir', '-p', out_dir])
        strip = f"grep -v '^track' {shlex.quote(str(inputs.get('input1', '')))} > {shlex.quote(trackless)}"
        cmd = ['wigToBigWig', trackless, cls._chrom_sizes(inputs), cls._output_path(inputs)]
        if cls._settings_type(inputs) == 'full':
            cmd.append(f"-blockSize={inputs.get('blockSize', 256)}")
            cmd.append(f"-itemsPerSlot={inputs.get('itemsPerSlot', 1024)}")
            if inputs.get('clip', True):
                cmd.append('-clip')
            if inputs.get('unc'):
                cmd.append('-unc')
        else:
            cmd.append('-clip')
        return f'{setup} && {strip} && {_shell_join(cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out_file1.bw']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input1', '')).strip():
            return 'input1 is required'
        genome_source = cls._genome_source(inputs)
        if genome_source not in cls.GENOME_SOURCE_OPTIONS:
            return f"genome_type_select must be one of: {', '.join(cls.GENOME_SOURCE_OPTIONS)}"
        if not cls._chrom_sizes(inputs).strip():
            return 'chromfile is required' if genome_source == 'history' else 'index_len_path is required'
        settings_type = cls._settings_type(inputs)
        if settings_type not in cls.SETTINGS_OPTIONS:
            return f"settingsType must be one of: {', '.join(cls.SETTINGS_OPTIONS)}"
        if settings_type == 'full':
            for name, default in (('blockSize', 256), ('itemsPerSlot', 1024)):
                value = inputs.get(name, default)
                if int(value) < 1:
                    return f'{name} must be greater than or equal to 1'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input1': ('FILE', {'description': 'Wiggle or bedGraph file to convert'})}, 'optional': {'genome_type_select': ('STRING', {'default': 'indexed', 'options': cls.GENOME_SOURCE_OPTIONS, 'description': 'Use built-in genome lengths or a chromosome length file from history'}), 'index_len_path': ('STRING', {'default': '', 'description': 'Path to cached chromosome length file for the selected genome build'}), 'chromfile': ('FILE', {'description': 'Chromosome length file for a history reference genome'}), 'settingsType': ('STRING', {'default': 'preset', 'options': cls.SETTINGS_OPTIONS, 'description': 'Use default converter settings or expose the full parameter list'}), 'blockSize': ('INT', {'default': 256, 'min': 1, 'description': 'Items to bundle in the R-tree'}), 'itemsPerSlot': ('INT', {'default': 1024, 'min': 1, 'description': 'Data points bundled at the lowest level'}), 'clip': ('BOOLEAN', {'default': True, 'description': 'Warn and clip items beyond chromosome ends instead of failing'}), 'unc': ('BOOLEAN', {'default': False, 'description': 'Write an uncompressed bigWig file'})}, 'hidden': {'output': ('STRING', {})}}


class UcscAxtToMafNode(CommandNode):
    """Convert UCSC AXT alignments to MAF."""
    NODE_ID = 'ucsc_axtomaf'
    DISPLAY_NAME = 'axtToMaf'
    REQUIRED_CONDA_PACKAGES = ['ucsc-axttomaf']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Convert UCSC AXT pairwise alignments to MAF format.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_axtomaf', 'axtToMaf', 'AXT to MAF', 'multiple alignment format', 'pairwise alignment', 'chrom sizes']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('out',)
    REQUIRED_EXECUTABLES = ['axtToMaf']
    DOCUMENTATION_URL = 'https://genome.ucsc.edu/FAQ/FAQformat.html#format5'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy1'
    REFERENCE_SOURCE_OPTIONS = ['cached', 'history']

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out.maf'

    @classmethod
    def _source(cls, inputs: dict[str, Any], prefix: str) -> str:
        return str(inputs.get(f'{prefix}_reference_index_source_selector', 'history') or 'history')

    @classmethod
    def _index_path(cls, inputs: dict[str, Any], prefix: str) -> str:
        source = cls._source(inputs, prefix)
        if prefix == 'target':
            return str(inputs.get('tar_ref_index_path' if source == 'cached' else 'in_tar_ref_index', ''))
        return str(inputs.get('que_ref_index_path' if source == 'cached' else 'in_que_ref_index', ''))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['axtToMaf', str(inputs.get('in_axt', '')), cls._index_path(inputs, 'target'), cls._index_path(inputs, 'query')]
        if str(inputs.get('t_prefix', '')) != '':
            cmd.append(f"-tPrefix={inputs.get('t_prefix')}")
        if str(inputs.get('q_prefix', '')) != '':
            cmd.append(f"-qPrefix={inputs.get('q_prefix')}")
        if inputs.get('score'):
            cmd.append('-score')
        if inputs.get('scoreZero'):
            cmd.append('-scoreZero')
        cmd.append(cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out.maf']

    @classmethod
    def _validate_index(cls, inputs: dict[str, Any], prefix: str) -> bool | str:
        selector_name = f'{prefix}_reference_index_source_selector'
        source = cls._source(inputs, prefix)
        if source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"{selector_name} must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        if prefix == 'target':
            required_name = 'tar_ref_index_path' if source == 'cached' else 'in_tar_ref_index'
        else:
            required_name = 'que_ref_index_path' if source == 'cached' else 'in_que_ref_index'
        if not cls._index_path(inputs, prefix).strip():
            return f'{required_name} is required'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('in_axt', '')).strip():
            return 'in_axt is required'
        for prefix in ('target', 'query'):
            index_validation = cls._validate_index(inputs, prefix)
            if index_validation is not True:
                return index_validation
        for name in ('t_prefix', 'q_prefix'):
            if ' ' in str(inputs.get(name, '')):
                return f'{name} cannot contain spaces'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_axt': ('FILE', {'description': 'UCSC AXT pairwise alignment file'})}, 'optional': {'target_reference_index_source_selector': ('STRING', {'default': 'history', 'options': cls.REFERENCE_SOURCE_OPTIONS, 'description': 'Use a cached or history target genome index'}), 'in_tar_ref_index': ('FILE', {'description': 'History target chrom sizes or FASTA index file'}), 'tar_ref_index_path': ('STRING', {'default': '', 'description': 'Path to cached target chrom sizes or FASTA index file'}), 'query_reference_index_source_selector': ('STRING', {'default': 'history', 'options': cls.REFERENCE_SOURCE_OPTIONS, 'description': 'Use a cached or history query genome index'}), 'in_que_ref_index': ('FILE', {'description': 'History query chrom sizes or FASTA index file'}), 'que_ref_index_path': ('STRING', {'default': '', 'description': 'Path to cached query chrom sizes or FASTA index file'}), 't_prefix': ('STRING', {'default': '', 'description': 'Prefix added to target sequence names in the MAF output'}), 'q_prefix': ('STRING', {'default': '', 'description': 'Prefix added to query sequence names in the MAF output'}), 'score': ('BOOLEAN', {'default': False, 'description': 'Recalculate alignment scores'}), 'scoreZero': ('BOOLEAN', {'default': False, 'description': 'Recalculate scores only when the AXT score is zero'})}, 'hidden': {'output': ('STRING', {})}}


class UcscAxtChainNode(CommandNode):
    """Chain UCSC AXT or PSL pairwise alignments."""
    NODE_ID = 'ucsc_axtchain'
    DISPLAY_NAME = 'axtChain'
    REQUIRED_CONDA_PACKAGES = ['ucsc-axtchain']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Chain together UCSC AXT or PSL pairwise alignments into chain format.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_axtchain', 'axtChain', 'chain together axt', 'AXT chain', 'PSL chain', 'linear gap costs']
    RETURN_TYPES = ('FILE', 'TXT')
    RETURN_NAMES = ('out', 'out_details')
    REQUIRED_EXECUTABLES = ['axtChain', 'gzip']
    DOCUMENTATION_URL = 'https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/mouseStuff/axtChain/axtChain.c'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy2'
    SHELL = True
    ALIGNMENT_FORMATS = ['', 'axt', 'psl']
    LINEAR_GAP_OPTIONS = ['loose', 'medium', 'linear_gap_file']

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out.chain'

    @classmethod
    def _details_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out_details.txt'

    @classmethod
    def _alignment_format(cls, inputs: dict[str, Any]) -> str:
        selected = str(inputs.get('alignment_format', '') or '')
        if selected:
            return selected
        suffixes = [suffix.lower() for suffix in Path(str(inputs.get('in_aln', ''))).suffixes]
        if suffixes and suffixes[-1] == '.gz':
            suffixes = suffixes[:-1]
        if suffixes and suffixes[-1] in {'.axt', '.psl'}:
            return suffixes[-1].lstrip('.')
        return ''

    @classmethod
    def _linear_gap(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('linear_gap', 'loose') or 'loose')

    @classmethod
    def _linear_gap_value(cls, inputs: dict[str, Any]) -> str:
        if cls._linear_gap(inputs) == 'linear_gap_file':
            return str(inputs.get('lineargap_input', ''))
        return cls._linear_gap(inputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['axtChain', '-faQ', '-faT']
        if cls._alignment_format(inputs) == 'psl':
            cmd.append('-psl')
        if str(inputs.get('minScore', '')) != '':
            cmd.append(f"-minScore={inputs.get('minScore')}")
        if str(inputs.get('scoreScheme', '')) != '':
            cmd.append(f"-scoreScheme={inputs.get('scoreScheme')}")
        if inputs.get('details_output'):
            cmd.append(f'-details={cls._details_path(inputs)}')
        cmd.append(f'-linearGap={cls._linear_gap_value(inputs)}')
        command = _shell_join(cmd)
        aln = shlex.quote(str(inputs.get('in_aln', '')))
        tail = _shell_join([str(inputs.get('in_target', '')), str(inputs.get('in_query', '')), cls._output_path(inputs)])
        return f'{command} <(gzip -cdfq {aln}) {tail}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'out.chain']
        if inputs.get('details_output', False):
            outputs.append(out / 'out_details.txt')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ('in_aln', 'in_target', 'in_query'):
            if not str(inputs.get(name, '')).strip():
                return f'{name} is required'
        selected_format = str(inputs.get('alignment_format', '') or '')
        if selected_format not in cls.ALIGNMENT_FORMATS:
            return f"alignment_format must be one of: {', '.join(cls.ALIGNMENT_FORMATS)}"
        linear_gap = cls._linear_gap(inputs)
        if linear_gap not in cls.LINEAR_GAP_OPTIONS:
            return f"linear_gap must be one of: {', '.join(cls.LINEAR_GAP_OPTIONS)}"
        if linear_gap == 'linear_gap_file' and (not str(inputs.get('lineargap_input', '')).strip()):
            return 'lineargap_input is required when linear_gap is linear_gap_file'
        if str(inputs.get('minScore', '')) != '' and int(inputs.get('minScore')) < 0:
            return 'minScore must be greater than or equal to 0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_aln': ('FILE', {'description': 'Pairwise AXT or PSL alignments, optionally gzip-compressed'}), 'in_target': ('FASTA', {'description': 'Target FASTA sequence file matching alignment target names'}), 'in_query': ('FASTA', {'description': 'Query FASTA sequence file matching alignment query names'})}, 'optional': {'alignment_format': ('STRING', {'default': '', 'options': cls.ALIGNMENT_FORMATS, 'description': 'Alignment format override; otherwise inferred from .axt/.psl extension'}), 'linear_gap': ('STRING', {'default': 'loose', 'options': cls.LINEAR_GAP_OPTIONS, 'description': 'Use UCSC loose/medium linear gap costs or a custom cost file'}), 'lineargap_input': ('FILE', {'description': 'Custom tabular linear gap cost file used when linear_gap is linear_gap_file'}), 'minScore': ('INT', {'default': '', 'min': 0, 'description': 'Minimum chain score to report'}), 'scoreScheme': ('FILE', {'description': 'Optional BLASTZ-format scoring matrix'}), 'details_output': ('BOOLEAN', {'default': False, 'description': 'Write per-chain gap and scoring details'})}, 'hidden': {'output': ('STRING', {})}}


class UcscChainNetNode(CommandNode):
    """Create UCSC alignment net files from chains."""
    NODE_ID = 'ucsc_chainnet'
    DISPLAY_NAME = 'chainNet'
    REQUIRED_CONDA_PACKAGES = ['ucsc-chainnet']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Create target and query UCSC net alignment files from chain alignments.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_chainnet', 'chainNet', 'UCSC chain', 'UCSC net', 'alignment nets', 'target net', 'query net']
    RETURN_TYPES = ('FILE', 'FILE')
    RETURN_NAMES = ('targetNet', 'queryNet')
    REQUIRED_EXECUTABLES = ['chainNet']
    DOCUMENTATION_URL = 'https://genome.ucsc.edu/goldenPath/help/net.html'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    REFERENCE_SOURCE_OPTIONS = ['cached', 'history']
    NONNEGATIVE_OPTIONS = ('minSpace', 'minFill', 'verbose')

    @classmethod
    def _target_net_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/target.net'

    @classmethod
    def _query_net_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/query.net'

    @classmethod
    def _source(cls, inputs: dict[str, Any], prefix: str) -> str:
        return str(inputs.get(f'{prefix}_reference_index_source_selector', 'history') or 'history')

    @classmethod
    def _index_path(cls, inputs: dict[str, Any], prefix: str) -> str:
        source = cls._source(inputs, prefix)
        if prefix == 'target':
            return str(inputs.get('tar_ref_index_path' if source == 'cached' else 'in_tar_ref_index', ''))
        return str(inputs.get('que_ref_index_path' if source == 'cached' else 'in_que_ref_index', ''))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['chainNet', str(inputs.get('in_chain', '')), cls._index_path(inputs, 'target'), cls._index_path(inputs, 'query'), cls._target_net_path(inputs), cls._query_net_path(inputs)]
        for name in ('minSpace', 'minFill', 'minScore'):
            if str(inputs.get(name, '')) != '':
                cmd.append(f'-{name}={inputs.get(name)}')
        if inputs.get('inclHap'):
            cmd.append('-inclHap')
        if str(inputs.get('verbose', '')) != '':
            cmd.append(f"-verbose={inputs.get('verbose')}")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'target.net', out / 'query.net']

    @classmethod
    def _validate_index(cls, inputs: dict[str, Any], prefix: str) -> bool | str:
        selector_name = f'{prefix}_reference_index_source_selector'
        source = cls._source(inputs, prefix)
        if source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"{selector_name} must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        if prefix == 'target':
            required_name = 'tar_ref_index_path' if source == 'cached' else 'in_tar_ref_index'
        else:
            required_name = 'que_ref_index_path' if source == 'cached' else 'in_que_ref_index'
        if not cls._index_path(inputs, prefix).strip():
            return f'{required_name} is required'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('in_chain', '')).strip():
            return 'in_chain is required'
        for prefix in ('target', 'query'):
            index_validation = cls._validate_index(inputs, prefix)
            if index_validation is not True:
                return index_validation
        for name in cls.NONNEGATIVE_OPTIONS:
            value = inputs.get(name, '')
            if str(value) != '' and int(value) < 0:
                return f'{name} must be greater than or equal to 0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_chain': ('FILE', {'description': 'UCSC chain alignment file to net'})}, 'optional': {'target_reference_index_source_selector': ('STRING', {'default': 'history', 'options': cls.REFERENCE_SOURCE_OPTIONS, 'description': 'Use a cached or history target genome index'}), 'in_tar_ref_index': ('FILE', {'description': 'History target chrom sizes or FASTA index file'}), 'tar_ref_index_path': ('STRING', {'default': '', 'description': 'Path to cached target chrom sizes or FASTA index file'}), 'query_reference_index_source_selector': ('STRING', {'default': 'history', 'options': cls.REFERENCE_SOURCE_OPTIONS, 'description': 'Use a cached or history query genome index'}), 'in_que_ref_index': ('FILE', {'description': 'History query chrom sizes or FASTA index file'}), 'que_ref_index_path': ('STRING', {'default': '', 'description': 'Path to cached query chrom sizes or FASTA index file'}), 'minSpace': ('INT', {'default': '', 'min': 0, 'description': 'Minimum gap size to fill'}), 'minFill': ('INT', {'default': '', 'min': 0, 'description': 'Minimum fill size to record'}), 'minScore': ('INT', {'default': '', 'description': 'Minimum chain score to consider'}), 'inclHap': ('BOOLEAN', {'default': False, 'description': 'Include query sequences named *_hap* or *_alt*'}), 'verbose': ('INT', {'default': '', 'min': 0, 'description': 'Verbosity level'})}, 'hidden': {'output': ('STRING', {})}}


class UcscMafFilterNode(CommandNode):
    """Filter UCSC MAF alignment blocks."""
    NODE_ID = 'ucsc_maffilter'
    DISPLAY_NAME = 'mafFilter'
    REQUIRED_CONDA_PACKAGES = ['ucsc-maffilter']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Filter UCSC MAF alignment blocks by size, score, species, and component criteria.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_mafFilter', 'ucsc_maffilter', 'mafFilter', 'MAF block filter', 'multiple alignment format', 'species filter', 'component filter', 'rejected MAF blocks']
    RETURN_TYPES = ('FILE', 'FILE')
    RETURN_NAMES = ('output_maf', 'rejected_maf')
    REQUIRED_EXECUTABLES = ['mafFilter']
    DOCUMENTATION_URL = 'https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/ratStuff/mafFilter/mafFilter.c'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    FACTOR_OPTIONS = ['no', 'yes']

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output.maf'

    @classmethod
    def _reject_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/rejected.maf'

    @classmethod
    def _factor_enabled(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('factor_enabled', 'no') or 'no')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['mafFilter']
        if inputs.get('tolerate'):
            cmd.append('-tolerate')
        for name, default in (('minCol', 1), ('minRow', 2), ('maxRow', 100)):
            cmd.append(f'-{name}={inputs.get(name, default)}')
        if cls._factor_enabled(inputs) == 'yes':
            cmd.append('-factor')
            cmd.append(f"-minFactor={inputs.get('minFactor', 5)}")
        elif str(inputs.get('minScore', '')) != '':
            cmd.append(f"-minScore={inputs.get('minScore')}")
        if inputs.get('reject'):
            cmd.append(f'-reject={cls._reject_path(inputs)}')
        if str(inputs.get('needComp', '')) != '':
            cmd.append(f"-needComp={inputs.get('needComp')}")
        if inputs.get('overlap'):
            cmd.append('-overlap')
        if str(inputs.get('componentFilter', '')) != '':
            cmd.append(f"-componentFilter={inputs.get('componentFilter')}")
        if str(inputs.get('speciesFilter', '')) != '':
            cmd.append(f"-speciesFilter={inputs.get('speciesFilter')}")
        cmd.append(str(inputs.get('input_maf', '')))
        return f'{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'output.maf']
        if inputs.get('reject', False):
            outputs.append(out / 'rejected.maf')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_maf', '')).strip():
            return 'input_maf is required'
        for name, minimum in (('minCol', 1), ('minRow', 1), ('maxRow', 1)):
            value = inputs.get(name, '')
            if str(value) != '' and int(value) < minimum:
                return f'{name} must be greater than or equal to {minimum}'
        factor_enabled = cls._factor_enabled(inputs)
        if factor_enabled not in cls.FACTOR_OPTIONS:
            return f"factor_enabled must be one of: {', '.join(cls.FACTOR_OPTIONS)}"
        if factor_enabled == 'yes':
            if str(inputs.get('minFactor', '')) != '' and int(inputs.get('minFactor')) < 0:
                return 'minFactor must be greater than or equal to 0'
            if str(inputs.get('minScore', '')) != '':
                return 'minScore cannot be used when factor_enabled is yes'
        if str(inputs.get('minScore', '')) != '' and float(inputs.get('minScore')) < 0:
            return 'minScore must be greater than or equal to 0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_maf': ('FILE', {'description': 'UCSC MAF multiple-alignment file to filter'})}, 'optional': {'tolerate': ('BOOLEAN', {'default': False, 'description': 'Ignore bad input instead of aborting'}), 'minCol': ('INT', {'default': 1, 'min': 1, 'description': 'Filter out blocks with fewer columns'}), 'minRow': ('INT', {'default': 2, 'min': 1, 'description': 'Filter out blocks with fewer rows'}), 'maxRow': ('INT', {'default': 100, 'min': 1, 'description': 'Filter out blocks with at least this many rows'}), 'factor_enabled': ('STRING', {'default': 'no', 'options': cls.FACTOR_OPTIONS, 'description': 'Enable factor-based score filtering instead of minimum score filtering'}), 'minFactor': ('INT', {'default': 5, 'min': 0, 'description': 'Factor used with factor-based score filtering'}), 'minScore': ('FLOAT', {'default': '', 'min': 0, 'description': 'Minimum allowed MAF block score'}), 'reject': ('BOOLEAN', {'default': False, 'description': 'Write rejected MAF blocks to a second output'}), 'needComp': ('STRING', {'default': '', 'description': 'Require this species component in every alignment block'}), 'overlap': ('BOOLEAN', {'default': False, 'description': 'Reject overlapping reference blocks in ordered input'}), 'componentFilter': ('FILE', {'description': 'File listing components required for a block to pass'}), 'speciesFilter': ('FILE', {'description': 'File listing species required for a block to pass'})}, 'hidden': {'output': ('STRING', {})}}


class UcscMafFetchNode(CommandNode):
    """Fetch UCSC MAF records overlapping BED intervals."""
    NODE_ID = 'ucsc_maffetch'
    DISPLAY_NAME = 'mafFetch'
    REQUIRED_CONDA_PACKAGES = ['ucsc-maffetch']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Fetch UCSC MAF records overlapping BED regions from an indexed UCSC table.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_mafFetch', 'ucsc_maffetch', 'mafFetch', 'MAF indexed lookup', 'multiple alignment format', 'BED overlap', 'UCSC MAF table']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['mafFetch']
    DOCUMENTATION_URL = 'https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/mouseStuff/mafFetch/mafFetch.c'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out.maf'

    @classmethod
    def _ucsc_db_connection(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('ucsc_db_connection', 'ucsc_db_connection.conf') or 'ucsc_db_connection.conf')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        setup = f'cp {shlex.quote(cls._ucsc_db_connection(inputs))} ${{HOME}}/.hg.conf && chmod 600 ${{HOME}}/.hg.conf'
        cmd = ['mafFetch', str(inputs.get('genome', '')), str(inputs.get('track', '')), str(inputs.get('bed_file', '')), cls._output_path(inputs)]
        return f'{setup} && {_shell_join(cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out.maf']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ('bed_file', 'genome', 'track'):
            if not str(inputs.get(name, '')).strip():
                return f'{name} is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bed_file': ('BED', {'description': 'BED6 or BED12 intervals used to fetch overlapping MAF records'}), 'genome': ('STRING', {'description': 'UCSC genome database name'}), 'track': ('STRING', {'description': 'UCSC MAF table name, such as multiz46way'})}, 'optional': {'ucsc_db_connection': ('FILE', {'description': 'UCSC database connection configuration copied to ~/.hg.conf'})}, 'hidden': {'output': ('STRING', {})}}


class UcscMafAddIRowsNode(CommandNode):
    """Add i rows to UCSC MAF alignments."""
    NODE_ID = 'ucsc_mafaddirows'
    DISPLAY_NAME = 'mafAddIRows'
    REQUIRED_CONDA_PACKAGES = ['ucsc-mafaddirows']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Add UCSC MAF i rows or N/dash sequence rows using a twoBit reference.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_mafAddIRows', 'ucsc_mafaddirows', 'mafAddIRows', 'MAF i rows', 'multiple alignment format', 'twoBit reference', 'N BED files']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('output_maf',)
    REQUIRED_EXECUTABLES = ['mafAddIRows']
    DOCUMENTATION_URL = 'https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/ratStuff/mafAddIRows/mafAddIRows.c'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output.maf'

    @classmethod
    def _nbed_links(cls, inputs: dict[str, Any]) -> list[str]:
        commands = []
        for bed in _as_list(inputs.get('nBeds')):
            identifier = _safe_label(Path(bed).name)
            commands.append(_shell_join(['ln', '-s', bed, identifier]))
            commands.append(f'echo {shlex.quote(identifier)} >> bed.txt')
        return commands

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['mafAddIRows', str(inputs.get('input_maf', '')), str(inputs.get('twoBitFile', '')), cls._output_path(inputs)]
        if _as_list(inputs.get('nBeds')):
            cmd.append('-nBeds=bed.txt')
        if inputs.get('addN'):
            cmd.append('-addN')
        if inputs.get('addDash'):
            cmd.append('-addDash')
        parts = cls._nbed_links(inputs) + [_shell_join(cmd)]
        return ' && '.join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output.maf']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_maf', '')).strip():
            return 'input_maf is required'
        if not str(inputs.get('twoBitFile', '')).strip():
            return 'twoBitFile is required'
        if inputs.get('addN') and inputs.get('addDash'):
            return 'addN and addDash cannot both be enabled'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_maf': ('FILE', {'description': 'MAF file with a single target sequence'}), 'twoBitFile': ('FILE', {'description': 'twoBit reference genome file'})}, 'optional': {'nBeds': ('BED', {'multiple': True, 'default': [], 'description': 'BED files, one per species, containing N locations'}), 'addN': ('BOOLEAN', {'default': False, 'description': 'Add rows of Ns into MAF blocks'}), 'addDash': ('BOOLEAN', {'default': False, 'description': 'Add rows of dashes into MAF blocks'})}, 'hidden': {'output': ('STRING', {})}}


class UcscMafFragNode(CommandNode):
    """Extract one UCSC MAF alignment region from a database track."""
    NODE_ID = 'ucsc_maffrag'
    DISPLAY_NAME = 'mafFrag'
    REQUIRED_CONDA_PACKAGES = ['ucsc-maffrag']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Extract UCSC MAF sequences for one genomic region from a database track.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_mafFrag', 'ucsc_maffrag', 'mafFrag', 'MAF region extract', 'multiple alignment format', 'UCSC MAF track', 'single region']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['mafFrag']
    DOCUMENTATION_URL = 'https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/ratStuff/mafFrag/mafFrag.c'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    SHELL = True
    STRAND_OPTIONS = ['.', '+', '-']

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out.maf'

    @classmethod
    def _strand(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('strand', '.') or '.')

    @classmethod
    def _ucsc_db_connection(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('ucsc_db_connection', 'ucsc_db_connection.conf') or 'ucsc_db_connection.conf')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        setup = f'cp {shlex.quote(cls._ucsc_db_connection(inputs))} ${{HOME}}/.hg.conf && chmod 600 ${{HOME}}/.hg.conf'
        cmd = ['mafFrag', str(inputs.get('genome', '')), str(inputs.get('track', '')), str(inputs.get('chrom', '')), str(inputs.get('start', '')), str(inputs.get('end', '')), cls._strand(inputs), cls._output_path(inputs)]
        if str(inputs.get('outName', '')) != '':
            cmd.append(f"-outName={inputs.get('outName')}")
        return f'{setup} && {_shell_join(cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out.maf']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ('genome', 'track', 'chrom'):
            if not str(inputs.get(name, '')).strip():
                return f'{name} is required'
        if str(inputs.get('start', '')) == '':
            return 'start is required'
        if str(inputs.get('end', '')) == '':
            return 'end is required'
        strand = cls._strand(inputs)
        if strand not in cls.STRAND_OPTIONS:
            return f"strand must be one of: {', '.join(cls.STRAND_OPTIONS)}"
        try:
            start = int(inputs.get('start'))
        except (TypeError, ValueError):
            return 'start must be an integer'
        try:
            end = int(inputs.get('end'))
        except (TypeError, ValueError):
            return 'end must be an integer'
        if start < 0:
            return 'start must be greater than or equal to 0'
        if end <= start:
            return 'end must be greater than start'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'genome': ('STRING', {'description': 'UCSC genome database name, such as hg19 or hg38'}), 'track': ('STRING', {'description': 'UCSC MAF table name, such as multiz46way'}), 'chrom': ('STRING', {'description': 'Chromosome or sequence name to extract'}), 'start': ('INT', {'min': 0, 'description': '0-based start coordinate'}), 'end': ('INT', {'min': 1, 'description': '0-based end coordinate'}), 'strand': ('STRING', {'default': '.', 'options': cls.STRAND_OPTIONS, 'description': 'Region strand: no strand, forward, or reverse'})}, 'optional': {'ucsc_db_connection': ('FILE', {'description': 'UCSC database connection configuration copied to ~/.hg.conf'}), 'outName': ('STRING', {'default': '', 'description': 'Override the database.chrom sequence name in the output MAF'})}, 'hidden': {'output': ('STRING', {})}}


class UcscMafFragsNode(CommandNode):
    """Extract UCSC MAF alignments for BED regions from a database track."""
    NODE_ID = 'ucsc_maffrags'
    DISPLAY_NAME = 'mafFrags'
    REQUIRED_CONDA_PACKAGES = ['ucsc-maffrags']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Extract UCSC MAF alignments for multiple BED regions from a database track.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_mafFrags', 'ucsc_maffrags', 'mafFrags', 'BED region MAF extraction', 'multiple alignment format', 'BED12 exons', 'UCSC MAF track']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['mafFrags']
    DOCUMENTATION_URL = 'https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/ratStuff/mafFrags/mafFrags.c'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out.maf'

    @classmethod
    def _ucsc_db_connection(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('ucsc_db_connection', 'ucsc_db_connection.conf') or 'ucsc_db_connection.conf')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        setup = f'cp {shlex.quote(cls._ucsc_db_connection(inputs))} ${{HOME}}/.hg.conf && chmod 600 ${{HOME}}/.hg.conf'
        cmd = ['mafFrags', str(inputs.get('genome', '')), str(inputs.get('track', '')), str(inputs.get('bed_file', ''))]
        for flag in ('bed12', 'thickOnly', 'meFirst', 'txStarts', 'refCoords'):
            if inputs.get(flag):
                cmd.append(f'-{flag}')
        if str(inputs.get('orgs', '')) != '':
            cmd.append(f"-orgs={inputs.get('orgs')}")
        cmd.append(cls._output_path(inputs))
        return f'{setup} && {_shell_join(cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out.maf']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ('bed_file', 'genome', 'track'):
            if not str(inputs.get(name, '')).strip():
                return f'{name} is required'
        if inputs.get('bed12') and (inputs.get('txStarts') or inputs.get('refCoords')):
            return 'bed12 cannot be combined with txStarts or refCoords'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bed_file': ('BED', {'description': 'BED6 or BED12 regions to extract from the UCSC MAF track'}), 'genome': ('STRING', {'description': 'UCSC genome database name, such as hg19 or hg38'}), 'track': ('STRING', {'description': 'UCSC MAF table name, such as multiz46way'})}, 'optional': {'bed12': ('BOOLEAN', {'default': False, 'description': 'Treat the input BED as BED12 exon blocks'}), 'thickOnly': ('BOOLEAN', {'default': False, 'description': 'When using BED12, extract only thickStart to thickEnd regions'}), 'meFirst': ('BOOLEAN', {'default': False, 'description': 'Place the reference genome sequence first in each MAF block'}), 'txStarts': ('BOOLEAN', {'default': False, 'description': 'Add txstart r-lines using BED names and reference coordinates'}), 'refCoords': ('BOOLEAN', {'default': False, 'description': 'Use actual reference genome coordinates in the output MAF'}), 'orgs': ('TXT', {'description': 'Optional organism order file used with the UCSC -orgs option'}), 'ucsc_db_connection': ('FILE', {'description': 'UCSC database connection configuration copied to ~/.hg.conf'})}, 'hidden': {'output': ('STRING', {})}}


class UcscMafGeneNode(CommandNode):
    """Extract FASTA gene alignments from UCSC MAF and genePred inputs."""
    NODE_ID = 'ucsc_mafgene'
    DISPLAY_NAME = 'mafGene'
    REQUIRED_CONDA_PACKAGES = ['ucsc-mafgene']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Extract FASTA protein or nucleotide alignments from UCSC MAF and genePred inputs.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_mafGene', 'ucsc_mafgene', 'mafGene', 'genePred protein alignments', 'multiple alignment format', 'species list', 'UTR alignment']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['mafGene']
    DOCUMENTATION_URL = 'https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/ratStuff/mafGene/mafGene.c'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '490+galaxy0'
    SHELL = True
    SELECTION_TYPES = ['all', 'single', 'list', 'bed', 'chrom']

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output.fasta'

    @classmethod
    def _selection_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('selection_type', 'all') or 'all')

    @classmethod
    def _ucsc_db_connection(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('ucsc_db_connection', 'ucsc_db_connection.conf') or 'ucsc_db_connection.conf')

    @staticmethod
    def _linked_name(path_value: Any) -> str:
        return _safe_label(Path(str(path_value)).name)

    @classmethod
    def _should_use_file(cls, inputs: dict[str, Any], genepred_name: str) -> bool:
        return bool(inputs.get('useFile')) or genepred_name.endswith('.gp')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        maf_name = cls._linked_name(inputs.get('maf_file', ''))
        genepred_name = cls._linked_name(inputs.get('genepred_file', ''))
        setup = [f'cp {shlex.quote(cls._ucsc_db_connection(inputs))} ${{HOME}}/.hg.conf', 'chmod 600 ${HOME}/.hg.conf', _shell_join(['ln', '-s', str(inputs.get('twoBitFile', '')), 'input.2bit']), _shell_join(['ln', '-s', str(inputs.get('maf_file', '')), maf_name]), _shell_join(['ln', '-s', str(inputs.get('genepred_file', '')), genepred_name])]
        cmd = ['mafGene', '-twoBit=input.2bit', str(inputs.get('db_name', '')), maf_name, genepred_name, str(inputs.get('species_list', '')), cls._output_path(inputs)]
        selection_type = cls._selection_type(inputs)
        if selection_type == 'single':
            cmd.append(f"-geneName={inputs.get('gene_name')}")
        elif selection_type == 'list':
            cmd.append(f"-geneList={inputs.get('gene_list')}")
        elif selection_type == 'bed':
            cmd.append(f"-geneBeds={inputs.get('gene_beds')}")
        elif selection_type == 'chrom':
            cmd.append(f"-chrom={inputs.get('chrom')}")
        for flag in ('exons', 'noTrans', 'uniqAA', 'includeUtr', 'noDash'):
            if inputs.get(flag):
                cmd.append(f'-{flag}')
        if cls._should_use_file(inputs, genepred_name):
            cmd.append('-useFile')
        if str(inputs.get('delay', '')) != '':
            cmd.append(f"-delay={inputs.get('delay')}")
        return ' && '.join(setup + [_shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output.fasta']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ('twoBitFile', 'db_name', 'maf_file', 'genepred_file', 'species_list'):
            if not str(inputs.get(name, '')).strip():
                return f'{name} is required'
        selection_type = cls._selection_type(inputs)
        if selection_type not in cls.SELECTION_TYPES:
            return f"selection_type must be one of: {', '.join(cls.SELECTION_TYPES)}"
        required_for_mode = {'single': 'gene_name', 'list': 'gene_list', 'bed': 'gene_beds', 'chrom': 'chrom'}
        required_name = required_for_mode.get(selection_type)
        if required_name and (not str(inputs.get(required_name, '')).strip()):
            return f'{required_name} is required when selection_type is {selection_type}'
        if inputs.get('includeUtr') and (not inputs.get('noTrans')):
            return 'includeUtr requires noTrans'
        delay = inputs.get('delay', '')
        if str(delay) != '':
            try:
                delay_value = int(delay)
            except (TypeError, ValueError):
                return 'delay must be an integer'
            if delay_value < 0:
                return 'delay must be greater than or equal to 0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'twoBitFile': ('FILE', {'description': 'twoBit reference genome used to fill alignment gaps'}), 'db_name': ('STRING', {'description': 'UCSC genome database name, such as hg38 or sacCer3'}), 'maf_file': ('FILE', {'description': 'MAF, bigMaf, or UCSC MAF table to extract alignments from'}), 'genepred_file': ('FILE', {'description': 'genePred table or .gp file containing gene predictions'}), 'species_list': ('STRING', {'description': 'Species list file with one species name per line'})}, 'optional': {'selection_type': ('STRING', {'default': 'all', 'options': cls.SELECTION_TYPES, 'description': 'Select all genes, one gene, a gene list, BED-defined genes, or one chromosome'}), 'gene_name': ('STRING', {'default': '', 'description': 'Gene name used when selection_type is single'}), 'gene_list': ('STRING', {'default': '', 'description': 'File containing gene names used when selection_type is list'}), 'gene_beds': ('BED', {'description': 'BED4 file of genes used when selection_type is bed'}), 'chrom': ('STRING', {'default': '', 'description': 'Chromosome name used when selection_type is chrom'}), 'exons': ('BOOLEAN', {'default': False, 'description': 'Output exon alignments instead of full genes'}), 'noTrans': ('BOOLEAN', {'default': False, 'description': 'Keep nucleotide alignments instead of translating to amino acids'}), 'uniqAA': ('BOOLEAN', {'default': False, 'description': 'Emit a unique pseudo-amino-acid code for every codon'}), 'includeUtr': ('BOOLEAN', {'default': False, 'description': 'Include untranslated regions; requires noTrans'}), 'noDash': ('BOOLEAN', {'default': False, 'description': 'Skip output rows containing only dashes'}), 'useFile': ('BOOLEAN', {'default': False, 'description': 'Treat the genePred input as a file instead of a database table'}), 'delay': ('INT', {'default': '', 'min': 0, 'description': 'Optional delay in seconds between genes'}), 'ucsc_db_connection': ('FILE', {'description': 'UCSC database connection configuration copied to ~/.hg.conf'})}, 'hidden': {'output': ('STRING', {})}}


class UcscMafCoverageNode(CommandNode):
    """Measure genome coverage from UCSC MAF alignments."""
    NODE_ID = 'ucsc_mafcoverage'
    DISPLAY_NAME = 'mafCoverage'
    REQUIRED_CONDA_PACKAGES = ['ucsc-mafcoverage']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Analyse chromosome and genome-wide coverage from sorted UCSC MAF alignments.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_mafCoverage', 'ucsc_mafcoverage', 'mafCoverage', 'MAF coverage', 'multiple alignment format', 'genome-wide coverage', 'restricted coverage']
    RETURN_TYPES = ('TXT',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['mafCoverage']
    DOCUMENTATION_URL = 'https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/mouseStuff/mafCoverage/mafCoverage.c'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    SHELL = True
    RESTRICT_OPTIONS = ['no', 'yes']

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/coverage.txt'

    @classmethod
    def _restrict_select(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('restrict_select', 'no') or 'no')

    @classmethod
    def _ucsc_db_connection(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('ucsc_db_connection', 'ucsc_db_connection.conf') or 'ucsc_db_connection.conf')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        setup = f'cp {shlex.quote(cls._ucsc_db_connection(inputs))} ${{HOME}}/.hg.conf && chmod 600 ${{HOME}}/.hg.conf'
        cmd = ['mafCoverage', str(inputs.get('genome', '')), str(inputs.get('maf_file', ''))]
        if cls._restrict_select(inputs) == 'yes':
            cmd.append(f"-restrict={inputs.get('restrict_bed', '')}")
        if str(inputs.get('count', '')) != '':
            cmd.append(f"-count={inputs.get('count')}")
        return f'{setup} && {_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'coverage.txt']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('maf_file', '')).strip():
            return 'maf_file is required'
        if not str(inputs.get('genome', '')).strip():
            return 'genome is required'
        restrict_select = cls._restrict_select(inputs)
        if restrict_select not in cls.RESTRICT_OPTIONS:
            return f"restrict_select must be one of: {', '.join(cls.RESTRICT_OPTIONS)}"
        if restrict_select == 'yes' and (not str(inputs.get('restrict_bed', '')).strip()):
            return 'restrict_bed is required when restrict_select is yes'
        count = inputs.get('count', '')
        if str(count) != '':
            try:
                count_value = int(count)
            except (TypeError, ValueError):
                return 'count must be an integer'
            if count_value < 1:
                return 'count must be greater than or equal to 1'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'maf_file': ('FILE', {'description': 'Sorted UCSC MAF alignment file'}), 'genome': ('STRING', {'description': 'UCSC genome database name'})}, 'optional': {'restrict_select': ('STRING', {'default': 'no', 'options': cls.RESTRICT_OPTIONS, 'description': 'Restrict coverage calculation to regions in a BED file'}), 'restrict_bed': ('BED', {'description': 'BED intervals used when restricted coverage is enabled'}), 'count': ('INT', {'default': '', 'min': 1, 'description': 'Threshold for bases covered by at least this many species'}), 'ucsc_db_connection': ('FILE', {'description': 'UCSC database connection configuration copied to ~/.hg.conf'})}, 'hidden': {'output': ('STRING', {})}}


class UcscChainAntiRepeatNode(CommandNode):
    """Remove repeat-dominated UCSC chains."""
    NODE_ID = 'ucsc_chainantirepeat'
    DISPLAY_NAME = 'chainAntiRepeat'
    REQUIRED_CONDA_PACKAGES = ['ucsc-chainantirepeat']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Remove UCSC chains that primarily represent repeats or degenerate DNA.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_chainantirepeat', 'chainAntiRepeat', 'UCSC chain', 'twoBit', 'repeat chains', 'degenerate DNA']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('out',)
    REQUIRED_EXECUTABLES = ['chainAntiRepeat']
    DOCUMENTATION_URL = 'https://genome.ucsc.edu/goldenPath/help/chain.html'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out.chain'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['chainAntiRepeat', str(inputs.get('in_target', '')), str(inputs.get('in_query', '')), str(inputs.get('in_chain', '')), cls._output_path(inputs)]
        if str(inputs.get('minScore', '')) != '':
            cmd.append(f"-minScore={inputs.get('minScore')}")
        if str(inputs.get('noCheckScore', '')) != '':
            cmd.append(f"-noCheckScore={inputs.get('noCheckScore')}")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out.chain']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ('in_target', 'in_query', 'in_chain'):
            if not str(inputs.get(name, '')).strip():
                return f'{name} is required'
        for name in ('minScore', 'noCheckScore'):
            value = inputs.get(name, '')
            if str(value) != '' and int(value) < 0:
                return f'{name} must be greater than or equal to 0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_target': ('FILE', {'description': 'TwoBit file containing the target sequence'}), 'in_query': ('FILE', {'description': 'TwoBit file containing the query sequence'}), 'in_chain': ('FILE', {'description': 'UCSC chain file to filter'})}, 'optional': {'minScore': ('INT', {'default': '', 'min': 0, 'description': 'Minimum post-repeat score required to pass'}), 'noCheckScore': ('INT', {'default': '', 'min': 0, 'description': 'Score threshold that passes chains without repeat checks'})}, 'hidden': {'output': ('STRING', {})}}
