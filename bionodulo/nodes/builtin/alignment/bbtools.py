"""bbtools — alignment node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BBToolsBBMapNode(CommandNode):
    """Map short reads with BBTools BBMap."""
    NODE_ID = 'bbtools_bbmap'
    DISPLAY_NAME = 'BBTools BBMap'
    REQUIRED_CONDA_PACKAGES = ['bbmap', 'samtools']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Map short reads to a reference genome with BBMap and emit all, unmapped, and mapped BAM files.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'BBTools', 'BBMap', 'bbmap', 'bbtools_bbmap', 'short-read aligner', 'read mapping', 'BAM output', 'mapped reads']
    RETURN_TYPES = ('BAM', 'BAM', 'BAM')
    RETURN_NAMES = ('all_reads', 'unmapped_reads', 'mapped_reads')
    REQUIRED_EXECUTABLES = ['bbmap.sh', 'samtools']
    DOCUMENTATION_URL = 'https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/bbmap-guide/'
    CITATION_DOIS = [BBTOOLS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{BBTOOLS_CITATION_DOI}']
    CITATION_TEXT = BBTOOLS_CITATION_TEXT
    VERSION = '39.08'
    SHELL = True
    VALID_INPUT_TYPES = {'single', 'pair', 'paired'}
    VALID_OUTPUT_SORTS = {'coordinate', 'name', 'unsorted'}

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
    def _add_output_sort(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        out = _out(inputs)
        output_sort = str(inputs.get('output_sort', 'coordinate') or 'coordinate')
        cmd.extend(['out=all_reads.bam', 'outu=unmapped_reads.bam', 'outm=mapped_reads.bam'])
        if output_sort == 'coordinate':
            sort_flag = ''
        elif output_sort == 'name':
            sort_flag = '-n '
        else:
            cmd.extend(['&&', 'mv', 'all_reads.bam', f'{out}/all_reads.bam', '&&', 'mv', 'unmapped_reads.bam', f'{out}/unmapped_reads.bam', '&&', 'mv', 'mapped_reads.bam', f'{out}/mapped_reads.bam'])
            return
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"
        for source, target in (('all_reads.bam', f'{out}/all_reads.bam'), ('unmapped_reads.bam', f'{out}/unmapped_reads.bam'), ('mapped_reads.bam', f'{out}/mapped_reads.bam')):
            cmd.extend(['&&', 'samtools', 'sort', '--no-PG', f'-@{slots}'])
            if sort_flag:
                cmd.append(sort_flag.strip())
            cmd.extend(['-T', '${TMPDIR:-.}', '-O', 'bam', '-o', target, source])

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
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"
        cmd = ['bbmap.sh', 'nodisk=f', f"ref={inputs.get('reference', '')}", 'k=13', 'usemodulo=f', 'rebuild=f', f'in={read1_file}']
        if input_type in {'pair', 'paired'}:
            cmd.append(f'in2={read2_file}')
        cmd.extend(['fastareadlen=500', 'unpigz=f', 'touppercase=t', 'reads=-1', 'samplerate=1', 'skipreads=0', f"maxindel={inputs.get('maxindel', 16000)}", f"strictmaxindel={cls._bool_value(inputs, 'strictmaxindel', False)}", f"tipsearch={inputs.get('tipsearch', 100)}", f"minid={inputs.get('minid', 0.76)}", f"minhits={inputs.get('minhits', 1)}", f"local={cls._bool_value(inputs, 'local', False)}", f"perfectmode={cls._bool_value(inputs, 'perfectmode', False)}", f"semiperfectmode={cls._bool_value(inputs, 'semiperfectmode', False)}", f'threads={slots}', f"ambiguous={inputs.get('ambiguous', 'best')}", f"samestrandpairs={cls._bool_value(inputs, 'samestrandpairs', False)}", f"requirecorrectstrand={cls._bool_value(inputs, 'requirecorrectstrand', True)}", f"killbadpairs={cls._bool_value(inputs, 'killbadpairs', False)}", f"pairedonly={cls._bool_value(inputs, 'pairedonly', False)}", f"rcomp={cls._bool_value(inputs, 'rcomp', False)}", f"rcompmate={cls._bool_value(inputs, 'rcompmate', False)}", f"pairlen={inputs.get('pairlen', 32000)}", f"rescuedist={inputs.get('rescuedist', 1200)}", f"rescuemismatches={inputs.get('rescuemismatches', 32)}", f"averagepairdist={inputs.get('averagepairdist', 100)}", f"deterministic={cls._bool_value(inputs, 'deterministic', False)}", f"bandwidthratio={inputs.get('bandwidthratio', 0)}", f"bandwidth={inputs.get('bandwidth', 0)}", 'usejni=f', f"maxsites2={inputs.get('maxsites2', 800)}", f"ignorefrequentkmers={cls._bool_value(inputs, 'ignorefrequentkmers', True)}", f"excludefraction={inputs.get('excludefraction', 0.03)}", f"greedy={cls._bool_value(inputs, 'greedy', True)}", f"kfilter={inputs.get('kfilter', 0)}", 'qin=auto', 'qout=auto', f"qtrim={inputs.get('qtrim', 'f')}", f"untrim={cls._bool_value(inputs, 'untrim', False)}", f"trimq={inputs.get('trimq', 6)}", f"mintrimlength={inputs.get('mintrimlength', 60)}", f"fakefastaquality={inputs.get('fakefastaquality', -1)}", f"ignorebadquality={cls._bool_value(inputs, 'ignorebadquality', False)}", f"usequality={cls._bool_value(inputs, 'usequality', True)}", f"minaveragequality={inputs.get('minaveragequality', 0)}", f"maqb={inputs.get('maqb', 0)}", f"idfilter={inputs.get('idfilter', 0)}", f"subfilter={inputs.get('subfilter', -1)}", f"insfilter={inputs.get('insfilter', -1)}", f"delfilter={inputs.get('delfilter', -1)}", f"indelfilter={inputs.get('indelfilter', -1)}", f"editfilter={inputs.get('editfilter', -1)}", f"inslenfilter={inputs.get('inslenfilter', -1)}", f"dellenfilter={inputs.get('dellenfilter', -1)}", f"nfilter={inputs.get('nfilter', -1)}", f"secondary={cls._bool_value(inputs, 'secondary', False)}", f"maxsites={inputs.get('maxsites', 5)}", f"sssr={inputs.get('sssr', 0.95)}", f"ssao={cls._bool_value(inputs, 'ssao', False)}", f"quickmatch={cls._bool_value(inputs, 'quickmatch', False)}", f"trimreaddescriptions={cls._bool_value(inputs, 'trimreaddescriptions', False)}", f"machineout={cls._bool_value(inputs, 'machineout', False)}", f"printunmappedcount={cls._bool_value(inputs, 'printunmappedcount', False)}", f"renamebyinsert={cls._bool_value(inputs, 'renamebyinsert', False)}"])
        cls._add_output_sort(cmd, inputs)
        command = _shell_join(cmd)
        command = command.replace(shlex.quote(f'threads={slots}'), f'threads={slots}')
        command = command.replace(shlex.quote(f'-@{slots}'), f'-@{slots}')
        command = command.replace(shlex.quote('${TMPDIR:-.}'), '${TMPDIR:-.}')
        return ' && '.join(setup + [command])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'all_reads.bam', out / 'unmapped_reads.bam', out / 'mapped_reads.bam']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        if input_type not in cls.VALID_INPUT_TYPES:
            return 'input_type must be one of: single, pair, paired'
        read1, read2 = cls._read_pair(inputs)
        if not read1:
            return 'read1 FASTQ is required'
        if input_type in {'pair', 'paired'} and (not read2):
            return 'read2 FASTQ is required for paired input'
        if not inputs.get('reference'):
            return 'reference FASTA is required'
        output_sort = str(inputs.get('output_sort', 'coordinate') or 'coordinate')
        if output_sort not in cls.VALID_OUTPUT_SORTS:
            return 'output_sort must be one of: coordinate, name, unsorted'
        for key, default in (('threads', 4), ('minhits', 1), ('maxsites', 5), ('maxsites2', 800)):
            try:
                value = int(inputs.get(key, default))
            except (TypeError, ValueError):
                return f'{key} must be an integer'
            if value < 1:
                return f'{key} must be >= 1'
        try:
            minid = float(inputs.get('minid', 0.76))
        except (TypeError, ValueError):
            return 'minid must be a number'
        if not 0 <= minid <= 1:
            return 'minid must be between 0 and 1'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_type': ('STRING', {'default': 'single', 'options': ['single', 'pair', 'paired'], 'description': 'Galaxy input mode'}), 'read1': ('FASTQ', {'description': 'Single, forward, or paired-collection forward FASTQ'}), 'reference': ('FASTA', {'description': 'Reference genome FASTA'})}, 'optional': {'read2': ('FASTQ', {'default': '', 'description': 'Reverse FASTQ reads for paired input'}), 'reads_collection': ('FASTQ_LIST', {'default': '', 'description': 'Paired collection mapping or [forward, reverse]'}), 'output_sort': ('STRING', {'default': 'coordinate', 'options': ['coordinate', 'name', 'unsorted'], 'description': 'BAM sorting mode'}), 'maxindel': ('INT', {'default': 16000, 'description': 'Maximum indel length'}), 'strictmaxindel': ('BOOLEAN', {'default': False, 'description': 'Strictly disallow longer indels'}), 'tipsearch': ('INT', {'default': 100, 'description': 'Read-end deletion search distance'}), 'minid': ('FLOAT', {'default': 0.76, 'min': 0, 'max': 1, 'description': 'Approximate minimum identity'}), 'minhits': ('INT', {'default': 1, 'min': 1, 'description': 'Minimum seed hits'}), 'local': ('BOOLEAN', {'default': False, 'description': 'Use local alignments'}), 'ambiguous': ('STRING', {'default': 'best', 'options': ['best', 'toss', 'random', 'all'], 'description': 'Ambiguous mapping behavior'}), 'qtrim': ('STRING', {'default': 'f', 'options': ['f', 'l', 'r', 'lr'], 'description': 'Quality trim mode'}), 'trimq': ('INT', {'default': 6, 'description': 'Trim quality threshold'}), 'secondary': ('BOOLEAN', {'default': False, 'description': 'Output secondary alignments'}), 'maxsites': ('INT', {'default': 5, 'min': 1, 'description': 'Maximum alignments per read'}), 'idfilter': ('INT', {'default': 0, 'min': 0, 'max': 1, 'description': 'Minimum output alignment identity'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}
