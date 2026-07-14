"""arriba — visualization node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ArribaDrawFusionsNode(CommandNode):
    """Render Arriba fusion predictions to PDF."""
    NODE_ID = 'arriba_draw_fusions'
    DISPLAY_NAME = 'Arriba Draw Fusions'
    REQUIRED_CONDA_PACKAGES = ['arriba']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Render Arriba fusion predictions as transcript visualization PDFs.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Arriba Draw Fusions', 'arriba_draw_fusions', 'draw_fusions.R', 'fusion visualization', 'RNA-Seq fusion plot', 'fusions.pdf']
    RETURN_TYPES = ('PDF',)
    RETURN_NAMES = ('fusions_pdf',)
    REQUIRED_EXECUTABLES = ['draw_fusions.R', 'samtools']
    DOCUMENTATION_URL = 'https://github.com/suhrig/arriba/wiki/06-Visualization'
    CITATION_DOIS = [ARRIBA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{ARRIBA_CITATION_DOI}']
    CITATION_TEXT = ARRIBA_CITATION_TEXT
    VERSION = '2.5.1+galaxy0'
    SHELL = True
    ALIGNMENT_FORMATS = ['bam', 'sam']
    DRAW_VALUE_OPTIONS = ArribaNode.DRAW_VALUE_OPTIONS
    TRANSCRIPT_SELECTION_OPTIONS = ArribaNode.TRANSCRIPT_SELECTION_OPTIONS
    MIN_CONFIDENCE_OPTIONS = ArribaNode.MIN_CONFIDENCE_OPTIONS
    TRUE_FALSE_OPTIONS = ArribaNode.TRUE_FALSE_OPTIONS

    @classmethod
    def _path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f'{_out(inputs)}/{filename}'

    @staticmethod
    def _flag_value(flag: str, value: Any) -> str:
        return ArribaNode._flag_value(flag, value)

    @classmethod
    def _alignment_format(cls, inputs: dict[str, Any]) -> str:
        explicit_format = str(inputs.get('alignments_format', '') or '').lower()
        if explicit_format:
            return explicit_format
        suffixes = ''.join(Path(str(inputs.get('alignments', '') or '')).suffixes).lower()
        return 'sam' if suffixes.endswith('.sam') else 'bam'

    @classmethod
    def _sorted_bam(cls, inputs: dict[str, Any]) -> str:
        return cls._path(inputs, 'Aligned.sortedByCoord.out.bam')

    @classmethod
    def _draw_command(cls, inputs: dict[str, Any]) -> str:
        draw_cmd = ['draw_fusions.R', cls._flag_value('--fusions', inputs.get('fusions', '')), cls._flag_value('--alignments', cls._sorted_bam(inputs)), cls._flag_value('--annotation', inputs.get('annotation', '')), cls._flag_value('--output', cls._path(inputs, 'fusions.pdf'))]
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
        return ' '.join(draw_cmd)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        commands: list[str] = []
        alignments = str(inputs.get('alignments', '') or '')
        if cls._alignment_format(inputs) == 'sam':
            commands.extend([_shell_join(['ln', '-sf', str(inputs.get('genome_assembly', '') or ''), 'genome.fa']), 'samtools faidx genome.fa', _shell_join(['samtools', 'view', '-b', '-@', '${GALAXY_SLOTS:-1}', '-t', 'genome.fa.fai', alignments, '|', 'samtools', 'sort', '-O', 'bam', '-@', '${GALAXY_SLOTS:-1}', '-T', '${TMPDIR:-.}', '-o', cls._sorted_bam(inputs)]).replace("'${GALAXY_SLOTS:-1}'", '${GALAXY_SLOTS:-1}').replace("'${TMPDIR:-.}'", '${TMPDIR:-.}'), _shell_join(['samtools', 'index', cls._sorted_bam(inputs)])])
        else:
            commands.extend([_shell_join(['ln', '-sf', alignments, cls._sorted_bam(inputs)]), _shell_join(['ln', '-sf', str(inputs.get('alignments_index', '') or ''), f'{cls._sorted_bam(inputs)}.bai'])])
        commands.append(cls._draw_command(inputs))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'fusions.pdf']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('fusions', '') or '').strip():
            return 'fusions is required'
        if not str(inputs.get('alignments', '') or '').strip():
            return 'alignments is required'
        if not str(inputs.get('annotation', '') or '').strip():
            return 'annotation is required'
        alignments_format = cls._alignment_format(inputs)
        if alignments_format not in cls.ALIGNMENT_FORMATS:
            return f"alignments_format must be one of: {', '.join(cls.ALIGNMENT_FORMATS)}"
        if alignments_format == 'sam' and (not str(inputs.get('genome_assembly', '') or '').strip()):
            return 'genome_assembly is required when alignments_format is sam'
        transcript_selection = str(inputs.get('transcript_selection', '') or '')
        if transcript_selection and transcript_selection not in cls.TRANSCRIPT_SELECTION_OPTIONS:
            return f"transcript_selection must be one of: {', '.join(cls.TRANSCRIPT_SELECTION_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'fusions': ('TSV', {'description': 'Arriba fusions.tsv table'}), 'alignments': ('BAM', {'description': 'STAR Aligned.out SAM or BAM file'}), 'annotation': ('GTF', {'description': 'Gene annotation in GTF format'})}, 'optional': {'alignments_format': ('STRING', {'default': 'bam', 'options': cls.ALIGNMENT_FORMATS}), 'alignments_index': ('BAI', {'default': '', 'description': 'BAM index for BAM inputs'}), 'genome_assembly': ('FASTA', {'default': '', 'description': 'Genome FASTA required for SAM inputs'}), 'protein_domains': ('GFF', {'default': '', 'description': 'Protein domain annotation in GFF3 format'}), 'cytobands': ('TSV', {'default': '', 'description': 'Optional cytobands table'}), 'sample_name': ('STRING', {'default': '', 'advanced': True}), 'transcript_selection': ('STRING', {'default': 'provided', 'options': cls.TRANSCRIPT_SELECTION_OPTIONS, 'advanced': True}), 'min_confidence_for_circos_plot': ('STRING', {'default': '', 'options': cls.MIN_CONFIDENCE_OPTIONS, 'advanced': True}), 'squish_introns': ('STRING', {'default': '', 'options': cls.TRUE_FALSE_OPTIONS, 'advanced': True}), 'show_intergenic_vicinity': ('STRING', {'default': '', 'advanced': True}), 'merge_domains_overlapping_by': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'advanced': True}), 'print_exon_labels': ('STRING', {'default': '', 'options': cls.TRUE_FALSE_OPTIONS, 'advanced': True}), 'coverage_range': ('STRING', {'default': '', 'advanced': True}), 'render_3d_effect': ('STRING', {'default': '', 'options': cls.TRUE_FALSE_OPTIONS, 'advanced': True}), 'optimize_domain_colors': ('STRING', {'default': '', 'options': cls.TRUE_FALSE_OPTIONS, 'advanced': True}), 'color1': ('STRING', {'default': '', 'advanced': True}), 'color2': ('STRING', {'default': '', 'advanced': True}), 'pdf_width': ('FLOAT', {'default': '', 'min': 1, 'advanced': True}), 'pdf_height': ('FLOAT', {'default': '', 'min': 1, 'advanced': True}), 'font_family': ('STRING', {'default': '', 'advanced': True}), 'font_size': ('FLOAT', {'default': '', 'min': 0, 'advanced': True}), 'fixed_scale': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'plot_panels': ('BOOLEAN', {'default': False, 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
