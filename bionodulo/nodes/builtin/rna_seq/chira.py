"""chira — rna_seq node(s). One tool per file (extracted from wrapped_assembly_typing.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ChiraCollapseNode(CommandNode):
    """Deduplicate FASTQ reads for ChiRA analysis."""
    NODE_ID = 'chira_collapse'
    DISPLAY_NAME = 'ChiRA collapse'
    REQUIRED_CONDA_PACKAGES = ['chira']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Deduplicate FASTQ reads and write unique sequences with UMI and read counts.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ChiRA', 'ChiRA collapse', 'chira_collapse', 'chira_collapse.py', 'chimeric read analysis', 'RNA-RNA interactome', 'deduplicate fastq reads']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('collapsed_fasta',)
    REQUIRED_EXECUTABLES = ['chira_collapse.py', 'gunzip']
    DOCUMENTATION_URL = CHIRA_DOCUMENTATION_URL
    CITATION_DOIS = [CHIRA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHIRA_CITATION_DOI}']
    CITATION_TEXT = CHIRA_CITATION_TEXT
    VERSION = '1.4.3+galaxy1'
    SHELL = True

    @classmethod
    def _input_fastq(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_fastq', inputs.get('in', '')) or '')

    @classmethod
    def _command_input(cls, input_fastq: str) -> str:
        if input_fastq.endswith('.gz'):
            return f'<(gunzip -c {shlex.quote(input_fastq)})'
        return shlex.quote(input_fastq)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_fastq = cls._input_fastq(inputs)
        command_input = cls._command_input(input_fastq)
        cmd = f"chira_collapse.py -i {command_input} -u {shlex.quote(str(inputs.get('umi_len', 0)))} -o {shlex.quote(f'{out}/collapsed.fasta')}"
        return f"{_shell_join(['mkdir', '-p', out])} && {cmd}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'collapsed.fasta']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_fastq': ('FASTQ', {'description': 'Quality- and adapter-trimmed FASTQ reads'})}, 'optional': {'umi_len': ('INT', {'default': 0, 'min': 0, 'description': '5-prime UMI length'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_fastq(inputs).strip():
            return 'input_fastq is required'
        try:
            umi_len = int(inputs.get('umi_len', 0))
        except (TypeError, ValueError):
            return 'umi_len must be an integer'
        if umi_len < 0:
            return 'umi_len must be >= 0'
        return True


class ChiraMapNode(CommandNode):
    """Map ChiRA reads to transcriptome references."""
    NODE_ID = 'chira_map'
    DISPLAY_NAME = 'ChiRA map'
    REQUIRED_CONDA_PACKAGES = ['chira']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Map collapsed ChiRA reads to single or split transcriptome references.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ChiRA', 'ChiRA map', 'chira_map', 'chira_map.py', 'chimeric read mapping', 'RNA-RNA interactome', 'BWA-MEM', 'CLAN']
    RETURN_TYPES = ('BED', 'FASTA')
    RETURN_NAMES = ('mapped_bed', 'unmapped_fasta')
    REQUIRED_EXECUTABLES = ['chira_map.py']
    DOCUMENTATION_URL = CHIRA_DOCUMENTATION_URL
    CITATION_DOIS = [CHIRA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHIRA_CITATION_DOI}']
    CITATION_TEXT = CHIRA_CITATION_TEXT
    VERSION = '1.4.3+galaxy0'
    SHELL = True
    REF_TYPES = ['split', 'single']
    ALIGNERS = ['bwa', 'clan']
    STRANDED_OPTIONS = ['fw', 'rc', 'both']
    BWA_INT_DEFAULTS = {'seed_length1': 12, 'seed_length2': 16, 'align_score1': 18, 'align_score2': 16, 'match1': 1, 'mismatch1': 4, 'match2': 1, 'mismatch2': 6, 'gapo1': 6, 'gape1': 1, 'gapo2': 100, 'gape2': 100, 'nhits1': 50, 'nhits2': 100}

    @classmethod
    def _ref_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('ref_type', 'split') or 'split')

    @classmethod
    def _aligner(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('aligner', 'bwa') or 'bwa')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        aligner = cls._aligner(inputs)
        cmd = ['chira_map.py', '-b', '-a', aligner, '-i', str(inputs.get('query', ''))]
        if aligner == 'bwa':
            cmd.extend(['-s', str(inputs.get('stranded', 'fw') or 'fw'), '-l1', str(inputs.get('seed_length1', 12)), '-l2', str(inputs.get('seed_length2', 16)), '-s1', str(inputs.get('align_score1', 18)), '-s2', str(inputs.get('align_score2', 16)), '-ma1', str(inputs.get('match1', 1)), '-mm1', str(inputs.get('mismatch1', 4)), '-ma2', str(inputs.get('match2', 1)), '-mm2', str(inputs.get('mismatch2', 6)), '-go1', str(inputs.get('gapo1', 6)), '-ge1', str(inputs.get('gape1', 1)), '-go2', str(inputs.get('gapo2', 100)), '-ge2', str(inputs.get('gape2', 100)), '-h1', str(inputs.get('nhits1', 50)), '-h2', str(inputs.get('nhits2', 100))])
        else:
            cmd.extend(['-s2', str(inputs.get('align_score', 10)), '-co', str(inputs.get('chimeric_overlap', 2))])
        if cls._ref_type(inputs) == 'single':
            cmd.extend(['-f1', str(inputs.get('ref_fasta', ''))])
        else:
            cmd.extend(['-f1', str(inputs.get('ref_fasta1', '')), '-f2', str(inputs.get('ref_fasta2', ''))])
        cmd.extend(['-p', f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}", '-o', './'])
        command = _shell_join(cmd).replace("'${GALAXY_SLOTS:-", '${GALAXY_SLOTS:-').replace("}'", '}')
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {command}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'sorted.bed']
        if cls._aligner(inputs) == 'bwa':
            outputs.append(out / 'unmapped.fasta')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'query': ('FASTA', {'description': 'Collapsed ChiRA read FASTA'}), 'ref_type': ('STRING', {'default': 'split', 'options': cls.REF_TYPES, 'description': 'Single or split reference'}), 'aligner': ('STRING', {'default': 'bwa', 'options': cls.ALIGNERS, 'description': 'Alignment engine'})}, 'optional': {'ref_fasta': ('FASTA', {'default': '', 'description': 'Reference FASTA for single-reference mode'}), 'ref_fasta1': ('FASTA', {'default': '', 'description': 'First reference FASTA for split mode'}), 'ref_fasta2': ('FASTA', {'default': '', 'description': 'Second reference FASTA for split mode'}), 'stranded': ('STRING', {'default': 'fw', 'options': cls.STRANDED_OPTIONS, 'description': 'BWA strand mode'}), 'seed_length1': ('INT', {'default': 12, 'min': 1}), 'seed_length2': ('INT', {'default': 16, 'min': 1}), 'align_score1': ('INT', {'default': 18, 'min': 1}), 'align_score2': ('INT', {'default': 16, 'min': 1}), 'match1': ('INT', {'default': 1}), 'mismatch1': ('INT', {'default': 4}), 'match2': ('INT', {'default': 1}), 'mismatch2': ('INT', {'default': 6}), 'gapo1': ('INT', {'default': 6}), 'gape1': ('INT', {'default': 1}), 'gapo2': ('INT', {'default': 100}), 'gape2': ('INT', {'default': 100}), 'nhits1': ('INT', {'default': 50}), 'nhits2': ('INT', {'default': 100}), 'align_score': ('INT', {'default': 10, 'min': 1, 'description': 'CLAN minimum fragment length'}), 'chimeric_overlap': ('INT', {'default': 2, 'description': 'Maximum overlap between chimeric read segments'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], name: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f'{name} must be an integer'
        if value < minimum:
            return f'{name} must be >= {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('query', '')).strip():
            return 'query is required'
        ref_type = cls._ref_type(inputs)
        if ref_type not in cls.REF_TYPES:
            return f"ref_type must be one of: {', '.join(cls.REF_TYPES)}"
        aligner = cls._aligner(inputs)
        if aligner not in cls.ALIGNERS:
            return f"aligner must be one of: {', '.join(cls.ALIGNERS)}"
        if ref_type == 'single':
            if not str(inputs.get('ref_fasta', '')).strip():
                return 'ref_fasta is required when ref_type is single'
        else:
            if not str(inputs.get('ref_fasta1', '')).strip():
                return 'ref_fasta1 is required when ref_type is split'
            if not str(inputs.get('ref_fasta2', '')).strip():
                return 'ref_fasta2 is required when ref_type is split'
        if aligner == 'bwa':
            stranded = str(inputs.get('stranded', 'fw') or 'fw')
            if stranded not in cls.STRANDED_OPTIONS:
                return f"stranded must be one of: {', '.join(cls.STRANDED_OPTIONS)}"
            for name, default in cls.BWA_INT_DEFAULTS.items():
                result = cls._validate_int_min(inputs, name, default, 1)
                if result is not True:
                    return result
        else:
            for name in ['align_score', 'chimeric_overlap']:
                result = cls._validate_int_min(inputs, name, 10 if name == 'align_score' else 2, 1)
                if result is not True:
                    return result
        result = cls._validate_int_min(inputs, 'threads', 4, 1)
        if result is not True:
            return result
        return True


class ChiraMergeNode(CommandNode):
    """Merge ChiRA read alignments into loci."""
    NODE_ID = 'chira_merge'
    DISPLAY_NAME = 'ChiRA merge'
    REQUIRED_CONDA_PACKAGES = ['chira']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Merge overlapping ChiRA read alignments into read-concentrated loci.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ChiRA', 'ChiRA merge', 'chira_merge', 'chira_merge.py', 'read-concentrated loci', 'chimeric read loci', 'blockbuster']
    RETURN_TYPES = ('BED', 'TSV')
    RETURN_NAMES = ('segments_bed', 'merged_bed')
    REQUIRED_EXECUTABLES = ['chira_merge.py']
    DOCUMENTATION_URL = CHIRA_DOCUMENTATION_URL
    CITATION_DOIS = [CHIRA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHIRA_CITATION_DOI}']
    CITATION_TEXT = CHIRA_CITATION_TEXT
    VERSION = '1.4.3+galaxy0'
    SHELL = True
    ANNOTATION_CHOICES = ['yes', 'no']
    MERGE_MODES = ['overlap', 'blockbuster']
    REF_TYPES = ['single', 'split']

    @classmethod
    def _annotation_choice(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('annotation_choice', inputs.get('choice', 'no')) or 'no')

    @classmethod
    def _merge_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('merge_mode', inputs.get('mode', 'overlap')) or 'overlap')

    @classmethod
    def _ref_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('ref_type', 'single') or 'single')

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {'', 'false', '0', 'no', 'off'}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ['chira_merge.py', '-b', str(inputs.get('alignments', ''))]
        if cls._annotation_choice(inputs) == 'yes':
            cmd.extend(['-g', str(inputs.get('gtf', ''))])
        cmd.extend(['-so', str(inputs.get('segment_overlap', 0.7)), '-lt', str(inputs.get('length_threshold', 0.9)), '-ao', str(inputs.get('alignment_overlap', 0.7))])
        if cls._merge_mode(inputs) == 'blockbuster':
            cmd.extend(['-bb', '-d', str(inputs.get('distance', 30)), '-mc', str(inputs.get('min_cluster_height', 10)), '-mb', str(inputs.get('min_block_height', 10)), '-sc', str(inputs.get('scale', 0.1))])
        else:
            cmd.extend(['-ls', str(inputs.get('min_locus_size', 1))])
        if cls._ref_type(inputs) == 'split':
            cmd.extend(['-f1', str(inputs.get('ref_fasta1', '')), '-f2', str(inputs.get('ref_fasta2', ''))])
        if cls._bool_flag(inputs.get('chimeric_only', False)):
            cmd.append('-c')
        cmd.extend(['-o', './'])
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'segments.bed', out / 'merged.bed']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'alignments': ('BED', {'description': 'ChiRA alignment BED file'}), 'annotation_choice': ('STRING', {'default': 'no', 'options': cls.ANNOTATION_CHOICES}), 'merge_mode': ('STRING', {'default': 'overlap', 'options': cls.MERGE_MODES}), 'ref_type': ('STRING', {'default': 'single', 'options': cls.REF_TYPES})}, 'optional': {'gtf': ('GTF', {'default': '', 'description': 'GTF/GFF annotation for genomic coordinate conversion'}), 'segment_overlap': ('FLOAT', {'default': 0.7, 'min': 0, 'max': 1}), 'length_threshold': ('FLOAT', {'default': 0.9, 'min': 0, 'max': 1}), 'alignment_overlap': ('FLOAT', {'default': 0.7, 'min': 0, 'max': 1}), 'min_locus_size': ('INT', {'default': 1, 'min': 1}), 'distance': ('INT', {'default': 30, 'min': 0}), 'min_cluster_height': ('INT', {'default': 10, 'min': 0}), 'min_block_height': ('INT', {'default': 10, 'min': 0}), 'scale': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 1}), 'ref_fasta1': ('FASTA', {'default': '', 'description': 'First split-reference FASTA'}), 'ref_fasta2': ('FASTA', {'default': '', 'description': 'Second split-reference FASTA'}), 'chimeric_only': ('BOOLEAN', {'default': False})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], name: str, default: float) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f'{name} must be numeric'
        if not 0 <= value <= 1:
            return f'{name} must be between 0 and 1'
        return True

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], name: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f'{name} must be an integer'
        if value < minimum:
            return f'{name} must be >= {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('alignments', '')).strip():
            return 'alignments is required'
        annotation_choice = cls._annotation_choice(inputs)
        if annotation_choice not in cls.ANNOTATION_CHOICES:
            return f"annotation_choice must be one of: {', '.join(cls.ANNOTATION_CHOICES)}"
        if annotation_choice == 'yes' and (not str(inputs.get('gtf', '')).strip()):
            return 'gtf is required when annotation_choice is yes'
        merge_mode = cls._merge_mode(inputs)
        if merge_mode not in cls.MERGE_MODES:
            return f"merge_mode must be one of: {', '.join(cls.MERGE_MODES)}"
        ref_type = cls._ref_type(inputs)
        if ref_type not in cls.REF_TYPES:
            return f"ref_type must be one of: {', '.join(cls.REF_TYPES)}"
        if ref_type == 'split':
            if not str(inputs.get('ref_fasta1', '')).strip():
                return 'ref_fasta1 is required when ref_type is split'
            if not str(inputs.get('ref_fasta2', '')).strip():
                return 'ref_fasta2 is required when ref_type is split'
        for name, default in {'segment_overlap': 0.7, 'length_threshold': 0.9, 'alignment_overlap': 0.7}.items():
            result = cls._validate_float_range(inputs, name, default)
            if result is not True:
                return result
        if merge_mode == 'overlap':
            result = cls._validate_int_min(inputs, 'min_locus_size', 1, 1)
            if result is not True:
                return result
        else:
            for name, default in {'distance': 30, 'min_cluster_height': 10, 'min_block_height': 10}.items():
                result = cls._validate_int_min(inputs, name, default, 0)
                if result is not True:
                    return result
            result = cls._validate_float_range(inputs, 'scale', 0.1)
            if result is not True:
                return result
        return True


class ChiraQuantifyNode(CommandNode):
    """Quantify ChiRA read-concentrated loci."""
    NODE_ID = 'chira_quantify'
    DISPLAY_NAME = 'ChiRA quantify'
    REQUIRED_CONDA_PACKAGES = ['chira']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Create and quantify ChiRA read-concentrated loci from merged alignments.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ChiRA', 'ChiRA quantify', 'chira_quantify', 'chira_quantify.py', 'read-concentrated loci', 'CRL', 'CRL TPM', 'TPM']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('loci',)
    REQUIRED_EXECUTABLES = ['chira_quantify.py']
    DOCUMENTATION_URL = CHIRA_DOCUMENTATION_URL
    CITATION_DOIS = [CHIRA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHIRA_CITATION_DOI}']
    CITATION_TEXT = CHIRA_CITATION_TEXT
    VERSION = '1.4.3+galaxy0'
    SHELL = True

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.lower() not in {'', 'false', '0', 'no', 'off'}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ['chira_quantify.py', '-b', str(inputs.get('segments', '')), '-m', str(inputs.get('merged', '')), '-cs', str(inputs.get('crl_share', 0.7)), '-ls', str(inputs.get('min_locus_size', 10)), '-e', str(inputs.get('em_threshold', 1e-05))]
        if cls._bool_flag(inputs.get('crl', True)):
            cmd.append('-crl')
        cmd.extend(['-o', './'])
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'loci.counts']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'segments': ('BED', {'description': 'BED file of aligned ChiRA segments'}), 'merged': ('TSV', {'description': 'Tabular file of merged ChiRA alignments'})}, 'optional': {'crl_share': ('FLOAT', {'default': 0.7, 'min': 0, 'max': 1}), 'min_locus_size': ('INT', {'default': 10, 'min': 1}), 'em_threshold': ('FLOAT', {'default': 1e-05, 'min': 0}), 'crl': ('BOOLEAN', {'default': True, 'description': 'Create and quantify CRLs'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], name: str, default: float) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f'{name} must be numeric'
        if not 0 <= value <= 1:
            return f'{name} must be between 0 and 1'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('segments', '')).strip():
            return 'segments is required'
        if not str(inputs.get('merged', '')).strip():
            return 'merged is required'
        result = cls._validate_float_range(inputs, 'crl_share', 0.7)
        if result is not True:
            return result
        try:
            min_locus_size = int(inputs.get('min_locus_size', 10))
        except (TypeError, ValueError):
            return 'min_locus_size must be an integer'
        if min_locus_size < 1:
            return 'min_locus_size must be >= 1'
        try:
            em_threshold = float(inputs.get('em_threshold', 1e-05))
        except (TypeError, ValueError):
            return 'em_threshold must be numeric'
        if em_threshold < 0:
            return 'em_threshold must be >= 0'
        return True


class ChiraExtractNode(CommandNode):
    """Extract ChiRA chimeric alignments and interaction summaries."""
    NODE_ID = 'chira_extract'
    DISPLAY_NAME = 'ChiRA extract'
    REQUIRED_CONDA_PACKAGES = ['chira']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Extract best ChiRA chimeric alignments and optionally summarize interactions.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ChiRA', 'ChiRA extract', 'chira_extract', 'chira_extract.py', 'chimeric reads', 'chimeric alignments', 'RNA-RNA interactions', 'CRL', 'IntaRNA']
    RETURN_TYPES = ('TSV', 'TSV')
    RETURN_NAMES = ('chimeras', 'interactions')
    REQUIRED_EXECUTABLES = ['chira_extract.py']
    DOCUMENTATION_URL = CHIRA_DOCUMENTATION_URL
    CITATION_DOIS = [CHIRA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHIRA_CITATION_DOI}']
    CITATION_TEXT = CHIRA_CITATION_TEXT
    VERSION = '1.4.3+galaxy1'
    SHELL = True
    ANNOTATION_CHOICES = ['yes', 'no']
    FASTA_SOURCE_OPTIONS = ['history', 'preloaded']
    REF_TYPES = ['split', 'single']
    INTARNA_MODES = ['H', 'M', 'S']

    @classmethod
    def _annotation_choice(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('annot_choice', inputs.get('annotation_choice', 'no')) or 'no')

    @classmethod
    def _fasta_source_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('fasta_source_selector', 'history') or 'history')

    @classmethod
    def _ref_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('ref_type', 'split') or 'split')

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {'', 'false', '0', 'no', 'off'}
        return bool(value)

    @classmethod
    def _genomic_fasta(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('genomic_fasta', inputs.get('fasta', inputs.get('fasta_id', ''))) or '')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(['mkdir', '-p', out]), f'cd {shlex.quote(out)}']
        annot_choice = cls._annotation_choice(inputs)
        hybridize = cls._bool_flag(inputs.get('hybridize', False))
        genomic_ref = ''
        if annot_choice == 'yes':
            if cls._fasta_source_selector(inputs) == 'history':
                genomic_fasta = cls._genomic_fasta(inputs)
                if genomic_fasta:
                    commands.append(_shell_join(['ln', '-s', genomic_fasta, 'genome.fa']))
                    genomic_ref = 'genome.fa'
            else:
                genomic_ref = cls._genomic_fasta(inputs)
        cmd = ['chira_extract.py', '--loci', str(inputs.get('loci', ''))]
        if annot_choice == 'yes':
            cmd.extend(['--gtf', str(inputs.get('gtf', ''))])
            if hybridize:
                cmd.extend(['--ref', genomic_ref])
        cmd.extend(['--tpm_cutoff', str(inputs.get('tpm_cutoff', 0)), '--score_cutoff', str(inputs.get('score_cutoff', 0)), '--chimeric_overlap', str(inputs.get('chimeric_overlap', 2))])
        if cls._ref_type(inputs) == 'single':
            cmd.extend(['-f1', str(inputs.get('ref_fasta', ''))])
        else:
            cmd.extend(['-f1', str(inputs.get('ref_fasta1', '')), '-f2', str(inputs.get('ref_fasta2', ''))])
        if hybridize:
            cmd.append('-r')
        if not cls._bool_flag(inputs.get('seed_interaction', True)):
            cmd.append('--no_seed')
        cmd.extend(['--seed_bp', str(inputs.get('seed_bp', 5)), '--seed_min_pu', str(inputs.get('seed_min_pu', 0)), '--accessibility', 'C' if cls._bool_flag(inputs.get('accessibility', False)) else 'N', '--acc_width', str(inputs.get('acc_width', 150)), '--intarna_mode', str(inputs.get('intarna_mode', 'H') or 'H'), '--temperature', str(inputs.get('temperature', 37))])
        if cls._bool_flag(inputs.get('summarize', False)):
            cmd.append('-s')
        cmd.extend(['--processes', f"${{GALAXY_SLOTS:-{inputs.get('threads', 2)}}}", '--out', './'])
        command = _shell_join(cmd).replace("'${GALAXY_SLOTS:-", '${GALAXY_SLOTS:-').replace("}'", '}')
        commands.append(command)
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'chimeras']
        if cls._bool_flag(inputs.get('summarize', False)):
            outputs.append(out / 'interactions')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'loci': ('TSV', {'description': 'Tabular file containing ChiRA CRL information'}), 'annot_choice': ('STRING', {'default': 'no', 'options': cls.ANNOTATION_CHOICES}), 'ref_type': ('STRING', {'default': 'split', 'options': cls.REF_TYPES})}, 'optional': {'gtf': ('GTF', {'default': '', 'description': 'GTF/GFF annotation for genomic loci'}), 'fasta_source_selector': ('STRING', {'default': 'history', 'options': cls.FASTA_SOURCE_OPTIONS}), 'genomic_fasta': ('FASTA', {'default': '', 'description': 'Genomic FASTA for annotated hybridization'}), 'tpm_cutoff': ('FLOAT', {'default': 0, 'min': 0, 'max': 1}), 'score_cutoff': ('FLOAT', {'default': 0, 'min': 0, 'max': 2}), 'chimeric_overlap': ('INT', {'default': 2, 'min': 0}), 'ref_fasta1': ('FASTA', {'default': '', 'description': 'First split-reference FASTA'}), 'ref_fasta2': ('FASTA', {'default': '', 'description': 'Second split-reference FASTA'}), 'ref_fasta': ('FASTA', {'default': '', 'description': 'Single-reference FASTA'}), 'hybridize': ('BOOLEAN', {'default': False}), 'intarna_mode': ('STRING', {'default': 'H', 'options': cls.INTARNA_MODES}), 'seed_interaction': ('BOOLEAN', {'default': True}), 'seed_bp': ('INT', {'default': 5, 'min': 2, 'max': 20}), 'seed_min_pu': ('FLOAT', {'default': 0, 'min': 0, 'max': 1}), 'accessibility': ('BOOLEAN', {'default': False}), 'acc_width': ('INT', {'default': 150, 'min': 0, 'max': 99999}), 'temperature': ('FLOAT', {'default': 37, 'min': 0, 'max': 100}), 'summarize': ('BOOLEAN', {'default': False}), 'threads': ('INT', {'default': 2, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], name: str, default: float, minimum: float, maximum: float) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f'{name} must be numeric'
        if not minimum <= value <= maximum:
            return f'{name} must be between {minimum:g} and {maximum:g}'
        return True

    @classmethod
    def _validate_int_range(cls, inputs: dict[str, Any], name: str, default: int, minimum: int, maximum: int) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f'{name} must be an integer'
        if not minimum <= value <= maximum:
            return f'{name} must be between {minimum} and {maximum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('loci', '')).strip():
            return 'loci is required'
        annot_choice = cls._annotation_choice(inputs)
        if annot_choice not in cls.ANNOTATION_CHOICES:
            return f"annot_choice must be one of: {', '.join(cls.ANNOTATION_CHOICES)}"
        fasta_source = cls._fasta_source_selector(inputs)
        if fasta_source not in cls.FASTA_SOURCE_OPTIONS:
            return f"fasta_source_selector must be one of: {', '.join(cls.FASTA_SOURCE_OPTIONS)}"
        hybridize = cls._bool_flag(inputs.get('hybridize', False))
        if annot_choice == 'yes':
            if not str(inputs.get('gtf', '')).strip():
                return 'gtf is required when annot_choice is yes'
            if hybridize and (not cls._genomic_fasta(inputs).strip()):
                return f'genomic_fasta is required when annot_choice is yes, hybridize is true, and fasta_source_selector is {fasta_source}'
        for name, default, minimum, maximum in [('tpm_cutoff', 0, 0, 1), ('score_cutoff', 0, 0, 2), ('seed_min_pu', 0, 0, 1), ('temperature', 37, 0, 100)]:
            result = cls._validate_float_range(inputs, name, default, minimum, maximum)
            if result is not True:
                return result
        for name, default, minimum, maximum in [('chimeric_overlap', 2, 0, 99999), ('seed_bp', 5, 2, 20), ('acc_width', 150, 0, 99999), ('threads', 2, 1, 128)]:
            result = cls._validate_int_range(inputs, name, default, minimum, maximum)
            if result is not True:
                return result
        ref_type = cls._ref_type(inputs)
        if ref_type not in cls.REF_TYPES:
            return f"ref_type must be one of: {', '.join(cls.REF_TYPES)}"
        if ref_type == 'single':
            if not str(inputs.get('ref_fasta', '')).strip():
                return 'ref_fasta is required when ref_type is single'
        else:
            if not str(inputs.get('ref_fasta1', '')).strip():
                return 'ref_fasta1 is required when ref_type is split'
            if not str(inputs.get('ref_fasta2', '')).strip():
                return 'ref_fasta2 is required when ref_type is split'
        intarna_mode = str(inputs.get('intarna_mode', 'H') or 'H')
        if intarna_mode not in cls.INTARNA_MODES:
            return f"intarna_mode must be one of: {', '.join(cls.INTARNA_MODES)}"
        return True
