"""comebin — metagenomics node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class COMEBinNode(CommandNode):
    """Bin metagenomic contigs with COMEBin."""
    NODE_ID = 'comebin'
    DISPLAY_NAME = 'COMEBin'
    REQUIRED_CONDA_PACKAGES = ['comebin']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Bin metagenomic contigs using contrastive multi-view representation learning with COMEBin.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'COMEBin', 'COMEBin metagenomic binning', 'contrastive multi-view binning', 'metagenome bins', 'contig binning', 'coverage embeddings']
    RETURN_TYPES = ('DIRECTORY',)
    RETURN_NAMES = ('bins',)
    REQUIRED_EXECUTABLES = ['run_comebin.sh']
    DOCUMENTATION_URL = 'https://github.com/ziyewang/COMEBin'
    CITATION_DOIS = ['10.1038/s41467-023-44290-z']
    CITATION_URLS = [f'{DOI_URL}10.1038/s41467-023-44290-z']
    CITATION_TEXT = 'COMEBin enables accurate and robust binning of metagenomic contigs using contrastive multi-view representation learning.'
    VERSION = '1.0.4'
    SHELL = True

    @classmethod
    def _bam_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('bam_files'))

    @classmethod
    def _assembly_identifier(cls, inputs: dict[str, Any]) -> str:
        return _safe_identifier(str(inputs.get('assembly_identifier', Path(str(inputs.get('assembly_file', 'assembly'))).name or 'assembly')))

    @classmethod
    def _bam_identifiers(cls, inputs: dict[str, Any], bam_files: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get('bam_identifiers'))
        if identifiers:
            return [_safe_identifier(identifier) for identifier in identifiers]
        return [_safe_identifier(Path(path).stem) for path in bam_files]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        bam_files = cls._bam_files(inputs)
        assembly = f'{cls._assembly_identifier(inputs)}.fasta'
        commands = [_shell_join(['mkdir', '-p', out, 'outputs', 'bam_files']), _shell_join(['ln', '-s', str(inputs.get('assembly_file', '')), assembly])]
        for path, identifier in zip(bam_files, cls._bam_identifiers(inputs, bam_files), strict=False):
            commands.append(_shell_join(['ln', '-s', path, f'./bam_files/{identifier}.bam']))
        cmd = ['run_comebin.sh', '-a', assembly, '-o', 'outputs', '-p', 'bam_files', '-t', f"${{GALAXY_SLOTS:-{inputs.get('threads', 12)}}}", '-l', str(inputs.get('loss', 0.15)), '-n', str(inputs.get('learning', 6)), '-e', str(inputs.get('emb_comebin', 2048)), '-c', str(inputs.get('emb_cov', 2048)), '-b', str(inputs.get('batch', 1024))]
        commands.append(_shell_join(cmd).replace("'${GALAXY_SLOTS:-", '${GALAXY_SLOTS:-').replace("}'", '}'))
        commands.append(_shell_join(['cp', '-r', 'outputs/comebin_res/comebin_res_bins', f'{out}/bins']))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / 'bins').mkdir(parents=True, exist_ok=True)
        return [out / 'bins']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'assembly_file': ('FASTA', {'description': 'Metagenomic assembly FASTA'}), 'bam_files': ('BAM_LIST', {'multiple': True, 'description': 'BAM files aligned to the assembly'})}, 'optional': {'assembly_identifier': ('STRING', {'default': '', 'advanced': True, 'description': 'Galaxy collection element identifier for the assembly'}), 'bam_identifiers': ('STRING', {'default': [], 'multiple': True, 'advanced': True, 'description': 'Galaxy collection element identifiers for BAMs'}), 'learning': ('INT', {'default': 6, 'min': 1, 'description': 'Views for contrastive multi-view learning'}), 'loss': ('FLOAT', {'default': 0.15, 'min': 0, 'description': 'Temperature in the contrastive loss function'}), 'emb_comebin': ('INT', {'default': 2048, 'min': 1, 'description': 'Embedding size for the COMEBin network'}), 'emb_cov': ('INT', {'default': 2048, 'min': 1, 'description': 'Embedding size for the coverage network'}), 'batch': ('INT', {'default': 1024, 'min': 1, 'description': 'Batch size'}), 'threads': ('INT', {'default': 12, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('assembly_file', '')).strip():
            return 'assembly_file is required'
        if not cls._bam_files(inputs):
            return 'at least one BAM file is required'
        for name in ['learning', 'emb_comebin', 'emb_cov', 'batch', 'threads']:
            raw = inputs.get(name)
            if raw is None or str(raw) == '':
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < 1:
                return f'{name} must be >= 1'
        loss = float(inputs.get('loss', 0.15))
        if loss <= 0:
            return 'loss must be > 0'
        return super().VALIDATE_INPUTS(inputs)


class COMEBinBamNode(CommandNode):
    """Generate a COMEBin-compatible BAM file from reads and an assembly."""
    NODE_ID = 'comebin_bam'
    DISPLAY_NAME = 'Generate BAM file for COMEBin'
    REQUIRED_CONDA_PACKAGES = ['comebin']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Generate a COMEBin-compatible BAM coverage file from reads using the COMEBin MetaWRAP-derived helper.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'COMEBin BAM', 'COMEBin BAM generation', 'gen_cov_file.sh', 'COMEBin coverage BAM', 'metagenomic coverage']
    RETURN_TYPES = ('BAM',)
    RETURN_NAMES = ('bam_file',)
    REQUIRED_EXECUTABLES = ['gen_cov_file.sh']
    DOCUMENTATION_URL = 'https://github.com/ziyewang/COMEBin'
    CITATION_DOIS = ['10.1038/s41467-023-44290-z']
    CITATION_URLS = [f'{DOI_URL}10.1038/s41467-023-44290-z']
    CITATION_TEXT = 'COMEBin enables accurate and robust binning of metagenomic contigs using contrastive multi-view representation learning.'
    VERSION = '1.0.4'
    SHELL = True

    @classmethod
    def _read_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('read_type', inputs.get('is_select', 'normal')) or 'normal')

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_type', inputs.get('input_typ', 'paired')) or 'paired')

    @staticmethod
    def _is_gz(path: Any) -> bool:
        return str(path).endswith('.gz')

    @classmethod
    def _paired_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        reads = inputs.get('paired_reads')
        if isinstance(reads, dict):
            return (str(reads.get('forward', '')), str(reads.get('reverse', '')))
        parts = _as_list(reads)
        if len(parts) >= 2:
            return (parts[0], parts[1])
        return (str(inputs.get('forward', '')), str(inputs.get('reverse', '')))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(['mkdir', '-p', 'outputs', out])]
        assembly = str(inputs.get('assembly', ''))
        if cls._is_gz(assembly):
            commands.append(_shell_join(['ln', '-s', assembly, 'assembly.fasta.gz']))
            commands.append(_shell_join(['gunzip', 'assembly.fasta.gz']))
        else:
            commands.append(_shell_join(['ln', '-s', assembly, 'assembly.fasta']))
        read_type = cls._read_type(inputs)
        if read_type == 'normal':
            forward, reverse = cls._paired_reads(inputs)
            if cls._is_gz(forward):
                commands.append(_shell_join(['ln', '-s', forward, 'read_1.fastq.gz']))
                commands.append(_shell_join(['ln', '-s', reverse, 'read_2.fastq.gz']))
                commands.append(_shell_join(['gunzip', 'read_1.fastq.gz']))
                commands.append(_shell_join(['gunzip', 'read_2.fastq.gz']))
            else:
                commands.append(_shell_join(['ln', '-s', forward, 'read_1.fastq']))
                commands.append(_shell_join(['ln', '-s', reverse, 'read_2.fastq']))
        else:
            single_reads = str(inputs.get('single_reads', ''))
            if cls._is_gz(single_reads):
                commands.append(_shell_join(['ln', '-s', single_reads, 'read.fastq.gz']))
                commands.append(_shell_join(['gunzip', 'read.fastq.gz']))
            else:
                commands.append(_shell_join(['ln', '-s', single_reads, 'read.fastq']))
        cmd = ['gen_cov_file.sh', '-a', 'assembly.fasta', '-o', 'outputs', '-t', f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}", '-l', str(inputs.get('length', 1000))]
        if read_type == 'normal':
            cmd.extend(['read_1.fastq', 'read_2.fastq'])
        else:
            cmd.extend(['--single-end', 'read.fastq'])
        commands.append(_shell_join(cmd).replace("'${GALAXY_SLOTS:-", '${GALAXY_SLOTS:-').replace("}'", '}'))
        commands.append(_shell_join(['mv', 'outputs/work_files/read.bam', f'{out}/bam_file.bam']))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'bam_file.bam']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'assembly': ('FASTA', {'description': 'Assembly FASTA or FASTA.GZ'}), 'read_type': ('STRING', {'default': 'normal', 'options': ['normal', 'single'], 'description': 'Paired-end or single-end reads'})}, 'optional': {'input_type': ('STRING', {'default': 'paired', 'options': ['paired', 'single'], 'description': 'Paired collection or separate reads'}), 'paired_reads': ('FASTQ_LIST', {'default': '', 'description': 'Paired read collection or [forward, reverse]'}), 'forward': ('FASTQ', {'default': '', 'description': 'Forward FASTQ for separate paired reads'}), 'reverse': ('FASTQ', {'default': '', 'description': 'Reverse FASTQ for separate paired reads'}), 'single_reads': ('FASTQ', {'default': '', 'description': 'Single-end FASTQ'}), 'length': ('INT', {'default': 1000, 'min': 1, 'description': 'Minimum contig length'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('assembly', '')).strip():
            return 'assembly is required'
        read_type = cls._read_type(inputs)
        if read_type not in {'normal', 'single'}:
            return 'read_type must be one of: normal, single'
        if read_type == 'normal':
            input_type = cls._input_type(inputs)
            if input_type not in {'paired', 'single'}:
                return 'input_type must be one of: paired, single'
            forward, reverse = cls._paired_reads(inputs)
            if not forward or not reverse:
                return 'forward and reverse reads are required'
        elif not str(inputs.get('single_reads', '')).strip():
            return 'single_reads is required'
        for name in ['length', 'threads']:
            raw = inputs.get(name)
            if raw is None or str(raw) == '':
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < 1:
                return f'{name} must be >= 1'
        return super().VALIDATE_INPUTS(inputs)
