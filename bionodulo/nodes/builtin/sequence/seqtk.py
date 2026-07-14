"""seqtk — sequence node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class SeqTKCompNode(CommandNode):
    """Report nucleotide composition for FASTA/Q records with seqtk comp."""
    NODE_ID = 'seqtk_comp'
    DISPLAY_NAME = 'SeqTK Composition'
    REQUIRED_CONDA_PACKAGES = ['seqtk', 'gawk']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Report per-record nucleotide composition for FASTA or FASTQ data with seqtk comp.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqtk', 'seqtk comp', 'SeqTK comp', 'nucleotide composition', 'FASTA composition', 'FASTQ composition', 'base composition']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('composition',)
    REQUIRED_EXECUTABLES = ['seqtk', 'awk']
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = '1.5+galaxy0'
    SHELL = True
    HEADER = '#chr\\tlength\\t#A\\t#C\\t#G\\t#T\\t#2\\t#3\\t#4\\t#CpG\\t#tv\\t#ts\\t#CpG-ts'

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/composition.tsv'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['seqtk', 'comp']
        _add_if_value(cmd, '-r', inputs.get('in_bed'))
        cmd.append(str(inputs.get('in_file', '')))
        return f'''{_shell_join(cmd)} | awk 'BEGIN{{print "{cls.HEADER}"}}1' > {shlex.quote(cls._out_path(inputs))}'''

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'composition.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('FASTQ_LIST', {'description': 'Input FASTA/Q file, optionally gzip-compressed'})}, 'optional': {'in_bed': ('BED', {'default': '', 'description': 'Restrict composition to regions from this BED file'})}, 'hidden': {'output': ('STRING', {})}}


class SeqTKCutNNode(CommandNode):
    """Split FASTA/Q records at long N tracts with seqtk cutN."""
    NODE_ID = 'seqtk_cutN'
    DISPLAY_NAME = 'SeqTK CutN'
    REQUIRED_CONDA_PACKAGES = ['seqtk', 'pigz']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Split FASTA or FASTQ records at long N tracts with seqtk cutN.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqtk', 'seqtk cutN', 'SeqTK cutN', 'seqtk split at N', 'split at N', 'long N tracts', 'assembly gaps', 'gaps BED']
    RETURN_TYPES = ('FASTA', 'FASTQ', 'BED')
    RETURN_NAMES = ('split_sequences', 'split_reads', 'gaps_bed')
    REQUIRED_EXECUTABLES = ['seqtk', 'pigz']
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = '1.5+galaxy0'
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get('input_ext', '') or '').strip().lstrip('.')
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get('in_file', ''))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == '.gz':
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip('.')
        return 'fasta'

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        if inputs.get('g'):
            return 'gaps.bed'
        ext = cls._input_ext(inputs)
        if ext in {'fa', 'fna'}:
            ext = 'fasta'
        elif ext in {'fq', 'fastqsanger'}:
            ext = 'fastq'
        elif ext in {'fa.gz', 'fna.gz'}:
            ext = 'fasta.gz'
        elif ext in {'fq.gz', 'fastqsanger.gz'}:
            ext = 'fastq.gz'
        return f'cutN.{ext}'

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._output_name(inputs)}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['seqtk', 'cutN', '-n', str(inputs.get('n', 1000)), '-p', str(inputs.get('p', 10))]
        if inputs.get('g'):
            cmd.append('-g')
        cmd.append(str(inputs.get('in_file', '')))
        if not inputs.get('g') and cls._input_ext(inputs).endswith('.gz'):
            return f'{_shell_join(cmd)} | pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time > {shlex.quote(cls._out_path(inputs))}'
        return f'{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('FASTQ_LIST', {'description': 'Input FASTA/Q file, optionally gzip-compressed'})}, 'optional': {'n': ('INT', {'default': 1000, 'min': 1, 'description': 'Minimum size of N tract'}), 'p': ('INT', {'default': 10, 'min': 0, 'description': 'Penalty for a non-N base'}), 'g': ('BOOLEAN', {'default': False, 'description': 'Print gaps only as BED instead of split sequence'}), 'input_ext': ('STRING', {'default': 'fasta', 'options': ['fasta', 'fastq', 'fasta.gz', 'fastq.gz'], 'description': 'Input/output sequence format used to mirror Galaxy format_source', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class SeqTKDropSENode(CommandNode):
    """Remove unpaired records from interleaved paired-end FASTA/Q with seqtk dropse."""
    NODE_ID = 'seqtk_dropse'
    DISPLAY_NAME = 'SeqTK DropSE'
    REQUIRED_CONDA_PACKAGES = ['seqtk', 'pigz']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Remove unpaired records from interleaved paired-end FASTA or FASTQ data with seqtk dropse.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqtk', 'seqtk dropse', 'SeqTK dropse', 'drop single-end', 'remove unpaired reads', 'interleaved paired-end', 'paired reads only']
    RETURN_TYPES = ('FASTA', 'FASTQ')
    RETURN_NAMES = ('paired_sequences', 'paired_reads')
    REQUIRED_EXECUTABLES = ['seqtk', 'pigz']
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = '1.5+galaxy0'
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        return SeqTKCutNNode._input_ext(inputs)

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = cls._input_ext(inputs)
        if ext in {'fa', 'fna'}:
            ext = 'fasta'
        elif ext in {'fq', 'fastqsanger'}:
            ext = 'fastq'
        elif ext in {'fa.gz', 'fna.gz'}:
            ext = 'fasta.gz'
        elif ext in {'fq.gz', 'fastqsanger.gz'}:
            ext = 'fastq.gz'
        return f'paired.{ext}'

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._output_name(inputs)}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['seqtk', 'dropse', str(inputs.get('in_file', ''))]
        if cls._input_ext(inputs).endswith('.gz'):
            return f'{_shell_join(cmd)} | pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time > {shlex.quote(cls._out_path(inputs))}'
        return f'{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('FASTQ_LIST', {'description': 'Interleaved paired-end FASTA/Q file'})}, 'optional': {'input_ext': ('STRING', {'default': 'fastq', 'options': ['fasta', 'fastq', 'fasta.gz', 'fastq.gz'], 'description': 'Input/output sequence format used to mirror Galaxy format_source', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class SeqTKHetyNode(CommandNode):
    """Report regional heterozygosity with seqtk hety."""
    NODE_ID = 'seqtk_hety'
    DISPLAY_NAME = 'SeqTK Heterozygosity'
    REQUIRED_CONDA_PACKAGES = ['seqtk', 'gawk']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Report regional heterozygosity across FASTA or FASTQ data with seqtk hety.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqtk', 'seqtk hety', 'SeqTK hety', 'regional heterozygosity', 'heterozygous regions', 'masked lowercase', 'FASTA heterozygosity']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('heterozygous_regions',)
    REQUIRED_EXECUTABLES = ['seqtk', 'awk']
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = '1.5+galaxy0'
    SHELL = True
    HEADER = '#chr\\tstart\\tend\\tA\\tB\\tnum_het'

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/heterozygous_regions.tsv'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['seqtk', 'hety', '-w', str(inputs.get('w', 50000)), '-t', str(inputs.get('t', 5))]
        if inputs.get('m'):
            cmd.append('-m')
        cmd.append(str(inputs.get('in_file', '')))
        return f'''{_shell_join(cmd)} | awk 'BEGIN{{print "{cls.HEADER}"}}1' > {shlex.quote(cls._out_path(inputs))}'''

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'heterozygous_regions.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('FASTQ_LIST', {'description': 'Input FASTA/Q file, optionally gzip-compressed'})}, 'optional': {'w': ('INT', {'default': 50000, 'min': 1, 'description': 'Window size'}), 't': ('INT', {'default': 5, 'min': 1, 'description': 'Number of start positions in a window'}), 'm': ('BOOLEAN', {'default': False, 'description': 'Treat lowercase bases as masked'})}, 'hidden': {'output': ('STRING', {})}}


class SeqTKListHetNode(CommandNode):
    """List heterozygous ambiguity-base positions with seqtk listhet."""
    NODE_ID = 'seqtk_listhet'
    DISPLAY_NAME = 'SeqTK List Heterozygous Bases'
    REQUIRED_CONDA_PACKAGES = ['seqtk', 'gawk']
    CATEGORY = 'sequence'
    DESCRIPTION = 'List positions of heterozygous IUPAC ambiguity bases in FASTA or FASTQ data.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqtk', 'seqtk listhet', 'SeqTK listhet', 'heterozygous bases', 'heterozygous positions', 'IUPAC ambiguity bases', 'ambiguous bases']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('heterozygous_bases',)
    REQUIRED_EXECUTABLES = ['seqtk', 'awk']
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = '1.5+galaxy0'
    SHELL = True
    HEADER = '#chr\\tposition\\tbase'

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/heterozygous_bases.tsv'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['seqtk', 'listhet', str(inputs.get('in_file', ''))]
        return f'''{_shell_join(cmd)} | awk 'BEGIN{{print "{cls.HEADER}"}}1' > {shlex.quote(cls._out_path(inputs))}'''

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'heterozygous_bases.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('FASTQ_LIST', {'description': 'Input FASTA/Q file, optionally gzip-compressed'})}, 'hidden': {'output': ('STRING', {})}}


class SeqTKMergeFANode(CommandNode):
    """Merge two FASTA/Q files into FASTA with seqtk mergefa."""
    NODE_ID = 'seqtk_mergefa'
    DISPLAY_NAME = 'SeqTK Merge FASTA'
    REQUIRED_CONDA_PACKAGES = ['seqtk', 'pigz']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Merge two FASTA or FASTQ files into FASTA using IUPAC ambiguity codes.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqtk', 'seqtk mergefa', 'SeqTK mergefa', 'merge FASTA', 'merge FASTQ', 'IUPAC ambiguity codes', 'random allele', 'suppress hets']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('merged_fasta',)
    REQUIRED_EXECUTABLES = ['seqtk', 'pigz']
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = '1.5+galaxy1'
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get('input_ext', '') or '').strip().lstrip('.')
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get('in_fa1', ''))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == '.gz':
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip('.')
        return 'fasta'

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        if cls._input_ext(inputs).endswith('.gz'):
            return 'merged.fasta.gz'
        return 'merged.fasta'

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._output_name(inputs)}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['seqtk', 'mergefa', '-q', str(inputs.get('q', 0))]
        for key, flag in (('i', '-i'), ('m', '-m'), ('r', '-r'), ('h', '-h')):
            if inputs.get(key):
                cmd.append(flag)
        cmd.extend([str(inputs.get('in_fa1', '')), str(inputs.get('in_fa2', ''))])
        if cls._input_ext(inputs).endswith('.gz'):
            return f'{_shell_join(cmd)} | pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time > {shlex.quote(cls._out_path(inputs))}'
        return f'{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_fa1': ('FASTQ_LIST', {'description': 'First input FASTA/Q file'}), 'in_fa2': ('FASTQ_LIST', {'description': 'Second input FASTA/Q file'})}, 'optional': {'q': ('INT', {'default': 0, 'min': 0, 'description': 'Quality threshold for FASTQ input'}), 'i': ('BOOLEAN', {'default': False, 'description': 'Take the intersection of records'}), 'm': ('BOOLEAN', {'default': False, 'description': 'Pick the least ambiguous base, masking conflicts and uncertainties'}), 'r': ('BOOLEAN', {'default': False, 'description': 'Pick a random allele from heterozygous bases'}), 'h': ('BOOLEAN', {'default': False, 'description': 'Suppress heterozygous bases in the input'}), 'input_ext': ('STRING', {'default': 'fasta', 'options': ['fasta', 'fastq', 'fasta.gz', 'fastq.gz'], 'description': 'First input format used to mirror Galaxy dynamic output metadata', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class SeqTKMergePENode(CommandNode):
    """Interleave paired FASTA/Q files with seqtk mergepe."""
    NODE_ID = 'seqtk_mergepe'
    DISPLAY_NAME = 'SeqTK Merge Paired-End'
    REQUIRED_CONDA_PACKAGES = ['seqtk', 'pigz']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Interleave two unpaired FASTA or FASTQ files into a paired-end FASTA/Q file.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqtk', 'seqtk mergepe', 'SeqTK mergepe', 'interleaved paired-end', 'paired-end interleave', 'merge paired reads', 'paired FASTQ']
    RETURN_TYPES = ('FASTQ',)
    RETURN_NAMES = ('interleaved_pairs',)
    REQUIRED_EXECUTABLES = ['seqtk', 'pigz']
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = '1.5+galaxy0'
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get('input_ext', '') or '').strip().lstrip('.')
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get('in_fq1', ''))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == '.gz':
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip('.')
        return 'fastq'

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = cls._input_ext(inputs)
        if ext in {'fa', 'fna'}:
            ext = 'fasta'
        elif ext in {'fq', 'fastqsanger'}:
            ext = 'fastq'
        elif ext in {'fa.gz', 'fna.gz'}:
            ext = 'fasta.gz'
        elif ext in {'fq.gz', 'fastqsanger.gz'}:
            ext = 'fastq.gz'
        return f'interleaved.{ext}'

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._output_name(inputs)}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['seqtk', 'mergepe', str(inputs.get('in_fq1', '')), str(inputs.get('in_fq2', ''))]
        if cls._input_ext(inputs).endswith('.gz'):
            return f'{_shell_join(cmd)} | pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time > {shlex.quote(cls._out_path(inputs))}'
        return f'{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_fq1': ('FASTQ_LIST', {'description': 'First unpaired FASTA/Q file'}), 'in_fq2': ('FASTQ_LIST', {'description': 'Second unpaired FASTA/Q file'})}, 'optional': {'input_ext': ('STRING', {'default': 'fastq', 'options': ['fasta', 'fastq', 'fasta.gz', 'fastq.gz'], 'description': 'First input format used to mirror Galaxy format_source metadata', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class SeqTKMutFANode(CommandNode):
    """Apply point mutations to FASTA/Q records with seqtk mutfa."""
    NODE_ID = 'seqtk_mutfa'
    DISPLAY_NAME = 'SeqTK Mutate FASTA'
    REQUIRED_CONDA_PACKAGES = ['seqtk', 'pigz']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Apply point mutations from a tabular SNP file to FASTA or FASTQ sequences.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqtk', 'seqtk mutfa', 'SeqTK mutfa', 'point mutations', 'SNP mutations', 'mutate FASTA', 'mutate FASTQ']
    RETURN_TYPES = ('FASTA', 'FASTQ')
    RETURN_NAMES = ('mutated_sequences', 'mutated_reads')
    REQUIRED_EXECUTABLES = ['seqtk', 'pigz']
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = '1.5+galaxy0'
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get('input_ext', '') or '').strip().lstrip('.')
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get('in_file', ''))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == '.gz':
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip('.')
        return 'fasta'

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = cls._input_ext(inputs)
        if ext in {'fa', 'fna'}:
            ext = 'fasta'
        elif ext in {'fq', 'fastqsanger'}:
            ext = 'fastq'
        elif ext in {'fa.gz', 'fna.gz'}:
            ext = 'fasta.gz'
        elif ext in {'fq.gz', 'fastqsanger.gz'}:
            ext = 'fastq.gz'
        return f'mutated.{ext}'

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._output_name(inputs)}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['seqtk', 'mutfa', str(inputs.get('in_file', '')), str(inputs.get('in_snp', ''))]
        if cls._input_ext(inputs).endswith('.gz'):
            return f'{_shell_join(cmd)} | pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time > {shlex.quote(cls._out_path(inputs))}'
        return f'{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('FASTQ_LIST', {'description': 'Input FASTA/Q file, optionally gzip-compressed'}), 'in_snp': ('TSV', {'description': 'SNP table with chromosome, 1-based position, placeholder, and replacement base columns'})}, 'optional': {'input_ext': ('STRING', {'default': 'fasta', 'options': ['fasta', 'fastq', 'fasta.gz', 'fastq.gz'], 'description': 'Input/output sequence format used to mirror Galaxy format_source metadata', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class SeqTKRandBaseNode(CommandNode):
    """Randomly resolve ambiguous bases with seqtk randbase."""
    NODE_ID = 'seqtk_randbase'
    DISPLAY_NAME = 'SeqTK Random Base'
    REQUIRED_CONDA_PACKAGES = ['seqtk', 'pigz']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Randomly resolve ambiguous IUPAC bases in FASTA or FASTQ sequences.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqtk', 'seqtk randbase', 'SeqTK randbase', 'ambiguous bases', 'IUPAC ambiguity', 'random base', 'resolve heterozygous bases']
    RETURN_TYPES = ('FASTA', 'FASTQ')
    RETURN_NAMES = ('unambiguous_sequences', 'unambiguous_reads')
    REQUIRED_EXECUTABLES = ['seqtk', 'pigz']
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = '1.5+galaxy0'
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get('input_ext', '') or '').strip().lstrip('.')
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get('in_file', ''))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == '.gz':
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip('.')
        return 'fasta'

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = cls._input_ext(inputs)
        if ext in {'fa', 'fna'}:
            ext = 'fasta'
        elif ext in {'fq', 'fastqsanger'}:
            ext = 'fastq'
        elif ext in {'fa.gz', 'fna.gz'}:
            ext = 'fasta.gz'
        elif ext in {'fq.gz', 'fastqsanger.gz'}:
            ext = 'fastq.gz'
        return f'unambiguous.{ext}'

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._output_name(inputs)}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['seqtk', 'randbase', str(inputs.get('in_file', ''))]
        if cls._input_ext(inputs).endswith('.gz'):
            return f'{_shell_join(cmd)} | pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time > {shlex.quote(cls._out_path(inputs))}'
        return f'{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('FASTQ_LIST', {'description': 'Input FASTA/Q file, optionally gzip-compressed'})}, 'optional': {'input_ext': ('STRING', {'default': 'fasta', 'options': ['fasta', 'fastq', 'fasta.gz', 'fastq.gz'], 'description': 'Input/output sequence format used to mirror Galaxy format_source metadata', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class SeqTKSampleNode(CommandNode):
    """Randomly subsample FASTA/Q records with seqtk sample."""
    NODE_ID = 'seqtk_sample'
    DISPLAY_NAME = 'SeqTK Sample'
    REQUIRED_CONDA_PACKAGES = ['seqtk', 'pigz']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Randomly subsample FASTA or FASTQ sequences with a reproducible seed.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqtk', 'seqtk sample', 'SeqTK sample', 'subsample reads', 'random subsample', 'FASTQ subsampling', 'RNG seed']
    RETURN_TYPES = ('FASTA', 'FASTQ')
    RETURN_NAMES = ('subsampled_sequences', 'subsampled_reads')
    REQUIRED_EXECUTABLES = ['seqtk', 'pigz']
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = '1.5+galaxy0'
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get('input_ext', '') or '').strip().lstrip('.')
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get('in_file', ''))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == '.gz':
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip('.')
        return 'fasta'

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = cls._input_ext(inputs)
        if ext in {'fa', 'fna'}:
            ext = 'fasta'
        elif ext in {'fq', 'fastqsanger'}:
            ext = 'fastq'
        elif ext in {'fa.gz', 'fna.gz'}:
            ext = 'fasta.gz'
        elif ext in {'fq.gz', 'fastqsanger.gz'}:
            ext = 'fastq.gz'
        return f'subsampled.{ext}'

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on'}
        return bool(value)

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._output_name(inputs)}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['seqtk', 'sample', '-s', str(inputs.get('s', 4))]
        if not cls._bool_value(inputs.get('single_pass_mode', False)):
            cmd.append('-2')
        cmd.extend([str(inputs.get('in_file', '')), str(inputs.get('subsample_size', 100))])
        if cls._input_ext(inputs).endswith('.gz'):
            return f'{_shell_join(cmd)} | pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time > {shlex.quote(cls._out_path(inputs))}'
        return f'{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('FASTQ_LIST', {'description': 'Input FASTA/Q file, optionally gzip-compressed'}), 'subsample_size': ('FLOAT', {'default': 100, 'description': 'Subsample size as an integer read count or decimal fraction'})}, 'optional': {'s': ('INT', {'default': 4, 'description': 'Random number generator seed'}), 'single_pass_mode': ('BOOLEAN', {'default': False, 'description': 'Enable one-pass mode; default two-pass mode emits -2 for lower memory use', 'advanced': True}), 'input_ext': ('STRING', {'default': 'fasta', 'options': ['fasta', 'fastq', 'fasta.gz', 'fastq.gz'], 'description': 'Input/output sequence format used to mirror Galaxy format_source metadata', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class SeqTKSeqNode(CommandNode):
    """Transform FASTA/Q records with seqtk seq."""
    NODE_ID = 'seqtk_seq'
    DISPLAY_NAME = 'SeqTK Seq'
    REQUIRED_CONDA_PACKAGES = ['seqtk', 'pigz']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Transform FASTA or FASTQ sequences with seqtk seq.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqtk', 'seqtk seq', 'SeqTK seq', 'reverse complement', 'force FASTA', 'quality masking', 'mask regions', 'drop ambiguous bases', 'sample fraction']
    RETURN_TYPES = ('FASTA', 'FASTQ')
    RETURN_NAMES = ('transformed_sequences', 'transformed_reads')
    REQUIRED_EXECUTABLES = ['seqtk', 'pigz']
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = '1.5+galaxy1'
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get('input_ext', '') or '').strip().lstrip('.')
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get('in_file', ''))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == '.gz':
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip('.')
        return 'fasta'

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on'}
        return bool(value)

    @classmethod
    def _normalized_output_ext(cls, inputs: dict[str, Any]) -> str:
        ext = cls._input_ext(inputs)
        if cls._bool_value(inputs.get('A', False)):
            return 'fasta.gz' if ext in {'fasta.gz', 'fastq.gz'} else 'fasta'
        if ext in {'fa', 'fna'}:
            return 'fasta'
        if ext in {'fq', 'fastqsanger', 'fastqillumina'}:
            return 'fastq'
        if ext in {'fa.gz', 'fna.gz'}:
            return 'fasta.gz'
        if ext in {'fq.gz', 'fastqsanger.gz', 'fastqillumina.gz'}:
            return 'fastq.gz'
        return ext or 'fasta'

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return f'transformed.{cls._normalized_output_ext(inputs)}'

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._output_name(inputs)}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['seqtk', 'seq', '-q', str(inputs.get('q', 0)), '-X', str(inputs.get('X', 255))]
        _add_if_value(cmd, '-n', inputs.get('n'))
        cmd.extend(['-l', str(inputs.get('l', 0)), '-Q', str(inputs.get('Q', 33)), '-s', str(inputs.get('s', 11)), '-f', str(inputs.get('f', 1))])
        _add_if_value(cmd, '-M', inputs.get('M'))
        cmd.extend(['-L', str(inputs.get('L', 0))])
        if cls._bool_value(inputs.get('c', False)):
            cmd.append('-c')
        direction = str(inputs.get('direction', 'forward') or 'forward')
        if direction != 'forward':
            cmd.append(direction)
        for key, flag in (('A', '-A'), ('C', '-C'), ('N', '-N'), ('x1', '-1'), ('x2', '-2')):
            if cls._bool_value(inputs.get(key, False)):
                cmd.append(flag)
        if cls._input_ext(inputs) == 'fastqillumina' or cls._bool_value(inputs.get('fastqillumina', False)):
            cmd.append('-V')
        cmd.append(str(inputs.get('in_file', '')))
        if cls._normalized_output_ext(inputs).endswith('.gz'):
            return f'{_shell_join(cmd)} | pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time > {shlex.quote(cls._out_path(inputs))}'
        return f'{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('FASTQ_LIST', {'description': 'Input FASTA/Q file, optionally gzip-compressed'})}, 'optional': {'q': ('INT', {'default': 0, 'description': 'Mask bases with quality lower than this value'}), 'X': ('INT', {'default': 255, 'description': 'Mask bases with quality higher than this value'}), 'n': ('STRING', {'default': '', 'description': 'Convert masked bases to this character; blank leaves lowercase masking'}), 'l': ('INT', {'default': 0, 'description': 'Number of residues per line; 0 keeps seqtk default'}), 'Q': ('INT', {'default': 33, 'description': 'ASCII quality offset used for quality comparisons'}), 's': ('INT', {'default': 11, 'description': 'Random seed used with sample fraction'}), 'f': ('FLOAT', {'default': 1, 'description': 'Sample fraction of sequences'}), 'M': ('FILE', {'default': '', 'description': 'BED or name-list file of regions to mask'}), 'L': ('INT', {'default': 0, 'description': 'Drop sequences shorter than this length'}), 'c': ('BOOLEAN', {'default': False, 'description': 'Mask complement regions when a mask file is supplied'}), 'direction': ('STRING', {'default': 'forward', 'options': ['forward', '-r', '-R'], 'description': 'Output forward, reverse complement, or both directions'}), 'A': ('BOOLEAN', {'default': False, 'description': 'Force FASTA output and discard qualities'}), 'C': ('BOOLEAN', {'default': False, 'description': 'Drop comments from header lines'}), 'N': ('BOOLEAN', {'default': False, 'description': 'Drop sequences containing ambiguous bases'}), 'x1': ('BOOLEAN', {'default': False, 'description': 'Output only 2n-1 reads'}), 'x2': ('BOOLEAN', {'default': False, 'description': 'Output only 2n reads'}), 'fastqillumina': ('BOOLEAN', {'default': False, 'description': 'Apply the Galaxy fastqillumina quality-shift flag (-V)', 'advanced': True}), 'input_ext': ('STRING', {'default': 'fasta', 'options': ['fasta', 'fastq', 'fasta.gz', 'fastq.gz', 'fastqillumina'], 'description': 'Input/output sequence format used to mirror Galaxy dynamic output metadata', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class SeqTKSubseqNode(CommandNode):
    """Extract selected FASTA/Q records with seqtk subseq."""
    NODE_ID = 'seqtk_subseq'
    DISPLAY_NAME = 'SeqTK Subsequence'
    REQUIRED_CONDA_PACKAGES = ['seqtk', 'gawk', 'pigz']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Extract selected FASTA or FASTQ records by BED regions or sequence IDs.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqtk', 'seqtk subseq', 'SeqTK subseq', 'extract subsequences', 'BED regions', 'sequence ID list', 'FASTA IDs', 'selected sequences']
    RETURN_TYPES = ('FASTA', 'FASTQ', 'TSV')
    RETURN_NAMES = ('selected_sequences', 'selected_reads', 'selected_table')
    REQUIRED_EXECUTABLES = ['seqtk', 'awk', 'pigz']
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = '1.5+galaxy0'
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get('input_ext', '') or '').strip().lstrip('.')
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get('in_file', ''))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == '.gz':
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip('.')
        return 'fasta'

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on', '-t'}
        return bool(value)

    @classmethod
    def _output_ext(cls, inputs: dict[str, Any]) -> str:
        if cls._bool_value(inputs.get('t', False)):
            return 'tsv'
        ext = cls._input_ext(inputs)
        if ext in {'fa', 'fna'}:
            return 'fasta'
        if ext in {'fq', 'fastqsanger'}:
            return 'fastq'
        if ext in {'fa.gz', 'fna.gz'}:
            return 'fasta.gz'
        if ext in {'fq.gz', 'fastqsanger.gz'}:
            return 'fastq.gz'
        return ext or 'fasta'

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return f'selected.{cls._output_ext(inputs)}'

    @classmethod
    def _source_path(cls, inputs: dict[str, Any]) -> str:
        source_type = str(inputs.get('source_type', 'bed') or 'bed')
        if source_type == 'bed':
            return str(inputs.get('in_bed', ''))
        return str(inputs.get('name_list', ''))

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._output_name(inputs)}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['seqtk', 'subseq']
        if cls._bool_value(inputs.get('t', False)):
            cmd.append('-t')
        cmd.extend(['-l', str(inputs.get('l', 0)), str(inputs.get('in_file', '')), cls._source_path(inputs)])
        command = _shell_join(cmd)
        if cls._bool_value(inputs.get('t', False)):
            return f"""{command} | awk 'BEGIN{{print "chr\\tunknown\\tseq"}}1' > {shlex.quote(cls._out_path(inputs))}"""
        if cls._output_ext(inputs).endswith('.gz'):
            return f'{command} | pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time > {shlex.quote(cls._out_path(inputs))}'
        return f'{command} > {shlex.quote(cls._out_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base = super().VALIDATE_INPUTS(inputs)
        if base is not True:
            return base
        source_type = str(inputs.get('source_type', 'bed') or 'bed')
        if source_type not in {'bed', 'name'}:
            return f'Unsupported source_type: {source_type}'
        if source_type == 'bed' and (not str(inputs.get('in_bed', '')).strip()):
            return "in_bed is required when source_type is 'bed'"
        if source_type == 'name' and (not str(inputs.get('name_list', '')).strip()):
            return "name_list is required when source_type is 'name'"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('FASTQ_LIST', {'description': 'Input FASTA/Q file, optionally gzip-compressed'})}, 'optional': {'source_type': ('STRING', {'default': 'bed', 'options': ['bed', 'name'], 'description': 'Select sequences by BED regions or by a newline-delimited ID list'}), 'in_bed': ('BED', {'default': '', 'description': 'BED intervals to extract when source_type is bed'}), 'name_list': ('TXT', {'default': '', 'description': 'Newline-delimited FASTA/Q IDs to extract when source_type is name'}), 't': ('BOOLEAN', {'default': False, 'description': 'Emit tab-delimited output with a Galaxy header'}), 'l': ('INT', {'default': 0, 'description': 'Sequence line length'}), 'input_ext': ('STRING', {'default': 'fasta', 'options': ['fasta', 'fastq', 'fasta.gz', 'fastq.gz'], 'description': 'Input/output sequence format used to mirror Galaxy format_source metadata', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class SeqTKTeloNode(CommandNode):
    """Find telomeric repeats with seqtk telo."""
    NODE_ID = 'seqtk_telo'
    DISPLAY_NAME = 'SeqTK Telomere'
    REQUIRED_CONDA_PACKAGES = ['seqtk', 'pigz']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Find telomeric repeat regions in FASTA or FASTQ sequences.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqtk', 'seqtk telo', 'SeqTK telo', 'telomere', 'telomere repeat', 'vertebrate repeat', 'CCCTAA', 'telomeric regions']
    RETURN_TYPES = ('BED',)
    RETURN_NAMES = ('telomeres',)
    REQUIRED_EXECUTABLES = ['seqtk']
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = '1.5+galaxy0'
    SHELL = True

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on', '-p'}
        return bool(value)

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/telomeres.bed'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['seqtk', 'telo', '-m', str(inputs.get('m', 'CCCTAA')), '-p', str(inputs.get('p', 1)), '-d', str(inputs.get('d', 2000)), '-s', str(inputs.get('s', 300))]
        if cls._bool_value(inputs.get('P', False)):
            cmd.append('-P')
        cmd.append(str(inputs.get('in_file', '')))
        return f'{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'telomeres.bed']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('FASTQ_LIST', {'description': 'Input FASTA/Q file, optionally gzip-compressed'})}, 'optional': {'m': ('STRING', {'default': 'CCCTAA', 'description': 'Telomere repeat motif to search for'}), 'p': ('INT', {'default': 1, 'description': 'Penalty for a non-repeat'}), 'd': ('INT', {'default': 2000, 'description': 'Maximum score drop'}), 's': ('INT', {'default': 300, 'description': 'Minimum telomere score'}), 'P': ('BOOLEAN', {'default': False, 'description': 'Print scoring information'})}, 'hidden': {'output': ('STRING', {})}}
