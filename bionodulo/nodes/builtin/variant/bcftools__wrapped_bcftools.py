"""bcftools — variant node(s). One tool per file (extracted from wrapped_bcftools.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BCFtoolsMpileupNode(CommandNode):
    """Generate VCF/BCF genotype likelihoods from BAM or CRAM alignments."""
    NODE_ID = 'bcftools_mpileup'
    DISPLAY_NAME = 'BCFtools Mpileup'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib', 'samtools']
    CATEGORY = 'variant'
    DESCRIPTION = 'Generate VCF or BCF containing genotype likelihoods for one or multiple BAM/CRAM alignment files.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'mpileup', 'genotype likelihoods', 'BAM CRAM pileup', 'variant pileup']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('mpileup_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools', 'samtools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#mpileup'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22+galaxy0'
    SHELL = True
    REFERENCE_SOURCE_OPTIONS = ['history', 'cached', 'none']
    INDEL_CALLING_OPTIONS = ['perform_indel_calling_def', 'perform_indel_calling', 'do_not_perform_indel_calling']
    AMBIG_READS_OPTIONS = ['', 'drop', 'incAD', 'incAD0']
    BAQ_OPTIONS = ['', '--no-BAQ', '--redo-BAQ']
    OUTPUT_TYPES = ['b', 'u', 'z', 'v']
    OUTPUT_TAG_OPTIONS = ['DP', 'AD', 'ADF', 'ADR', 'INFO/AD', 'INFO/ADF', 'INFO/ADR', 'SP', 'DV', 'QS', 'DP4', 'DPR', 'INFO/DPR']

    @staticmethod
    def _selected(value: Any) -> bool:
        return value is not None and str(value) != ''

    @classmethod
    def _input_bams(cls, inputs: dict[str, Any]) -> list[str]:
        bams = _as_list(inputs.get('input_bams'))
        if bams:
            return bams
        return _as_list(inputs.get('input_bam', inputs.get('bam')))

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('reference_source', inputs.get('reference_source_selector', 'history')) or 'history')

    @classmethod
    def _reference(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('reference', inputs.get('ref_file', inputs.get('fasta_ref', ''))) or '')

    @classmethod
    def _flag_sum(cls, value: Any) -> int:
        total = 0
        for flag in _as_list(value):
            for part in str(flag).split(','):
                if part.strip():
                    total += int(part)
        return total

    @classmethod
    def _add_reference(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._reference_source(inputs) == 'none':
            cmd.append('--non-reference')
            return
        _add_if_value(cmd, '--fasta-ref', cls._reference(inputs))

    @classmethod
    def _add_indel_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        mode = str(inputs.get('perform_indel_calling', 'perform_indel_calling_def') or 'perform_indel_calling_def')
        if mode == 'do_not_perform_indel_calling':
            cmd.append('--skip-indels')
        elif mode == 'perform_indel_calling':
            _add_if_value(cmd, '-o', inputs.get('gap_open_sequencing_error_probability'))
            _add_if_value(cmd, '-e', inputs.get('gap_extension_sequencing_error_probability'))
            _add_if_value(cmd, '-h', inputs.get('coefficient_for_modeling_homopolymer_errors'))
            _add_if_value(cmd, '-L', inputs.get('skip_indel_calling_above_sample_depth'))
            _add_if_value(cmd, '-m', inputs.get('minimum_gapped_reads_for_indel_candidates'))
            _add_if_value(cmd, '--open-prob', inputs.get('open_seq_error_probability'))
            _add_if_value(cmd, '-F', inputs.get('minimum_gapped_read_fraction'))
            if inputs.get('gapped_read_per_sample'):
                cmd.append('-p')
            platforms = ','.join(_as_list(inputs.get('platforms', inputs.get('platform_list'))))
            _add_if_value(cmd, '-P', platforms)
        _add_if_value(cmd, '--ambig-reads', inputs.get('ambig_reads'))
        _add_if_value(cmd, '--indel-bias', inputs.get('indel_bias'))
        _add_if_value(cmd, '--indel-size', inputs.get('indel_size'))

    @classmethod
    def _add_filter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        for name, flag in (('skip_all_set', '--skip-all-set'), ('skip_any_set', '--skip-any-set'), ('skip_all_unset', '--skip-all-unset'), ('skip_any_unset', '--skip-any-unset')):
            value = cls._flag_sum(inputs.get(name))
            if value:
                cmd.extend([flag, str(value)])
        cmd.extend(['-d', str(inputs.get('max_reads_per_bam', inputs.get('max_depth', 250)) or 250)])
        if inputs.get('ignore_overlaps'):
            cmd.append('-x')
        if inputs.get('skip_anomalous_read_pairs'):
            cmd.append('-A')
        baq = str(inputs.get('baq', '') or '')
        if baq:
            cmd.append(baq)
        _add_if_value(cmd, '-q', inputs.get('minimum_mapping_quality'))
        _add_if_value(cmd, '-Q', inputs.get('minimum_base_quality', inputs.get('min_bq')))
        _add_if_value(cmd, '-C', inputs.get('coefficient_for_downgrading'))
        if inputs.get('ignore_read_groups'):
            cmd.append('--ignore-RG')
        read_groups = inputs.get('read_groups')
        if cls._selected(read_groups):
            prefix = '^' if inputs.get('exclude_read_groups') else ''
            cmd.extend(['-G', f'{prefix}{read_groups}'])

    @classmethod
    def _add_samples(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._selected(inputs.get('samples')):
            prefix = '^' if inputs.get('invert_samples') else ''
            cmd.extend(['--samples', f"{prefix}{inputs['samples']}"])
        if cls._selected(inputs.get('samples_file')):
            prefix = '^' if inputs.get('invert_samples_file') else ''
            cmd.extend(['--samples-file', f"{prefix}{inputs['samples_file']}"])

    @classmethod
    def _add_targets(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        prefix = '^' if inputs.get('invert_targets') or inputs.get('invert_targets_file') else ''
        if cls._selected(inputs.get('targets')):
            cmd.extend(['--targets', f"{prefix}{inputs['targets']}"])
        if cls._selected(inputs.get('targets_file')):
            cmd.extend(['--targets-file', f"{prefix}{inputs['targets_file']}"])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'mpileup']
        cls._add_reference(cmd, inputs)
        cls._add_indel_options(cmd, inputs)
        cls._add_filter_options(cmd, inputs)
        output_tags = ','.join(_as_list(inputs.get('output_tags')))
        _add_if_value(cmd, '--annotate', output_tags)
        _add_if_value(cmd, '--gvcf', inputs.get('gvcf'))
        cls._add_samples(cmd, inputs)
        _add_if_value(cmd, '--regions', inputs.get('regions'))
        _add_if_value(cmd, '--regions-file', inputs.get('regions_file'))
        cls._add_targets(cmd, inputs)
        threads = inputs.get('threads')
        if cls._selected(threads) and str(threads) != '0':
            cmd.extend(['--threads', str(threads)])
        _bcftools_add_output_type(cmd, inputs)
        cmd.extend(cls._input_bams(inputs))
        _add_shell_redirect(cmd, f'{_out(inputs)}/mpileup{_bcftools_variant_suffix(inputs)}')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f'mpileup{_bcftools_variant_suffix(inputs)}', output_dir)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_bams(inputs):
            return 'at least one input BAM/CRAM is required'
        reference_source = cls._reference_source(inputs)
        if reference_source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"reference_source must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        if reference_source in {'history', 'cached'} and (not cls._reference(inputs).strip()):
            return f'reference is required when reference_source is {reference_source}'
        indel_mode = str(inputs.get('perform_indel_calling', 'perform_indel_calling_def') or 'perform_indel_calling_def')
        if indel_mode not in cls.INDEL_CALLING_OPTIONS:
            return f"perform_indel_calling must be one of: {', '.join(cls.INDEL_CALLING_OPTIONS)}"
        ambig_reads = str(inputs.get('ambig_reads', '') or '')
        if ambig_reads not in cls.AMBIG_READS_OPTIONS:
            return 'ambig_reads must be one of: drop, incAD, incAD0'
        baq = str(inputs.get('baq', '') or '')
        if baq not in cls.BAQ_OPTIONS:
            return 'baq must be one of: --no-BAQ, --redo-BAQ'
        output_type = str(inputs.get('output_type', 'z') or 'z')
        if output_type not in cls.OUTPUT_TYPES:
            return f"output_type must be one of: {', '.join(cls.OUTPUT_TYPES)}"
        for output_tag in _as_list(inputs.get('output_tags')):
            if output_tag not in cls.OUTPUT_TAG_OPTIONS:
                return f"output_tags must contain only: {', '.join(cls.OUTPUT_TAG_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_bams': ('BAM_LIST', {'multiple': True, 'description': 'One or more indexed BAM/CRAM alignment files'})}, 'optional': {'reference_source': ('STRING', {'default': 'history', 'options': cls.REFERENCE_SOURCE_OPTIONS, 'description': 'Reference source for mpileup, or none for --non-reference'}), 'reference': ('FASTA', {'description': 'Reference FASTA for BAM/CRAM pileup'}), 'perform_indel_calling': ('STRING', {'default': 'perform_indel_calling_def', 'options': cls.INDEL_CALLING_OPTIONS, 'description': 'Whether to use default, advanced, or disabled INDEL calling'}), 'gap_open_sequencing_error_probability': ('INT', {'default': '', 'description': 'Advanced -o value'}), 'gap_extension_sequencing_error_probability': ('INT', {'default': '', 'description': 'Advanced -e value'}), 'coefficient_for_modeling_homopolymer_errors': ('INT', {'default': '', 'description': 'Advanced -h value'}), 'skip_indel_calling_above_sample_depth': ('INT', {'default': '', 'description': 'Advanced -L value'}), 'minimum_gapped_reads_for_indel_candidates': ('INT', {'default': '', 'description': 'Advanced -m value'}), 'open_seq_error_probability': ('INT', {'default': '', 'description': 'Advanced --open-prob value'}), 'minimum_gapped_read_fraction': ('FLOAT', {'default': '', 'description': 'Advanced -F value'}), 'gapped_read_per_sample': ('BOOLEAN', {'default': False, 'description': 'Apply gapped-read thresholds per sample'}), 'platforms': ('STRING_LIST', {'default': [], 'description': 'Comma-joined platforms for INDEL candidates'}), 'ambig_reads': ('STRING', {'default': '', 'options': cls.AMBIG_READS_OPTIONS, 'description': 'Ambiguous indel read handling'}), 'indel_bias': ('FLOAT', {'default': '', 'min': 0, 'description': 'Indel bias score adjustment'}), 'indel_size': ('INT', {'default': '', 'min': 0, 'description': 'Indel window size'}), 'max_reads_per_bam': ('INT', {'default': 250, 'min': 1, 'description': 'Maximum reads per BAM'}), 'ignore_overlaps': ('BOOLEAN', {'default': False, 'description': 'Disable read-pair overlap detection'}), 'skip_anomalous_read_pairs': ('BOOLEAN', {'default': False, 'description': 'Do not skip anomalous read pairs'}), 'skip_all_set': ('STRING_LIST', {'default': [], 'description': 'Skip reads with all listed FLAG bits set'}), 'skip_any_set': ('STRING_LIST', {'default': [], 'description': 'Skip reads with any listed FLAG bit set'}), 'skip_all_unset': ('STRING_LIST', {'default': [], 'description': 'Skip reads with all listed FLAG bits unset'}), 'skip_any_unset': ('STRING_LIST', {'default': [], 'description': 'Skip reads with any listed FLAG bit unset'}), 'baq': ('STRING', {'default': '', 'options': cls.BAQ_OPTIONS, 'description': 'BAQ handling'}), 'minimum_mapping_quality': ('INT', {'default': '', 'min': 0, 'description': 'Minimum mapping quality'}), 'minimum_base_quality': ('INT', {'default': '', 'min': 0, 'description': 'Minimum base quality'}), 'coefficient_for_downgrading': ('INT', {'default': '', 'min': 0, 'description': 'Mapping quality downgrade coefficient'}), 'read_groups': ('TSV', {'description': 'Read groups to include or exclude'}), 'exclude_read_groups': ('BOOLEAN', {'default': False, 'description': 'Exclude read groups instead of including them'}), 'ignore_read_groups': ('BOOLEAN', {'default': False, 'description': 'Ignore read group tags'}), 'output_tags': ('STRING_LIST', {'options': cls.OUTPUT_TAG_OPTIONS, 'description': 'Annotation tags to emit'}), 'gvcf': ('STRING', {'default': '', 'description': 'Depth ranges for gVCF reference blocks'}), 'samples': ('STRING', {'default': '', 'description': 'Comma-separated samples to include or exclude'}), 'samples_file': ('TSV', {'description': 'File of samples to include or exclude'}), 'invert_samples': ('BOOLEAN', {'default': False, 'description': 'Exclude samples listed in samples'}), 'invert_samples_file': ('BOOLEAN', {'default': False, 'description': 'Exclude samples listed in samples_file'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict pileup to regions'}), 'regions_file': ('BED', {'description': 'Restrict pileup to regions from file'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict pileup to targets'}), 'targets_file': ('TSV', {'description': 'Restrict pileup to targets from file'}), 'invert_targets': ('BOOLEAN', {'default': False, 'description': 'Invert inline targets'}), 'invert_targets_file': ('BOOLEAN', {'default': False, 'description': 'Invert targets file'}), 'output_type': ('STRING', {'default': 'z', 'options': cls.OUTPUT_TYPES, 'description': 'BCFtools output type'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'}), 'bam': ('BAM', {'description': 'Compatibility alias for input_bams', 'advanced': True}), 'input_bam': ('BAM', {'description': 'Compatibility alias for input_bams', 'advanced': True}), 'max_depth': ('INT', {'default': '', 'min': 1, 'description': 'Compatibility alias for max_reads_per_bam', 'advanced': True}), 'min_bq': ('INT', {'default': '', 'min': 0, 'description': 'Compatibility alias for minimum_base_quality', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsCallNode(CommandNode):
    """Call SNP and indel variants from genotype likelihoods in VCF/BCF."""
    NODE_ID = 'bcftools_call'
    DISPLAY_NAME = 'BCFtools Call'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Call SNP and indel variants from genotype likelihoods in VCF/BCF using bcftools call.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'call', 'variant calling', 'SNP indel calling', 'multiallelic caller', 'consensus caller']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('called_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#call'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22+galaxy0'
    SHELL = True
    METHODS = ['multiallelic', 'consensus']
    MULTIALLELIC_CONSTRAINTS = ['none', 'alleles', 'trio']
    CONSENSUS_CONSTRAINTS = ['none', 'trio']
    OUTPUT_TYPES = ['b', 'u', 'z', 'v']
    PLOIDY_OPTIONS = ['', 'GRCh37', 'GRCh38', 'X', 'Y', '1']
    SKIP_VARIANTS_OPTIONS = ['', 'indels', 'snps']
    OUTPUT_TAG_OPTIONS = ['INFO/PV4', 'FORMAT/GQ', 'FORMAT/GP']

    @staticmethod
    def _selected(value: Any) -> bool:
        return value is not None and str(value) != ''

    @classmethod
    def _method(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('method', 'multiallelic') or 'multiallelic')

    @classmethod
    def _constrain(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('constrain', 'none') or 'none')

    @classmethod
    def _add_targets(cls, cmd: list[str], inputs: dict[str, Any], *, include_overlap: bool=True) -> None:
        prefix = '^' if inputs.get('invert_targets') or inputs.get('invert_targets_file') else ''
        if cls._selected(inputs.get('targets')):
            cmd.extend(['--targets', f"{prefix}{inputs['targets']}"])
        if cls._selected(inputs.get('targets_file')):
            cmd.extend(['--targets-file', f"{prefix}{inputs['targets_file']}"])
        if include_overlap:
            _add_if_value(cmd, '--targets-overlap', inputs.get('targets_overlap'))

    @classmethod
    def _add_novel_rate(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        novel_rate = [str(inputs[key]) for key in ('novel_rate_snp', 'novel_rate_del', 'novel_rate_ins') if cls._selected(inputs.get(key))]
        if novel_rate:
            cmd.extend(['--novel-rate', ','.join(novel_rate)])

    @classmethod
    def _add_samples(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._selected(inputs.get('samples')):
            prefix = '^' if inputs.get('invert_samples') else ''
            cmd.extend(['--samples', f"{prefix}{inputs['samples']}"])
        if cls._selected(inputs.get('samples_file')):
            prefix = '^' if inputs.get('invert_samples_file') else ''
            cmd.extend(['--samples-file', f"{prefix}{inputs['samples_file']}"])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'call']
        method = cls._method(inputs)
        constrain = cls._constrain(inputs)
        if method == 'consensus':
            cmd.append('-c')
            _add_if_value(cmd, '--pval-threshold', inputs.get('pval_threshold'))
            if constrain == 'trio':
                cmd.extend(['--constrain', 'trio'])
                cls._add_novel_rate(cmd, inputs)
            cls._add_targets(cmd, inputs)
        else:
            cmd.append('-m')
            _add_if_value(cmd, '--gvcf', inputs.get('gvcf'))
            _add_if_value(cmd, '--prior-freqs', inputs.get('prior_freqs'))
            _add_if_value(cmd, '--prior', inputs.get('prior'))
            if constrain == 'alleles':
                cmd.extend(['--constrain', 'alleles'])
                if inputs.get('insert_missed'):
                    cmd.append('--insert-missed')
                cls._add_targets(cmd, inputs)
            else:
                if constrain == 'trio':
                    cmd.extend(['--constrain', 'trio'])
                    cls._add_novel_rate(cmd, inputs)
                cls._add_targets(cmd, inputs)
        _add_if_value(cmd, '--regions', inputs.get('regions'))
        _add_if_value(cmd, '--regions-overlap', inputs.get('regions_overlap'))
        cls._add_samples(cmd, inputs)
        _add_if_value(cmd, '--ploidy', inputs.get('ploidy'))
        _add_if_value(cmd, '--ploidy-file', inputs.get('ploidy_file'))
        if inputs.get('group_samples'):
            cmd.extend(['--group-samples', '-'])
        if inputs.get('keep_alts'):
            cmd.append('--keep-alts')
        _add_if_value(cmd, '--format-fields', inputs.get('format_fields'))
        if inputs.get('keep_masked_ref'):
            cmd.append('--keep-masked-ref')
        _add_if_value(cmd, '--skip-variants', inputs.get('skip_variants'))
        if inputs.get('variants_only'):
            cmd.append('--variants-only')
        output_tags = ','.join(_as_list(inputs.get('output_tags')))
        _add_if_value(cmd, '--annotate', output_tags)
        _bcftools_add_output_type(cmd, inputs)
        _add_if_value(cmd, '--threads', inputs.get('threads'))
        cmd.append(str(inputs.get('input_file', '')))
        _add_shell_redirect(cmd, f'{_out(inputs)}/called{_bcftools_variant_suffix(inputs)}')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f'called{_bcftools_variant_suffix(inputs)}', output_dir)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'input_file is required'
        method = cls._method(inputs)
        if method not in cls.METHODS:
            return f"method must be one of: {', '.join(cls.METHODS)}"
        constrain = cls._constrain(inputs)
        constraints = cls.CONSENSUS_CONSTRAINTS if method == 'consensus' else cls.MULTIALLELIC_CONSTRAINTS
        if constrain not in constraints:
            return f"constrain must be one of: {', '.join(constraints)}"
        if method == 'multiallelic' and constrain == 'alleles' and (not str(inputs.get('targets_file', '')).strip()):
            return 'targets_file is required when constrain is alleles'
        output_type = str(inputs.get('output_type', 'z') or 'z')
        if output_type not in cls.OUTPUT_TYPES:
            return f"output_type must be one of: {', '.join(cls.OUTPUT_TYPES)}"
        ploidy = str(inputs.get('ploidy', '') or '')
        if ploidy not in cls.PLOIDY_OPTIONS:
            return f"ploidy must be one of: {', '.join((option for option in cls.PLOIDY_OPTIONS if option))}"
        skip_variants = str(inputs.get('skip_variants', '') or '')
        if skip_variants not in cls.SKIP_VARIANTS_OPTIONS:
            return 'skip_variants must be one of: indels, snps'
        for output_tag in _as_list(inputs.get('output_tags')):
            if output_tag not in cls.OUTPUT_TAG_OPTIONS:
                return f"output_tags must contain only: {', '.join(cls.OUTPUT_TAG_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file with genotype likelihoods, usually from bcftools mpileup'})}, 'optional': {'method': ('STRING', {'default': 'multiallelic', 'options': cls.METHODS, 'description': 'Galaxy calling method'}), 'constrain': ('STRING', {'default': 'none', 'options': cls.MULTIALLELIC_CONSTRAINTS, 'description': 'Constrain genotypes for multiallelic or consensus calling'}), 'gvcf': ('INT', {'default': '', 'min': 0, 'description': 'Minimum per-sample depth for gVCF reference blocks'}), 'prior_freqs': ('STRING', {'default': '', 'description': 'INFO tags with prior allele frequencies, for example REF_AN,REF_AC'}), 'prior': ('FLOAT', {'default': '', 'description': 'Expected substitution rate prior'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict calling to target regions'}), 'targets_file': ('TSV', {'description': 'Target alleles or regions file'}), 'invert_targets': ('BOOLEAN', {'default': False, 'description': 'Invert inline targets'}), 'invert_targets_file': ('BOOLEAN', {'default': False, 'description': 'Invert targets file'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Target overlap mode'}), 'insert_missed': ('BOOLEAN', {'default': False, 'description': 'Output sites missed by mpileup but present in targets_file'}), 'novel_rate_snp': ('FLOAT', {'default': '', 'description': 'Novel SNP mutation rate for trio calling'}), 'novel_rate_del': ('FLOAT', {'default': '', 'description': 'Novel deletion mutation rate for trio calling'}), 'novel_rate_ins': ('FLOAT', {'default': '', 'description': 'Novel insertion mutation rate for trio calling'}), 'pval_threshold': ('FLOAT', {'default': '', 'description': 'Consensus caller P(ref|D) threshold'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict calling to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Region overlap mode'}), 'samples': ('STRING', {'default': '', 'description': 'Comma-separated samples to include or exclude'}), 'samples_file': ('TSV', {'description': 'File of samples to include or exclude'}), 'invert_samples': ('BOOLEAN', {'default': False, 'description': 'Exclude samples listed in samples'}), 'invert_samples_file': ('BOOLEAN', {'default': False, 'description': 'Exclude samples listed in samples_file'}), 'ploidy': ('STRING', {'default': '', 'options': cls.PLOIDY_OPTIONS, 'description': 'Predefined ploidy model'}), 'ploidy_file': ('TSV', {'description': 'CHROM,FROM,TO,SEX,PLOIDY ploidy file'}), 'group_samples': ('BOOLEAN', {'default': False, 'description': 'Group samples by population for single-sample calling'}), 'keep_alts': ('BOOLEAN', {'default': False, 'description': 'Keep alternate alleles seen in alignments'}), 'format_fields': ('STRING', {'default': '', 'description': 'Comma-separated FORMAT fields such as GQ,GP'}), 'keep_masked_ref': ('BOOLEAN', {'default': False, 'description': 'Output sites where REF is N'}), 'skip_variants': ('STRING', {'default': '', 'options': cls.SKIP_VARIANTS_OPTIONS, 'description': 'Skip indel or SNP sites'}), 'variants_only': ('BOOLEAN', {'default': False, 'description': 'Output variant sites only'}), 'output_tags': ('STRING_LIST', {'options': cls.OUTPUT_TAG_OPTIONS, 'description': 'Annotation tags to emit'}), 'output_type': ('STRING', {'default': 'z', 'options': cls.OUTPUT_TYPES, 'description': 'BCFtools output type'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsFilterNode(CommandNode):
    """Apply fixed-threshold filters to VCF/BCF records."""
    NODE_ID = 'bcftools_filter'
    DISPLAY_NAME = 'BCFtools Filter'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Apply fixed-threshold, expression, and optional soft filters to VCF/BCF records with bcftools filter.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'filter', 'fixed-threshold filters', 'variant filter', 'soft filter', 'filter vcf']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('filtered_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#filter'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22+galaxy0'
    SHELL = True
    OUTPUT_TYPES = ['b', 'u', 'z', 'v']
    MODE_OPTIONS = ['+', 'x']
    SET_GT_OPTIONS = ['', '.', '0']
    OVERLAP_OPTIONS = ['', '0', '1', '2']

    @staticmethod
    def _selected(value: Any) -> bool:
        return value is not None and str(value) != ''

    @classmethod
    def _input_file(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_file', inputs.get('vcf', '')) or '')

    @classmethod
    def _mode(cls, inputs: dict[str, Any]) -> str:
        return ''.join((part.replace(',', '') for part in _as_list(inputs.get('mode'))))

    @classmethod
    def _include(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get('include', inputs.get('expr'))

    @classmethod
    def _set_gts(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get('select_set_GTs', inputs.get('set_gt'))

    @classmethod
    def _add_targets(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        prefix = '^' if inputs.get('invert_targets') or inputs.get('invert_targets_file') else ''
        if cls._selected(inputs.get('targets')):
            cmd.extend(['--targets', f"{prefix}{inputs['targets']}"])
        if cls._selected(inputs.get('targets_file')):
            cmd.extend(['--targets-file', f"{prefix}{inputs['targets_file']}"])
        _add_if_value(cmd, '--targets-overlap', inputs.get('targets_overlap'))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'filter']
        _add_if_value(cmd, '--SnpGap', inputs.get('SnpGap', inputs.get('snp_gap')))
        _add_if_value(cmd, '--IndelGap', inputs.get('IndelGap', inputs.get('indel_gap')))
        mode = cls._mode(inputs)
        _add_if_value(cmd, '--mode', mode)
        if inputs.get('soft_filter_enabled', False) or cls._selected(inputs.get('soft_filter')):
            _add_if_value(cmd, '--soft-filter', inputs.get('soft_filter'))
            _add_if_value(cmd, '--mask', inputs.get('mask'))
            _add_if_value(cmd, '--mask-file', inputs.get('mask_file'))
            _add_if_value(cmd, '--mask-overlap', inputs.get('mask_overlap'))
        _add_if_value(cmd, '--set-GTs', cls._set_gts(inputs))
        _add_if_value(cmd, '--regions', inputs.get('regions'))
        _add_if_value(cmd, '--regions-file', inputs.get('regions_file'))
        _add_if_value(cmd, '--regions-overlap', inputs.get('regions_overlap'))
        cls._add_targets(cmd, inputs)
        _add_if_value(cmd, '--include', cls._include(inputs))
        _add_if_value(cmd, '--exclude', inputs.get('exclude'))
        _bcftools_add_output_type(cmd, inputs)
        _add_if_value(cmd, '--threads', inputs.get('threads'))
        cmd.append(cls._input_file(inputs))
        _add_shell_redirect(cmd, f'{_out(inputs)}/filtered{_bcftools_variant_suffix(inputs)}')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f'filtered{_bcftools_variant_suffix(inputs)}', output_dir)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_file(inputs).strip():
            return 'input_file is required'
        for mode in _as_list(inputs.get('mode')):
            if mode not in cls.MODE_OPTIONS:
                return f"mode must contain only: {', '.join(cls.MODE_OPTIONS)}"
        output_type = str(inputs.get('output_type', 'z') or 'z')
        if output_type not in cls.OUTPUT_TYPES:
            return f"output_type must be one of: {', '.join(cls.OUTPUT_TYPES)}"
        set_gts = str(cls._set_gts(inputs) or '')
        if set_gts not in cls.SET_GT_OPTIONS:
            return 'select_set_GTs must be one of: ., 0'
        if inputs.get('soft_filter_enabled', False) and (not str(inputs.get('soft_filter', '')).strip()):
            return 'soft_filter is required when soft filtering is enabled'
        for name in ('regions_overlap', 'targets_overlap', 'mask_overlap'):
            value = str(inputs.get(name, '') or '')
            if value not in cls.OVERLAP_OPTIONS:
                return f'{name} must be one of: 0, 1, 2'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file to filter'})}, 'optional': {'SnpGap': ('INT', {'default': '', 'min': 0, 'description': 'Filter SNPs within this many bp of an indel'}), 'IndelGap': ('INT', {'default': '', 'min': 0, 'description': 'Filter indel clusters separated by this many bp or fewer'}), 'mode': ('STRING_LIST', {'options': cls.MODE_OPTIONS, 'description': 'FILTER annotation mode flags'}), 'soft_filter_enabled': ('BOOLEAN', {'default': False, 'description': 'Enable soft-filter annotation'}), 'soft_filter': ('STRING', {'default': '', 'description': 'FILTER annotation label'}), 'mask': ('STRING', {'default': '', 'description': 'Mask regions for soft filtering'}), 'mask_file': ('BED', {'description': 'Mask regions file for soft filtering'}), 'mask_overlap': ('STRING', {'default': '', 'options': cls.OVERLAP_OPTIONS, 'description': 'Mask overlap mode'}), 'select_set_GTs': ('STRING', {'default': '', 'options': cls.SET_GT_OPTIONS, 'description': 'Set genotypes of failed samples'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict filtering to regions'}), 'regions_file': ('BED', {'description': 'Restrict filtering to regions from file'}), 'regions_overlap': ('STRING', {'default': '', 'options': cls.OVERLAP_OPTIONS, 'description': 'Region overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict filtering to targets'}), 'targets_file': ('TSV', {'description': 'Restrict filtering to targets from file'}), 'invert_targets': ('BOOLEAN', {'default': False, 'description': 'Invert inline targets'}), 'invert_targets_file': ('BOOLEAN', {'default': False, 'description': 'Invert targets file'}), 'targets_overlap': ('STRING', {'default': '', 'options': cls.OVERLAP_OPTIONS, 'description': 'Target overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'output_type': ('STRING', {'default': 'z', 'options': cls.OUTPUT_TYPES, 'description': 'BCFtools output type'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'}), 'vcf': ('VCF_GZ', {'description': 'Compatibility alias for input_file', 'advanced': True}), 'expr': ('STRING', {'default': '', 'description': 'Compatibility alias for include', 'advanced': True}), 'set_gt': ('STRING', {'default': '', 'description': 'Compatibility alias for select_set_GTs', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsStatsNode(CommandNode):
    """Parse VCF/BCF files and produce bcftools stats reports."""
    NODE_ID = 'bcftools_stats'
    DISPLAY_NAME = 'BCFtools Stats'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib', 'samtools', 'matplotlib-base', 'tectonic']
    CATEGORY = 'variant'
    DESCRIPTION = 'Parse VCF or BCF files with bcftools stats and optionally render plot-vcfstats summaries.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'stats', 'vcf stats', 'plot-vcfstats', 'variant statistics', 'genotype concordance']
    RETURN_TYPES = ('STATS_FILE', 'PDF_REPORT')
    RETURN_NAMES = ('stats', 'summary_pdf')
    REQUIRED_EXECUTABLES = ['bcftools', 'plot-vcfstats', 'samtools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#stats'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22+galaxy0'
    SHELL = True
    COLLAPSE_OPTIONS = ['', 'snps', 'indels', 'both', 'some', 'any', 'none', 'id']
    AFBINS_OPTIONS = ['default', 'af_bins_list', 'af_bins_file']
    OVERLAP_OPTIONS = ['', '0', '1', '2']

    @staticmethod
    def _selected(value: Any) -> bool:
        return value is not None and str(value) != ''

    @classmethod
    def _input_file(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_file', inputs.get('vcf', '')) or '')

    @classmethod
    def _stats_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/stats.txt'

    @classmethod
    def _add_targets(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        prefix = '^' if inputs.get('invert_targets') or inputs.get('invert_targets_file') else ''
        if cls._selected(inputs.get('targets')):
            cmd.extend(['--targets', f"{prefix}{inputs['targets']}"])
        if cls._selected(inputs.get('targets_file')):
            cmd.extend(['--targets-file', f"{prefix}{inputs['targets_file']}"])
        _add_if_value(cmd, '--targets-overlap', inputs.get('targets_overlap'))

    @classmethod
    def _add_samples(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._selected(inputs.get('samples')):
            prefix = '^' if inputs.get('invert_samples') else ''
            cmd.extend(['--samples', f"{prefix}{inputs['samples']}"])
        if cls._selected(inputs.get('samples_file')):
            prefix = '^' if inputs.get('invert_samples_file') else ''
            cmd.extend(['--samples-file', f"{prefix}{inputs['samples_file']}"])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'stats']
        _add_if_value(cmd, '--fasta-ref', inputs.get('reference', inputs.get('fasta_ref')))
        _add_if_value(cmd, '--exons', inputs.get('exons_file'))
        if inputs.get('first_allele_only'):
            cmd.append('--1st-allele-only')
        depth_requested = cls._selected(inputs.get('depth_min')) or cls._selected(inputs.get('depth_max')) or cls._selected(inputs.get('depth_bin_size'))
        if depth_requested:
            cmd.extend(['--depth', f"{inputs.get('depth_min', 0) or 0},{inputs.get('depth_max', 500) or 500},{inputs.get('depth_bin_size', 1) or 1}"])
        _add_if_value(cmd, '--user-tstv', inputs.get('user_tstv'))
        af_bins_select = str(inputs.get('af_bins_select', '') or '')
        if af_bins_select == 'af_bins_file':
            _add_if_value(cmd, '--af-bins', inputs.get('af_bins_file'))
        else:
            _add_if_value(cmd, '--af-bins', inputs.get('af_bins_list'))
        _add_if_value(cmd, '--af-tag', inputs.get('af_tag'))
        if inputs.get('split_by_ID') and (not cls._selected(inputs.get('inputB_file'))):
            cmd.append('--split-by-ID')
        if inputs.get('verbose'):
            cmd.append('--verbose')
        _add_if_value(cmd, '--apply-filters', inputs.get('apply_filters'))
        _add_if_value(cmd, '--collapse', inputs.get('collapse'))
        _add_if_value(cmd, '--regions', inputs.get('regions'))
        _add_if_value(cmd, '--regions-file', inputs.get('regions_file'))
        _add_if_value(cmd, '--regions-overlap', inputs.get('regions_overlap'))
        cls._add_samples(cmd, inputs)
        cls._add_targets(cmd, inputs)
        _add_if_value(cmd, '--include', inputs.get('include'))
        _add_if_value(cmd, '--exclude', inputs.get('exclude'))
        cmd.append(cls._input_file(inputs))
        if cls._selected(inputs.get('inputB_file')):
            cmd.append(str(inputs['inputB_file']))
        stats_path = cls._stats_path(inputs)
        _add_shell_redirect(cmd, stats_path)
        if cls._selected(inputs.get('plot_title')):
            cmd.extend(['&&', 'plot-vcfstats', '-p', f'{_out(inputs)}/plot_tmp', '-T', str(inputs['plot_title']), '-s', stats_path])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        outputs = [_bcftools_common_output(cls.NODE_ID, 'stats.txt', output_dir)]
        if cls._selected(inputs.get('plot_title')):
            outputs.append(_bcftools_common_output(cls.NODE_ID, 'summary.pdf', output_dir))
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_file(inputs).strip():
            return 'input_file is required'
        try:
            depth_min = int(inputs.get('depth_min', 0) or 0)
            depth_max = int(inputs.get('depth_max', 500) or 500)
            depth_bin_size = int(inputs.get('depth_bin_size', 1) or 1)
        except (TypeError, ValueError):
            return 'depth values must be integers'
        if depth_min < 0:
            return 'depth_min must be at least 0'
        if depth_max < depth_min:
            return 'depth_max must be greater than or equal to depth_min'
        if depth_bin_size < 1:
            return 'depth_bin_size must be at least 1'
        af_bins_select = str(inputs.get('af_bins_select', 'default') or 'default')
        if af_bins_select not in cls.AFBINS_OPTIONS:
            return f"af_bins_select must be one of: {', '.join(cls.AFBINS_OPTIONS)}"
        collapse = str(inputs.get('collapse', '') or '')
        if collapse not in cls.COLLAPSE_OPTIONS:
            return 'collapse must be one of: snps, indels, both, some, any, none, id'
        for name in ('regions_overlap', 'targets_overlap'):
            value = str(inputs.get(name, '') or '')
            if value not in cls.OVERLAP_OPTIONS:
                return f'{name} must be one of: 0, 1, 2'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'Primary VCF/BCF file for bcftools stats'})}, 'optional': {'inputB_file': ('VCF', {'description': 'Optional comparison VCF/BCF file'}), 'reference': ('FASTA', {'description': 'Reference FASTA used for substitution statistics'}), 'exons_file': ('TSV', {'description': 'Exons file for indel frameshift statistics'}), 'first_allele_only': ('BOOLEAN', {'default': False, 'description': 'Include only first allele at multiallelic sites'}), 'depth_min': ('INT', {'default': '', 'min': 0, 'description': 'Depth distribution minimum'}), 'depth_max': ('INT', {'default': '', 'min': 1, 'description': 'Depth distribution maximum'}), 'depth_bin_size': ('INT', {'default': '', 'min': 1, 'description': 'Depth distribution bin size'}), 'user_tstv': ('STRING', {'default': '', 'description': 'Ts/Tv binning tag such as TAG:min:max:binsize'}), 'af_bins_select': ('STRING', {'default': 'default', 'options': cls.AFBINS_OPTIONS, 'description': 'Allele-frequency bin source'}), 'af_bins_list': ('STRING', {'default': '', 'description': 'Comma-separated allele-frequency bins'}), 'af_bins_file': ('TSV', {'description': 'File listing allele-frequency bins'}), 'af_tag': ('STRING', {'default': '', 'description': 'Allele-frequency tag to use'}), 'split_by_ID': ('BOOLEAN', {'default': False, 'description': 'Split known and novel sites by ID for one input'}), 'verbose': ('BOOLEAN', {'default': False, 'description': 'Produce verbose per-site and per-sample output'}), 'apply_filters': ('STRING', {'default': '', 'description': 'Skip sites whose FILTER value is not listed'}), 'collapse': ('STRING', {'default': '', 'options': cls.COLLAPSE_OPTIONS, 'description': 'Compatibility mode for duplicate records'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict stats to regions'}), 'regions_file': ('BED', {'description': 'Restrict stats to regions from file'}), 'regions_overlap': ('STRING', {'default': '', 'options': cls.OVERLAP_OPTIONS, 'description': 'Region overlap mode'}), 'samples': ('STRING', {'default': '', 'description': 'Comma-separated samples to include or exclude'}), 'samples_file': ('TSV', {'description': 'File of samples to include or exclude'}), 'invert_samples': ('BOOLEAN', {'default': False, 'description': 'Exclude samples listed in samples'}), 'invert_samples_file': ('BOOLEAN', {'default': False, 'description': 'Exclude samples listed in samples_file'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict stats to targets'}), 'targets_file': ('TSV', {'description': 'Restrict stats to targets from file'}), 'invert_targets': ('BOOLEAN', {'default': False, 'description': 'Invert inline targets'}), 'invert_targets_file': ('BOOLEAN', {'default': False, 'description': 'Invert targets file'}), 'targets_overlap': ('STRING', {'default': '', 'options': cls.OVERLAP_OPTIONS, 'description': 'Target overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'plot_title': ('STRING', {'default': '', 'description': 'Create plot-vcfstats PDF with this title'}), 'vcf': ('VCF_GZ', {'description': 'Compatibility alias for input_file', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsNormNode(CommandNode):
    """Left-align, normalize, split, join, and atomize VCF/BCF records."""
    NODE_ID = 'bcftools_norm'
    DISPLAY_NAME = 'BCFtools Norm'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib', 'samtools']
    CATEGORY = 'variant'
    DESCRIPTION = 'Left-align and normalize indels, check reference alleles, split or join multiallelic records, and atomize complex variants.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'norm', 'normalize', 'left-align indels', 'split multiallelic', 'join multiallelic', 'atomize variants']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('normalized_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools', 'samtools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#norm'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22+galaxy0'
    SHELL = True
    CHECK_REF_OPTIONS = ['w', 'wx', 'ws', 'e']
    RM_DUP_OPTIONS = ['', 'snps', 'indels', 'both', 'any']
    ATOMIZATION_OPTIONS = ['', '--atomize', '--atomize --atom-overlaps .']
    MULTIALLELIC_MODE_OPTIONS = ['', '-', '+']
    MULTIALLELIC_TYPES_OPTIONS = ['snps', 'indels', 'both', 'any']
    SORT_OPTIONS = ['pos', 'lex']
    OUTPUT_TYPES = ['b', 'u', 'z', 'v']
    OVERLAP_OPTIONS = ['', '0', '1', '2']
    LEGACY_MULTIALLELICS = {'none': '', 'split': '-', 'join': '+'}
    LEGACY_DEDUPLICATE = {'none': '', 'snps': 'snps', 'indels': 'indels', 'both': 'both', 'all': 'any'}
    LEGACY_CHECK_REF = {'exit': 'e', 'warn': 'w', 'exclude': 'wx', 'set': 'ws'}

    @staticmethod
    def _selected(value: Any) -> bool:
        return value is not None and str(value) != ''

    @classmethod
    def _input_file(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_file', inputs.get('vcf', '')) or '')

    @classmethod
    def _check_ref(cls, inputs: dict[str, Any]) -> str:
        value = str(inputs.get('check_ref', 'w') or 'w')
        return cls.LEGACY_CHECK_REF.get(value, value)

    @classmethod
    def _rm_dup(cls, inputs: dict[str, Any]) -> str:
        value = str(inputs.get('rm_dup', inputs.get('deduplicate', '')) or '')
        return cls.LEGACY_DEDUPLICATE.get(value, value)

    @classmethod
    def _multiallelic_mode(cls, inputs: dict[str, Any]) -> str:
        value = str(inputs.get('multiallelic_mode', inputs.get('multiallelics', '')) or '')
        return cls.LEGACY_MULTIALLELICS.get(value, value)

    @classmethod
    def _multiallelic_types(cls, inputs: dict[str, Any], mode: str) -> str:
        value = str(inputs.get('multiallelic_types', '') or '')
        if value:
            return value
        return 'both' if mode in {'-', '+'} else ''

    @classmethod
    def _add_targets(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        prefix = '^' if inputs.get('invert_targets') or inputs.get('invert_targets_file') else ''
        if cls._selected(inputs.get('targets')):
            cmd.extend(['--targets', f"{prefix}{inputs['targets']}"])
        if cls._selected(inputs.get('targets_file')):
            cmd.extend(['--targets-file', f"{prefix}{inputs['targets_file']}"])
        _add_if_value(cmd, '--targets-overlap', inputs.get('targets_overlap'))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'norm']
        _add_if_value(cmd, '--fasta-ref', inputs.get('reference', inputs.get('fasta_ref')))
        cmd.extend(['--check-ref', cls._check_ref(inputs)])
        if inputs.get('normalize_indels') is False:
            cmd.append('--do-not-normalize')
        _add_if_value(cmd, '--rm-dup', cls._rm_dup(inputs))
        atomization = str(inputs.get('atomization', '') or '')
        if atomization:
            cmd.extend(atomization.split())
        _add_if_value(cmd, '--old-rec-tag', inputs.get('old_rec_tag'))
        multiallelic_mode = cls._multiallelic_mode(inputs)
        if multiallelic_mode:
            cmd.extend(['--multiallelics', f'{multiallelic_mode}{cls._multiallelic_types(inputs, multiallelic_mode)}'])
        if multiallelic_mode == '+' and inputs.get('strict_filter'):
            cmd.append('--strict-filter')
        _add_if_value(cmd, '--site-win', inputs.get('site_win'))
        cmd.extend(['--sort', str(inputs.get('sort', 'pos') or 'pos')])
        _add_if_value(cmd, '--include', inputs.get('include'))
        _add_if_value(cmd, '--exclude', inputs.get('exclude'))
        _add_if_value(cmd, '--regions', inputs.get('regions'))
        _add_if_value(cmd, '--regions-file', inputs.get('regions_file'))
        _add_if_value(cmd, '--regions-overlap', inputs.get('regions_overlap'))
        cls._add_targets(cmd, inputs)
        _bcftools_add_output_type(cmd, inputs)
        threads = inputs.get('threads')
        if cls._selected(threads) and str(threads) != '0':
            cmd.extend(['--threads', str(threads)])
        cmd.append(cls._input_file(inputs))
        _add_shell_redirect(cmd, f'{_out(inputs)}/normalized{_bcftools_variant_suffix(inputs)}')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f'normalized{_bcftools_variant_suffix(inputs)}', output_dir)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_file(inputs).strip():
            return 'input_file is required'
        check_ref = cls._check_ref(inputs)
        if check_ref not in cls.CHECK_REF_OPTIONS:
            return f"check_ref must be one of: {', '.join(cls.CHECK_REF_OPTIONS)}"
        rm_dup = cls._rm_dup(inputs)
        if rm_dup not in cls.RM_DUP_OPTIONS:
            return 'rm_dup must be one of: snps, indels, both, any'
        atomization = str(inputs.get('atomization', '') or '')
        if atomization not in cls.ATOMIZATION_OPTIONS:
            return 'atomization must be one of: --atomize, --atomize --atom-overlaps .'
        multiallelic_mode = cls._multiallelic_mode(inputs)
        if multiallelic_mode not in cls.MULTIALLELIC_MODE_OPTIONS:
            return 'multiallelic_mode must be one of: -, +'
        multiallelic_types = cls._multiallelic_types(inputs, multiallelic_mode)
        if multiallelic_types and multiallelic_types not in cls.MULTIALLELIC_TYPES_OPTIONS:
            return 'multiallelic_types must be one of: snps, indels, both, any'
        sort = str(inputs.get('sort', 'pos') or 'pos')
        if sort not in cls.SORT_OPTIONS:
            return f"sort must be one of: {', '.join(cls.SORT_OPTIONS)}"
        output_type = str(inputs.get('output_type', 'z') or 'z')
        if output_type not in cls.OUTPUT_TYPES:
            return f"output_type must be one of: {', '.join(cls.OUTPUT_TYPES)}"
        for name in ('regions_overlap', 'targets_overlap'):
            value = str(inputs.get(name, '') or '')
            if value not in cls.OVERLAP_OPTIONS:
                return f'{name} must be one of: 0, 1, 2'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file to normalize'})}, 'optional': {'reference': ('FASTA', {'description': 'Reference FASTA for left-alignment and REF checks'}), 'check_ref': ('STRING', {'default': 'w', 'options': cls.CHECK_REF_OPTIONS, 'description': 'REF allele mismatch handling'}), 'normalize_indels': ('BOOLEAN', {'default': True, 'description': 'Left-align and normalize indels'}), 'rm_dup': ('STRING', {'default': '', 'options': cls.RM_DUP_OPTIONS, 'description': 'Remove duplicate variant records'}), 'atomization': ('STRING', {'default': '', 'options': cls.ATOMIZATION_OPTIONS, 'description': 'Atomize complex variants'}), 'old_rec_tag': ('STRING', {'default': '', 'description': 'INFO tag storing the original variant record'}), 'multiallelic_mode': ('STRING', {'default': '', 'options': cls.MULTIALLELIC_MODE_OPTIONS, 'description': 'Split or join multiallelic records'}), 'multiallelic_types': ('STRING', {'default': 'both', 'options': cls.MULTIALLELIC_TYPES_OPTIONS, 'description': 'Variant types for split or join mode'}), 'strict_filter': ('BOOLEAN', {'default': False, 'description': 'Require all merged records to PASS'}), 'site_win': ('INT', {'default': '', 'min': 0, 'description': 'Sorting buffer for changed positions'}), 'sort': ('STRING', {'default': 'pos', 'options': cls.SORT_OPTIONS, 'description': 'Output allele sort order'}), 'include': ('STRING', {'default': '', 'description': 'Normalize only matching records'}), 'exclude': ('STRING', {'default': '', 'description': 'Skip normalization for matching records'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict normalization to regions'}), 'regions_file': ('BED', {'description': 'Restrict normalization to regions from file'}), 'regions_overlap': ('STRING', {'default': '', 'options': cls.OVERLAP_OPTIONS, 'description': 'Region overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict normalization to targets'}), 'targets_file': ('TSV', {'description': 'Restrict normalization to targets from file'}), 'invert_targets': ('BOOLEAN', {'default': False, 'description': 'Invert inline targets'}), 'invert_targets_file': ('BOOLEAN', {'default': False, 'description': 'Invert targets file'}), 'targets_overlap': ('STRING', {'default': '', 'options': cls.OVERLAP_OPTIONS, 'description': 'Target overlap mode'}), 'output_type': ('STRING', {'default': 'z', 'options': cls.OUTPUT_TYPES, 'description': 'BCFtools output type'}), 'threads': ('INT', {'default': '', 'min': 1, 'max': 128, 'display': 'slider'}), 'vcf': ('VCF_GZ', {'description': 'Compatibility alias for input_file', 'advanced': True}), 'fasta_ref': ('FASTA', {'description': 'Compatibility alias for reference', 'advanced': True}), 'multiallelics': ('STRING', {'default': '', 'description': 'Compatibility alias for multiallelic_mode', 'advanced': True}), 'deduplicate': ('STRING', {'default': '', 'description': 'Compatibility alias for rm_dup', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsConcatNode(CommandNode):
    """Concatenate or combine VCF/BCF files with matching sample columns."""
    NODE_ID = 'bcftools_concat'
    DISPLAY_NAME = 'BCFtools Concat'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Concatenate chromosome shards or combine sorted VCF/BCF files with compatible sample columns.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'concat', 'concatenate vcf', 'combine vcf', 'ligate phased vcfs']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('concat_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#concat'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'concat']
        if inputs.get('naive'):
            cmd.append('--naive')
        else:
            if inputs.get('allow_overlaps'):
                cmd.append('--allow-overlaps')
                _add_if_value(cmd, '--rm-dups', inputs.get('rm_dups'))
            if inputs.get('ligate'):
                cmd.append('--ligate')
            ligate_mode = str(inputs.get('ligate_mode', '')).strip()
            if ligate_mode:
                cmd.append(ligate_mode)
        if inputs.get('compact_ps'):
            cmd.append('--compact-PS')
        _add_if_value(cmd, '--min-PQ', inputs.get('min_pq'))
        _add_if_value(cmd, '--regions', inputs.get('regions'))
        _bcftools_add_output_type(cmd, inputs)
        _add_if_value(cmd, '--threads', inputs.get('threads'))
        cmd.extend(_as_list(inputs.get('input_files', inputs.get('inputs'))))
        _add_shell_redirect(cmd, f'{_out(inputs)}/concat{_bcftools_variant_suffix(inputs)}')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f'concat{_bcftools_variant_suffix(inputs)}', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_files': ('VCF_LIST', {'description': 'Sorted VCF/BCF files with compatible sample columns'})}, 'optional': {'naive': ('BOOLEAN', {'default': False, 'description': 'Concatenate without recompression or header checks'}), 'allow_overlaps': ('BOOLEAN', {'default': False, 'description': 'Allow overlapping positions between adjacent files'}), 'rm_dups': ('STRING', {'default': '', 'options': ['', 'snps', 'indels', 'both', 'all', 'none'], 'description': 'Remove duplicate records when overlaps are allowed'}), 'ligate': ('BOOLEAN', {'default': False, 'description': 'Ligate phased VCF chunks'}), 'ligate_mode': ('STRING', {'default': '', 'options': ['', '--ligate-warn', '--ligate-force'], 'description': 'Fine control of ligate behavior'}), 'compact_ps': ('BOOLEAN', {'default': False, 'description': 'Emit phase-set tag only at phase block starts'}), 'min_pq': ('INT', {'default': '', 'min': 0, 'description': 'Break phase set below this phasing quality'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict output to regions'}), 'output_type': ('STRING', {'default': 'z', 'options': ['z', 'v', 'b', 'u'], 'description': 'BCFtools output type'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsConsensusNode(CommandNode):
    """Apply VCF variants to a reference FASTA to build a consensus sequence."""
    NODE_ID = 'bcftools_consensus'
    DISPLAY_NAME = 'BCFtools Consensus'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Create a consensus FASTA by applying VCF/BCF variants, masks, and sample or haplotype choices to a reference.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'consensus', 'consensus fasta', 'apply variants', 'haplotype consensus']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('consensus_fasta',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#consensus'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'consensus', '--fasta-ref', str(inputs.get('reference', inputs.get('fasta_ref', '')))]
        mode = str(inputs.get('mode', 'genotype_iupac'))
        if mode == 'first_alt':
            cmd.extend(['-s', '-'])
        elif mode == 'all_iupac':
            cmd.extend(['-I', '-s', '-'])
        elif mode == 'haplotype':
            cmd.extend(['-H', str(inputs.get('haplotype', '1'))])
            _add_if_value(cmd, '--sample', inputs.get('sample'))
        else:
            _add_if_value(cmd, '--samples', inputs.get('samples'))
        masks = _as_list(inputs.get('mask'))
        mask_with_value = inputs.get('mask_with')
        if isinstance(mask_with_value, str) and ',' in mask_with_value:
            mask_with = [part.strip() for part in mask_with_value.split(',') if part.strip()]
        else:
            mask_with = _as_list(mask_with_value)
        for index, mask in enumerate(masks):
            cmd.extend(['--mask', mask])
            if index < len(mask_with):
                cmd.extend(['--mask-with', mask_with[index]])
            elif len(mask_with) == 1:
                cmd.extend(['--mask-with', mask_with[0]])
        _add_if_value(cmd, '--absent', inputs.get('absent'))
        _add_if_value(cmd, '--mark-del', inputs.get('mark_del'))
        _add_if_value(cmd, '--mark-ins', inputs.get('mark_ins'))
        _add_if_value(cmd, '--mark-snv', inputs.get('mark_snv'))
        _add_if_value(cmd, '--include', inputs.get('include'))
        _add_if_value(cmd, '--exclude', inputs.get('exclude'))
        if inputs.get('chain'):
            cmd.extend(['--chain', f'{_out(inputs)}/consensus.chain'])
        cmd.extend(['--output', f'{_out(inputs)}/consensus.fa', str(inputs.get('input_file', ''))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        outputs = [_bcftools_common_output(cls.NODE_ID, 'consensus.fa', output_dir)]
        if inputs.get('chain'):
            outputs.append(_bcftools_common_output(cls.NODE_ID, 'consensus.chain', output_dir))
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF variants to apply'}), 'reference': ('FASTA', {'description': 'Reference FASTA'})}, 'optional': {'mode': ('STRING', {'default': 'genotype_iupac', 'options': ['first_alt', 'all_iupac', 'genotype_iupac', 'haplotype'], 'description': 'Galaxy consensus building mode'}), 'samples': ('STRING', {'default': '', 'description': 'Comma-separated samples for genotype-IUPAC mode'}), 'sample': ('STRING', {'default': '', 'description': 'Single sample for haplotype mode'}), 'haplotype': ('STRING', {'default': '1', 'description': 'Haplotype selector such as 1, 2, 1pIu, R, A, LR, LA, SR, or SA'}), 'mask': ('BED_LIST', {'description': 'Regions to mask before applying variants'}), 'mask_with': ('STRING_LIST', {'description': 'Mask replacement values matching mask files'}), 'absent': ('STRING', {'default': '', 'description': 'Character for reference bases absent from VCF'}), 'mark_del': ('STRING', {'default': '', 'description': 'Character for deleted reference bases'}), 'mark_ins': ('STRING', {'default': '', 'description': 'Insertion marking mode or character'}), 'mark_snv': ('STRING', {'default': '', 'description': 'SNV marking mode or character'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'chain': ('BOOLEAN', {'default': False, 'description': 'Write a liftover chain file'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsQueryNode(CommandNode):
    """Extract fields from one or more VCF/BCF files in a user-defined format."""
    NODE_ID = 'bcftools_query'
    DISPLAY_NAME = 'BCFtools Query'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Transform VCF/BCF records into tabular or custom text output using bcftools query format strings.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'query', 'extract fields', 'format vcf', 'vcf to tsv']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('query_table',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#query'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'query', '--format', str(inputs.get('format', '%CHROM\\t%POS\\t%REF\\t%ALT\\n'))]
        if inputs.get('allow_undef_tags'):
            cmd.append('--allow-undef-tags')
        if inputs.get('print_header'):
            cmd.append('--print-header')
        _bcftools_add_restrict(cmd, inputs)
        cmd.extend(_as_list(inputs.get('input_files', inputs.get('input_file'))))
        _add_shell_redirect(cmd, f'{_out(inputs)}/query.tsv')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'query.tsv', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_files': ('VCF_LIST', {'description': 'One or more VCF/BCF files'}), 'format': ('STRING', {'default': '%CHROM\\t%POS\\t%REF\\t%ALT\\n', 'description': 'bcftools query format string'})}, 'optional': {'allow_undef_tags': ('BOOLEAN', {'default': False, 'description': 'Print . for undefined tags'}), 'print_header': ('BOOLEAN', {'default': False, 'description': 'Print a header line'}), 'collapse': ('STRING', {'default': '', 'description': 'Compatibility collapse mode'}), 'samples': ('STRING', {'default': '', 'description': 'Comma-separated samples'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsQueryListSamplesNode(CommandNode):
    """List sample names from a VCF/BCF file."""
    NODE_ID = 'bcftools_query_list_samples'
    DISPLAY_NAME = 'BCFtools List Samples'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'List sample names from a VCF/BCF file using bcftools query --list-samples.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'query', 'list samples', 'sample names', 'vcf samples']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('samples',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#query'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'query', '--list-samples', str(inputs.get('input_file', ''))]
        _add_shell_redirect(cmd, f'{_out(inputs)}/samples.tsv')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'samples.tsv', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsReheaderNode(CommandNode):
    """Modify VCF/BCF headers and sample names."""
    NODE_ID = 'bcftools_reheader'
    DISPLAY_NAME = 'BCFtools Reheader'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Replace a VCF/BCF header and optionally rename samples using a sample mapping file.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'reheader', 'rename samples', 'change header', 'sample names']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('reheadered_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#reheader'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'reheader']
        _add_if_value(cmd, '--header', inputs.get('header'))
        _add_if_value(cmd, '--samples', inputs.get('sample_file', inputs.get('samples_file')))
        if inputs.get('sample_lines'):
            cmd.extend(['--samples', str(inputs.get('sample_lines'))])
        cmd.append(str(inputs.get('input_file', '')))
        cmd.extend(['|', 'bcftools', 'view'])
        _bcftools_add_output_type(cmd, inputs)
        _add_shell_redirect(cmd, f'{_out(inputs)}/reheadered{_bcftools_variant_suffix(inputs)}')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f'reheadered{_bcftools_variant_suffix(inputs)}', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file'})}, 'optional': {'header': ('VCF', {'description': 'Replacement VCF header'}), 'sample_file': ('TSV', {'description': 'Sample names or old/new sample mapping'}), 'sample_lines': ('STRING', {'default': '', 'description': 'Inline sample renaming text'}), 'output_type': ('STRING', {'default': 'z', 'options': ['z', 'v', 'b', 'u'], 'description': 'BCFtools output type'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsViewNode(CommandNode):
    """Convert, subset, and filter VCF/BCF files."""
    NODE_ID = 'bcftools_view'
    DISPLAY_NAME = 'BCFtools View'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Subset samples, filter variants, and convert VCF/BCF files with bcftools view.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'view', 'subset vcf', 'filter vcf', 'vcf conversion']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('view_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#view'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'view']
        if inputs.get('trim_alt_alleles'):
            cmd.append('--trim-alt-alleles')
        if inputs.get('no_update'):
            cmd.append('--no-update')
        _add_if_value(cmd, '--samples', inputs.get('samples'))
        if inputs.get('force_samples'):
            cmd.append('--force-samples')
        _add_if_value(cmd, '--min-ac', inputs.get('min_ac'))
        _add_if_value(cmd, '--max-ac', inputs.get('max_ac'))
        _add_if_value(cmd, '--genotype', inputs.get('select_genotype'))
        known_or_novel = str(inputs.get('known_or_novel', '')).strip()
        if known_or_novel:
            cmd.append(known_or_novel)
        _add_if_value(cmd, '--min-alleles', inputs.get('min_alleles'))
        _add_if_value(cmd, '--max-alleles', inputs.get('max_alleles'))
        phased = str(inputs.get('phased', '')).strip()
        if phased:
            cmd.append(phased)
        _add_if_value(cmd, '--min-af', inputs.get('min_af'))
        _add_if_value(cmd, '--max-af', inputs.get('max_af'))
        uncalled = str(inputs.get('uncalled', '')).strip()
        if uncalled:
            cmd.append(uncalled)
        types = _as_list(inputs.get('types'))
        if types:
            cmd.extend(['--types', ','.join(types)])
        exclude_types = _as_list(inputs.get('exclude_types'))
        if exclude_types:
            cmd.extend(['--exclude-types', ','.join(exclude_types)])
        private = str(inputs.get('private', '')).strip()
        if private:
            cmd.append(private)
        if inputs.get('drop_genotypes'):
            cmd.append('--drop-genotypes')
        header = str(inputs.get('header', '')).strip()
        if header:
            cmd.append(header)
        _add_if_value(cmd, '--compression-level', inputs.get('compression_level'))
        restrict_inputs = {**inputs, '_skip_samples_restrict': True}
        _bcftools_add_restrict(cmd, restrict_inputs)
        _bcftools_add_output_type(cmd, inputs)
        _add_if_value(cmd, '--threads', inputs.get('threads'))
        cmd.append(str(inputs.get('input_file', '')))
        _add_shell_redirect(cmd, f'{_out(inputs)}/view{_bcftools_variant_suffix(inputs)}')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f'view{_bcftools_variant_suffix(inputs)}', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file'})}, 'optional': {'samples': ('STRING', {'default': '', 'description': 'Comma-separated samples'}), 'force_samples': ('BOOLEAN', {'default': False, 'description': 'Only warn about unknown subset samples'}), 'no_update': ('BOOLEAN', {'default': False, 'description': 'Do not recalculate INFO AC/AN after subsetting'}), 'trim_alt_alleles': ('BOOLEAN', {'default': False, 'description': 'Trim alternate alleles not seen in subset'}), 'min_ac': ('INT', {'default': '', 'description': 'Minimum allele count'}), 'max_ac': ('INT', {'default': '', 'description': 'Maximum allele count'}), 'select_genotype': ('STRING', {'default': '', 'options': ['', 'hom', 'het', 'miss', '^hom', '^het', '^miss'], 'description': 'Genotype filter'}), 'types': ('STRING_LIST', {'description': 'Variant types to include'}), 'exclude_types': ('STRING_LIST', {'description': 'Variant types to exclude'}), 'known_or_novel': ('STRING', {'default': '', 'options': ['', '--novel', '--known'], 'description': 'Filter known or novel IDs'}), 'min_alleles': ('INT', {'default': '', 'description': 'Minimum number of REF/ALT alleles'}), 'max_alleles': ('INT', {'default': '', 'description': 'Maximum number of REF/ALT alleles'}), 'phased': ('STRING', {'default': '', 'options': ['', '--phased', '--exclude-phased'], 'description': 'Phasing filter'}), 'min_af': ('FLOAT', {'default': '', 'description': 'Minimum allele frequency'}), 'max_af': ('FLOAT', {'default': '', 'description': 'Maximum allele frequency'}), 'uncalled': ('STRING', {'default': '', 'options': ['', '--uncalled', '--exclude-uncalled'], 'description': 'Uncalled genotype filter'}), 'private': ('STRING', {'default': '', 'options': ['', '--private', '--exclude-private'], 'description': 'Private allele filter'}), 'drop_genotypes': ('BOOLEAN', {'default': False, 'description': 'Drop genotype columns'}), 'header': ('STRING', {'default': '', 'options': ['', '--no-header', '--header-only'], 'description': 'Header output mode'}), 'compression_level': ('INT', {'default': '', 'min': 0, 'max': 9, 'description': 'Compression level'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'output_type': ('STRING', {'default': 'z', 'options': ['z', 'v', 'b', 'u'], 'description': 'BCFtools output type'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsMergeNode(CommandNode):
    """Merge VCF/BCF files from non-overlapping sample sets."""
    NODE_ID = 'bcftools_merge'
    DISPLAY_NAME = 'BCFtools Merge'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Merge multiple VCF/BCF files from non-overlapping sample sets into one multi-sample file.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'merge', 'merge samples', 'multi-sample vcf', 'combine cohorts']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('merged_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#merge'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'merge']
        if inputs.get('print_header'):
            cmd.append('--print-header')
        _add_if_value(cmd, '--use-header', inputs.get('use_header'))
        if inputs.get('force_samples'):
            cmd.append('--force-samples')
        _add_if_value(cmd, '--info-rules', inputs.get('info_rules'))
        _add_if_value(cmd, '--merge', inputs.get('merge'))
        if inputs.get('no_index'):
            cmd.append('--no-index')
        _bcftools_add_apply_filters(cmd, inputs)
        _bcftools_add_region_targets(cmd, inputs)
        _add_if_value(cmd, '--include', inputs.get('include'))
        _add_if_value(cmd, '--exclude', inputs.get('exclude'))
        _bcftools_add_output_type(cmd, inputs)
        _add_if_value(cmd, '--threads', inputs.get('threads'))
        cmd.extend(_as_list(inputs.get('input_files', inputs.get('inputs'))))
        _add_shell_redirect(cmd, f'{_out(inputs)}/merged{_bcftools_variant_suffix(inputs)}')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f'merged{_bcftools_variant_suffix(inputs)}', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_files': ('VCF_LIST', {'description': 'VCF/BCF files from non-overlapping sample sets'})}, 'optional': {'force_samples': ('BOOLEAN', {'default': False, 'description': 'Resolve duplicate sample names'}), 'info_rules': ('STRING', {'default': '', 'description': 'INFO merge rules such as DP:sum,AD:join'}), 'merge': ('STRING', {'default': '', 'options': ['', 'none', 'snps', 'indels', 'both', 'all', 'id'], 'description': 'Allow multiallelic records for the selected class'}), 'no_index': ('BOOLEAN', {'default': False, 'description': 'Allow merging unindexed files'}), 'print_header': ('BOOLEAN', {'default': False, 'description': 'Print only the merged header'}), 'use_header': ('VCF', {'description': 'Header to use for the merged output'}), 'apply_filters': ('STRING', {'default': '', 'description': 'Skip sites whose FILTER does not match these terms'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'output_type': ('STRING', {'default': 'z', 'options': ['z', 'v', 'b', 'u'], 'description': 'BCFtools output type'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsIsecNode(CommandNode):
    """Create intersections, unions, and complements of VCF/BCF files."""
    NODE_ID = 'bcftools_isec'
    DISPLAY_NAME = 'BCFtools Isec'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Create intersections, unions, and complements across multiple VCF/BCF files.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'isec', 'variant intersection', 'vcf union', 'vcf complement']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('isec_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#isec'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'isec']
        if inputs.get('complement'):
            cmd.append('--complement')
        _add_if_value(cmd, '--nfiles', inputs.get('nfiles'))
        _bcftools_add_region_targets(cmd, inputs)
        _add_if_value(cmd, '--collapse', inputs.get('collapse'))
        _bcftools_add_apply_filters(cmd, inputs)
        _add_if_value(cmd, '--include', inputs.get('include'))
        _add_if_value(cmd, '--exclude', inputs.get('exclude'))
        _bcftools_add_output_type(cmd, inputs)
        _add_if_value(cmd, '--threads', inputs.get('threads'))
        cmd.extend(_as_list(inputs.get('input_files', inputs.get('inputs'))))
        _add_shell_redirect(cmd, f'{_out(inputs)}/isec{_bcftools_variant_suffix(inputs)}')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f'isec{_bcftools_variant_suffix(inputs)}', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_files': ('VCF_LIST', {'description': 'VCF/BCF files to intersect or compare'})}, 'optional': {'nfiles': ('STRING', {'default': '', 'description': 'Output positions present in =N, +N, -N, or ~bitmask files'}), 'complement': ('BOOLEAN', {'default': False, 'description': 'Output positions present only in the first file'}), 'collapse': ('STRING', {'default': '', 'options': ['', 'snps', 'indels', 'both', 'all', 'some', 'none', 'id'], 'description': 'Compatibility mode for records at duplicate positions'}), 'apply_filters': ('STRING', {'default': '', 'description': 'Skip sites whose FILTER does not match these terms'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'output_type': ('STRING', {'default': 'z', 'options': ['z', 'v', 'b', 'u'], 'description': 'BCFtools output type'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsGTcheckNode(CommandNode):
    """Check sample identity and genotype concordance."""
    NODE_ID = 'bcftools_gtcheck'
    DISPLAY_NAME = 'BCFtools GTcheck'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Check sample identity by comparing genotypes within or between VCF/BCF files.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'gtcheck', 'sample identity', 'genotype concordance', 'discordance']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('gtcheck_table',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#gtcheck'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'gtcheck']
        _add_if_value(cmd, '--genotypes', inputs.get('genotypes'))
        if inputs.get('all_sites'):
            cmd.append('--all-sites')
        if inputs.get('homs_only'):
            cmd.append('--homs-only')
        _add_if_value(cmd, '--plot', inputs.get('plot'))
        _add_if_value(cmd, '--query-sample', inputs.get('query_sample'))
        _add_if_value(cmd, '--target-sample', inputs.get('target_sample'))
        _bcftools_add_region_targets(cmd, inputs)
        cmd.append(str(inputs.get('input_file', '')))
        _add_shell_redirect(cmd, f'{_out(inputs)}/gtcheck.tsv')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'gtcheck.tsv', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'Query VCF/BCF file'})}, 'optional': {'genotypes': ('VCF', {'description': 'Genotypes to compare against'}), 'target_sample': ('STRING', {'default': '', 'description': 'Target sample in the genotype file'}), 'all_sites': ('BOOLEAN', {'default': False, 'description': 'Output comparison for all sites'}), 'homs_only': ('BOOLEAN', {'default': False, 'description': 'Use homozygous genotypes only'}), 'query_sample': ('STRING', {'default': '', 'description': 'Query sample'}), 'plot': ('STRING', {'default': '', 'description': 'Plot prefix name'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsConvertToVcfNode(CommandNode):
    """Convert gVCF, TSV, GEN/SAMPLE, or HAP/SAMPLE data to VCF/BCF."""
    NODE_ID = 'bcftools_convert_to_vcf'
    DISPLAY_NAME = 'BCFtools Convert to VCF'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Convert gVCF, tabular genotype data, and IMPUTE2/SHAPEIT files into VCF/BCF.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'convert', 'gvcf to vcf', 'tsv to vcf', 'shapeit to vcf']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('converted_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#convert'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'convert']
        _bcftools_add_output_type(cmd, inputs)
        mode = str(inputs.get('convert_from', 'tsv'))
        if mode == 'gen_sample':
            cmd.extend(['--gensample2vcf', f"{inputs.get('input_file', '')},{inputs.get('input_sample', '')}"])
        elif mode == 'hap_sample':
            cmd.extend(['--hapsample2vcf', f"{inputs.get('input_file', '')},{inputs.get('input_sample', '')}"])
        elif mode == 'hap_legend_sample':
            cmd.extend(['--haplegendsample2vcf', f"{inputs.get('input_file', '')},{inputs.get('input_legend', '')},{inputs.get('input_sample', '')}"])
        elif mode == 'gvcf':
            _add_if_value(cmd, '--fasta-ref', inputs.get('reference'))
            cmd.extend(['--gvcf2vcf', str(inputs.get('input_file', ''))])
        else:
            _add_if_value(cmd, '--fasta-ref', inputs.get('reference'))
            _add_if_value(cmd, '--samples', inputs.get('samples'))
            _add_if_value(cmd, '--columns', inputs.get('columns'))
            cmd.extend(['--tsv2vcf', str(inputs.get('input_file', ''))])
        _add_shell_redirect(cmd, f'{_out(inputs)}/converted{_bcftools_variant_suffix(inputs)}')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f'converted{_bcftools_variant_suffix(inputs)}', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FILE', {'description': 'Input gVCF, TSV, GEN, HAP, or related file'})}, 'optional': {'convert_from': ('STRING', {'default': 'tsv', 'options': ['tsv', 'gvcf', 'gen_sample', 'hap_sample', 'hap_legend_sample'], 'description': 'Galaxy conversion source mode'}), 'input_sample': ('TSV', {'description': 'Sample file for GEN/HAP input'}), 'input_legend': ('TSV', {'description': 'Legend file for HAP/LEGEND/SAMPLE input'}), 'reference': ('FASTA', {'description': 'Reference FASTA for gVCF or TSV conversion'}), 'samples': ('STRING', {'default': '', 'description': 'Comma-separated sample names for TSV conversion'}), 'columns': ('STRING', {'default': '', 'description': 'Column mapping for TSV conversion'}), 'output_type': ('STRING', {'default': 'z', 'options': ['z', 'v', 'b', 'u'], 'description': 'BCFtools output type'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsConvertFromVcfNode(CommandNode):
    """Convert VCF/BCF to IMPUTE2 or SHAPEIT tabular formats."""
    NODE_ID = 'bcftools_convert_from_vcf'
    DISPLAY_NAME = 'BCFtools Convert from VCF'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Convert VCF/BCF records to GEN/SAMPLE, HAP/SAMPLE, or HAP/LEGEND/SAMPLE files.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'convert', 'vcf to shapeit', 'vcf to impute2', 'hap legend sample']
    RETURN_TYPES = ('TSV', 'TSV', 'TSV')
    RETURN_NAMES = ('converted_variants', 'converted_legend', 'converted_samples')
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#convert'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ['bcftools', 'convert']
        mode = str(inputs.get('convert_to', 'gen_sample'))
        if mode == 'gen_sample':
            _add_if_value(cmd, '--tag', inputs.get('tag', 'GT'))
            if inputs.get('convert_3n6'):
                cmd.append('--3N6')
            if inputs.get('vcf_ids'):
                cmd.append('--vcf-ids')
            cmd.extend(['--gensample', f'{out}/converted.gen,{out}/converted.samples'])
        elif mode == 'hap_sample':
            if inputs.get('vcf_ids'):
                cmd.append('--vcf-ids')
            if inputs.get('haploid2diploid'):
                cmd.append('--haploid2diploid')
            cmd.extend(['--hapsample', f'{out}/converted.hap,{out}/converted.samples'])
        else:
            if inputs.get('vcf_ids'):
                cmd.append('--vcf-ids')
            if inputs.get('haploid2diploid'):
                cmd.append('--haploid2diploid')
            cmd.extend(['--haplegendsample', f'{out}/converted.hap,{out}/converted.legend,{out}/converted.samples'])
        _add_if_value(cmd, '--sex', inputs.get('sex_file', inputs.get('sex_info_file')))
        if inputs.get('keep_duplicates'):
            cmd.append('--keep-duplicates')
        _add_if_value(cmd, '--include', inputs.get('include'))
        _add_if_value(cmd, '--exclude', inputs.get('exclude'))
        _bcftools_add_region_targets(cmd, inputs)
        _add_if_value(cmd, '--samples', inputs.get('samples'))
        cmd.extend([str(inputs.get('input_file', '')), '.'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return _bcftools_convert_from_outputs(inputs, output_dir)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file to convert'})}, 'optional': {'convert_to': ('STRING', {'default': 'gen_sample', 'options': ['gen_sample', 'hap_sample', 'hap_legend_sample'], 'description': 'Galaxy conversion target mode'}), 'tag': ('STRING', {'default': 'GT', 'options': ['GT', 'PL', 'GP'], 'description': 'Tag to use for GEN/SAMPLE output'}), 'convert_3n6': ('BOOLEAN', {'default': False, 'description': 'Use 3N+6 GEN format'}), 'vcf_ids': ('BOOLEAN', {'default': False, 'description': 'Output VCF IDs instead of CHROM:POS_REF_ALT'}), 'haploid2diploid': ('BOOLEAN', {'default': False, 'description': 'Convert haploid genotypes to diploid homozygotes'}), 'sex_file': ('TSV', {'description': 'Per-sample sex designation file'}), 'keep_duplicates': ('BOOLEAN', {'default': False, 'description': 'Keep all multiallelic variants'}), 'samples': ('STRING', {'default': '', 'description': 'Comma-separated samples'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsCNVNode(CommandNode):
    """Call copy number variation from VCF BAF and LRR intensity fields."""
    NODE_ID = 'bcftools_cnv'
    DISPLAY_NAME = 'BCFtools CNV'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib', 'matplotlib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Call copy number variation from VCF B-allele frequency and Log R Ratio intensity annotations.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'cnv', 'copy number variation', 'BAF', 'LRR']
    RETURN_TYPES = ('TSV', 'TSV', 'HTML')
    RETURN_NAMES = ('cnv_calls', 'summary', 'plots')
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#cnv'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True
    CNV_POSTPROCESS_SCRIPT = '\nfrom pathlib import Path\nimport base64\nimport shutil\nimport sys\n\ntmp = Path(sys.argv[1])\ncn_out = Path(sys.argv[2])\nsummary_out = Path(sys.argv[3])\nplots_out = Path(sys.argv[4])\ninclude_plots = sys.argv[5] == "1"\n\ndef move_first(patterns, destination):\n    for pattern in patterns:\n        matches = sorted(tmp.glob(pattern))\n        if matches:\n            destination.parent.mkdir(parents=True, exist_ok=True)\n            shutil.move(str(matches[0]), destination)\n            return\n    raise FileNotFoundError(f"Missing bcftools cnv output matching {patterns!r}")\n\nmove_first(["cn.*.tab"], cn_out)\nmove_first(["summary.tab", "summary.*.tab"], summary_out)\nplots_out.parent.mkdir(parents=True, exist_ok=True)\nwith plots_out.open("w", encoding="utf-8") as handle:\n    handle.write("<html><body>")\n    if include_plots:\n        for plot in sorted(tmp.glob("*.png")):\n            encoded = base64.b64encode(plot.read_bytes()).decode("ascii")\n            handle.write(\'<div><img src="data:image/png;base64,\')\n            handle.write(encoded)\n            handle.write(\'" /></div><hr>\')\n    handle.write("</body></html>")\n'.strip()

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cnv_tmp = f'{out}/cnv_tmp'
        cmd = ['bcftools', 'cnv', '--output-dir', cnv_tmp]
        _add_if_value(cmd, '-c', inputs.get('control_sample'))
        _add_if_value(cmd, '-s', inputs.get('query_sample', inputs.get('sample')))
        _bcftools_add_af_file(cmd, inputs)
        plot_threshold = inputs.get('plot_threshold')
        plot_mode = inputs.get('generate_plots')
        include_plots = bool(plot_mode)
        if isinstance(plot_mode, str):
            include_plots = plot_mode.lower() not in ('', '0', 'false', 'none', 'no')
        if plot_threshold is not None and str(plot_threshold) != '':
            include_plots = True
        if include_plots:
            cmd.extend(['--plot-threshold', str(plot_threshold if plot_threshold is not None and str(plot_threshold) != '' else 0)])
        if inputs.get('aberrant_query') is not None or inputs.get('aberrant_control') is not None:
            cmd.extend(['--aberrant', f"{inputs.get('aberrant_query', '')},{inputs.get('aberrant_control', '')}"])
        _add_if_value(cmd, '--optimize', inputs.get('optimize'))
        _add_if_value(cmd, '--BAF-weight', inputs.get('baf_weight'))
        if inputs.get('baf_dev_query') is not None or inputs.get('baf_dev_control') is not None:
            cmd.extend(['--BAF-dev', f"{inputs.get('baf_dev_query', '')},{inputs.get('baf_dev_control', '')}"])
        _add_if_value(cmd, '--LRR-weight', inputs.get('lrr_weight'))
        if inputs.get('lrr_dev_query') is not None or inputs.get('lrr_dev_control') is not None:
            cmd.extend(['--LRR-dev', f"{inputs.get('lrr_dev_query', '')},{inputs.get('lrr_dev_control', '')}"])
        _add_if_value(cmd, '--LRR-smooth-win', inputs.get('lrr_smooth_win'))
        _add_if_value(cmd, '--same-prob', inputs.get('same_prob'))
        _add_if_value(cmd, '--err-prob', inputs.get('err_prob'))
        _add_if_value(cmd, '--xy-prob', inputs.get('xy_prob'))
        _bcftools_add_region_targets(cmd, inputs)
        cmd.append(str(inputs.get('input_file', '')))
        cmd.extend(['&&', 'python', '-c', cls.CNV_POSTPROCESS_SCRIPT, cnv_tmp, f'{out}/cnv.tab', f'{out}/summary.tab', f'{out}/plots.html', '1' if include_plots else '0'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'cnv.tab', output_dir), _bcftools_common_output(cls.NODE_ID, 'summary.tab', output_dir), _bcftools_common_output(cls.NODE_ID, 'plots.html', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF with BAF and LRR intensity annotations'}), 'query_sample': ('STRING', {'description': 'Sample to call for copy number variation'})}, 'optional': {'control_sample': ('STRING', {'default': '', 'description': 'Optional control sample for pairwise calling'}), 'AF_file': ('TSV', {'description': 'Allele frequency table with CHR, POS, REF, ALT, and AF columns'}), 'plot_threshold': ('FLOAT', {'default': '', 'description': 'Plot only chromosomes above this CNV quality threshold'}), 'generate_plots': ('BOOLEAN', {'default': False, 'description': 'Plan an HTML plot summary output'}), 'aberrant_query': ('FLOAT', {'default': '', 'description': 'Aberrant copy-number prior for the query sample'}), 'aberrant_control': ('FLOAT', {'default': '', 'description': 'Aberrant copy-number prior for the control sample'}), 'optimize': ('FLOAT', {'default': '', 'description': 'Adjust purity estimates using this step size'}), 'baf_weight': ('FLOAT', {'default': '', 'description': 'Relative weight of BAF evidence'}), 'baf_dev_query': ('FLOAT', {'default': '', 'description': 'Expected query BAF deviation'}), 'baf_dev_control': ('FLOAT', {'default': '', 'description': 'Expected control BAF deviation'}), 'lrr_weight': ('FLOAT', {'default': '', 'description': 'Relative weight of LRR evidence'}), 'lrr_dev_query': ('FLOAT', {'default': '', 'description': 'Expected query LRR deviation'}), 'lrr_dev_control': ('FLOAT', {'default': '', 'description': 'Expected control LRR deviation'}), 'lrr_smooth_win': ('INT', {'default': '', 'min': 0, 'description': 'LRR smoothing window'}), 'same_prob': ('FLOAT', {'default': '', 'description': 'Prior probability that query and control share a copy-number state'}), 'err_prob': ('FLOAT', {'default': '', 'description': 'HMM transition probability to another copy-number state'}), 'xy_prob': ('FLOAT', {'default': '', 'description': 'Prior probability for X/Y chromosome copy-number states'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsCSQNode(CommandNode):
    """Annotate haplotype-aware variant consequences with bcftools csq."""
    NODE_ID = 'bcftools_csq'
    DISPLAY_NAME = 'BCFtools CSQ'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Annotate VCF/BCF records with haplotype-aware consequence predictions from a FASTA and GFF3 annotation.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'csq', 'consequence prediction', 'haplotype aware consequence', 'BCSQ']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('csq_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#csq'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'csq', '--fasta-ref', str(inputs.get('reference', inputs.get('fasta_ref', ''))), '--gff-annot', str(inputs.get('gff_annot', inputs.get('annotation', '')))]
        _add_if_value(cmd, '--ncsq', inputs.get('ncsq'))
        if inputs.get('local_csq'):
            cmd.append('--local-csq')
        _add_if_value(cmd, '--phase', inputs.get('phase'))
        _add_if_value(cmd, '--custom-tag', inputs.get('custom_tag'))
        _add_if_value(cmd, '--trim-protein-seq', inputs.get('trim_protein_seq'))
        _add_if_value(cmd, '--genetic-code', inputs.get('genetic_code'))
        _add_if_value(cmd, '--samples', inputs.get('samples'))
        _add_if_value(cmd, '--include', inputs.get('include'))
        _add_if_value(cmd, '--exclude', inputs.get('exclude'))
        _bcftools_add_region_targets(cmd, inputs)
        _bcftools_add_output_type(cmd, inputs)
        cmd.append(str(inputs.get('input_file', '')))
        _add_shell_redirect(cmd, f'{_out(inputs)}/csq{_bcftools_variant_suffix(inputs)}')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f'csq{_bcftools_variant_suffix(inputs)}', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file to annotate'}), 'reference': ('FASTA', {'description': 'Reference FASTA'}), 'gff_annot': ('GFF3', {'description': 'GFF3 annotation formatted for bcftools csq'})}, 'optional': {'ncsq': ('INT', {'default': '', 'min': 1, 'description': 'Maximum number of consequences referenced per sample'}), 'local_csq': ('BOOLEAN', {'default': False, 'description': 'Run localized consequence prediction one record at a time'}), 'phase': ('STRING', {'default': '', 'options': ['', 'a', 'm', 'r', 'R', 's'], 'description': 'How unphased genotypes are handled'}), 'custom_tag': ('STRING', {'default': '', 'description': 'Custom INFO/FORMAT tag name for consequences'}), 'trim_protein_seq': ('INT', {'default': '', 'min': 0, 'description': 'Trim protein sequence context to this length'}), 'genetic_code': ('STRING', {'default': '', 'description': 'NCBI genetic code identifier'}), 'samples': ('STRING', {'default': '', 'description': "Comma-separated samples or '-' to ignore samples"}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'output_type': ('STRING', {'default': 'z', 'options': ['z', 'v', 'b', 'u'], 'description': 'BCFtools output type'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsROHNode(CommandNode):
    """Detect runs of homozygosity or autozygosity with bcftools roh."""
    NODE_ID = 'bcftools_roh'
    DISPLAY_NAME = 'BCFtools ROH'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Detect runs of homozygosity or autozygosity in VCF/BCF genotypes using a hidden Markov model.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'roh', 'runs of homozygosity', 'autozygosity', 'HMM']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('roh_table',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#roh'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'roh']
        _add_if_value(cmd, '--sample', inputs.get('sample'))
        _bcftools_add_af_file(cmd, inputs)
        _add_if_value(cmd, '--AF-tag', inputs.get('AF_tag', inputs.get('af_tag')))
        _add_if_value(cmd, '--AF-dflt', inputs.get('AF_dflt', inputs.get('af_dflt')))
        _add_if_value(cmd, '--estimate-AF', inputs.get('estimate_AF', inputs.get('estimate_af')))
        _add_if_value(cmd, '--GTs-only', inputs.get('GTs_only', inputs.get('gts_only')))
        if inputs.get('skip_indels'):
            cmd.append('--skip-indels')
        _add_if_value(cmd, '--genetic-map', inputs.get('genetic_map'))
        _add_if_value(cmd, '--rec-rate', inputs.get('rec_rate'))
        buffer_size = inputs.get('buffer_size')
        buffer_overlap = inputs.get('buffer_overlap')
        if buffer_size is not None and str(buffer_size) != '':
            if buffer_overlap is not None and str(buffer_overlap) != '':
                cmd.extend(['--buffer-size', f'{buffer_size},{buffer_overlap}'])
            else:
                cmd.extend(['--buffer-size', str(buffer_size)])
        if inputs.get('ignore_homref'):
            cmd.append('--ignore-homref')
        if inputs.get('include_noalt'):
            cmd.append('--include-noalt')
        _add_if_value(cmd, '--hw-to-az', inputs.get('hw_to_az'))
        _add_if_value(cmd, '--az-to-hw', inputs.get('az_to_hw'))
        if inputs.get('viterbi_training'):
            cmd.append('--viterbi-training')
        _bcftools_add_region_targets(cmd, inputs)
        _add_if_value(cmd, '--samples', inputs.get('samples'))
        _bcftools_add_output_type(cmd, {**inputs, 'output_type': inputs.get('output_type', 'r')})
        cmd.append(str(inputs.get('input_file', '')))
        _add_shell_redirect(cmd, f'{_out(inputs)}/roh.tsv')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'roh.tsv', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file for ROH detection'})}, 'optional': {'sample': ('STRING', {'default': '', 'description': 'Single sample to analyze'}), 'AF_file': ('TSV', {'description': 'Allele frequency table'}), 'AF_tag': ('STRING', {'default': '', 'description': 'INFO tag containing allele frequencies'}), 'AF_dflt': ('FLOAT', {'default': '', 'description': 'Default allele frequency when unavailable'}), 'estimate_AF': ('TSV', {'description': 'Samples file used to estimate allele frequencies'}), 'GTs_only': ('FLOAT', {'default': '', 'min': 0, 'description': 'Use genotypes only and set quality cap'}), 'skip_indels': ('BOOLEAN', {'default': False, 'description': 'Skip indel records'}), 'genetic_map': ('TSV', {'description': 'Genetic map file'}), 'rec_rate': ('FLOAT', {'default': '', 'description': 'Constant recombination rate'}), 'buffer_size': ('INT', {'default': '', 'description': 'Number of sites to keep in memory'}), 'buffer_overlap': ('INT', {'default': '', 'description': 'Number of overlapping sites in the sliding buffer'}), 'ignore_homref': ('BOOLEAN', {'default': False, 'description': 'Ignore homozygous reference genotypes'}), 'include_noalt': ('BOOLEAN', {'default': False, 'description': 'Include sites without alternate alleles'}), 'hw_to_az': ('FLOAT', {'default': '', 'description': 'Hardy-Weinberg to autozygous transition probability'}), 'az_to_hw': ('FLOAT', {'default': '', 'description': 'Autozygous to Hardy-Weinberg transition probability'}), 'viterbi_training': ('BOOLEAN', {'default': False, 'description': 'Estimate transition probabilities with Viterbi training'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'samples': ('STRING', {'default': '', 'description': 'Comma-separated samples'}), 'output_type': ('STRING', {'default': 'r', 'options': ['s', 'r'], 'description': 'ROH output type: per-site or regions'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsPluginCountsNode(CommandNode):
    """Count samples and variant classes with the bcftools +counts plugin."""
    NODE_ID = 'bcftools_plugin_counts'
    DISPLAY_NAME = 'BCFtools +counts'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Count samples, SNPs, indels, MNPs, and total sites in a VCF/BCF file.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'plugin', 'counts', 'variant counts', 'sample counts']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('counts_table',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://samtools.github.io/bcftools/howtos/plugins.html#counts'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True
    COUNTS_POSTPROCESS_SCRIPT = '\nfrom pathlib import Path\nimport sys\n\nraw = Path(sys.argv[1])\nout = Path(sys.argv[2])\nvalues = {\n    "samples": "0",\n    "SNPs": "0",\n    "INDELs": "0",\n    "sites": "0",\n}\nlabels = {\n    "Number of samples": "samples",\n    "Number of SNPs": "SNPs",\n    "Number of INDELs": "INDELs",\n    "Number of total sites": "sites",\n}\nfor line in raw.read_text(encoding="utf-8").splitlines():\n    label, separator, value = line.partition(":")\n    if separator and label in labels:\n        values[labels[label]] = value.strip()\nout.parent.mkdir(parents=True, exist_ok=True)\nout.write_text(\n    "#samples\\tSNPs\\tINDELs\\tsites\\n"\n    f"{values[\'samples\']}\\t{values[\'SNPs\']}\\t{values[\'INDELs\']}\\t{values[\'sites\']}\\n",\n    encoding="utf-8",\n)\n'.strip()

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        raw_counts = f'{out}/counts.raw.txt'
        cmd = _bcftools_plugin_base_cmd('counts', inputs)
        cmd.append(str(inputs.get('input_file', '')))
        _add_shell_redirect(cmd, raw_counts)
        cmd.extend(['&&', 'python', '-c', cls.COUNTS_POSTPROCESS_SCRIPT, raw_counts, f'{out}/counts.tsv'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'counts.tsv', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file to count'})}, 'optional': {'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsPluginDosageNode(CommandNode):
    """Calculate genotype dosage with the bcftools +dosage plugin."""
    NODE_ID = 'bcftools_plugin_dosage'
    DISPLAY_NAME = 'BCFtools +dosage'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Calculate per-sample genotype dosage from PL, GL, or GT tags in VCF/BCF records.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'plugin', 'dosage', 'genotype dosage', 'PL GL GT']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('dosage_table',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://samtools.github.io/bcftools/howtos/plugins.html#dosage'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd('dosage', inputs)
        cmd.append(str(inputs.get('input_file', '')))
        plugin_args: list[str] = []
        _add_if_value(plugin_args, '--tags', inputs.get('tags'))
        _bcftools_add_plugin_separator(cmd, plugin_args)
        _add_shell_redirect(cmd, f'{_out(inputs)}/dosage.tsv')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'dosage.tsv', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file with dosage source tags'})}, 'optional': {'tags': ('STRING', {'default': '', 'description': 'Comma-separated dosage source tags such as PL,GL,GT'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsPluginMissing2refNode(CommandNode):
    """Set missing genotypes to reference or major allele calls."""
    NODE_ID = 'bcftools_plugin_missing2ref'
    DISPLAY_NAME = 'BCFtools +missing2ref'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Replace missing genotypes with reference or major-allele calls using the bcftools +missing2ref plugin.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'plugin', 'missing2ref', 'set missing genotypes', 'missing to reference']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('missing2ref_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://samtools.github.io/bcftools/howtos/plugins.html#missing2ref'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd('missing2ref', inputs)
        _bcftools_add_plugin_vcf_output(cmd, inputs)
        cmd.append(str(inputs.get('input_file', '')))
        plugin_args: list[str] = []
        if inputs.get('phased'):
            plugin_args.append('--phased')
        if inputs.get('major'):
            plugin_args.append('--major')
        _bcftools_add_plugin_separator(cmd, plugin_args)
        _add_shell_redirect(cmd, f'{_out(inputs)}/missing2ref.vcf.gz')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'missing2ref.vcf.gz', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file with missing genotypes'})}, 'optional': {'phased': ('BOOLEAN', {'default': False, 'description': 'Set missing genotypes to phased reference calls'}), 'major': ('BOOLEAN', {'default': False, 'description': 'Set missing genotypes to the major allele'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsPluginTag2tagNode(CommandNode):
    """Convert between related VCF FORMAT and INFO tags."""
    NODE_ID = 'bcftools_plugin_tag2tag'
    DISPLAY_NAME = 'BCFtools +tag2tag'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Convert between related genotype likelihood and probability tags such as GL, PL, GP, and GT.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'plugin', 'tag2tag', 'convert genotype tags', 'GL PL GP GT']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('tag2tag_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://samtools.github.io/bcftools/howtos/plugins.html#tag2tag'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd('tag2tag', inputs)
        _bcftools_add_plugin_vcf_output(cmd, inputs)
        cmd.append(str(inputs.get('input_file', '')))
        plugin_args = [str(inputs.get('conversion', '--gp-to-gl'))]
        if inputs.get('replace', True):
            plugin_args.append('--replace')
        if plugin_args[0] == '--gp-to-gt':
            _add_if_value(plugin_args, '--threshold', inputs.get('threshold'))
        _bcftools_add_plugin_separator(cmd, plugin_args)
        _add_shell_redirect(cmd, f'{_out(inputs)}/tag2tag.vcf.gz')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'tag2tag.vcf.gz', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file with tags to convert'})}, 'optional': {'conversion': ('STRING', {'default': '--gp-to-gl', 'options': ['--gp-to-gl', '--gp-to-gt', '--gl-to-pl', '--pl-to-gl', '--QR-QA-to-QS'], 'description': 'Tag conversion mode'}), 'replace': ('BOOLEAN', {'default': True, 'description': 'Drop the source tag after conversion'}), 'threshold': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 1, 'description': 'GP-to-GT hard-call threshold'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsPluginFillAnAcNode(CommandNode):
    """Fill INFO/AN and INFO/AC with the deprecated bcftools plugin."""
    NODE_ID = 'bcftools_plugin_fill_an_ac'
    DISPLAY_NAME = 'BCFtools +fill-AN-AC'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Fill INFO/AN and INFO/AC allele count fields in VCF/BCF records with the deprecated bcftools +fill-AN-AC plugin.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'plugin', 'fill-AN-AC', 'fill AN AC', 'allele count tags']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('fill_an_ac_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://samtools.github.io/bcftools/howtos/plugins.html'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd('fill-AN-AC', inputs)
        _bcftools_add_plugin_vcf_output(cmd, inputs)
        cmd.append(str(inputs.get('input_file', '')))
        _add_shell_redirect(cmd, f'{_out(inputs)}/fill_an_ac.vcf.gz')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'fill_an_ac.vcf.gz', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file to annotate with AN and AC'})}, 'optional': {'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsPluginFillTagsNode(CommandNode):
    """Fill INFO and FORMAT summary tags with the bcftools +fill-tags plugin."""
    NODE_ID = 'bcftools_plugin_fill_tags'
    DISPLAY_NAME = 'BCFtools +fill-tags'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Set INFO tags such as AF, AC, AN, HWE, MAF, NS, and FORMAT/VAF with the bcftools +fill-tags plugin.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'plugin', 'fill-tags', 'fill INFO tags', 'allele frequency tags']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('fill_tags_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://samtools.github.io/bcftools/howtos/plugin.fill-tags.html'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd('fill-tags', inputs)
        _bcftools_add_plugin_vcf_output(cmd, inputs)
        cmd.append(str(inputs.get('input_file', '')))
        plugin_args: list[str] = []
        tags = _as_list(inputs.get('tags'))
        if tags:
            plugin_args.extend(['--tags', ','.join(tags)])
        samples = str(inputs.get('samples', '')).strip()
        if samples:
            if inputs.get('invert_samples'):
                samples = f'^{samples}'
            plugin_args.extend(['--samples', samples])
        samples_file = str(inputs.get('samples_file', '')).strip()
        if samples_file:
            if inputs.get('invert_samples_file'):
                samples_file = f'^{samples_file}'
            plugin_args.extend(['--samples-file', samples_file])
        if inputs.get('drop_missing'):
            plugin_args.append('--drop-missing')
        _bcftools_add_plugin_separator(cmd, plugin_args)
        _add_shell_redirect(cmd, f'{_out(inputs)}/fill_tags.vcf.gz')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'fill_tags.vcf.gz', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file to annotate with derived INFO/FORMAT tags'})}, 'optional': {'tags': ('STRING_LIST', {'default': [], 'options': ['AF', 'AN', 'AC', 'AC_Hom', 'AC_Het', 'AC_Hemi', 'HWE', 'ExcHet', 'MAF', 'NS', 'TYPE', 'FORMAT/VAF'], 'description': 'Output tags to set; leave empty to use the plugin default'}), 'samples': ('STRING', {'default': '', 'description': 'Comma-separated samples to include, or - for all samples'}), 'invert_samples': ('BOOLEAN', {'default': False, 'description': 'Exclude the listed samples instead of including them'}), 'samples_file': ('TSV', {'description': 'Sample or population assignment file'}), 'invert_samples_file': ('BOOLEAN', {'default': False, 'description': 'Exclude samples from the sample file'}), 'drop_missing': ('BOOLEAN', {'default': False, 'description': 'Do not count half-missing genotypes as hemizygous'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsPluginSetgtNode(CommandNode):
    """Set genotypes using the bcftools +setGT plugin."""
    NODE_ID = 'bcftools_plugin_setgt'
    DISPLAY_NAME = 'BCFtools +setGT'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Set genotypes to missing, reference, major, minor, phased, unphased, or custom calls using bcftools +setGT.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'plugin', 'setGT', 'set genotype calls', 'replace genotypes']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('setgt_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://samtools.github.io/bcftools/howtos/plugin.setGT.html'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'plugin', 'setGT']
        _bcftools_add_region_targets(cmd, inputs)
        _bcftools_add_plugin_vcf_output(cmd, inputs)
        cmd.append(str(inputs.get('input_file', '')))
        plugin_args = ['--target-gt', str(inputs.get('target_gt', '.')), '--new-gt', str(inputs.get('new_gt', '0'))]
        _add_if_value(plugin_args, '--include', inputs.get('include'))
        _add_if_value(plugin_args, '--exclude', inputs.get('exclude'))
        _add_if_value(plugin_args, '--seed', inputs.get('seed'))
        _bcftools_add_plugin_separator(cmd, plugin_args)
        _add_shell_redirect(cmd, f'{_out(inputs)}/setgt.vcf.gz')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'setgt.vcf.gz', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file with genotypes to edit'})}, 'optional': {'target_gt': ('STRING', {'default': '.', 'options': ['./.', './x', '.', 'a', 'b', 'q'], 'description': 'Target genotypes to change: missing, partially missing, all, binomial-test, or query-selected'}), 'new_gt': ('STRING', {'default': '0', 'options': ['.', '0', 'c:GT', 'c:./.', 'M', 'm', 'p', 'u'], 'description': 'New genotype value or transformation'}), 'include': ('STRING', {'default': '', 'description': 'Plugin genotype include expression; requires target_gt q'}), 'exclude': ('STRING', {'default': '', 'description': 'Plugin genotype exclude expression; requires target_gt q'}), 'seed': ('INT', {'default': '', 'description': 'Random seed for target_gt r modes'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsPluginFixploidyNode(CommandNode):
    """Fix genotype ploidy with bcftools +fixploidy."""
    NODE_ID = 'bcftools_plugin_fixploidy'
    DISPLAY_NAME = 'BCFtools +fixploidy'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Adjust genotype ploidy from sample sex and ploidy-region tables using the bcftools +fixploidy plugin.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'plugin', 'fixploidy', 'fix ploidy', 'sample sex ploidy']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('fixploidy_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://samtools.github.io/bcftools/howtos/plugins.html'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd('fixploidy', inputs)
        _bcftools_add_plugin_vcf_output(cmd, inputs)
        cmd.append(str(inputs.get('input_file', '')))
        plugin_args: list[str] = []
        _add_if_value(plugin_args, '--ploidy', inputs.get('ploidy_file'))
        _add_if_value(plugin_args, '--sex', inputs.get('sex'))
        _add_if_value(plugin_args, '--default-ploidy', inputs.get('default_ploidy'))
        _add_if_value(plugin_args, '--force-ploidy', inputs.get('force_ploidy'))
        _add_if_value(plugin_args, '--tags', inputs.get('tags', 'GT'))
        _bcftools_add_plugin_separator(cmd, plugin_args)
        _add_shell_redirect(cmd, f'{_out(inputs)}/fixploidy.vcf.gz')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'fixploidy.vcf.gz', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file with genotypes to resize by ploidy'})}, 'optional': {'ploidy_file': ('TSV', {'description': 'Tabular CHROM,FROM,TO,SEX,PLOIDY ploidy map'}), 'sex': ('TSV', {'description': 'Sample sex file with NAME SEX columns'}), 'default_ploidy': ('INT', {'default': '', 'description': 'Default ploidy for regions not listed in the ploidy map'}), 'force_ploidy': ('INT', {'default': '', 'description': 'Ignore the ploidy file and force this ploidy for all genotypes'}), 'tags': ('STRING', {'default': 'GT', 'options': ['GT'], 'description': 'VCF tag to fix; bcftools currently supports GT'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsPluginMendelianNode(CommandNode):
    """Count and filter Mendelian-consistent or inconsistent genotypes."""
    NODE_ID = 'bcftools_plugin_mendelian'
    DISPLAY_NAME = 'BCFtools +mendelian2'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Count, annotate, filter, or repair Mendelian-consistent and inconsistent trio genotypes with bcftools +mendelian2.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'plugin', 'mendelian2', 'mendelian consistency', 'trio genotypes']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('mendelian_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://samtools.github.io/bcftools/howtos/plugin.mendelian.html'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        stderr_path = f'{out}/mendelian.stderr.txt'
        cmd = ['bcftools', 'plugin', 'mendelian2']
        _bcftools_add_restrict(cmd, inputs)
        cmd.extend(['--output-type', 'z'])
        cmd.append(str(inputs.get('input_file', '')))
        plugin_args: list[str] = []
        if str(inputs.get('trios_src', 'trio')) == 'trio_file':
            _add_if_value(plugin_args, '--ped', inputs.get('trio_file'))
        else:
            child = str(inputs.get('child', ''))
            father = str(inputs.get('father', ''))
            mother = str(inputs.get('mother', ''))
            sex_prefix = str(inputs.get('num_x', inputs.get('sex_pattern', '2X')) or '2X')
            plugin_args.extend(['--pfm', f'{sex_prefix}:{child},{father},{mother}'])
        _add_if_value(plugin_args, '--rules', inputs.get('rules'))
        _add_if_value(plugin_args, '--rules-file', inputs.get('rules_file'))
        plugin_args.extend(['--mode', _bcftools_join_mode(inputs.get('mode'), 'a')])
        _bcftools_add_plugin_separator(cmd, plugin_args)
        cmd.extend(['2>', stderr_path])
        _add_shell_redirect(cmd, f'{out}/mendelian.vcf.gz')
        cmd.extend(['&&', 'cat', stderr_path])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'mendelian.vcf.gz', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file containing trio samples'})}, 'optional': {'trios_src': ('STRING', {'default': 'trio', 'options': ['trio', 'trio_file'], 'description': 'Provide one inline trio or a PED trio file'}), 'child': ('STRING', {'default': '', 'description': 'Child/proband sample name for inline trio mode'}), 'mother': ('STRING', {'default': '', 'description': 'Mother sample name for inline trio mode'}), 'father': ('STRING', {'default': '', 'description': 'Father sample name for inline trio mode'}), 'num_x': ('STRING', {'default': '2X', 'options': ['1X', '2X'], 'description': 'ChrX inheritance pattern for the child'}), 'trio_file': ('TSV', {'description': 'PED file with family, proband, father, mother, and sex columns'}), 'mode': ('STRING_LIST', {'default': ['a'], 'options': ['a', 'd', 'e', 'E', 'g', 'm', 'M', 'S'], 'description': 'VCF output modes to combine'}), 'rules': ('STRING', {'default': '', 'options': ['', 'GRCh37', 'GRCh38'], 'description': 'Predefined inheritance rules'}), 'rules_file': ('TSV', {'description': 'Custom inheritance rules file'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsPluginImputeInfoNode(CommandNode):
    """Add IMPUTE2 information metrics with bcftools +impute-info."""
    NODE_ID = 'bcftools_plugin_impute_info'
    DISPLAY_NAME = 'BCFtools +impute-info'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Add IMPUTE2-style imputation information metrics from FORMAT/GP probabilities using the bcftools +impute-info plugin.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'plugin', 'impute-info', 'imputation info', 'IMPUTE2 INFO']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('impute_info_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://samtools.github.io/bcftools/howtos/plugins.html'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd('impute-info', inputs)
        _bcftools_add_plugin_vcf_output(cmd, inputs)
        cmd.append(str(inputs.get('input_file', '')))
        _add_shell_redirect(cmd, f'{_out(inputs)}/impute_info.vcf.gz')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'impute_info.vcf.gz', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file with FORMAT/GP probabilities'})}, 'optional': {'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsPluginColorChrsNode(CommandNode):
    """Color shared chromosomal segments with bcftools +color-chrs."""
    NODE_ID = 'bcftools_plugin_color_chrs'
    DISPLAY_NAME = 'BCFtools +color-chrs'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Color shared chromosomal segments between trio or unrelated phased genotype samples with the bcftools +color-chrs plugin.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'plugin', 'color-chrs', 'color shared chromosomal segments', 'phased GTs']
    RETURN_TYPES = ('TSV', 'IMAGE')
    RETURN_NAMES = ('segments_table', 'segments_svg')
    REQUIRED_EXECUTABLES = ['bcftools', 'color-chrs.pl']
    DOCUMENTATION_URL = 'https://samtools.github.io/bcftools/howtos/plugins.html'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        prefix = f'{out}/color_chrs_tmp'
        cmd = _bcftools_plugin_base_cmd('color-chrs', inputs)
        _add_if_value(cmd, '--threads', inputs.get('threads'))
        cmd.append(str(inputs.get('input_file', '')))
        if str(inputs.get('sample_rel_sel', 'trio')) == 'unrelated':
            relation_args = ['--unrelated', f"{inputs.get('sample_a', '')},{inputs.get('sample_b', '')}"]
        else:
            relation_args = ['--trio', f"{inputs.get('mother', '')},{inputs.get('father', '')},{inputs.get('child', '')}"]
        plugin_args = [*relation_args, '-p', prefix]
        _bcftools_add_plugin_separator(cmd, plugin_args)
        cmd.extend(['&&', 'color-chrs.pl', f'{prefix}.dat', '-p', prefix, '&&', 'mv', f'{prefix}.dat', f'{out}/color_chrs.tsv', '&&', 'mv', f'{prefix}.svg', f'{out}/color_chrs.svg'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'color_chrs.tsv', output_dir), _bcftools_common_output(cls.NODE_ID, 'color_chrs.svg', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'Phased VCF/BCF file with GT genotypes'})}, 'optional': {'sample_rel_sel': ('STRING', {'default': 'trio', 'options': ['trio', 'unrelated'], 'description': 'Sample relationship mode'}), 'mother': ('STRING', {'default': '', 'description': 'Mother sample name for trio mode'}), 'father': ('STRING', {'default': '', 'description': 'Father sample name for trio mode'}), 'child': ('STRING', {'default': '', 'description': 'Child sample name for trio mode'}), 'sample_a': ('STRING', {'default': '', 'description': 'First sample name for unrelated mode'}), 'sample_b': ('STRING', {'default': '', 'description': 'Second sample name for unrelated mode'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsPluginFrameshiftsNode(CommandNode):
    """Annotate frameshift indels with bcftools +frameshifts."""
    NODE_ID = 'bcftools_plugin_frameshifts'
    DISPLAY_NAME = 'BCFtools +frameshifts'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Annotate indel records with out-of-frame status from exon intervals using the bcftools +frameshifts plugin.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'plugin', 'frameshifts', 'frameshift indels', 'OOF annotation']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('frameshifts_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools', 'bgzip', 'tabix']
    DOCUMENTATION_URL = 'https://samtools.github.io/bcftools/howtos/plugins.html'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        exons_gz = f'{out}/exons.bed.gz'
        cmd = ['bgzip', '-c', str(inputs.get('exons', '')), '>', exons_gz, '&&', 'tabix', exons_gz, '&&']
        plugin_cmd = _bcftools_plugin_base_cmd('frameshifts', inputs)
        _bcftools_add_plugin_vcf_output(plugin_cmd, inputs)
        plugin_cmd.append(str(inputs.get('input_file', '')))
        _bcftools_add_plugin_separator(plugin_cmd, ['--exons', exons_gz])
        _add_shell_redirect(plugin_cmd, f'{out}/frameshifts.vcf.gz')
        cmd.extend(plugin_cmd)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'frameshifts.vcf.gz', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file containing indels to annotate'}), 'exons': ('BED', {'description': 'BED file describing reference genome exons'})}, 'optional': {'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class BCFtoolsPluginSplitVepNode(CommandNode):
    """Extract structured annotation fields with bcftools +split-vep."""
    NODE_ID = 'bcftools_plugin_split_vep'
    DISPLAY_NAME = 'BCFtools +split-vep'
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    CATEGORY = 'variant'
    DESCRIPTION = 'Extract fields from VEP, ANN, EFF, or other structured INFO annotations into new VCF INFO tags.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bcftools', 'plugin', 'split-vep', 'split VEP annotations', 'structured annotations']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('split_vep_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://samtools.github.io/bcftools/howtos/plugin.split-vep.html'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd('split-vep', inputs)
        cmd.extend(['--output-type', 'z'])
        cmd.append(str(inputs.get('input_file', '')))
        plugin_args = ['-a', str(inputs.get('a', 'CSQ')), '-c', str(inputs.get('c', ''))]
        if inputs.get('d'):
            plugin_args.append('-d')
        if inputs.get('allow_undef_tags'):
            plugin_args.append('--allow-undef-tags')
        _add_if_value(plugin_args, '-p', inputs.get('p'))
        _add_if_value(plugin_args, '-s', inputs.get('s'))
        _bcftools_add_plugin_separator(cmd, plugin_args)
        _add_shell_redirect(cmd, f'{_out(inputs)}/split_vep.vcf.gz')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'split_vep.vcf.gz', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file with structured INFO annotations'})}, 'optional': {'a': ('STRING', {'default': 'CSQ', 'description': 'INFO annotation tag to parse, such as CSQ, ANN, EFF, or BCSQ'}), 'c': ('STRING', {'default': '', 'description': 'Annotation fields to extract by name or index, optionally with :Integer or :Float types'}), 'd': ('BOOLEAN', {'default': False, 'description': 'Output each transcript or allele consequence on a new line'}), 'allow_undef_tags': ('BOOLEAN', {'default': False, 'description': 'Print missing values for undefined annotation tags'}), 'p': ('STRING', {'default': '', 'description': 'Prefix for newly created INFO annotations'}), 's': ('STRING', {'default': '', 'description': 'Transcript and consequence selector such as worst or :missense'}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'})}, 'hidden': {'output': ('STRING', {})}}
