"""snippy — variant node(s). One tool per file (extracted from wrapped_assembly_typing.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class SnippyNode(CommandNode):
    """Call bacterial SNPs and indels with the Galaxy IUC Snippy wrapper behavior."""
    NODE_ID = 'snippy'
    DISPLAY_NAME = 'Snippy'
    REQUIRED_CONDA_PACKAGES = ['snippy', 'tar']
    CATEGORY = 'variant'
    DESCRIPTION = 'Call SNPs and indels between a haploid reference genome and reads or contigs with Snippy.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Snippy', 'snippy', 'haploid variant calling', 'fast bacterial variant calling', 'NGS reads', 'core genome alignment', 'snippy-core', 'SNPs', 'indels']
    RETURN_TYPES = ('VCF', 'GFF', 'TSV', 'TSV', 'TXT', 'FASTA', 'FASTA', 'BAM', 'ZIP')
    RETURN_NAMES = ('snpvcf', 'snpgff', 'snptab', 'snpsum', 'snplog', 'snpalign', 'snpconsensus', 'snpsbam', 'outdir')
    REQUIRED_EXECUTABLES = ['snippy', 'tar']
    DOCUMENTATION_URL = SNIPPY_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SNIPPY_CITATION_URL]
    CITATION_TEXT = SNIPPY_CITATION_TEXT
    VERSION = '4.6.0+galaxy0'
    SHELL = True
    REFERENCE_SOURCES = ['history', 'cached']
    REFERENCE_TYPES = ['fasta', 'genbank']
    INPUT_SELECTORS = ['paired', 'single', 'paired_collection', 'paired_iv', 'contigs']
    OUTPUT_SELECTIONS = ['outvcf', 'outgff', 'outtab', 'outsum', 'outlog', 'outaln', 'outcon', 'outbam', 'outzip']
    DEFAULT_OUTPUTS = ['outvcf', 'outtab', 'outzip']
    OUTPUT_FILES = {'outvcf': ('out', 'snps.vcf'), 'outgff': ('out', 'snps.gff'), 'outtab': ('out', 'snps.tab'), 'outsum': ('out', 'snps.txt'), 'outlog': ('out', 'snps.log'), 'outaln': ('out', 'snps.aligned.fa'), 'outcon': ('out', 'snps.consensus.fa'), 'outbam': ('out', 'snps.bam'), 'outzip': ('', 'out.tgz')}

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('reference_source_selector', 'history') or 'history')

    @classmethod
    def _reference_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('ref_type', 'fasta') or 'fasta')

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        selected = _as_list(inputs.get('outputs'))
        return selected or list(cls.DEFAULT_OUTPUTS)

    @classmethod
    def _format_int(cls, inputs: dict[str, Any], key: str, default: int) -> str:
        value = inputs.get(key, default)
        if value in (None, ''):
            value = default
        return str(int(value))

    @classmethod
    def _format_float(cls, inputs: dict[str, Any], key: str, default: float) -> str:
        value = inputs.get(key, default)
        if value in (None, ''):
            value = default
        parsed = float(value)
        if key == 'minqual':
            return str(value)
        return str(int(parsed)) if parsed.is_integer() else format(parsed, 'g')

    @classmethod
    def _reference_stage_command(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        ref_file = str(inputs.get('ref_file', '') or '')
        if cls._reference_source(inputs) == 'cached':
            return (_shell_join(['ln', '-sf', ref_file, 'ref.fna']), 'ref.fna')
        if cls._reference_type(inputs) == 'genbank':
            return (_shell_join(['ln', '-sf', ref_file, 'ref.gbk']), 'ref.gbk')
        return (_shell_join(['ln', '-sf', ref_file, 'ref.fna']), 'ref.fna')

    @classmethod
    def _collection_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        collection = inputs.get('fastq_input')
        if isinstance(collection, dict):
            return (str(collection.get('forward', '') or ''), str(collection.get('reverse', '') or ''))
        if isinstance(collection, (list, tuple)) and len(collection) >= 2:
            return (str(collection[0]), str(collection[1]))
        return ('', '')

    @classmethod
    def _dir_name(cls, inputs: dict[str, Any]) -> str:
        selector = str(inputs.get('fastq_input_selector', 'paired') or 'paired')
        if selector == 'paired':
            label = str(inputs.get('fastq_input1_label', '') or Path(str(inputs.get('fastq_input1', ''))).name)
        elif selector == 'paired_collection':
            collection = inputs.get('fastq_input')
            label = str(collection.get('name', '') if isinstance(collection, dict) else '')
            if not label:
                forward, _reverse = cls._collection_reads(inputs)
                label = Path(forward).name
        elif selector == 'single':
            label = str(inputs.get('fastq_input_single_label', '') or Path(str(inputs.get('fastq_input_single', ''))).name)
        elif selector == 'paired_iv':
            label = str(inputs.get('fastq_input_interleaved_label', '') or Path(str(inputs.get('fastq_input_interleaved', ''))).name)
        else:
            label = str(inputs.get('fasta_input_label', '') or Path(str(inputs.get('fasta_input', ''))).name)
        return _safe_identifier(label)

    @classmethod
    def _input_args(cls, inputs: dict[str, Any]) -> list[str]:
        selector = str(inputs.get('fastq_input_selector', 'paired') or 'paired')
        if selector == 'paired':
            return ['--R1', str(inputs.get('fastq_input1', '') or ''), '--R2', str(inputs.get('fastq_input2', '') or '')]
        if selector == 'paired_collection':
            forward, reverse = cls._collection_reads(inputs)
            return ['--R1', forward, '--R2', reverse]
        if selector == 'single':
            return ['--se', str(inputs.get('fastq_input_single', '') or '')]
        if selector == 'paired_iv':
            return ['--peil', str(inputs.get('fastq_input_interleaved', '') or '')]
        return ['--ctgs', str(inputs.get('fasta_input', '') or '')]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        ref_stage, ref_name = cls._reference_stage_command(inputs)
        dir_name = cls._dir_name(inputs)
        memory = '$((${GALAXY_MEMORY_MB:-4096}/1024))'
        slots = '${GALAXY_SLOTS:-1}'
        cmd = ['snippy', '--outdir', dir_name, '--cpus', slots, '--ram', memory, '--ref', ref_name, '--mapqual', cls._format_int(inputs, 'mapqual', 60), '--mincov', cls._format_int(inputs, 'mincov', 10), '--minfrac', cls._format_float(inputs, 'minfrac', 0.9), '--minqual', cls._format_float(inputs, 'minqual', 100.0)]
        if str(inputs.get('rgid', '') or '').strip():
            cmd.extend(['--rgid', str(inputs.get('rgid'))])
        if str(inputs.get('bwaopt', '') or '').strip():
            cmd.extend(['--bwaopt', str(inputs.get('bwaopt'))])
        cmd.extend(cls._input_args(inputs))
        snippy_command = _shell_join(cmd).replace(shlex.quote(slots), slots).replace(shlex.quote(memory), memory)
        commands = [ref_stage, snippy_command]
        if 'outcon' in cls._selected_outputs(inputs) and inputs.get('rename_cons'):
            commands.append(f"sed -i 's/>.*/>{dir_name}/' {shlex.quote(f'{dir_name}/snps.consensus.fa')}")
        commands.extend([f"cp -r {shlex.quote(dir_name)} {shlex.quote(f'{_out(inputs)}/out')}", f"tar -czf {shlex.quote(f'{_out(inputs)}/out.tgz')} {shlex.quote(dir_name)}"])
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / 'out').mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        selected = set(cls._selected_outputs(inputs))
        for selection in cls.OUTPUT_SELECTIONS:
            if selection not in selected:
                continue
            output_subdir, filename = cls.OUTPUT_FILES[selection]
            outputs.append(out / output_subdir / filename if output_subdir else out / filename)
        return outputs

    @classmethod
    def _validate_nonnegative_int(cls, inputs: dict[str, Any], key: str, default: int) -> bool | str:
        try:
            value = int(inputs.get(key, default) if inputs.get(key, default) not in (None, '') else default)
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if value < 0:
            return f'{key} must be greater than or equal to 0'
        return True

    @classmethod
    def _validate_nonnegative_float(cls, inputs: dict[str, Any], key: str, default: float) -> bool | str:
        try:
            value = float(inputs.get(key, default) if inputs.get(key, default) not in (None, '') else default)
        except (TypeError, ValueError):
            return f'{key} must be a number'
        if value < 0:
            return f'{key} must be greater than or equal to 0'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        source = cls._reference_source(inputs)
        if source not in cls.REFERENCE_SOURCES:
            return f"reference_source_selector must be one of: {', '.join(cls.REFERENCE_SOURCES)}"
        if not str(inputs.get('ref_file', '') or '').strip():
            return 'ref_file is required'
        ref_type = cls._reference_type(inputs)
        if source == 'history' and ref_type not in cls.REFERENCE_TYPES:
            return f"ref_type must be one of: {', '.join(cls.REFERENCE_TYPES)}"
        selector = str(inputs.get('fastq_input_selector', 'paired') or 'paired')
        if selector not in cls.INPUT_SELECTORS:
            return f"fastq_input_selector must be one of: {', '.join(cls.INPUT_SELECTORS)}"
        if selector == 'paired':
            if not str(inputs.get('fastq_input1', '') or '').strip():
                return 'fastq_input1 is required for paired input'
            if not str(inputs.get('fastq_input2', '') or '').strip():
                return 'fastq_input2 is required for paired input'
        elif selector == 'paired_collection':
            forward, reverse = cls._collection_reads(inputs)
            if not forward or not reverse:
                return 'fastq_input collection with forward and reverse reads is required'
        elif selector == 'single':
            if not str(inputs.get('fastq_input_single', '') or '').strip():
                return 'fastq_input_single is required for single input'
        elif selector == 'paired_iv':
            if not str(inputs.get('fastq_input_interleaved', '') or '').strip():
                return 'fastq_input_interleaved is required for interleaved paired input'
        elif not str(inputs.get('fasta_input', '') or '').strip():
            return 'fasta_input is required for contigs input'
        for key, default in (('mapqual', 60), ('mincov', 10)):
            result = cls._validate_nonnegative_int(inputs, key, default)
            if result is not True:
                return result
        result = cls._validate_nonnegative_float(inputs, 'minqual', 100.0)
        if result is not True:
            return result
        try:
            minfrac = float(inputs.get('minfrac', 0.9) if inputs.get('minfrac', 0.9) not in (None, '') else 0.9)
        except (TypeError, ValueError):
            return 'minfrac must be a number'
        if minfrac < 0 or minfrac > 1:
            return 'minfrac must be between 0 and 1'
        invalid_outputs = [selection for selection in cls._selected_outputs(inputs) if selection not in cls.OUTPUT_SELECTIONS]
        if invalid_outputs:
            return f"outputs values must be one of: {', '.join(cls.OUTPUT_SELECTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reference_source_selector': ('STRING', {'default': 'history', 'options': cls.REFERENCE_SOURCES, 'description': 'Use a reference from history or a cached Galaxy fasta index'}), 'ref_file': ('FILE', {'description': 'Reference genome FASTA, GenBank, or cached reference path'}), 'fastq_input_selector': ('STRING', {'default': 'paired', 'options': cls.INPUT_SELECTORS, 'description': 'Galaxy input type for paired, single, interleaved, or contig inputs'})}, 'optional': {'ref_type': ('STRING', {'default': 'fasta', 'options': cls.REFERENCE_TYPES, 'description': 'History reference datatype'}), 'fastq_input1': ('FASTQ', {'default': '', 'description': 'Forward reads for paired input'}), 'fastq_input2': ('FASTQ', {'default': '', 'description': 'Reverse reads for paired input'}), 'fastq_input1_label': ('STRING', {'default': '', 'advanced': True, 'description': 'Galaxy element identifier for paired R1'}), 'fastq_input_single': ('FASTQ', {'default': '', 'description': 'Single-end reads'}), 'fastq_input_single_label': ('STRING', {'default': '', 'advanced': True, 'description': 'Galaxy element identifier for single reads'}), 'fastq_input': ('FILE', {'default': '', 'description': 'Paired collection object with forward and reverse reads'}), 'fastq_input_interleaved': ('FASTQ', {'default': '', 'description': 'Interleaved paired-end reads'}), 'fastq_input_interleaved_label': ('STRING', {'default': '', 'advanced': True, 'description': 'Galaxy element identifier for interleaved reads'}), 'fasta_input': ('FASTA', {'default': '', 'description': 'Assembled contigs for --ctgs mode'}), 'fasta_input_label': ('STRING', {'default': '', 'advanced': True, 'description': 'Galaxy element identifier for contigs'}), 'outputs': ('STRING_LIST', {'default': cls.DEFAULT_OUTPUTS, 'options': cls.OUTPUT_SELECTIONS, 'description': 'Galaxy output files to collect from the Snippy run'}), 'mapqual': ('INT', {'default': 60, 'min': 0, 'description': 'Minimum mapping quality'}), 'mincov': ('INT', {'default': 10, 'min': 0, 'description': 'Minimum coverage to call a SNP'}), 'minfrac': ('FLOAT', {'default': 0.9, 'min': 0, 'max': 1, 'description': 'Minimum variant evidence fraction'}), 'minqual': ('FLOAT', {'default': 100.0, 'min': 0, 'description': 'Minimum VCF QUAL'}), 'rgid': ('STRING', {'default': '', 'description': 'BAM header read-group ID'}), 'bwaopt': ('STRING', {'default': '', 'description': 'Extra BWA MEM options'}), 'rename_cons': ('BOOLEAN', {'default': False, 'description': 'Rename consensus FASTA header to the input identifier'})}, 'hidden': {'output': ('STRING', {})}}


class SnippyCoreNode(CommandNode):
    """Combine multiple Snippy outputs into a core SNP alignment."""
    NODE_ID = 'snippy_core'
    DISPLAY_NAME = 'snippy-core'
    REQUIRED_CONDA_PACKAGES = ['snippy', 'tar']
    CATEGORY = 'variant'
    DESCRIPTION = 'Combine multiple Snippy outputs into a core SNP alignment.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'snippy-core', 'Snippy core', 'Snippy', 'core SNP alignment', 'core genome alignment', 'core SNP phylogeny', 'bacterial SNP alignment']
    RETURN_TYPES = ('FASTA', 'FASTA', 'TSV', 'TXT')
    RETURN_NAMES = ('alignment_fasta', 'full_alignment_fasta', 'alignment_table', 'alignment_summary')
    REQUIRED_EXECUTABLES = ['snippy-core', 'tar']
    DOCUMENTATION_URL = SNIPPY_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SNIPPY_CITATION_URL]
    CITATION_TEXT = SNIPPY_CITATION_TEXT
    VERSION = '4.6.0+galaxy0'
    SHELL = True
    REFERENCE_SOURCES = ['history', 'cached']
    REFERENCE_TYPES = ['fasta', 'genbank']
    OUTPUT_SELECTIONS = ['outaln', 'outfull', 'outtab', 'outtxt']
    DEFAULT_OUTPUTS = ['outaln']
    OUTPUT_FILES = {'outaln': 'core.aln', 'outfull': 'core.full.aln', 'outtab': 'core.tab', 'outtxt': 'core.txt'}

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('reference_source_selector', 'history') or 'history')

    @classmethod
    def _reference_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('ref_type', 'fasta') or 'fasta')

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        selected = _as_list(inputs.get('outputs'))
        return selected or list(cls.DEFAULT_OUTPUTS)

    @classmethod
    def _reference_stage_command(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        ref_file = str(inputs.get('ref_file', '') or '')
        if cls._reference_source(inputs) == 'cached':
            return (_shell_join(['ln', '-sf', ref_file, 'ref.fna']), 'ref.fna')
        if cls._reference_type(inputs) == 'genbank':
            return (_shell_join(['ln', '-sf', ref_file, 'ref.gbk']), 'ref.gbk')
        return (_shell_join(['ln', '-sf', ref_file, 'ref.fna']), 'ref.fna')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        ref_stage, ref_name = cls._reference_stage_command(inputs)
        commands = [ref_stage, 'mkdir snippy_dirs']
        commands.extend((_shell_join(['tar', '-xf', archive, '-C', 'snippy_dirs']) for archive in _as_list(inputs.get('indirs')) if archive.strip()))
        snippy_cmd = f"{_shell_join(['snippy-core', '--ref', ref_name])} snippy_dirs/*"
        commands.extend([snippy_cmd, f'mkdir -p {shlex.quote(_out(inputs))}'])
        commands.extend((f"cp {shlex.quote(filename)} {shlex.quote(f'{_out(inputs)}/{filename}')}" for filename in (cls.OUTPUT_FILES[selection] for selection in cls._selected_outputs(inputs))))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILES[selection] for selection in cls._selected_outputs(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        indirs = [indir for indir in _as_list(inputs.get('indirs')) if indir.strip()]
        if len(indirs) < 2:
            return 'at least two indirs are required'
        source = cls._reference_source(inputs)
        if source not in cls.REFERENCE_SOURCES:
            return f"reference_source_selector must be one of: {', '.join(cls.REFERENCE_SOURCES)}"
        if not str(inputs.get('ref_file', '') or '').strip():
            return 'ref_file is required'
        ref_type = cls._reference_type(inputs)
        if source == 'history' and ref_type not in cls.REFERENCE_TYPES:
            return f"ref_type must be one of: {', '.join(cls.REFERENCE_TYPES)}"
        invalid_outputs = [selection for selection in cls._selected_outputs(inputs) if selection not in cls.OUTPUT_SELECTIONS]
        if invalid_outputs:
            return f"outputs values must be one of: {', '.join(cls.OUTPUT_SELECTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'indirs': ('FILE', {'multiple': True, 'description': 'Snippy output tar archives produced with cleanup disabled'}), 'reference_source_selector': ('STRING', {'default': 'history', 'options': cls.REFERENCE_SOURCES, 'description': 'Use a reference from history or a cached Galaxy fasta index'}), 'ref_file': ('FILE', {'description': 'Reference genome FASTA, GenBank, or cached reference path'})}, 'optional': {'ref_type': ('STRING', {'default': 'fasta', 'options': cls.REFERENCE_TYPES, 'description': 'History reference datatype'}), 'outputs': ('STRING_LIST', {'default': cls.DEFAULT_OUTPUTS, 'options': cls.OUTPUT_SELECTIONS, 'multiple': True, 'description': 'Galaxy output files to collect from the snippy-core run'})}, 'hidden': {'output': ('STRING', {})}}


class SnippyCleanFullAlnNode(CommandNode):
    """Replace non-standard characters in a Snippy whole-genome alignment."""
    NODE_ID = 'snippy_clean_full_aln'
    DISPLAY_NAME = 'snippy-clean_full_aln'
    REQUIRED_CONDA_PACKAGES = ['snippy', 'tar']
    CATEGORY = 'variant'
    DESCRIPTION = 'Replace non-standard sequence characters in a Snippy core.full.aln alignment.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'snippy-clean_full_aln', 'Snippy clean full alignment', 'Snippy', 'core.full.aln', 'clean.full.aln', 'whole genome SNP alignment', 'Gubbins']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('clean_full_aln',)
    REQUIRED_EXECUTABLES = ['snippy-clean_full_aln']
    DOCUMENTATION_URL = SNIPPY_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SNIPPY_CITATION_URL]
    CITATION_TEXT = SNIPPY_CITATION_TEXT
    VERSION = '4.6.0+galaxy0'
    SHELL = True
    OUTPUT_FILENAME = 'clean.full.aln'

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls.OUTPUT_FILENAME}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['snippy-clean_full_aln', str(inputs.get('full_aln', '') or '')]
        if inputs.get('custom_char_selector'):
            cmd.extend(['--to', str(inputs.get('to_char', 'N') or 'N')])
        return f'{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('full_aln', '') or '').strip():
            return 'full_aln is required'
        if inputs.get('custom_char_selector'):
            to_char = str(inputs.get('to_char', '') or '')
            if not to_char:
                return 'to_char is required when custom_char_selector is true'
            if "'" in to_char:
                return 'to_char must not contain a single quote'
            if len(to_char) != 1:
                return 'to_char must be a single replacement character'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'full_aln': ('FASTA', {'description': 'Snippy core.full.aln FASTA alignment to clean'})}, 'optional': {'custom_char_selector': ('BOOLEAN', {'default': False, 'description': "Use a custom replacement character instead of Snippy's N"}), 'to_char': ('STRING', {'default': 'N', 'description': 'Single replacement character for non-AGTCN-gap symbols when custom mode is enabled'})}, 'hidden': {'output': ('STRING', {})}}
