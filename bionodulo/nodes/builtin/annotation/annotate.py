"""annotate — annotation node(s). One tool per file (extracted from annotation.py)."""
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


class AnnotateVCFNode(CommandNode):
    """Annotate VCF records from one or more custom annotation sources."""
    NODE_ID = 'annotate_vcf'
    DISPLAY_NAME = 'Annotate VCF'
    CATEGORY = 'annotation'
    DESCRIPTION = 'Annotate VCF records with gene names, consequences, and frequencies from multiple sources.'
    SEARCH_ALIASES = ['annotate vcf', 'variant annotation', 'multi-source annotation', 'vcfanno', 'bcftools annotate', 'roadmap']
    RETURN_TYPES = ('VCF_GZ', 'VCF_INDEX')
    RETURN_NAMES = ('annotated_vcf', 'annotated_vcf_index')
    REQUIRED_EXECUTABLES = ['bcftools', 'vcfanno']
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'vcfanno']
    DOCUMENTATION_URL = 'https://github.com/brentp/vcfanno'
    VERSION = '1.0.0'
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'vcf': ('VCF_GZ', {'description': 'Input bgzipped VCF'})}, 'optional': {'mode': ('STRING', {'default': 'vcfanno', 'options': ['vcfanno', 'bcftools'], 'description': 'Annotation backend'}), 'annotation_files': ('STRING', {'default': '', 'description': 'Comma- or newline-separated BED/VCF/TSV annotation files'}), 'vcfanno_config': ('FILE', {'default': '', 'description': 'vcfanno TOML configuration'}), 'columns': ('STRING', {'default': '', 'description': 'Newline-separated bcftools column specs matching annotation_files, e.g. CHROM,FROM,TO,GENE'}), 'header_lines': ('STRING', {'default': '', 'description': "Newline-separated bcftools header files matching annotation_files; use '-' to skip a source"}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output filename stem'}), 'threads': ('INT', {'default': 4, 'min': 0, 'max': 64})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        mode = str(inputs.get('mode', 'vcfanno') or 'vcfanno').lower()
        if mode not in {'vcfanno', 'bcftools'}:
            return f'Unsupported annotation mode: {mode}'
        if mode == 'vcfanno' and (not str(inputs.get('vcfanno_config', '') or '').strip()):
            return 'vcfanno_config is required in vcfanno mode'
        if mode == 'bcftools':
            annotation_files = _split_annotation_files(inputs.get('annotation_files'))
            columns = _split_annotation_lines(inputs.get('columns'))
            header_lines = _split_annotation_lines(inputs.get('header_lines'))
            if not annotation_files:
                return 'At least one annotation file is required in bcftools mode'
            if not columns:
                return 'columns is required in bcftools mode'
            if len(columns) != len(annotation_files):
                return 'columns must provide one newline-separated entry per bcftools annotation file'
            if header_lines and len(header_lines) != len(annotation_files):
                return "header_lines must provide one newline-separated entry per bcftools annotation file, using '-' to skip a source"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        output_vcf = cls._output_vcf_path(inputs, inputs.get('output', inputs.get('output_dir', '.')))
        mode = str(inputs.get('mode', 'vcfanno') or 'vcfanno').lower()
        threads = int(inputs.get('threads', 4) or 0)
        if mode == 'vcfanno':
            return cls._render_vcfanno_command(inputs, output_vcf, threads)
        return cls._render_bcftools_command(inputs, output_vcf, threads)

    @classmethod
    def _render_vcfanno_command(cls, inputs: dict[str, Any], output_vcf: Path, threads: int) -> list[str]:
        cmd = ['set', '-euo', 'pipefail', '&&', 'vcfanno']
        if threads > 0:
            cmd.extend(['-p', str(threads)])
        cmd.extend([str(inputs.get('vcfanno_config', '')), str(inputs.get('vcf', '')), '|', 'bcftools', 'view', '-Oz', '-o', str(output_vcf), '&&', 'bcftools', 'index', '-f', '-t', str(output_vcf)])
        return cmd

    @classmethod
    def _render_bcftools_command(cls, inputs: dict[str, Any], output_vcf: Path, threads: int) -> list[str]:
        annotation_files = _split_annotation_files(inputs.get('annotation_files'))
        columns = _split_annotation_lines(inputs.get('columns'))
        header_lines = _split_annotation_lines(inputs.get('header_lines'))
        cmd: list[str] = ['set', '-euo', 'pipefail', '&&']
        for index, annotation_file in enumerate(annotation_files):
            if index > 0:
                cmd.append('|')
            cmd.extend(['bcftools', 'annotate', '-a', annotation_file])
            cmd.extend(['-c', columns[index]])
            if header_lines and header_lines[index] != '-':
                cmd.extend(['-h', header_lines[index]])
            if threads > 0:
                cmd.extend(['--threads', str(threads)])
            cmd.append('-Oz' if index == len(annotation_files) - 1 else '-Ou')
            if index == len(annotation_files) - 1:
                cmd.extend(['-o', str(output_vcf)])
            if index == 0:
                cmd.append(str(inputs.get('vcf', '')))
            else:
                cmd.append('-')
        cmd.extend(['&&', 'bcftools', 'index', '-f', '-t', str(output_vcf)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_vcf = cls._output_vcf_path(inputs, Path(output_dir) / cls.NODE_ID)
        output_index = Path(str(output_vcf) + '.tbi')
        output_vcf.parent.mkdir(parents=True, exist_ok=True)
        return [output_vcf, output_index]

    @classmethod
    def _output_vcf_path(cls, inputs: dict[str, Any], output_dir: str | Path) -> Path:
        stem = _safe_output_stem(str(inputs.get('output_name', '') or ''), 'annotated_vcf')
        return Path(output_dir) / f'{stem}.annotated.vcf.gz'
