"""bakta — annotation node(s). One tool per file (extracted from annotation.py)."""
from __future__ import annotations
import csv
import json
import re
from pathlib import Path
from typing import Any
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode, _shell_join
DOI_URL = 'https://doi.org/'
BCFTOOLS_CITATION_DOIS = ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btp352']
BCFTOOLS_CITATION_URLS = [f'{DOI_URL}{doi}' for doi in BCFTOOLS_CITATION_DOIS]
BCFTOOLS_CITATION_TEXT = 'Twelve years of SAMtools and BCFtools; The Sequence Alignment/Map format and SAMtools.'
def _annotation_node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, 'node_dir', '.') if context else '.')
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
def _safe_output_stem(value: str, default: str) -> str:
    stem = '_'.join(str(value or '').strip().split())
    stem = ''.join((char if char.isalnum() or char in '._-' else '_' for char in stem))
    stem = stem.strip('._-')
    return stem or default
def _split_annotation_files(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in re.split('[\\n,]+', str(value)) if part.strip()]
def _split_annotation_lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [line.strip() for line in str(value).splitlines() if line.strip()]
def _normalise_gene(value: Any, case_sensitive: bool) -> str:
    gene = str(value or '').strip()
    return gene if case_sensitive else gene.upper()
def _read_gene_query(path: str | Path, column: str, case_sensitive: bool) -> list[tuple[str, str]]:
    raw = Path(path).read_text(encoding='utf-8').splitlines()
    if not raw:
        return []
    if column:
        with Path(path).open(newline='', encoding='utf-8') as fh:
            sample = fh.read(2048)
            fh.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=',\t') if sample.strip() else csv.excel_tab
            reader = csv.DictReader(fh, dialect=dialect)
            if reader.fieldnames is None or column not in reader.fieldnames:
                raise ValueError(f'Column {column!r} not found in gene input')
            values = [row.get(column, '') for row in reader]
    else:
        values = raw
    genes: list[tuple[str, str]] = []
    seen: set[str] = set()
    for value in values:
        original = str(value or '').strip()
        normalised = _normalise_gene(original, case_sensitive)
        if normalised and normalised not in seen:
            seen.add(normalised)
            genes.append((original, normalised))
    return genes
