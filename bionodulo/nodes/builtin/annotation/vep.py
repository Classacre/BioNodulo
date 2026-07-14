"""vep — annotation node(s). One tool per file (extracted from annotation.py)."""
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


class VEPNode(CommandNode):
    """Annotate variants with Ensembl Variant Effect Predictor."""
    NODE_ID = 'vep'
    DISPLAY_NAME = 'VEP'
    CATEGORY = 'annotation'
    DESCRIPTION = 'Ensembl Variant Effect Predictor. Comprehensive functional annotation with frequencies, clinical significance.'
    SEARCH_ALIASES = ['vep', 'variant effect predictor', 'ensembl', 'variant annotation', 'clinvar']
    RETURN_TYPES = ('VCF', 'HTML_REPORT')
    RETURN_NAMES = ('annotated_vcf', 'vep_report')
    REQUIRED_EXECUTABLES = ['vep']
    REQUIRED_CONDA_PACKAGES = ['ensembl-vep']
    DOCUMENTATION_URL = 'https://www.ensembl.org/info/docs/tools/vep/'
    VERSION = '113'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        vcf = str(inputs.get('vcf', ''))
        fmt = str(inputs.get('output_format', 'vcf'))
        cmd = ['vep', '-i', vcf, '-o', f'{out_dir}/annotated_vcf.{fmt}', '--format', 'vcf', f'--{fmt}', '--fork', str(inputs.get('threads', 4)), '--assembly', str(inputs.get('assembly', 'GRCh38')), '--cache', '--dir_cache', str(inputs.get('cache_dir', '~/.vep'))]
        if inputs.get('everything'):
            cmd.append('--everything')
        if inputs.get('symbol'):
            cmd.append('--symbol')
        if inputs.get('af'):
            cmd.append('--af')
        if inputs.get('max_af'):
            cmd.append('--max_af')
        if inputs.get('sift'):
            cmd.extend(['--sift', str(inputs['sift'])])
        if inputs.get('polyphen'):
            cmd.extend(['--polyphen', str(inputs['polyphen'])])
        if inputs.get('clinvar'):
            cmd.extend(['--custom', f"{inputs['clinvar']},ClinVar,vcf,exact,0,CLNSIG"])
        cmd.extend(['--stats_file', f'{out_dir}/vep_report.html'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        fmt = str(inputs.get('output_format', 'vcf'))
        return [node_out / f'annotated_vcf.{fmt}', node_out / 'vep_report.html']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'vcf': ('VCF_GZ', {'description': 'Input VCF'}), 'assembly': ('STRING', {'default': 'GRCh38'}), 'cache_dir': ('DIRECTORY', {'description': 'VEP cache (~10-20GB)'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64})}, 'optional': {'everything': ('BOOLEAN', {'default': True}), 'symbol': ('BOOLEAN', {'default': True}), 'af': ('BOOLEAN', {'default': True}), 'max_af': ('BOOLEAN', {'default': True}), 'sift': ('STRING', {'default': 'b', 'options': ['b', 's', 'p']}), 'polyphen': ('STRING', {'default': 'b', 'options': ['b', 's', 'p']}), 'clinvar': ('VCF_GZ', {'description': 'ClinVar VCF'}), 'output_format': ('STRING', {'default': 'vcf', 'options': ['vcf', 'tab']})}, 'hidden': {'output': ('STRING', {})}}


class VEPAnnotateNode(VEPNode):
    """Compatibility wrapper for the VEP annotation roadmap node ID."""
    NODE_ID = 'vep_annotate'
    DISPLAY_NAME = 'VEP Annotate'
    DESCRIPTION = 'Annotate variants with Ensembl Variant Effect Predictor.'
    SEARCH_ALIASES = ['vep annotate', 'vep', 'variant effect predictor', 'ensembl', 'variant annotation', 'clinvar']
