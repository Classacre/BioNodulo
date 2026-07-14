"""arriba — rna_seq node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ArribaNode(CommandNode):
    """Detect gene fusions from STAR-aligned RNA-Seq data."""
    NODE_ID = 'arriba'
    DISPLAY_NAME = 'Arriba'
    REQUIRED_CONDA_PACKAGES = ['arriba']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Detect gene fusions from STAR aligned RNA-Seq data with Arriba.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Arriba', 'arriba', 'gene fusions', 'fusion transcript', 'STAR Chimeric.out.sam', 'RNA-Seq fusion detection', 'aberrant transcripts']
    RETURN_TYPES = ('TSV', 'TSV', 'VCF', 'DIRECTORY', 'PDF')
    RETURN_NAMES = ('fusions_tsv', 'discarded_fusions_tsv', 'fusions_vcf', 'fusion_bams', 'fusions_pdf')
    REQUIRED_EXECUTABLES = ['arriba', 'samtools', 'convert_fusions_to_vcf.sh', 'extract_fusion-supporting_alignments.sh', 'draw_fusions.R']
    DOCUMENTATION_URL = ARRIBA_DOCUMENTATION_URL
    CITATION_DOIS = [ARRIBA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{ARRIBA_CITATION_DOI}']
    CITATION_TEXT = ARRIBA_CITATION_TEXT
    VERSION = '2.5.1+galaxy0'
    SHELL = True
    FILTER_OPTIONS = ['top_expressed_viral_contigs', 'viral_contigs', 'low_coverage_viral_contigs', 'uninteresting_contigs', 'no_genomic_support', 'short_anchor', 'select_best', 'many_spliced', 'long_gap', 'merge_adjacent', 'hairpin', 'small_insert_size', 'same_gene', 'genomic_support', 'read_through', 'no_coverage', 'mismatches', 'homopolymer', 'low_entropy', 'multimappers', 'inconsistently_clipped', 'duplicates', 'homologs', 'blacklist', 'mismappers', 'spliced', 'relative_support', 'min_support', 'known_fusions', 'end_to_end', 'non_coding_neighbors', 'isoforms', 'intronic', 'in_vitro', 'intragenic_exonic', 'internal_tandem_duplication']
    STRANDEDNESS_OPTIONS = ['auto', 'yes', 'no', 'reverse']
    YES_NO_OPTIONS = ['yes', 'no']
    TRANSCRIPT_SELECTION_OPTIONS = ['coverage', 'provided', 'canonical']
    MIN_CONFIDENCE_OPTIONS = ['none', 'low', 'medium', 'high']
    TRUE_FALSE_OPTIONS = ['TRUE', 'FALSE']
    VALUE_FLAGS = [('gtf_features', '-G'), ('strandedness', '-s'), ('genome_contigs', '-i'), ('viral_contigs', '-v'), ('max_evalue', '-E'), ('min_supporting_reads', '-S'), ('max_mismappers', '-m'), ('max_homolog_identity', '-L'), ('homopolymer_length', '-H'), ('read_through_distance', '-R'), ('min_anchor_length', '-A'), ('many_spliced_events', '-M'), ('max_kmer_content', '-K'), ('max_mismatch_pvalue', '-V'), ('fragment_length', '-F'), ('max_reads', '-U'), ('quantile', '-Q'), ('exonic_fraction', '-e'), ('top_n', '-T'), ('covered_fraction', '-C'), ('max_itd_length', '-l'), ('min_itd_allele_fraction', '-z'), ('min_itd_supporting_reads', '-Z')]
    BOOLEAN_FLAGS = [('duplicate_marking', '-u'), ('fill_discarded_columns', '-X'), ('fill_the_gaps', '-I')]
    DRAW_VALUE_OPTIONS = [('transcript_selection', '--transcriptSelection', 'transcriptSelection'), ('min_confidence_for_circos_plot', '--minConfidenceForCircosPlot', 'minConfidenceForCircosPlot'), ('squish_introns', '--squishIntrons', 'squishIntrons'), ('merge_domains_overlapping_by', '--mergeDomainsOverlappingBy', 'mergeDomainsOverlappingBy'), ('sample_name', '--sampleName', 'sampleName'), ('print_exon_labels', '--printExonLabels', 'printExonLabels'), ('coverage_range', '--coverageRange', 'coverageRange'), ('render_3d_effect', '--render3dEffect', 'render3dEffect'), ('optimize_domain_colors', '--optimizeDomainColors', 'optimizeDomainColors'), ('color1', '--color1', 'color1'), ('color2', '--color2', 'color2'), ('pdf_width', '--pdfWidth', 'pdfWidth'), ('pdf_height', '--pdfHeight', 'pdfHeight'), ('font_family', '--fontFamily', 'fontFamily'), ('font_size', '--fontSize', 'fontSize'), ('fixed_scale', '--fixedScale', 'fixedScale'), ('plot_panels', '--plotPanels', 'plotPanels')]

    @classmethod
    def _path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f'{_out(inputs)}/{filename}'

    @classmethod
    def _bool_default_true(cls, inputs: dict[str, Any], name: str) -> bool:
        return bool(inputs.get(name, True))

    @classmethod
    def _do_viz(cls, inputs: dict[str, Any]) -> bool:
        return str(inputs.get('do_viz', inputs.get('visualization', 'no')) or 'no') == 'yes'

    @classmethod
    def _filters(cls, inputs: dict[str, Any]) -> list[str]:
        filters = _as_list(inputs.get('filters'))
        if not str(inputs.get('blacklist', '') or '').strip() and 'blacklist' not in filters:
            filters.append('blacklist')
        return filters

    @classmethod
    def _link_command(cls, source: str, target: str) -> str:
        return _shell_join(['ln', '-sf', source, target])

    @staticmethod
    def _flag_value(flag: str, value: Any) -> str:
        return f'{flag}={shlex.quote(str(value))}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        commands = [cls._link_command(str(inputs.get('genome_assembly', '') or ''), 'genome.fa'), cls._link_command(str(inputs.get('annotation', '') or ''), 'genome.gtf')]
        blacklist = str(inputs.get('blacklist', '') or '')
        blacklist_arg = blacklist
        if blacklist.endswith('.gz'):
            blacklist_arg = 'blacklist.tsv.gz'
            commands.append(cls._link_command(blacklist, blacklist_arg))
        known_fusions = str(inputs.get('known_fusions', '') or '')
        known_fusions_arg = known_fusions
        if known_fusions.endswith('.gz'):
            known_fusions_arg = 'known_fusions.tsv.gz'
            commands.append(cls._link_command(known_fusions, known_fusions_arg))
        tags = str(inputs.get('tags', '') or '')
        tags_arg = tags
        if tags.endswith('.gz'):
            tags_arg = 'tags.tsv.gz'
            commands.append(cls._link_command(tags, tags_arg))
        cmd = ['arriba', '-x', str(inputs.get('input', '') or '')]
        _add_if_value(cmd, '-c', inputs.get('chimeric'))
        cmd.extend(['-a', 'genome.fa', '-g', 'genome.gtf'])
        _add_if_value(cmd, '-b', blacklist_arg)
        filters = cls._filters(inputs)
        if filters:
            cmd.extend(['-f', ','.join(filters)])
        _add_if_value(cmd, '-p', inputs.get('protein_domains'))
        _add_if_value(cmd, '-k', known_fusions_arg)
        _add_if_value(cmd, '-t', tags_arg)
        if str(inputs.get('use_wgs', 'no') or 'no') == 'yes':
            _add_if_value(cmd, '-d', inputs.get('wgs'))
            _add_if_value(cmd, '-D', inputs.get('max_genomic_breakpoint_distance'))
        cmd.extend(['-o', cls._path(inputs, 'fusions.tsv')])
        if cls._bool_default_true(inputs, 'output_fusions_discarded'):
            cmd.extend(['-O', cls._path(inputs, 'fusions.discarded.tsv')])
        for name, flag in cls.VALUE_FLAGS:
            _add_if_value(cmd, flag, inputs.get(name))
        for name, flag in cls.BOOLEAN_FLAGS:
            if inputs.get(name):
                cmd.append(flag)
        commands.append(_shell_join(cmd))
        sorted_bam = cls._path(inputs, 'Aligned.sortedByCoord.out.bam')
        needs_sorted_bam = bool(inputs.get('output_fusion_bams')) or cls._do_viz(inputs)
        if needs_sorted_bam:
            sort_cmd = _shell_join(['samtools', 'sort', '-@', '${GALAXY_SLOTS:-1}', '-m', '4G', '-T', 'tmp', '-O', 'bam', str(inputs.get('input', '') or ''), '>', sorted_bam]).replace("'${GALAXY_SLOTS:-1}'", '${GALAXY_SLOTS:-1}')
            commands.append(sort_cmd)
            commands.append(_shell_join(['samtools', 'index', sorted_bam]))
        if cls._bool_default_true(inputs, 'output_fusions_vcf'):
            commands.append(_shell_join(['convert_fusions_to_vcf.sh', 'genome.fa', cls._path(inputs, 'fusions.tsv'), cls._path(inputs, 'fusions.vcf')]))
        if inputs.get('output_fusion_bams'):
            fusion_bams = cls._path(inputs, 'fusion_bams')
            commands.append(_shell_join(['mkdir', '-p', fusion_bams]))
            commands.append(_shell_join(['extract_fusion-supporting_alignments.sh', cls._path(inputs, 'fusions.tsv'), sorted_bam, f'{fusion_bams}/fusion']))
        if cls._do_viz(inputs):
            draw_cmd = ['draw_fusions.R', cls._flag_value('--fusions', cls._path(inputs, 'fusions.tsv')), cls._flag_value('--alignments', sorted_bam), '--annotation=genome.gtf', cls._flag_value('--output', cls._path(inputs, 'fusions.pdf'))]
            if inputs.get('cytobands') not in (None, ''):
                draw_cmd.append(cls._flag_value('--cytobands', inputs.get('cytobands')))
            if inputs.get('protein_domains') not in (None, ''):
                draw_cmd.append(cls._flag_value('--proteinDomains', inputs.get('protein_domains')))
            squish_introns = str(inputs.get('squish_introns', '') or '')
            for name, flag, alias in cls.DRAW_VALUE_OPTIONS:
                value = inputs.get(name, inputs.get(alias))
                if name == 'plot_panels' and value is True:
                    value = 'TRUE'
                if value not in (None, '', False):
                    draw_cmd.append(cls._flag_value(flag, value))
                if name == 'squish_introns':
                    squish_introns = str(value or squish_introns)
                    if squish_introns == 'FALSE':
                        show_intergenic_vicinity = inputs.get('show_intergenic_vicinity', inputs.get('showIntergenicVicinity'))
                        if show_intergenic_vicinity not in (None, ''):
                            draw_cmd.append(cls._flag_value('--showIntergenicVicinity', show_intergenic_vicinity))
            commands.append(' '.join(draw_cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'fusions.tsv']
        if cls._bool_default_true(inputs, 'output_fusions_discarded'):
            outputs.append(out / 'fusions.discarded.tsv')
        if cls._bool_default_true(inputs, 'output_fusions_vcf'):
            outputs.append(out / 'fusions.vcf')
        if inputs.get('output_fusion_bams'):
            outputs.append(out / 'fusion_bams')
        if cls._do_viz(inputs):
            outputs.append(out / 'fusions.pdf')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '') or '').strip():
            return 'input is required'
        if not str(inputs.get('genome_assembly', '') or '').strip():
            return 'genome_assembly is required'
        if not str(inputs.get('annotation', '') or '').strip():
            return 'annotation is required'
        invalid_filters = [value for value in _as_list(inputs.get('filters')) if value not in cls.FILTER_OPTIONS]
        if invalid_filters:
            return 'filters values must be one of the supported Arriba filter names'
        strandedness = str(inputs.get('strandedness', '') or '')
        if strandedness and strandedness not in cls.STRANDEDNESS_OPTIONS:
            return f"strandedness must be one of: {', '.join(cls.STRANDEDNESS_OPTIONS)}"
        if str(inputs.get('use_wgs', 'no') or 'no') == 'yes' and (not str(inputs.get('wgs', '') or '').strip()):
            return 'wgs is required when use_wgs is yes'
        do_viz = str(inputs.get('do_viz', 'no') or 'no')
        if do_viz not in cls.YES_NO_OPTIONS:
            return f"do_viz must be one of: {', '.join(cls.YES_NO_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('BAM', {'description': 'STAR Aligned.out SAM/BAM/CRAM file'}), 'genome_assembly': ('FASTA', {'description': 'Genome assembly FASTA used for STAR alignment'}), 'annotation': ('GTF', {'description': 'Gene annotation in GTF format'})}, 'optional': {'chimeric': ('BAM', {'default': '', 'description': 'STAR Chimeric.out.sam for SeparateSAMold mode'}), 'blacklist': ('TSV', {'default': '', 'description': 'Optional Arriba blacklist table'}), 'protein_domains': ('GFF', {'default': '', 'description': 'Protein domain annotation in GFF3 format'}), 'known_fusions': ('TSV', {'default': '', 'description': 'Known fusions table'}), 'tags': ('TSV', {'default': '', 'description': 'Fusion tag table'}), 'use_wgs': ('STRING', {'default': 'no', 'options': cls.YES_NO_OPTIONS}), 'wgs': ('FILE', {'default': '', 'description': 'Optional WGS structural variant calls'}), 'max_genomic_breakpoint_distance': ('INT', {'default': 100000, 'min': 0, 'advanced': True}), 'filters': ('STRING', {'default': [], 'multiple': True, 'options': cls.FILTER_OPTIONS, 'description': 'Arriba filters to disable'}), 'gtf_features': ('STRING', {'default': '', 'advanced': True}), 'strandedness': ('STRING', {'default': '', 'options': cls.STRANDEDNESS_OPTIONS, 'advanced': True}), 'genome_contigs': ('STRING', {'default': '', 'advanced': True}), 'viral_contigs': ('STRING', {'default': '', 'advanced': True}), 'max_evalue': ('FLOAT', {'default': '', 'min': 0, 'advanced': True}), 'min_supporting_reads': ('INT', {'default': '', 'min': 1, 'advanced': True}), 'max_mismappers': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'advanced': True}), 'max_homolog_identity': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'advanced': True}), 'homopolymer_length': ('INT', {'default': '', 'min': 1, 'advanced': True}), 'read_through_distance': ('INT', {'default': '', 'min': 1, 'advanced': True}), 'min_anchor_length': ('INT', {'default': '', 'min': 1, 'advanced': True}), 'many_spliced_events': ('INT', {'default': '', 'min': 1, 'advanced': True}), 'max_kmer_content': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'advanced': True}), 'max_mismatch_pvalue': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'advanced': True}), 'fragment_length': ('INT', {'default': '', 'min': 1, 'advanced': True}), 'max_reads': ('INT', {'default': '', 'min': 1, 'advanced': True}), 'quantile': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'advanced': True}), 'exonic_fraction': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'advanced': True}), 'top_n': ('INT', {'default': '', 'min': 1, 'advanced': True}), 'covered_fraction': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'advanced': True}), 'max_itd_length': ('INT', {'default': '', 'min': 1, 'advanced': True}), 'min_itd_allele_fraction': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'advanced': True}), 'min_itd_supporting_reads': ('INT', {'default': '', 'min': 1, 'advanced': True}), 'duplicate_marking': ('BOOLEAN', {'default': False, 'advanced': True}), 'fill_discarded_columns': ('BOOLEAN', {'default': False, 'advanced': True}), 'fill_the_gaps': ('BOOLEAN', {'default': False, 'advanced': True}), 'output_fusions_discarded': ('BOOLEAN', {'default': True}), 'output_fusions_vcf': ('BOOLEAN', {'default': True}), 'output_fusion_bams': ('BOOLEAN', {'default': False}), 'do_viz': ('STRING', {'default': 'no', 'options': cls.YES_NO_OPTIONS}), 'cytobands': ('TSV', {'default': '', 'advanced': True}), 'sample_name': ('STRING', {'default': '', 'advanced': True}), 'transcript_selection': ('STRING', {'default': 'provided', 'options': cls.TRANSCRIPT_SELECTION_OPTIONS, 'advanced': True}), 'min_confidence_for_circos_plot': ('STRING', {'default': '', 'options': cls.MIN_CONFIDENCE_OPTIONS, 'advanced': True}), 'squish_introns': ('STRING', {'default': '', 'options': cls.TRUE_FALSE_OPTIONS, 'advanced': True}), 'show_intergenic_vicinity': ('STRING', {'default': '', 'advanced': True}), 'merge_domains_overlapping_by': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'advanced': True}), 'print_exon_labels': ('STRING', {'default': '', 'options': cls.TRUE_FALSE_OPTIONS, 'advanced': True}), 'coverage_range': ('STRING', {'default': '', 'advanced': True}), 'render_3d_effect': ('STRING', {'default': '', 'options': cls.TRUE_FALSE_OPTIONS, 'advanced': True}), 'optimize_domain_colors': ('STRING', {'default': '', 'options': cls.TRUE_FALSE_OPTIONS, 'advanced': True}), 'color1': ('STRING', {'default': '', 'advanced': True}), 'color2': ('STRING', {'default': '', 'advanced': True}), 'pdf_width': ('FLOAT', {'default': '', 'min': 1, 'advanced': True}), 'pdf_height': ('FLOAT', {'default': '', 'min': 1, 'advanced': True}), 'font_family': ('STRING', {'default': '', 'advanced': True}), 'font_size': ('FLOAT', {'default': '', 'min': 0, 'advanced': True}), 'fixed_scale': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'plot_panels': ('BOOLEAN', {'default': False, 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