def _read_gene_sets(path: str | Path, database_format: str, case_sensitive: bool) -> dict[str, list[tuple[str, str]]]:
    fmt = str(database_format or 'auto').lower()
    source = Path(path)
    if fmt == 'auto':
        fmt = 'json' if source.suffix.lower() == '.json' else 'tsv'
    if fmt == 'json':
        payload = json.loads(source.read_text(encoding='utf-8'))
        if not isinstance(payload, dict):
            raise ValueError('JSON gene set database must be an object mapping set names to gene lists')
        gene_sets: dict[str, list[tuple[str, str]]] = {}
        for name, genes in payload.items():
            if not isinstance(genes, list):
                raise ValueError(f'Gene set {name!r} must be a list')
            gene_sets[str(name)] = [(str(gene).strip(), _normalise_gene(gene, case_sensitive)) for gene in genes]
        return gene_sets
    if fmt not in {'tsv', 'csv'}:
        raise ValueError(f'Unsupported database format: {database_format}')
    delimiter = ',' if fmt == 'csv' else '\t'
    gene_sets = {}
    with source.open(newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        if reader.fieldnames is None or not {'gene_set', 'gene'}.issubset(reader.fieldnames):
            raise ValueError('Table gene set database must contain gene_set and gene columns')
        for row in reader:
            name = str(row.get('gene_set', '')).strip()
            gene = str(row.get('gene', '')).strip()
            if name and gene:
                gene_sets.setdefault(name, []).append((gene, _normalise_gene(gene, case_sensitive)))
    return gene_sets


class BaktaNode(CommandNode):
    """Galaxy-aligned bacterial genome annotation with Bakta."""
    NODE_ID = 'bakta'
    DISPLAY_NAME = 'Bakta'
    CATEGORY = 'annotation'
    DESCRIPTION = 'Rapid and standardized annotation of bacterial genomes, MAGs and plasmids.'
    SEARCH_ALIASES = ['BioNodulo builtin', 'Bakta', 'bakta', 'bacterial genome annotation', 'MAGs', 'plasmids', 'AMRFinderPlus', 'GFF3']
    RETURN_TYPES = ('TSV', 'GFF3', 'GBFF', 'EMBL', 'FASTA', 'FASTA', 'FASTA', 'TSV', 'FASTA', 'TXT', 'JSON', 'SVG', 'TXT')
    RETURN_NAMES = ('annotation_tsv', 'annotation_gff3', 'annotation_gbff', 'annotation_embl', 'annotation_fna', 'annotation_ffn', 'annotation_faa', 'hypotheticals_tsv', 'hypotheticals_faa', 'summary_txt', 'annotation_json', 'annotation_plot', 'logfile')
    REQUIRED_EXECUTABLES = ['bakta', 'ln', 'mkdir', 'cp']
    REQUIRED_CONDA_PACKAGES = ['bakta']
    DOCUMENTATION_URL = 'https://github.com/oschwengers/bakta'
    CITATION_DOIS = ['10.1099/mgen.0.000685']
    CITATION_URLS = ['https://doi.org/10.1099/mgen.0.000685']
    CITATION_TEXT = 'Bakta: rapid and standardized annotation of bacterial genomes via alignment-free sequence identification.'
    VERSION = '1.9.4+galaxy1'
    SHELL = True
    SKIP_ANALYSIS_OPTIONS = ['--skip-trna', '--skip-tmrna', '--skip-rrna', '--skip-ncrna', '--skip-ncrna-region', '--skip-crispr', '--skip-cds', '--skip-pseudo', '--skip-sorf', '--skip-gap', '--skip-ori', '--skip-plot']
    OUTPUT_SELECTION_OPTIONS = ['file_tsv', 'file_gff3', 'file_gbff', 'file_embl', 'file_fna', 'file_ffn', 'file_faa', 'hypo_tsv', 'hypo_fa', 'sum_txt', 'file_json', 'file_plot', 'log_txt']
    DEFAULT_OUTPUT_SELECTION = ['file_tsv', 'file_gff3', 'file_ffn', 'file_plot']
    OUTPUT_FILES = {'file_tsv': ('annotation_tsv.tsv', 'bakta_output/bakta_output.tsv'), 'file_gff3': ('annotation_gff3.gff3', 'bakta_output/bakta_output.gff3'), 'file_gbff': ('annotation_gbff.gbff', 'bakta_output/bakta_output.gbff'), 'file_embl': ('annotation_embl.embl', 'bakta_output/bakta_output.embl'), 'file_fna': ('annotation_fna.fasta', 'bakta_output/bakta_output.fna'), 'file_ffn': ('annotation_ffn.fasta', 'bakta_output/bakta_output.ffn'), 'file_faa': ('annotation_faa.fasta', 'bakta_output/bakta_output.faa'), 'hypo_tsv': ('hypotheticals_tsv.tsv', 'bakta_output/bakta_output.hypotheticals.tsv'), 'hypo_fa': ('hypotheticals_faa.fasta', 'bakta_output/bakta_output.hypotheticals.faa'), 'sum_txt': ('summary_txt.txt', 'bakta_output/bakta_output.txt'), 'file_json': ('annotation_json.json', 'bakta_output/bakta_output.json'), 'file_plot': ('annotation_plot.svg', 'bakta_output/bakta_output.svg'), 'log_txt': ('logfile.txt', 'logfile.txt')}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'Genome in FASTA or FASTA.GZ format'}), 'bakta_db': ('DIRECTORY', {'description': 'Bakta database path'}), 'amrfinder_db': ('DIRECTORY', {'description': 'AMRFinderPlus database path'})}, 'optional': {'min_contig_length': ('INT', {'default': 1, 'min': 0, 'description': 'Minimum contig size; Galaxy uses 200 in compliant mode when unset'}), 'genus': ('STRING', {'default': ''}), 'species': ('STRING', {'default': ''}), 'strain': ('STRING', {'default': ''}), 'plasmid': ('STRING', {'default': ''}), 'complete': ('BOOLEAN', {'default': False}), 'prodigal': ('TXT', {'default': '', 'description': 'Prodigal training file'}), 'translation_table': ('STRING', {'default': '11', 'options': ['4', '11'], 'description': 'Genetic translation table'}), 'keep_contig_headers': ('BOOLEAN', {'default': False}), 'replicons': ('TSV', {'default': ''}), 'compliant': ('BOOLEAN', {'default': False}), 'proteins': ('FASTA', {'default': ''}), 'meta': ('BOOLEAN', {'default': False}), 'regions': ('GFF', {'default': ''}), 'skip_analysis': ('STRING_LIST', {'default': [], 'options': cls.SKIP_ANALYSIS_OPTIONS, 'is_list': True}), 'output_selection': ('STRING_LIST', {'default': list(cls.DEFAULT_OUTPUT_SELECTION), 'options': cls.OUTPUT_SELECTION_OPTIONS, 'is_list': True}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 64})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def _as_list(cls, value: Any, default: list[str] | None=None) -> list[str]:
        if value is None or value == '':
            return list(default or [])
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value if str(item)]
        return [part.strip() for part in re.split('[\\n,]+', str(value)) if part.strip()]

    @classmethod
    def _output_selection(cls, inputs: dict[str, Any]) -> list[str]:
        return cls._as_list(inputs.get('output_selection'), cls.DEFAULT_OUTPUT_SELECTION)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ('input_file', 'bakta_db', 'amrfinder_db'):
            if not str(inputs.get(name, '')).strip():
                return f'{name} is required'
        min_contig_length = inputs.get('min_contig_length')
        if min_contig_length not in (None, ''):
            try:
                if int(min_contig_length) < 0:
                    return 'min_contig_length must be >= 0'
            except (TypeError, ValueError):
                return 'min_contig_length must be an integer'
        if str(inputs.get('translation_table', '11') or '11') not in {'4', '11'}:
            return 'translation_table must be one of: 4, 11'
        skip_analysis = cls._as_list(inputs.get('skip_analysis'))
        invalid_skip = [entry for entry in skip_analysis if entry not in cls.SKIP_ANALYSIS_OPTIONS]
        if invalid_skip:
            return f"skip_analysis entries must be one of: {', '.join(cls.SKIP_ANALYSIS_OPTIONS)}"
        output_selection = cls._output_selection(inputs)
        invalid_outputs = [entry for entry in output_selection if entry not in cls.OUTPUT_SELECTION_OPTIONS]
        if invalid_outputs:
            return f"output_selection entries must be one of: {', '.join(cls.OUTPUT_SELECTION_OPTIONS)}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out_dir = str(inputs.get('output', '.'))
        cmd = ['bakta', '--verbose', '--threads', str(inputs.get('threads', 1) or 1), '--db', './database_path', '--output', 'bakta_output', '--min-contig-length', str(inputs.get('min_contig_length', 1) or 1), '--prefix', 'bakta_output']
        for flag, input_name in (('--genus', 'genus'), ('--species', 'species'), ('--strain', 'strain'), ('--plasmid', 'plasmid')):
            if inputs.get(input_name):
                cmd.extend([flag, str(inputs[input_name])])
        for input_name, flag in (('complete', '--complete'), ('meta', '--meta')):
            if inputs.get(input_name):
                cmd.append(flag)
        if inputs.get('prodigal'):
            cmd.extend(['--prodigal-tf', str(inputs['prodigal'])])
        if inputs.get('translation_table'):
            cmd.extend(['--translation-table', str(inputs['translation_table'])])
        cmd.extend(['--gram', '?'])
        if inputs.get('keep_contig_headers'):
            cmd.append('--keep-contig-headers')
        if inputs.get('replicons'):
            cmd.extend(['--replicons', str(inputs['replicons'])])
        if inputs.get('compliant'):
            cmd.append('--compliant')
        if inputs.get('proteins'):
            cmd.extend(['--proteins', str(inputs['proteins'])])
        if inputs.get('regions'):
            cmd.extend(['--regions', str(inputs['regions'])])
        cmd.extend(cls._as_list(inputs.get('skip_analysis')))
        cmd.extend([str(inputs.get('input_file', '')), '2>&1', '|', 'tee', f'{out_dir}/logfile.txt'])
        commands = [_shell_join(['mkdir', '-p', './database_path/amrfinderplus-db', out_dir]), f"ln -s {_shell_join([str(inputs.get('bakta_db', ''))])}/* database_path", _shell_join(['ln', '-s', f"{str(inputs.get('amrfinder_db', '')).rstrip('/')}/", 'database_path/amrfinderplus-db/latest']), _shell_join(cmd)]
        for selected in cls._output_selection(inputs):
            if selected == 'log_txt':
                continue
            target, source = cls.OUTPUT_FILES[selected]
            commands.append(_shell_join(['cp', source, f'{out_dir}/{target}']))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / cls.OUTPUT_FILES[selected][0] for selected in cls._output_selection(inputs)]
